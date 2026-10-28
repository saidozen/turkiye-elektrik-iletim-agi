"""Ağ analizi fonksiyonlari: temel olculer, derece dagilimi, merkeziyet, topluluk,
null model, tek hata noktalari (eklem noktalari/koprüler) ve dayaniklilik analizi.

Tum rastgele islemler TOHUM (seed) ile sabitlenmistir -> sonuclar tekrarlanabilir.
Kaynak veri: OpenStreetMap acik altyapi verisi (power=line, power=substation).
"""
from collections import Counter

import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

TOHUM = 42


# ----------------------------------------------------------------------------- yardimcilar
def en_buyuk_bilesen(G):
    """En büyük bağlı bileşeni, düğüm ve kenarları SIRALI yeni bir graf olarak döndürür.

    Python kümelerinin (set) sırası her çalıştırmada değişebildiği için Louvain gibi sıraya
    duyarlı algoritmalar aynı tohumla farklı sonuç verebilir; sıralı graf bunu önler.
    """
    c = max(nx.connected_components(G), key=lambda s: (len(s), min(s)))
    H = nx.Graph()
    H.add_nodes_from((n, G.nodes[n]) for n in sorted(c))
    H.add_edges_from((u, v, G[u][v]) for u, v in sorted(tuple(sorted(e)) for e in G.subgraph(c).edges()))
    return H


def _ort_yol_ve_cap(G, buyuk_esik=1500, ornek=1000, tohum=TOHUM):
    """Ortalama en kisa yol ve cap. Buyuk aglarda dugum ornekleyerek yaklasik hesaplar."""
    H = en_buyuk_bilesen(G)
    n = H.number_of_nodes()
    if n <= buyuk_esik:
        return nx.average_shortest_path_length(H), nx.diameter(H), False
    rng = np.random.default_rng(tohum)
    dugumler = list(H.nodes())
    secili = rng.choice(dugumler, size=min(ornek, n), replace=False)
    toplam, sayi, cap = 0, 0, 0
    for s in secili:
        uz = nx.single_source_shortest_path_length(H, s)
        toplam += sum(uz.values())
        sayi += len(uz) - 1
        cap = max(cap, max(uz.values()))
    return toplam / sayi, cap, True


# ----------------------------------------------------------------------------- 1) temel olculer
def temel_olculer(G):
    n, m = G.number_of_nodes(), G.number_of_edges()
    bilesenler = sorted((len(c) for c in nx.connected_components(G)), reverse=True)
    dereceler = [d for _, d in G.degree()]
    ort_yol, cap, ornekli = _ort_yol_ve_cap(G)
    try:
        assort = nx.degree_assortativity_coefficient(G)
    except Exception:
        assort = float("nan")
    return {
        "dugum_sayisi": n,
        "kenar_sayisi": m,
        "yogunluk": nx.density(G),
        "ortalama_derece": 2 * m / n,
        "maksimum_derece": max(dereceler),
        "bilesen_sayisi": len(bilesenler),
        "en_buyuk_bilesen_dugum": bilesenler[0],
        "en_buyuk_bilesen_oran": bilesenler[0] / n,
        "ortalama_kumelenme": nx.average_clustering(G),
        "gecislilik_transitivity": nx.transitivity(G),
        "derece_assortativity": assort,
        "ortalama_en_kisa_yol": ort_yol,
        "cap_diameter": cap,
        "yol_cap_ornekli_mi": ornekli,
    }


# ----------------------------------------------------------------------------- 2) derece dagilimi
def derece_dagilimi(G, pl_yolu=("vendor/mpmath", "vendor/pl_full")):
    """Derece dagilimini ve kuvvet yasasi (power-law) uyumunu dondurur.

    powerlaw paketi varsa alpha, xmin ve dagitim karsilastirmalarini (R, p) hesaplar.
    """
    import sys
    for p in pl_yolu:
        if p not in sys.path:
            sys.path.insert(0, p)
    dereceler = np.array([d for _, d in G.degree() if d > 0])
    sayac = Counter(dereceler.tolist())
    sonuc = {"derece_histogrami": dict(sorted(sayac.items()))}
    try:
        import powerlaw
        fit = powerlaw.Fit(dereceler, discrete=True, verbose=False)
        karsilastir = {}
        for alt in ["exponential", "lognormal", "truncated_power_law"]:
            try:
                R, p = fit.distribution_compare("power_law", alt, normalized_ratio=True)
                karsilastir[alt] = {"R": float(R), "p": float(p)}
            except Exception:
                pass
        sonuc["powerlaw"] = {
            "alpha": float(fit.power_law.alpha),
            "xmin": float(fit.power_law.xmin),
            "sigma": float(fit.power_law.sigma),
            "karsilastirma_power_law_vs": karsilastir,
            "aciklama": ("R>0 power-law'un digerinden daha iyi, R<0 digeri daha iyi; "
                         "p<0.05 ise fark anlamli."),
        }
    except Exception as e:
        sonuc["powerlaw_hata"] = f"powerlaw paketi yuklenemedi: {e!r}"
    return sonuc


# ----------------------------------------------------------------------------- 3) merkeziyet
def merkeziyetler(G, ilk=10, betw_ornek=None, tohum=TOHUM):
    """Dort merkeziyet olcusu, ilk-N tablosu ve olculer arasi Spearman korelasyonu."""
    H = en_buyuk_bilesen(G)
    derece = dict(H.degree())
    betw = nx.betweenness_centrality(H, k=betw_ornek, seed=tohum, normalized=True)  # tam hesap
    close = nx.closeness_centrality(H)
    try:
        eig = nx.eigenvector_centrality(H, max_iter=2000, tol=1e-06)
    except nx.PowerIterationFailedConvergence:
        eig = nx.pagerank(H, alpha=0.85)
    df = pd.DataFrame({
        "derece": pd.Series(derece),
        "betweenness": pd.Series(betw),
        "closeness": pd.Series(close),
        "eigenvector": pd.Series(eig),
        "pagerank": pd.Series(nx.pagerank(H, alpha=0.85)),
    })
    for n, d in H.nodes(data=True):
        df.loc[n, "ad"] = d.get("ad", "")
        df.loc[n, "il"] = d.get("il", "")
    spearman = df[["derece", "betweenness", "closeness", "eigenvector", "pagerank"]].corr(method="spearman")
    ilk_tablo = {
        olcu: df.sort_values(olcu, ascending=False)
        .head(ilk)[[olcu, "ad", "il"]].reset_index().rename(columns={"index": "id"})
        .to_dict("records")
        for olcu in ["derece", "betweenness", "closeness", "eigenvector", "pagerank"]
    }
    return {"tablo": df, "ilk_n": ilk_tablo, "spearman": spearman}


# ----------------------------------------------------------------------------- 4) topluluk
def _partisyon_etiketi(komlar, G):
    etiket = {}
    for i, c in enumerate(komlar):
        for n in c:
            etiket[n] = i
    return [etiket[n] for n in G.nodes()]


def topluluk_tespiti(G, tohum=TOHUM, kararlilik_tekrar=10):
    """Louvain ve Leiden; modularite; 10 tohumla kararlilik (NMI/ARI); topluluk adlari."""
    H = en_buyuk_bilesen(G)
    lou = nx.community.louvain_communities(H, seed=tohum, weight=None)
    try:
        lei = nx.community.leiden_communities(H, seed=tohum, metric="modularity", weight=None)
    except Exception as e:
        lei = lou
        lei_hata = repr(e)
    else:
        lei_hata = None
    q_lou = nx.community.modularity(H, lou, weight=None)
    q_lei = nx.community.modularity(H, lei, weight=None)

    # kararlilik: farkli tohumlarla Louvain, ikili NMI/ARI
    def kararlilik(algoritma):
        parts, qs = [], []
        for s in range(kararlilik_tekrar):
            if algoritma == "louvain":
                c = nx.community.louvain_communities(H, seed=s, weight=None)
            else:
                c = nx.community.leiden_communities(H, seed=s, metric="modularity", weight=None)
            parts.append(_partisyon_etiketi(c, H))
            qs.append(nx.community.modularity(H, c, weight=None))
        nmi, ari = [], []
        for i in range(len(parts)):
            for j in range(i + 1, len(parts)):
                nmi.append(normalized_mutual_info_score(parts[i], parts[j]))
                ari.append(adjusted_rand_score(parts[i], parts[j]))
        return {"tekrar": kararlilik_tekrar,
                "nmi_ortalama": float(np.mean(nmi)), "nmi_std": float(np.std(nmi)),
                "ari_ortalama": float(np.mean(ari)), "ari_std": float(np.std(ari)),
                "modularite_ortalama": float(np.mean(qs)), "modularite_std": float(np.std(qs))}
    kar_lou, kar_lei = kararlilik("louvain"), kararlilik("leiden")
    a, b = _partisyon_etiketi(lou, H), _partisyon_etiketi(lei, H)
    uyum = {"nmi": float(normalized_mutual_info_score(a, b)), "ari": float(adjusted_rand_score(a, b))}

    # en buyuk 5 toplulugu cografi olarak adlandir
    buyuk = sorted(lou, key=len, reverse=True)[:5]
    adlar = []
    for k, c in enumerate(buyuk):
        iller = Counter(H.nodes[n].get("il", "?") for n in c)
        bolgeler = Counter(H.nodes[n].get("bolge", "?") for n in c)
        hakim_bolge = bolgeler.most_common(1)[0][0]
        ilk_iller = ", ".join(f"{il}" for il, _ in iller.most_common(3))
        en_buyuk_merkez = sorted(c, key=lambda n: -H.degree(n))[:3]
        adlar.append({
            "topluluk": k,
            "baslica_merkezler": [H.nodes[n].get("ad", "") or n for n in en_buyuk_merkez],
            "iller_tumu": dict(iller.most_common()),
            "dugum_sayisi": len(c),
            "hakim_bolge": hakim_bolge,
            "baslica_iller": ilk_iller,
            "onerilen_ad": f"{hakim_bolge} kümesi ({ilk_iller})",
        })
    return {
        "louvain": {"topluluk_sayisi": len(lou), "modularite": q_lou},
        "leiden": {"topluluk_sayisi": len(lei), "modularite": q_lei, "hata": lei_hata},
        "kararlilik": kar_lou,
        "kararlilik_leiden": kar_lei,
        "louvain_leiden_uyumu": uyum,
        "buyuk_topluluk_adlari": adlar,
        "_louvain_partisyon": lou,
    }


# ----------------------------------------------------------------------------- 5) null model
def null_model(G, tekrar=100, tohum=TOHUM):
    """Ayni derece dizisine sahip rastgele aglar (configuration model) + Erdos-Renyi.

    Olculen degerleri bu dagilimlarla karsilastirip z-skoru verir.
    """
    H = en_buyuk_bilesen(G)
    n, m = H.number_of_nodes(), H.number_of_edges()
    derece_dizisi = [d for _, d in H.degree()]
    def _ort_yol(R):
        return nx.average_shortest_path_length(en_buyuk_bilesen(R))

    gozlem = {
        "ortalama_kumelenme": nx.average_clustering(H),
        "ortalama_en_kisa_yol": _ort_yol(H),
        "derece_assortativity": nx.degree_assortativity_coefficient(H),
        "modularite": nx.community.modularity(
            H, nx.community.louvain_communities(H, seed=tohum, weight=None), weight=None),
    }
    rng = np.random.default_rng(tohum)
    dagilim = {"configuration": {k: [] for k in gozlem},
               "erdos_renyi": {k: [] for k in gozlem}}
    for t in range(tekrar):
        s = int(rng.integers(0, 1_000_000))
        # configuration model: ayni derece dizisi, cok-kenar/dongu temizlenir
        cfg = nx.configuration_model(derece_dizisi, seed=s)
        cfg = nx.Graph(cfg)
        cfg.remove_edges_from(nx.selfloop_edges(cfg))
        er = nx.gnm_random_graph(n, m, seed=s)
        for ad, R in (("configuration", cfg), ("erdos_renyi", er)):
            dagilim[ad]["ortalama_kumelenme"].append(nx.average_clustering(R))
            dagilim[ad]["ortalama_en_kisa_yol"].append(_ort_yol(R))
            dagilim[ad]["derece_assortativity"].append(nx.degree_assortativity_coefficient(R))
            dagilim[ad]["modularite"].append(nx.community.modularity(
                R, nx.community.louvain_communities(R, seed=tohum, weight=None), weight=None))
    sonuc = {"gozlem": gozlem, "tekrar": tekrar, "karsilastirma": {},
             "_dagilim": dagilim}
    for model in dagilim:
        sonuc["karsilastirma"][model] = {}
        for k, deg in gozlem.items():
            arr = np.array(dagilim[model][k])
            mu, sd = arr.mean(), arr.std()
            z = (deg - mu) / sd if sd > 0 else float("nan")
            sonuc["karsilastirma"][model][k] = {
                "gozlem": deg, "null_ortalama": float(mu), "null_std": float(sd),
                "z_skoru": float(z)}
    return sonuc


# ----------------------------------------------------------------------------- 6) tek hata noktalari
def tek_hata_noktalari(G):
    """Eklem noktalari (articulation points) ve koprüler (bridges).

    Bir eklem noktasi kaldirildiginda ag birden fazla parcaya ayrilir -> tek hata noktasi.
    """
    H = en_buyuk_bilesen(G)
    eklem = list(nx.articulation_points(H))
    koprü = list(nx.bridges(H))
    # her eklem noktasi kaldirildiginda olusan ekstra parca sayisi
    etki = []
    taban = nx.number_connected_components(H)
    for v in eklem:
        Hc = H.copy()
        Hc.remove_node(v)
        yeni = nx.number_connected_components(Hc)
        kopan = H.number_of_nodes() - 1 - len(max(nx.connected_components(Hc), key=len))
        etki.append({"id": v, "ad": H.nodes[v].get("ad", ""), "il": H.nodes[v].get("il", ""),
                     "olusan_parca": yeni - taban + 1, "kopan_dugum": kopan})
    etki.sort(key=lambda x: x["kopan_dugum"], reverse=True)
    return {
        "eklem_noktasi_sayisi": len(eklem),
        "koprü_sayisi": len(koprü),
        "eklem_orani": len(eklem) / H.number_of_nodes(),
        "en_kritik_eklem_noktalari": etki[:15],
        "_eklem_idler": eklem,
        "_koprüler": koprü,
    }


# ----------------------------------------------------------------------------- 7) dayaniklilik
def dayaniklilik_sokme(G, tohum=TOHUM):
    """Dugumleri (a) rastgele ve (b) en yuksek betweenness sirasiyla cikararak
    en buyuk bilesenin kuculmesini olcer. Hedefli sokme kritik dugumlere duyarliligi gosterir."""
    H = en_buyuk_bilesen(G)
    n0 = H.number_of_nodes()
    rng = np.random.default_rng(tohum)

    def egri(sira):
        Hc = H.copy()
        oran_kaldirilan, oran_ebb = [0.0], [1.0]
        for i, v in enumerate(sira, 1):
            if v in Hc:
                Hc.remove_node(v)
            if i % max(1, n0 // 100) == 0 or i == len(sira):
                ebb = len(max(nx.connected_components(Hc), key=len)) if Hc.number_of_nodes() else 0
                oran_kaldirilan.append(i / n0)
                oran_ebb.append(ebb / n0)
        return oran_kaldirilan, oran_ebb

    rastgele = list(H.nodes()); rng.shuffle(rastgele)
    betw = nx.betweenness_centrality(H, k=min(n0, 800), seed=tohum)
    hedefli = [v for v, _ in sorted(betw.items(), key=lambda x: x[1], reverse=True)]
    rx, ry = egri(rastgele)
    hx, hy = egri(hedefli)

    def auc(x, y):
        trapez = getattr(np, "trapezoid", getattr(np, "trapz", None))
        return float(trapez(y, x))

    return {
        "rastgele": {"x": rx, "ebb_orani": ry, "dayaniklilik_auc": auc(rx, ry)},
        "hedefli_betweenness": {"x": hx, "ebb_orani": hy, "dayaniklilik_auc": auc(hx, hy)},
    }


# ----------------------------------------------------------------------------- 8) yeniden dagitim modeli
def yeniden_dagitim_modeli(G, baslangic=None, kapasite_payi=1.5, tohum=TOHUM, en_fazla_adim=50):
    """Basit akis-tabanli yeniden dagitim modeli (Motter-Lai benzeri, sadelestirilmis).

    Her dugume baslangic yuku = betweenness; kapasite = kapasite_payi * baslangic_yuk.
    Secilen dugum devre disi kalir; yukler kalan agda yeniden hesaplanir; kapasitesini
    asan dugumler de devre disi kalir; bu zincir durana kadar surer. Cikti: devre disi
    kalan toplam dugum ve en buyuk bilesenin kuculmesi.

    Not: Bu bir ogretim modelidir, gercek elektriksel akis (AC power flow) degildir;
    raporda bu sinir acikca belirtilmelidir.
    """
    H = en_buyuk_bilesen(G)
    n0 = H.number_of_nodes()
    temel = nx.betweenness_centrality(H, k=min(n0, 500), seed=tohum, normalized=False)
    kapasite = {v: kapasite_payi * y + 1 for v, y in temel.items()}

    if baslangic is None:
        baslangic = max(temel, key=temel.get)   # en yuklu dugum
    if not isinstance(baslangic, (list, tuple, set)):
        baslangic = [baslangic]

    aktif = set(H.nodes()) - set(baslangic)
    devre_disi = set(baslangic)
    tarihce = [len(devre_disi)]
    for adim in range(en_fazla_adim):
        alt = H.subgraph(aktif)
        if alt.number_of_nodes() == 0:
            break
        yuk = nx.betweenness_centrality(alt, k=min(alt.number_of_nodes(), 400),
                                        seed=tohum, normalized=False)
        asan = [v for v in aktif if yuk.get(v, 0) > kapasite[v]]
        if not asan:
            break
        aktif -= set(asan)
        devre_disi |= set(asan)
        tarihce.append(len(devre_disi))
    alt = H.subgraph(aktif)
    ebb = len(max(nx.connected_components(alt), key=len)) / n0 if alt.number_of_nodes() else 0
    return {
        "baslangic_dugum": list(baslangic),
        "kapasite_payi": kapasite_payi,
        "devre_disi_toplam": len(devre_disi),
        "devre_disi_oran": len(devre_disi) / n0,
        "son_en_buyuk_bilesen_oran": ebb,
        "adim_tarihcesi": tarihce,
    }
