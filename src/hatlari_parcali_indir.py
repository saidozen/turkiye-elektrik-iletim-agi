"""Yedek indirme — iletim hatlarını (power=line) Türkiye'yi parçalara bölerek indirir.

Tek büyük sorgu Overpass'ta zaman aşımına uğrarsa kullanılır. Türkiye'nin sınır kutusu
3 x 4 = 12 karoya bölünür; her karoda yalnızca Türkiye alanı içindeki hatlar istenir.
Sonuçlar birleştirilir ve aynı yol/düğüm tekrarları ayıklanır.

Çalıştırma:  python src/hatlari_parcali_indir.py
Çıktı:       data/raw/lines.json  (+ data/raw/meta_lines.json)
Veri lisansı: © OpenStreetMap katkıcıları, ODbL 1.0.
"""
import json
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

# Türkiye sınır kutusu (güney, batı, kuzey, doğu)
GUNEY, BATI, KUZEY, DOGU = 35.8, 25.6, 42.2, 44.9
SATIR, SUTUN = 3, 4


def sorgu(g, b, k, d):
    return f"""
[out:json][timeout:300];
area["ISO3166-1"="TR"][admin_level=2]->.tr;
way["power"="line"]({g},{b},{k},{d})(area.tr);
out body;
>;
out skel qt;
"""


def indir(q, ad):
    for tur in range(4):
        for url in SUNUCULAR:
            try:
                r = requests.post(url, data={"data": q}, headers={"User-Agent": USER_AGENT},
                                  timeout=400)
                if r.status_code == 200:
                    v = r.json()
                    if "remark" in v and "error" in v["remark"].lower():
                        print(f"  [{ad}] sunucu uyarısı: {v['remark'][:120]}")
                        continue
                    return v, url
                print(f"  [{ad}] {url.split('/')[2]} HTTP {r.status_code}")
            except Exception as e:
                print(f"  [{ad}] {url.split('/')[2]} hata: {type(e).__name__}")
            time.sleep(10)
        time.sleep(30 * (tur + 1))  # üstel bekleme
    raise SystemExit(f"{ad} indirilemedi; biraz bekleyip tekrar çalıştırın.")


def main():
    HAM.mkdir(parents=True, exist_ok=True)
    yollar, dugumler, kullanilan = {}, {}, []
    dlat, dlon = (KUZEY - GUNEY) / SATIR, (DOGU - BATI) / SUTUN
    sayac = 0
    for i in range(SATIR):
        for j in range(SUTUN):
            sayac += 1
            g, k = GUNEY + i * dlat, GUNEY + (i + 1) * dlat
            b, d = BATI + j * dlon, BATI + (j + 1) * dlon
            ad = f"karo {sayac}/{SATIR * SUTUN}"
            t0 = time.time()
            v, url = indir(sorgu(round(g, 3), round(b, 3), round(k, 3), round(d, 3)), ad)
            for e in v["elements"]:
                (yollar if e["type"] == "way" else dugumler)[e["id"]] = e
            kullanilan.append(url)
            print(f"[{ad}] {len(v['elements'])} öğe, {time.time() - t0:.0f} sn — "
                  f"toplam {len(yollar)} hat")
            time.sleep(5)  # sunucuya nezaket beklemesi
    el = list(yollar.values()) + list(dugumler.values())
    (HAM / "lines.json").write_text(json.dumps({"elements": el}), encoding="utf-8")
    (HAM / "meta_lines.json").write_text(json.dumps({
        "indirme_zamani_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "yontem": f"{SATIR}x{SUTUN} karo, her karoda (area.tr) filtresi",
        "sunucular": sorted(set(kullanilan)),
        "lisans": "© OpenStreetMap katkıcıları, ODbL 1.0",
        "ornek_sorgu": sorgu(GUNEY, BATI, KUZEY, DOGU).strip()}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"Bitti → {HAM / 'lines.json'}  ({len(yollar)} hat, {len(dugumler)} direk düğümü)")


if __name__ == "__main__":
    main()
