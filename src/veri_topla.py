"""1. adım — OpenStreetMap Overpass API'den Türkiye'deki iletim hatlarını ve trafo merkezlerini indirir.

Çalıştırma:
    python src/veri_topla.py

Çıktılar (data/raw/):
    lines.json        power=line yolları (way) + bu yolların düğüm (direk) koordinatları
    substations.json  power=substation nesneleri (node/way/relation), merkez ve sınır kutusu
    meta.json         sorgular, kullanılan sunucu ve indirme zamanı (tekrarlanabilirlik için)

Overpass kullanım kurallarına uymak için iki sorgu arasında bekler, tek seferde
yalnızca bir istek gönderir ve kendini User-Agent ile tanıtır.
Veri lisansı: © OpenStreetMap katkıcıları, ODbL 1.0.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

KOK = Path(__file__).resolve().parents[1]
HAM = KOK / "data" / "raw"

SUNUCULAR = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
USER_AGENT = "MCBU-SosyalAgAnalizi-Odev/1.0 (egitim amacli; tek seferlik indirme)"

# Türkiye sınırı: ISO 3166-1 kodu TR olan ülke alanı
ALAN = 'area["ISO3166-1"="TR"][admin_level=2]->.tr;'

SORGU_HATLAR = f"""
[out:json][timeout:900][maxsize:1073741824];
{ALAN}
way["power"="line"](area.tr);
out body;
>;
out skel qt;
"""

SORGU_TRAFOLAR = f"""
[out:json][timeout:600];
{ALAN}
nwr["power"="substation"](area.tr);
out tags center bb;
"""


def overpass(sorgu, ad):
    son_hata = None
    for url in SUNUCULAR:
        for deneme in range(3):
            try:
                print(f"[{ad}] {url} (deneme {deneme + 1}) ...", flush=True)
                t0 = time.time()
                r = requests.post(url, data={"data": sorgu},
                                  headers={"User-Agent": USER_AGENT}, timeout=1200)
                if r.status_code == 200:
                    veri = r.json()
                    print(f"[{ad}] {len(veri.get('elements', []))} öğe, "
                          f"{len(r.content) / 1e6:.1f} MB, {time.time() - t0:.0f} sn")
                    return veri, url
                son_hata = f"HTTP {r.status_code}: {r.text[:200]}"
                print(f"[{ad}] {son_hata}")
                bekle = 60 if r.status_code in (429, 504) else 20
            except Exception as e:  # ağ hatası, zaman aşımı
                son_hata = repr(e)
                print(f"[{ad}] hata: {son_hata}")
                bekle = 30
            time.sleep(bekle)
    sys.exit(f"Overpass'tan veri alınamadı: {son_hata}")


def main():
    HAM.mkdir(parents=True, exist_ok=True)
    meta = {"indirme_zamani_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lisans": "© OpenStreetMap katkıcıları, ODbL 1.0 (https://www.openstreetmap.org/copyright)",
            "sorgular": {"lines": SORGU_HATLAR.strip(), "substations": SORGU_TRAFOLAR.strip()}}

    trafolar, url1 = overpass(SORGU_TRAFOLAR, "trafo merkezleri")
    (HAM / "substations.json").write_text(json.dumps(trafolar), encoding="utf-8")
    time.sleep(15)  # sunucuya nezaket beklemesi

    hatlar, url2 = overpass(SORGU_HATLAR, "iletim hatları")
    (HAM / "lines.json").write_text(json.dumps(hatlar), encoding="utf-8")

    meta["sunucular"] = {"substations": url1, "lines": url2}
    meta["osm_base"] = hatlar.get("osm3s", {}).get("timestamp_osm_base")
    (HAM / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Bitti →", HAM)


if __name__ == "__main__":
    main()
