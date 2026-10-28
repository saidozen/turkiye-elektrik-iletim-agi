"""Gerçek verinin indirildiği betik (Google Colab'da çalıştırıldı, 28.10.2026).

Trafo merkezlerini tek sorguyla, iletim hatlarını Türkiye'yi 3x4 = 12 karoya bölerek indirir.
Her karo indirildikçe kaydedilir; bağlantı koparsa yeniden çalıştırınca kaldığı yerden devam eder.
Sonunda substations.json, lines.json ve meta.json dosyalarını KLASOR'e yazar.
(src/veri_topla.py + src/hatlari_parcali_indir.py ile aynı sorgular; Colab için tek dosya.)

    python src/colab_indir.py            # çıktı: data/raw/
"""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

KLASOR = str(Path(__file__).resolve().parents[1] / "data" / "raw")
os.makedirs(KLASOR, exist_ok=True)
SUNUCULAR = ["https://overpass-api.de/api/interpreter",
             "https://overpass.kumi.systems/api/interpreter",
             "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
UA = {"User-Agent": "MCBU-SosyalAgAnalizi-Odev/1.0 (egitim amacli)"}
ALAN = 'area["ISO3166-1"="TR"][admin_level=2]->.tr;'


def indir(sorgu, ad):
    for tur in range(6):
        for url in SUNUCULAR:
            try:
                r = requests.post(url, data={"data": sorgu}, headers=UA, timeout=400)
                if r.status_code == 200:
                    return r.json()
                print(f"  [{ad}] {url.split('/')[2]} HTTP {r.status_code}")
            except Exception as e:
                print(f"  [{ad}] {url.split('/')[2]} hata: {type(e).__name__}")
            time.sleep(10)
        time.sleep(30 * (tur + 1))  # üstel bekleme (Overpass kullanım kuralları)
    raise SystemExit(f"{ad} indirilemedi, tekrar çalıştırın (kaldığı yerden devam eder).")


def main():
    tf = f"{KLASOR}/substations.json"
    if not os.path.exists(tf):
        v = indir(f'[out:json][timeout:600];{ALAN}nwr["power"="substation"](area.tr);out tags center bb;',
                  "trafolar")
        json.dump(v, open(tf, "w")); print("trafolar:", len(v["elements"]))

    G, B, K, D = 35.8, 25.6, 42.2, 44.9
    SATIR, SUTUN = 3, 4
    dlat, dlon = (K - G) / SATIR, (D - B) / SUTUN
    n = 0
    for i in range(SATIR):
        for j in range(SUTUN):
            n += 1
            dosya = f"{KLASOR}/karo_{n:02d}.json"
            if os.path.exists(dosya):
                print(f"[karo {n}/12] zaten var, atlandı"); continue
            g, k = round(G + i * dlat, 3), round(G + (i + 1) * dlat, 3)
            b, d = round(B + j * dlon, 3), round(B + (j + 1) * dlon, 3)
            s = (f'[out:json][timeout:300];{ALAN}way["power"="line"]({g},{b},{k},{d})(area.tr);'
                 'out body;>;out skel qt;')
            t0 = time.time(); v = indir(s, f"karo {n}/12")
            json.dump(v, open(dosya, "w"))
            print(f"[karo {n}/12] {len(v['elements'])} öğe, {time.time() - t0:.0f} sn")
            time.sleep(5)

    yollar, noktalar = {}, {}
    for n in range(1, 13):
        for e in json.load(open(f"{KLASOR}/karo_{n:02d}.json"))["elements"]:
            (yollar if e["type"] == "way" else noktalar)[e["id"]] = e
    json.dump({"elements": list(yollar.values()) + list(noktalar.values())}, open(f"{KLASOR}/lines.json", "w"))
    json.dump({"indirme_zamani_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "yontem": "trafolar tek sorgu; hatlar 3x4 karo, her karoda (area.tr)",
               "lisans": "© OpenStreetMap katkıcıları, ODbL 1.0"}, open(f"{KLASOR}/meta.json", "w"))
    for n in range(1, 13):
        os.remove(f"{KLASOR}/karo_{n:02d}.json")
    print(f"Bitti → {len(yollar)} hat")


if __name__ == "__main__":
    main()
