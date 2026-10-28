"""2. adım — Ham OSM verisinden trafo merkezi ağını kurar.

Düğüm  : trafo merkezi (power=substation; substation=minor_distribution hariç)
Kenar  : iki trafo merkezini (doğrudan ya da bir branşman/T-bağlantı üzerinden) birleştiren
         iletim hattı (power=line, gerilimi >= 66 kV veya gerilimi etiketlenmemiş)
Yön    : yönsüz — AC iletim şebekesinde güç akışı iki yönlü olabilir.
Ağırlık: analizde ağırlıksız (topolojik). Kenarda bilgi olarak hat sayısı, uzunluk (km)
         ve en yüksek gerilim (kV) saklanır.

Neden bu kadar adım var? OSM'de bir hat trafo merkezinin "içine" çizilir ama çoğu zaman
trafo merkezi nesnesiyle ortak bir OSM noktası paylaşmaz. Bu yüzden:
  1) Her hat (way) uç noktası, sınır kutusunun içinde (50 m pay) ya da merkezine 300 m'den
     yakın olduğu trafo merkezine "yapıştırılır" (snapping).
  2) Hatlar birbirine direklerde (ortak OSM noktası) bağlanabilir. Trafo merkezine
     yapışmamış hat parçalarından oluşan her bağlı küme bir "branşman kümesi"dir; bu kümeye
     değen trafo merkezleri birbirine bağlanır (<=3 merkez ise hepsi ikişer ikişer, daha
     fazlaysa hat uzunluğuna göre en küçük kapsayan ağaçla — sahte kenar şişmesini önlemek için).
  3) Aynı iki merkez arasındaki paralel hatlar tek kenarda birleştirilir (hat_sayisi).

Çalıştırma:  python src/ag_kur.py
Çıktılar (data/processed/): nodes.csv, edges.csv, grid.graphml, grid_strict.graphml,
                             build_report.json
"""
import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

try:
    from src.iller import en_yakin_il, IL_BOLGE
except ImportError:  # betik doğrudan çalıştırılırsa
    from iller import en_yakin_il, IL_BOLGE

KOK = Path(__file__).resolve().parents[1]
HAM = KOK / "data" / "raw"
ISLENMIS = KOK / "data" / "processed"

R = 6371000.0
LAT0 = math.radians(39.0)
MIN_GERILIM = 66000           # V — Türkiye'de iletim seviyesi 66 kV ve üzeri (154/380 kV ağırlıklı)
YAPISMA_M = 300               # merkezden en fazla bu kadar metre
KUTU_PAYI_M = 50              # sınır kutusuna eklenen pay
HARIC_TRAFO_TURU = {"minor_distribution"}


def xy(lat, lon):
    """Eşdikdörtgen izdüşüm (metre). Türkiye ölçeğinde mesafe hatası %1 mertebesinde."""
    return R * math.radians(lon) * math.cos(LAT0), R * math.radians(lat)


def gerilim_coz(deger):
    """'154000;380000', '154 kV', '34500;380' gibi değerleri volt listesine çevirir.

    OSM'de gerilim volt cinsinden yazılır. '34500;380' bir dağıtım trafosudur: 34,5 kV / 380 V.
    Bu yüzden değerlerden biri >= 1000 ise 1000'in altındakiler volt kabul edilir; yalnızca
    tüm değerler 1000'in altındaysa ('154', '380 kV') kV yazıldığı varsayılır.
    """
    if not deger:
        return []
    ham = []
    for p in str(deger).replace(",", ";").split(";"):
        p = p.strip().lower().replace("kv", "").replace(" ", "")
        try:
            ham.append(float(p))
        except ValueError:
            continue
    if ham and max(ham) < 1000:
        ham = [v * 1000 for v in ham]
    return [int(v) for v in ham]


def trafolari_oku(veri):
    trafolar = {}
    for e in veri["elements"]:
        t = e.get("tags", {})
        if t.get("power") != "substation" or t.get("substation") in HARIC_TRAFO_TURU:
            continue
        if e["type"] == "node":
            lat, lon = e["lat"], e["lon"]
            kutu = None
        else:
            c = e.get("center")
            b = e.get("bounds")
            if c:
                lat, lon = c["lat"], c["lon"]
            elif b:   # Overpass "center bb" isteğinde bazen yalnızca sınır kutusu döner
                lat, lon = (b["minlat"] + b["maxlat"]) / 2, (b["minlon"] + b["maxlon"]) / 2
            else:
                continue
            kutu = (b["minlat"], b["minlon"], b["maxlat"], b["maxlon"]) if b else None
        sid = e["type"][0] + str(e["id"])
        x, y = xy(lat, lon)
        if kutu:
            x0, y0 = xy(kutu[0], kutu[1])
            x1, y1 = xy(kutu[2], kutu[3])
            kutu_m = (x0 - KUTU_PAYI_M, y0 - KUTU_PAYI_M, x1 + KUTU_PAYI_M, y1 + KUTU_PAYI_M)
        else:
            kutu_m = None
        gl = gerilim_coz(t.get("voltage"))
        trafolar[sid] = dict(
            id=sid, ad=t.get("name", ""), isletmeci=t.get("operator", ""),
            tur=t.get("substation", ""), gerilim_kv_etiket=(max(gl) // 1000 if gl else None),
            lat=lat, lon=lon, x=x, y=y, kutu_m=kutu_m)
    return trafolar


def hatlari_oku(veri):
    noktalar, yollar = {}, []
    for e in veri["elements"]:
        if e["type"] == "node":
            noktalar[e["id"]] = (e["lat"], e["lon"])
        elif e["type"] == "way" and e.get("tags", {}).get("power") == "line":
            yollar.append(e)
    return noktalar, yollar


class Yapistirici:
    """Hat uç noktalarını trafo merkezlerine eşler."""

    def __init__(self, trafolar):
        self.ids = list(trafolar)
        self.t = trafolar
        pts = np.array([[trafolar[i]["x"], trafolar[i]["y"]] for i in self.ids])
        self.agac = cKDTree(pts)
        yaricap = [math.hypot(k[2] - k[0], k[3] - k[1]) / 2 for k in
                   (trafolar[i]["kutu_m"] for i in self.ids) if k]
        self.arama_r = max([YAPISMA_M] + yaricap)

    def bul(self, x, y):
        en, ed = None, 1e18
        for j in self.agac.query_ball_point([x, y], self.arama_r):
            s = self.t[self.ids[j]]
            d = math.hypot(s["x"] - x, s["y"] - y)
            k = s["kutu_m"]
            icinde = k is not None and k[0] <= x <= k[2] and k[1] <= y <= k[3]
            if (icinde or d <= YAPISMA_M) and d < ed:
                en, ed = s["id"], d
        return en


def ag_kur(hat_verisi, trafo_verisi, bilinmeyen_gerilim_dahil=True):
    trafolar = trafolari_oku(trafo_verisi)
    noktalar, yollar = hatlari_oku(hat_verisi)
    rapor = Counter()
    rapor["osm_trafo_merkezi"] = len(trafolar)
    rapor["osm_hat_yolu"] = len(yollar)

    # --- 1) gerilim süzgeci
    secili = []
    for w in yollar:
        gl = gerilim_coz(w.get("tags", {}).get("voltage"))
        if not gl:
            rapor["hat_gerilim_bilinmiyor"] += 1
            if not bilinmeyen_gerilim_dahil:
                continue
        elif max(gl) < MIN_GERILIM:
            rapor["hat_dagitim_seviyesi_elenen"] += 1
            continue
        if not all(n in noktalar for n in w["nodes"]) or len(w["nodes"]) < 2:
            rapor["hat_eksik_geometri"] += 1
            continue
        w["_kv"] = max(gl) // 1000 if gl else None
        secili.append(w)
    rapor["hat_secilen"] = len(secili)

    # --- 2) uç noktaları yapıştır
    yap = Yapistirici(trafolar)
    kullanim = Counter(n for w in secili for n in set(w["nodes"]))
    ek = {}
    for w in secili:
        for n in (w["nodes"][0], w["nodes"][-1]):
            if n in ek:
                continue
            lat, lon = noktalar[n]
            ek[n] = yap.bul(*xy(lat, lon))
    rapor["uc_nokta"] = len(ek)
    rapor["uc_nokta_yapisan"] = sum(v is not None for v in ek.values())

    # --- 3) hat parçalarından ara graf: kilit noktalar = uçlar + birden çok yolun paylaştığı direkler
    K = nx.Graph()
    def dugum(n):
        s = ek.get(n)
        return ("S", s) if s else ("N", n)

    for w in secili:
        ns = w["nodes"]
        bas, uz = ns[0], 0.0
        for a, b in zip(ns, ns[1:]):
            (la, loa), (lb, lob) = noktalar[a], noktalar[b]
            xa, ya = xy(la, loa); xb, yb = xy(lb, lob)
            uz += math.hypot(xb - xa, yb - ya)
            if b == ns[-1] or kullanim[b] >= 2:
                u, v = dugum(bas), dugum(b)
                if u != v:
                    if K.has_edge(u, v) and K[u][v]["uz"] <= uz:
                        K[u][v]["hat"] |= {w["id"]}
                    else:
                        eski = K[u][v]["hat"] if K.has_edge(u, v) else set()
                        K.add_edge(u, v, uz=uz, kv=w["_kv"], hat=eski | {w["id"]})
                bas, uz = b, 0.0

    kenarlar = defaultdict(lambda: dict(uzunluk_m=1e18, kv=None, hatlar=set(), branşman=False))

    def kenar_ekle(s, t, uz, kv, hatlar, bransman):
        if s == t:
            return
        k = tuple(sorted((s, t)))
        e = kenarlar[k]
        e["uzunluk_m"] = min(e["uzunluk_m"], uz)
        if kv is not None:
            e["kv"] = max(e["kv"] or 0, kv)
        e["hatlar"] |= hatlar
        e["branşman"] = e["branşman"] or bransman

    # doğrudan trafo-trafo parçaları
    for u, v, d in K.edges(data=True):
        if u[0] == "S" and v[0] == "S":
            kenar_ekle(u[1], v[1], d["uz"], d["kv"], d["hat"], False)

    # branşman kümeleri
    ara = K.subgraph([n for n in K if n[0] == "N"])
    for kume in nx.connected_components(ara):
        temas = defaultdict(list)       # trafo -> [(küme düğümü, kenar uzunluğu)]
        kv_max, hatlar = None, set()
        for n in kume:
            for m in K[n]:
                d = K[n][m]
                hatlar |= d["hat"]
                if d["kv"] is not None:
                    kv_max = max(kv_max or 0, d["kv"])
                if m[0] == "S":
                    temas[m[1]].append((n, d["uz"]))
        sarkan = sum(1 for n in kume if K.degree(n) == 1 and n[1] in ek)
        rapor["sarkan_uc_nokta"] += sarkan
        if len(temas) < 2:
            if len(temas) == 0:
                rapor["kume_trafoya_degmeyen"] += 1
            continue
        alt = K.subgraph(kume)
        mesafe = {}
        trs = list(temas)
        for s in trs:
            # trafo s'den kümeye giriş kenarlarının uzunluğunu hesaba katmak için sanal kaynak
            alt2 = nx.Graph(alt)
            alt2.add_node("_src")
            for n, L in temas[s]:
                if alt2.has_edge("_src", n):
                    alt2["_src"][n]["uz"] = min(alt2["_src"][n]["uz"], L)
                else:
                    alt2.add_edge("_src", n, uz=L)
            dist = nx.single_source_dijkstra_path_length(alt2, "_src", weight="uz")
            for t in trs:
                if t <= s:
                    continue
                dmin = min((dist.get(n, 1e18) + L for n, L in temas[t]), default=1e18)
                if dmin < 1e17:
                    mesafe[(s, t)] = dmin
        if len(trs) <= 3:
            ciftler = list(mesafe.items())
        else:
            rapor["kume_3ten_fazla_trafo"] += 1
            T = nx.Graph()
            for (s, t), d in mesafe.items():
                T.add_edge(s, t, w=d)
            ciftler = [((s, t), d["w"]) for s, t, d in nx.minimum_spanning_edges(T, weight="w", data=True)]
        for (s, t), d in ciftler:
            kenar_ekle(s, t, d, kv_max, hatlar, True)

    # --- 4) son graf
    G = nx.Graph()
    G.add_nodes_from(sorted({n for k in kenarlar for n in k}))   # sıralı: tekrarlanabilir dosya
    for (s, t), e in sorted(kenarlar.items()):
        G.add_edge(s, t, uzunluk_km=round(e["uzunluk_m"] / 1000, 2),
                   gerilim_kv=e["kv"] if e["kv"] is not None else -1,
                   hat_sayisi=len(e["hatlar"]), bransman=int(e["branşman"]))
    for n in G:
        tr = trafolar[n]
        il = en_yakin_il(tr["lat"], tr["lon"])
        kvs = [d["gerilim_kv"] for _, _, d in G.edges(n, data=True) if d["gerilim_kv"] > 0]
        G.nodes[n].update(
            ad=tr["ad"], isletmeci=tr["isletmeci"], tur=tr["tur"], lat=round(tr["lat"], 6),
            lon=round(tr["lon"], 6), il=il, bolge=IL_BOLGE[il],
            gerilim_kv=tr["gerilim_kv_etiket"] or (max(kvs) if kvs else -1))
    rapor["dugum"] = G.number_of_nodes()
    rapor["kenar"] = G.number_of_edges()
    rapor["bilesen"] = nx.number_connected_components(G)
    rapor["en_buyuk_bilesen"] = len(max(nx.connected_components(G), key=len)) if len(G) else 0
    rapor["trafo_hatsiz_disarida"] = len(trafolar) - G.number_of_nodes()
    return G, dict(rapor)


def kaydet(G, ad):
    ISLENMIS.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(G, ISLENMIS / f"{ad}.graphml")


def main():
    hat = json.loads((HAM / "lines.json").read_text(encoding="utf-8"))
    trafo = json.loads((HAM / "substations.json").read_text(encoding="utf-8"))
    G, rapor = ag_kur(hat, trafo, bilinmeyen_gerilim_dahil=True)
    Gs, rapor_s = ag_kur(hat, trafo, bilinmeyen_gerilim_dahil=False)
    kaydet(G, "grid")
    kaydet(Gs, "grid_strict")

    nd = pd.DataFrame([{"id": n, **d} for n, d in G.nodes(data=True)])
    nd["osm_url"] = nd["id"].map(lambda i: "https://www.openstreetmap.org/" +
                                 {"n": "node", "w": "way", "r": "relation"}[i[0]] + "/" + i[1:])
    nd.to_csv(ISLENMIS / "nodes.csv", index=False, encoding="utf-8")
    ed = pd.DataFrame([{"kaynak": u, "hedef": v, **d} for u, v, d in G.edges(data=True)])
    ed.to_csv(ISLENMIS / "edges.csv", index=False, encoding="utf-8")

    meta = {}
    mp = HAM / "meta.json"
    if mp.exists():
        meta = json.loads(mp.read_text(encoding="utf-8"))
    cikti = {"ana_ag": rapor, "siki_ag_sadece_bilinen_gerilim": rapor_s,
             "parametreler": {"min_gerilim_v": MIN_GERILIM, "yapisma_m": YAPISMA_M,
                              "kutu_payi_m": KUTU_PAYI_M, "haric_trafo_turu": sorted(HARIC_TRAFO_TURU)},
             "indirme_zamani_utc": meta.get("indirme_zamani_utc"),
             "osm_veri_zamani": meta.get("osm_base")}
    (ISLENMIS / "build_report.json").write_text(json.dumps(cikti, ensure_ascii=False, indent=2),
                                                encoding="utf-8")
    print(json.dumps(cikti, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
