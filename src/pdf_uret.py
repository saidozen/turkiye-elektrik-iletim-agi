"""6. adım — Rapor, poster ve sunum HTML'lerini PDF'e çevirir (Chromium / Playwright).

    python src/pdf_uret.py

docs/kaynak/*.html  →  docs/rapor.pdf (A4), docs/poster.pdf (A3), docs/sunum.pdf (16:9)
Sayfa boyutu her HTML dosyasının kendi @page kuralından gelir.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

KOK = Path(__file__).resolve().parents[1]
ISLER = [("rapor.html", "rapor.pdf"), ("poster.html", "poster.pdf"), ("sunum.html", "sunum.pdf")]


def main(secili=None):
    with sync_playwright() as p:
        tarayici = p.chromium.launch()
        sayfa = tarayici.new_page()
        for kaynak, hedef in ISLER:
            if secili and kaynak not in secili:
                continue
            yol = KOK / "docs" / "kaynak" / kaynak
            if not yol.exists():
                continue
            sayfa.goto(yol.as_uri(), wait_until="networkidle")
            sayfa.wait_for_timeout(300)
            sayfa.pdf(path=str(KOK / "docs" / hedef), prefer_css_page_size=True, print_background=True)
            print("→", KOK / "docs" / hedef)
        tarayici.close()


if __name__ == "__main__":
    import sys
    main(sys.argv[1:] or None)
