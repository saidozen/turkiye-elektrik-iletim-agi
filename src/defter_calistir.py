"""Yardımcı: notebooks/analiz.ipynb defterindeki kod hücrelerini sırayla çalıştırıp çıktıları
(metin, tablo, şekil) deftere yazar. Jupyter kuruluysa bunun yerine
`jupyter nbconvert --execute --to notebook --inplace notebooks/analiz.ipynb` kullanılabilir.

    python src/defter_calistir.py
"""
import ast
import base64
import contextlib
import io
import json
import os
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
DEFTER = KOK / "notebooks" / "analiz.ipynb"


def calistir():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    try:
        import IPython.display  # noqa: F401
    except ImportError:  # Jupyter olmayan ortam: Image/display için küçük yedek
        import types

        class Image:
            def __init__(self, filename, width=None):
                self.yol = Path(filename)

            def _repr_png_(self):
                return self.yol.read_bytes()

        mod = types.ModuleType("IPython.display")
        mod.Image, mod.display = Image, print
        sys.modules["IPython"] = types.ModuleType("IPython")
        sys.modules["IPython.display"] = mod

    nb = json.loads(DEFTER.read_text(encoding="utf-8"))
    os.chdir(KOK)
    sys.path.insert(0, str(KOK))
    ad_alani = {"__name__": "__main__"}
    sayac = 0
    for h in nb["cells"]:
        if h["cell_type"] != "code":
            continue
        sayac += 1
        kod = "".join(h["source"])
        cikti = []
        agac = ast.parse(kod)
        son = agac.body.pop() if agac.body and isinstance(agac.body[-1], ast.Expr) else None
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon):
            exec(compile(agac, f"<hücre {sayac}>", "exec"), ad_alani)
            deger = eval(compile(ast.Expression(son.value), f"<hücre {sayac}>", "eval"), ad_alani) if son else None
        if tampon.getvalue():
            cikti.append({"output_type": "stream", "name": "stdout", "text": tampon.getvalue()})
        for no in plt.get_fignums():
            b = io.BytesIO()
            plt.figure(no).savefig(b, format="png", dpi=90, bbox_inches="tight")
            cikti.append({"output_type": "display_data", "metadata": {},
                          "data": {"image/png": base64.b64encode(b.getvalue()).decode(), "text/plain": "<Figure>"}})
        plt.close("all")
        if deger is not None:
            veri = {"text/plain": repr(deger)}
            if hasattr(deger, "_repr_html_"):
                veri["text/html"] = deger._repr_html_()
            if hasattr(deger, "_repr_png_"):
                veri = {"image/png": base64.b64encode(deger._repr_png_()).decode(), "text/plain": "<Image>"}
                cikti.append({"output_type": "display_data", "metadata": {}, "data": veri})
            else:
                cikti.append({"output_type": "execute_result", "execution_count": sayac, "metadata": {}, "data": veri})
        h["outputs"] = cikti
        h["execution_count"] = sayac
        print(f"hücre {sayac} tamam")
    DEFTER.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    calistir()
