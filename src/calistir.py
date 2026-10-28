"""3. adım — Tüm analizi çalıştırır ve sonuçları results/ klasörüne yazar.

    python src/calistir.py                 # gerçek veri (data/processed/grid.graphml)
    python src/calistir.py --null-tekrar 20  # hızlı deneme

Önce: python src/ag_kur.py   (ham OSM verisinden ağı kurar)
Sonra: python src/sekiller.py  (şekilleri üretir), python src/etkilesimli.py (web verisi)

Çıktılar:
    results/analiz.json        tüm sayısal sonuçlar (rapor ve sunum bu dosyadan okur)
    results/merkeziyet.csv     düğüm başına merkeziyetler + topluluk + eklem bilgisi
    results/ilk10_*.csv        her merkeziyet ölçüsü için ilk 10
    results/eklem_noktalari.csv, results/kopruler.csv
    results/kaskad_deneyleri.csv, results/kaskad_ornek.json
    results/null_model_dagilim.json, results/topluluklar.json
Süre: 2 çekirdekte yaklaşık 20-25 dakika (kaskad deneyleri en uzun kısım).
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import networkx as nx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import analiz, kaskad  # noqa: E402

KOK = Path(__file__).resolve().parents[1]
SONUC = KOK / "results"
ISL = KOK / "data" / "processed"


def jg(o):
    import numpy as np
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, (set, frozenset, tuple)):
        return list(o)
    return str(o)


def yaz(ad, veri):
    (SONUC / ad).write_text(json.dumps(veri, ensure_ascii=False, indent=1, default=jg),
                            encoding="utf-8")


def main():
    # Tam tekrarlanabilirlik: Python küme (set) sırası PYTHONHASHSEED'e bağlıdır ve Leiden gibi
    # algoritmalar bu sıradan etkilenir. Değişken 0 değilse betik kendini PYTHONHASHSEED=0 ile yeniden başlatır.
    if os.environ.get("PYTHONHASHSEED") != "0":
        os.execve(sys.executable, [sys.executable] + sys.argv, {**os.environ, "PYTHONHASHSEED": "0"})
    ap = argparse.ArgumentParser()
    ap.add_argument("--pl-yolu", default=str(KOK / ".vendor"))
    ap.add_argument("--null-tekrar", type=int, default=100)
    ap.add_argument("--isci", type=int, default=2)
    args = ap.parse_args()
    SONUC.mkdir(exist_ok=True)

    G = nx.read_graphml(ISL / "grid.graphml")
    kurulum = json.loads((ISL / "build_report.json").read_text(encoding="utf-8"))
    H = analiz.en_buyuk_bilesen(G)
    print(f"Ağ: {G.number_of_nodes()} düğüm, {G.number_of_edges()} kenar; "
          f"en büyük bileşen {H.number_of_nodes()} düğüm")
    S = {"kurulum": kurulum}
    t0 = time.time()

    def adim(ad):
        print(f"• {ad}  ({time.time() - t0:.0f} sn)", flush=True)

    adim("temel ölçüler (tüm ağ ve en büyük bileşen)")
    S["temel"] = analiz.temel_olculer(G)
    S["temel_ebb"] = analiz.temel_olculer(H)

    adim("derece dağılımı + powerlaw")
    S["derece_dagilimi"] = analiz.derece_dagilimi(G, pl_yolu=(args.pl_yolu,))

    adim("merkeziyetler (tam betweenness)")
    mc = analiz.merkeziyetler(G)
    S["merkeziyet"] = {"ilk_n": mc["ilk_n"], "spearman": mc["spearman"].round(3).to_dict()}
    for olcu, kayit in mc["ilk_n"].items():
        pd.DataFrame(kayit).to_csv(SONUC / f"ilk10_{olcu}.csv", index=False, encoding="utf-8")

    adim("topluluk tespiti (Louvain, Leiden, 10 tohum kararlılık)")
    top = analiz.topluluk_tespiti(G)
    lou = top.pop("_louvain_partisyon")
    S["topluluk"] = top
    yaz("topluluklar.json", [sorted(c) for c in sorted(lou, key=len, reverse=True)])

    adim("tek hata noktaları (eklem noktaları, köprüler)")
    th = kaskad.tek_hata_noktalari(G)
    eklem_hepsi, kopru_hepsi = th.pop("_eklem_hepsi"), th.pop("_kopru_hepsi")
    S["tek_hata_noktalari"] = th
    pd.DataFrame(eklem_hepsi).assign(kopan_iller=lambda d: d.kopan_iller.str.join(", ")) \
        .to_csv(SONUC / "eklem_noktalari.csv", index=False, encoding="utf-8")
    pd.DataFrame(kopru_hepsi).to_csv(SONUC / "kopruler.csv", index=False, encoding="utf-8")

    adim("dayanıklılık (rastgele vs hedefli sökme)")
    S["dayaniklilik"] = analiz.dayaniklilik_sokme(G)

    adim("kaskad deneyleri (Motter-Lai yük yeniden dağıtımı)")
    kd = kaskad.kaskad_deneyleri(G, eklem_hepsi, isci=args.isci)
    L0 = kd.pop("L0")
    pd.DataFrame(kd.pop("tekil")).assign(grup=lambda d: d.grup.str.join("+")) \
        .to_csv(SONUC / "kaskad_deneyleri.csv", index=False, encoding="utf-8")
    S["kaskad"] = kd

    adim("örnek kaskad (dalga dalga)")
    deney = pd.read_csv(SONUC / "kaskad_deneyleri.csv")
    a0 = 0.25
    en_kotu = deney[deney.alfa == a0].sort_values("G").iloc[0]
    ornek = {}
    for ad, v in [("en_yuksek_yuk", max(L0, key=L0.get)), ("en_hasarli", en_kotu.baslangic)]:
        r = kaskad.kaskad(H, L0, v, a0)
        r["ad"] = H.nodes[v].get("ad", "") or v
        r["il"] = H.nodes[v].get("il", "")
        r["dalga_detay"] = [[{"id": u, "ad": H.nodes[u].get("ad", "") or u,
                              "il": H.nodes[u].get("il", "")} for u in d] for d in r["dalgalar"]]
        r["dalga_iller"] = [sorted({H.nodes[u].get("il", "") for u in d}) for d in r["dalgalar"]]
        ornek[ad] = r
    yaz("kaskad_ornek.json", ornek)
    S["kaskad_ornek_ozet"] = {k: {kk: v[kk] for kk in ("ad", "il", "alfa", "dalga_sayisi",
                                                       "dusen_toplam", "G")}
                              for k, v in ornek.items()}
    S["kaskad_ornek_ozet"].update({k + "_dalga_boyutlari": [len(d) for d in v["dalgalar"]]
                                   for k, v in ornek.items()})

    adim(f"null model ({args.null_tekrar} configuration + {args.null_tekrar} Erdős–Rényi)")
    nm = analiz.null_model(G, tekrar=args.null_tekrar)
    yaz("null_model_dagilim.json", nm.pop("_dagilim"))
    S["null_model"] = nm

    # düğüm tablosu: merkeziyet + topluluk + eklem + yük
    etiket = {n: i for i, c in enumerate(sorted(lou, key=len, reverse=True)) for n in c}
    eklem_kopan = {e["id"]: e["kopan_dugum"] for e in eklem_hepsi}
    tablo = mc["tablo"].copy()
    tablo["topluluk"] = tablo.index.map(etiket)
    tablo["eklem_noktasi"] = tablo.index.map(lambda n: int(n in eklem_kopan))
    tablo["eklem_kopan_dugum"] = tablo.index.map(lambda n: eklem_kopan.get(n, 0))
    tablo["yuk_L0"] = tablo.index.map(L0)
    tablo.index.name = "id"
    tablo.to_csv(SONUC / "merkeziyet.csv", encoding="utf-8")

    yaz("analiz.json", S)
    print(f"Bitti ({time.time() - t0:.0f} sn). results/analiz.json hazır.")


if __name__ == "__main__":
    main()
