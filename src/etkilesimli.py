"""5. adım — Etkileşimli ağ sayfasını üretir (Cytoscape.js).

    python src/etkilesimli.py

Girdi : data/processed/grid.graphml, results/topluluklar.json, results/merkeziyet.csv,
        results/eklem_noktalari.csv, src/etkilesimli_sablon.html
Çıktı : docs/interaktif/index.html   (GitHub Pages / portfolyo için tam sayfa)

Neden yalnızca en büyük bileşen? Ana şebekeden kopuk 38 küçük parça (çoğu 2-5 merkez) OSM'de
eksik çizilmiş hatlardan kaynaklanır; tek hata noktası ve kaskad sorusu bağlı şebekede anlamlıdır.
Tüm düğümler (1072) gösterilir; kalabalığı azaltmak için etiket yalnızca en çok bağlantılı
merkezlerde vardır, diğer adlar tıklayınca/aramada görünür.
"""
import json
import math
from pathlib import Path

import networkx as nx
import pandas as pd

KOK = Path(__file__).resolve().parents[1]

# En büyük 8 Louvain topluluğunun adları (içerdikleri iller ve başlıca merkezlere bakılarak verildi)
TOPLULUK_ADLARI = [
    {"tr": "Trakya–İstanbul", "en": "Thrace–Istanbul"},
    {"tr": "Doğu Marmara", "en": "Eastern Marmara"},
    {"tr": "Konya–Antalya", "en": "Konya–Antalya"},
    {"tr": "Orta Anadolu–Karadeniz", "en": "Central Anatolia–Black Sea"},
    {"tr": "Afşin-Elbistan–Keban", "en": "Afşin-Elbistan–Keban"},
    {"tr": "Diyarbakır–Mardin", "en": "Diyarbakır–Mardin"},
    {"tr": "İzmir–Manisa", "en": "İzmir–Manisa"},
    {"tr": "Gaziantep–Şanlıurfa", "en": "Gaziantep–Şanlıurfa"},
]


def main():
    G = nx.read_graphml(KOK / "data/processed/grid.graphml")
    H = G.subgraph(max(nx.connected_components(G), key=len)).copy()
    topl = json.loads((KOK / "results/topluluklar.json").read_text(encoding="utf-8"))
    etiket = {n: i for i, c in enumerate(topl) for n in c}
    mc = pd.read_csv(KOK / "results/merkeziyet.csv", index_col="id")
    mc["btw_sira"] = mc["betweenness"].rank(ascending=False, method="min").astype(int)
    ek = pd.read_csv(KOK / "results/eklem_noktalari.csv").set_index("id")

    lat0 = math.radians(39)
    lats = [d["lat"] for _, d in H.nodes(data=True)]
    lons = [d["lon"] for _, d in H.nodes(data=True)]
    la1, lo0 = max(lats), min(lons)
    olcek = 140  # piksel / derece
    etiketli = set(sorted(H, key=lambda n: -H.degree(n))[:45])

    dugumler = []
    for n, d in H.nodes(data=True):
        e = ek.loc[n] if n in ek.index else None
        dugumler.append({
            "id": n, "ad": d.get("ad") or "(adsız trafo merkezi)", "il": d.get("il", ""),
            "bolge": d.get("bolge", ""), "kv": int(d.get("gerilim_kv", -1)), "derece": H.degree(n),
            "top": etiket.get(n, -1), "btw_sira": int(mc.loc[n, "btw_sira"]),
            "yuk": round(float(mc.loc[n, "yuk_L0"])),
            "eklem": int(e is not None), "kopan": int(e["kopan_dugum"]) if e is not None else 0,
            "kopan_iller": (e["kopan_iller"] if e is not None and isinstance(e["kopan_iller"], str) else ""),
            "etiket": (d.get("ad") or "").replace(" Trafo Merkezi", "").replace(" TM", "")
                      if n in etiketli and d.get("ad") else None,
            "x": round((d["lon"] - lo0) * olcek * math.cos(lat0), 1),
            "y": round((la1 - d["lat"]) * olcek, 1),
        })
    kenarlar = [{"s": u, "t": v, "kv": int(dd.get("gerilim_kv", -1))} for u, v, dd in H.edges(data=True)]
    topluluklar = [{"no": i, "ad": TOPLULUK_ADLARI[i], "boy": len(topl[i])} for i in range(len(TOPLULUK_ADLARI))]
    meta = json.loads((KOK / "data/raw/meta.json").read_text(encoding="utf-8"))
    tarih = meta["indirme_zamani_utc"][:10]
    tarih = f"{tarih[8:10]}.{tarih[5:7]}.{tarih[:4]}"
    veri = {
        "n": H.number_of_nodes(), "m": H.number_of_edges(), "tarih": tarih,
        "dugumler": dugumler, "kenarlar": kenarlar, "topluluklar": topluluklar,
        "diger_boy": sum(len(c) for c in topl[len(TOPLULUK_ADLARI):]),
        "baslangic": mc["yuk_L0"].idxmax(),
    }
    sablon = (KOK / "src/etkilesimli_sablon.html").read_text(encoding="utf-8")
    govde = sablon.replace("/*__VERI__*/null", json.dumps(veri, ensure_ascii=False, separators=(",", ":")))
    out = KOK / "docs/interaktif/index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    # tarayıcı <title>/<meta>/<link>/<style>'ı head'e, ilk görünür öğeden sonrasını body'ye koyar
    out.write_text('<!doctype html>\n<html lang="tr">\n<meta charset="utf-8">\n' + govde + "\n</html>\n",
                   encoding="utf-8")
    # artifact önizlemesi için iskeletsiz sürüm
    (KOK / "docs/interaktif/govde.html").write_text(govde, encoding="utf-8")
    print(f"{out}  ({len(dugumler)} düğüm, {len(kenarlar)} kenar, {out.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
