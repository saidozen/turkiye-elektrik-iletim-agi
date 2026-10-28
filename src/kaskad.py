"""Kişisel ileri yöntem — tek hata noktaları ve kaskad (zincirleme) arıza simülasyonu.

1) Eklem noktaları ve köprüler
   Eklem noktası: kaldırıldığında ağı parçalara ayıran trafo merkezi.
   Köprü: kaldırıldığında ağı parçalara ayıran iletim hattı.
   Her biri için "ana şebekeden kopan trafo merkezi sayısı" hesaplanır.

2) Yük yeniden dağıtım modeli (Motter & Lai, 2002, Phys. Rev. E 66, 065102)
   - Yük L_i  : i düğümünden geçen en kısa yol sayısı (normalize edilmemiş betweenness).
                Enerji en kısa yoldan aktığı varsayılır; elektriksel akış (AC power flow)
                DEĞİLDİR, topolojik bir yaklaşımdır.
   - Kapasite : C_i = (1 + α) · L_i(başlangıç). α = tolerans payı (0,25 → %25 yedek).
   - Başlangıç: bir trafo merkezi devre dışı kalır.
   - Adım     : yükler kalan ağda yeniden hesaplanır; yükü kapasitesini aşan her merkez
                devre dışı kalır ("dalga"). Aşan kalmayınca zincir durur.
   - Ölçü     : G = (son durumdaki en büyük bileşen) / (başlangıçtaki düğüm sayısı).
                G = 1 hasar yok, G → 0 şebeke çöktü.

Tüm hesaplar tam (örneklemesiz) betweenness ile yapılır; sonuç deterministiktir.
Rastgele başlangıç düğümleri TOHUM ile seçilir.
"""
from concurrent.futures import ProcessPoolExecutor

import networkx as nx
import numpy as np

TOHUM = 42
ALFALAR = (0.1, 0.25, 0.5, 1.0)


from src.analiz import en_buyuk_bilesen  # noqa: E402  (sıralı, tekrarlanabilir)


# ----------------------------------------------------------------------------- 1) eklem ve köprü
def tek_hata_noktalari(G):
    H = en_buyuk_bilesen(G)
    n = H.number_of_nodes()
    eklem = list(nx.articulation_points(H))
    kopruler = list(nx.bridges(H))

    etki = []
    for v in eklem:
        Hc = H.copy()
        Hc.remove_node(v)
        parcalar = sorted(nx.connected_components(Hc), key=len, reverse=True)
        kopan = n - 1 - len(parcalar[0])
        kopan_iller = sorted({H.nodes[u].get("il", "") for c in parcalar[1:] for u in c})
        etki.append({"id": v, "ad": H.nodes[v].get("ad", "") or v, "il": H.nodes[v].get("il", ""),
                     "gerilim_kv": H.nodes[v].get("gerilim_kv", -1), "derece": H.degree(v),
                     "parca_sayisi": len(parcalar), "kopan_dugum": kopan,
                     "kopan_iller": kopan_iller})
    etki.sort(key=lambda x: (-x["kopan_dugum"], -x["derece"]))

    kopru_etki = []
    for u, v in kopruler:
        Hc = H.copy()
        Hc.remove_edge(u, v)
        kucuk = min(nx.connected_components(Hc), key=len)
        d = H[u][v]
        kopru_etki.append({"u": u, "v": v,
                           "u_ad": H.nodes[u].get("ad", "") or u, "v_ad": H.nodes[v].get("ad", "") or v,
                           "u_il": H.nodes[u].get("il", ""), "v_il": H.nodes[v].get("il", ""),
                           "gerilim_kv": d.get("gerilim_kv", -1), "uzunluk_km": d.get("uzunluk_km", 0),
                           "kopan_dugum": len(kucuk)})
    kopru_etki.sort(key=lambda x: -x["kopan_dugum"])

    yaprak = sum(1 for v in H if H.degree(v) == 1)
    cekirdek2 = nx.k_core(H, 2).number_of_nodes()
    return {
        "dugum": n,
        "eklem_noktasi_sayisi": len(eklem),
        "eklem_orani": len(eklem) / n,
        "kopru_sayisi": len(kopruler),
        "kopru_orani": len(kopruler) / H.number_of_edges(),
        "eklem_10dan_fazla_koparan": sum(e["kopan_dugum"] >= 10 for e in etki),
        "eklem_sadece_1_koparan": sum(e["kopan_dugum"] == 1 for e in etki),
        "kopru_10dan_fazla_koparan": sum(k["kopan_dugum"] >= 10 for k in kopru_etki),
        "yaprak_dugum_derece1": yaprak,
        "iki_cekirdek_dugum": cekirdek2,
        "iki_cekirdek_oran": cekirdek2 / n,
        "en_kritik_eklem": etki[:15],
        "en_kritik_kopru": kopru_etki[:10],
        "_eklem_hepsi": etki,
        "_kopru_hepsi": kopru_etki,
    }


# ----------------------------------------------------------------------------- 2) kaskad
_H = None
_L0 = None


def _hazirla(H, L0):
    global _H, _L0
    _H, _L0 = H, L0


def kaskad(H, L0, baslangic, alfa, en_fazla_adim=30):
    """Tek bir kaskad. Dönüş: dalgalar (her adımda düşen düğümler) ve G."""
    n0 = H.number_of_nodes()
    kapasite = {v: (1 + alfa) * L0[v] for v in H}
    aktif = set(H) - {baslangic}
    dalgalar = [[baslangic]]
    for _ in range(en_fazla_adim):
        alt = H.subgraph(aktif)
        yuk = nx.betweenness_centrality(alt, normalized=False)
        # 1e-9: kayan nokta eşitliği yüzünden düğüm düşmesin; L0=0 olan yaprakların
        # kapasitesi 0'dır ama yükleri de 0 kalır (yaprak üzerinden yol geçmez).
        asan = [v for v in aktif if yuk[v] > kapasite[v] + 1e-9]
        if not asan:
            break
        aktif -= set(asan)
        dalgalar.append(sorted(asan))
    alt = H.subgraph(aktif)
    ebb = max((len(c) for c in nx.connected_components(alt)), default=0)
    return {"baslangic": baslangic, "alfa": alfa, "dalgalar": dalgalar,
            "dalga_sayisi": len(dalgalar) - 1,
            "dusen_toplam": n0 - len(aktif), "G": ebb / n0}


def _is(arg):
    v, a = arg
    s = kaskad(_H, _L0, v, a)
    s.pop("dalgalar")
    return s


def kaskad_deneyleri(G, eklem_listesi, alfalar=ALFALAR, ilk=10, rastgele_sayi=20, tohum=TOHUM,
                     isci=2):
    H = en_buyuk_bilesen(G)
    L0 = nx.betweenness_centrality(H, normalized=False)
    ust_betw = [v for v, _ in sorted(L0.items(), key=lambda x: -x[1])[:ilk]]
    ust_eklem = [e["id"] for e in eklem_listesi[:ilk]]
    rng = np.random.default_rng(tohum)
    rastgele = [str(v) for v in rng.choice(sorted(H.nodes()), size=rastgele_sayi, replace=False)]
    gruplar = {"en_yuksek_betweenness": ust_betw, "en_kritik_eklem": ust_eklem,
               "rastgele": rastgele}

    isler = sorted({(v, a) for g in gruplar.values() for v in g for a in alfalar})
    with ProcessPoolExecutor(max_workers=isci, initializer=_hazirla, initargs=(H, L0)) as ex:
        sonuc = dict(zip(isler, ex.map(_is, isler, chunksize=2)))

    ozet = {}
    for g, dugumler in gruplar.items():
        ozet[g] = {}
        for a in alfalar:
            Gs = [sonuc[(v, a)]["G"] for v in dugumler]
            dus = [sonuc[(v, a)]["dusen_toplam"] for v in dugumler]
            ozet[g][str(a)] = {"G_ortalama": float(np.mean(Gs)), "G_min": float(np.min(Gs)),
                               "dusen_ortalama": float(np.mean(dus)),
                               "dusen_max": int(np.max(dus))}
    tek = [dict(sonuc[(v, a)], ad=H.nodes[v].get("ad", "") or v, il=H.nodes[v].get("il", ""),
                grup=[g for g, d in gruplar.items() if v in d])
           for (v, a) in isler]
    return {"alfalar": list(alfalar), "gruplar": gruplar, "ozet": ozet, "tekil": tek,
            "L0": L0}
