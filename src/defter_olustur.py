"""notebooks/analiz.ipynb defterini oluşturur (hücre içerikleri burada tanımlı).

    python src/defter_olustur.py && python src/defter_calistir.py
"""
import json
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]

H = []


def md(t):
    H.append({"cell_type": "markdown", "metadata": {}, "source": t.strip("\n").splitlines(keepends=True)})


def kod(t):
    H.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
              "source": t.strip("\n").splitlines(keepends=True)})


md("""
# Türkiye Elektrik İletim Altyapısı — Ağ Analizi

**Said Özen · 2516016014 · Sosyal Ağ Analizi (MCBÜ Büyük Veri Analistliği)**

**Araştırma sorusu:** İletim ağında hangi trafo merkezleri tek hata noktası? Basit bir zincirleme arıza nasıl yayılır?

**Kaynak:** OpenStreetMap Overpass API (`power=line`, `power=substation`), © OpenStreetMap katkıcıları, ODbL.
**Düğüm:** trafo merkezi · **Kenar:** iletim hattı · yönsüz, ağırlıksız.

Bu defter depodaki betikleri sırayla çağırır ve sonuçları yorumlar. Uzun süren adımlar (kaskad deneyleri ve 200 rastgele ağlı null model, toplam ~20 dk) `TAM_CALISTIR = False` iken `results/` klasöründeki kayıtlı sonuçlardan okunur; `True` yapılırsa yeniden hesaplanır. Tüm rastgele işlemler tohum 42 ile sabittir.\n\n**Not:** Leiden, Python'un küme sırasından etkilenir. Sonuçların `results/` ile birebir aynı çıkması için Jupyter'i `PYTHONHASHSEED=0 jupyter notebook` komutuyla başlatın.
""")
kod("""
import json, sys, subprocess
from pathlib import Path
import networkx as nx
import pandas as pd
from IPython.display import Image, display  # Jupyter dışında da çalışır

KOK = Path.cwd() if (Path.cwd() / "src").exists() else Path.cwd().parent
sys.path.insert(0, str(KOK))
from src import analiz, kaskad

TAM_CALISTIR = False   # True: kaskad + null model yeniden hesaplanır (~20 dk)
TOHUM = 42
pd.set_option("display.precision", 3)
print("networkx", nx.__version__, "| pandas", pd.__version__)
""")
md("""
## 1. Veri toplama
`src/veri_topla.py` trafo merkezlerini ve hatları indirir. Tüm Türkiye için tek hat sorgusu Overpass sunucusunda zaman aşımına uğradığından hatlar `src/hatlari_parcali_indir.py` ile 12 karoda indirildi. İndirme ~30 dk sürebildiği için aşağıdaki komutlar yorum satırıdır; ham veri `data/raw/` klasöründedir.
""")
kod("""
# !python src/veri_topla.py              # trafo merkezleri (+ tek sorguda hatlar)
# !python src/hatlari_parcali_indir.py   # hatlar, 12 karo
meta = json.loads((KOK / "data/raw/meta.json").read_text(encoding="utf-8"))
ham_trafo = json.loads((KOK / "data/raw/substations.json").read_text(encoding="utf-8"))["elements"]
ham_hat = json.loads((KOK / "data/raw/lines.json").read_text(encoding="utf-8"))["elements"]
print(meta)
print("OSM trafo merkezi nesnesi:", len(ham_trafo))
print("OSM iletim hattı (way):", sum(e["type"] == "way" for e in ham_hat))
""")
md("""
## 2. Ağ kurma
`src/ag_kur.py`: hat uçları trafo alanına (50 m pay) ya da 300 m yakınına düşüyorsa o merkeze eşlenir; parçalı hatlar ve T-branşmanlar ortak direklerde birleştirilir; ≥ 66 kV ya da gerilimi etiketsiz hatlar alınır. Gerekçeler `docs/veri_sozlugu.md` dosyasında.
""")
kod("""
subprocess.run([sys.executable, str(KOK / "src/ag_kur.py")], check=True, capture_output=True)
rapor = json.loads((KOK / "data/processed/build_report.json").read_text(encoding="utf-8"))
pd.Series(rapor["ana_ag"], name="sayı").to_frame()
""")
kod("""
G = nx.read_graphml(KOK / "data/processed/grid.graphml")
H = analiz.en_buyuk_bilesen(G)
print(f"Ağ: {G.number_of_nodes()} düğüm, {G.number_of_edges()} kenar")
print(f"En büyük bileşen: {H.number_of_nodes()} düğüm, {H.number_of_edges()} kenar")
pd.read_csv(KOK / "data/processed/edges.csv").head()
""")
md("""
## 3. Temel ölçüler
""")
kod("""
temel = pd.DataFrame({"tüm ağ": analiz.temel_olculer(G), "en büyük bileşen": analiz.temel_olculer(H)})
temel
""")
md("""
**Yorum.**
- *Yoğunluk 0,0022, ortalama derece 2,6:* her merkez yalnızca yakınındaki 2–3 merkeze bağlı; hat yapmak pahalı olduğu için şebeke seyrek.
- *39 bileşen:* ana parça merkezlerin %90'ı; 38 küçük parça büyük olasılıkla OSM'de çizilmemiş bağlantı hatlarından kaynaklanıyor.
- *Ortalama en kısa yol 12,7, çap 35:* iki merkez arasında ortalama 12,7 hat var; coğrafya yüzünden "küçük dünya" değil.
- *Kümelenme 0,20:* bir merkezin iki komşusunun birbirine de bağlı olma olasılığı %20; bu üçgenler enerjiye alternatif yol açan halkalar.
- *Derece benzeşimi ≈ 0:* büyük merkezler özellikle büyüklerle bağlanmıyor.
""")
kod("""
dd = analiz.derece_dagilimi(G, pl_yolu=(str(KOK / ".vendor"),))
print(json.dumps(dd["powerlaw"], ensure_ascii=False, indent=1))
Image(filename=str(KOK / "figures/derece_dagilimi.png"), width=850)
""")
md("""
**Yorum.** Kuvvet yasası k ≥ 4 için α ≈ 3,8 verse de üstel (R < 0, p = 0,72) ve log-normal (R < 0, p = 0,08) dağılımdan daha iyi uymuyor. Derece dağılımı üstel benzeri: şebeke birkaç dev merkeze değil, uzun hat zincirlerine dayanıyor (Avrupa ve ABD şebekeleriyle uyumlu).

## 4. Merkeziyet
""")
kod("""
mc = analiz.merkeziyetler(G)
ilk = pd.DataFrame({olcu: [f"{r['ad']} ({r['il']})" for r in kayit] for olcu, kayit in mc["ilk_n"].items()},
                   index=range(1, 11))
ilk
""")
kod("""
mc["spearman"].round(2)
""")
md("""
**Yorum.** *Betweenness:* tüm en kısa yolların %44'ü Osmanca'dan (Düzce), %37'si Kurşunlu'dan (Çankırı), %35'i Kayabaşı'ndan (Amasya) geçiyor; üçü de Marmara'yı doğuya bağlayan 380 kV koridorunda. *Derece/PageRank:* santral ve sanayi bölgeleri (Aliağa, Seydişehir, Afşin-Elbistan). *Closeness:* şebekenin ortasındaki koridor ve İç Anadolu. *Eigenvector:* yoğun bağlı Kocaeli–Sakarya–Bursa çekirdeği. Spearman iki aile gösteriyor: {derece, PageRank, betweenness} ve {closeness, eigenvector}.

## 5. Topluluk tespiti
""")
kod("""
top = analiz.topluluk_tespiti(G)
top.pop("_louvain_partisyon")
pd.DataFrame({k: top[k] for k in ("louvain", "leiden")}).T
""")
kod("""
pd.DataFrame({"Louvain (10 tohum)": top["kararlilik"], "Leiden (10 tohum)": top["kararlilik_leiden"]}).T
""")
kod("""
pd.DataFrame(top["buyuk_topluluk_adlari"])[["dugum_sayisi", "baslica_iller", "baslica_merkezler"]]
""")
md("""
**Yorum.** Q = 0,889: hatların %94'ü aynı topluluk içindeki merkezleri bağlıyor. 10 tohumla NMI ≈ 0,92: büyük toplulukların sınırı kararlı. Verilen adlar: **Trakya**, **Konya–Antalya**, **Afşin-Elbistan–Keban**, **Doğu Marmara**, **İzmir–Manisa** (ardından Diyarbakır–Mardin, Van Gölü havzası, Çukurova).
""")
kod("""
Image(filename=str(KOK / "figures/topluluklar.png"), width=850)
""")
md("""
## 6. Null model (100 configuration + 100 Erdős–Rényi)
""")
kod("""
if TAM_CALISTIR:
    nm = analiz.null_model(G, tekrar=100); nm.pop("_dagilim")
else:
    nm = json.loads((KOK / "results/analiz.json").read_text(encoding="utf-8"))["null_model"]
pd.DataFrame(nm["karsilastirma"]["configuration"]).T[["gozlem", "null_ortalama", "null_std", "z_skoru"]]
""")
md("""
**Yorum.** Kümelenme (z = 140), ortalama yol (z = 88) ve modülerlik (z = 48) rastlantıyla açıklanamaz. Aynı derecelerle rastgele ağlar bile Q ≈ 0,72 alıyor; null model olmasaydı "0,89 yüksek" demek yanıltıcı olurdu. Derece benzeşimi rastgele ağdan farksız (z = −1).

## 7. İleri yöntem: eklem noktaları ve köprüler
""")
kod("""
th = kaskad.tek_hata_noktalari(G)
eklem = pd.DataFrame(th.pop("_eklem_hepsi")); th.pop("_kopru_hepsi")
print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in th.items() if not k.startswith("en_")})
eklem[["ad", "il", "gerilim_kv", "derece", "kopan_dugum", "kopan_iller"]].head(15)
""")
md("""
**Yorum.** 326 eklem noktası (%30) ve 367 köprü var, çünkü merkezlerin yalnızca %68'i bir halka üzerinde (2-çekirdek). Ama 162 eklem noktası sadece 1 merkez koparıyor; 10+ merkez koparan 14 tane: Kozan, Kozan Havza, Balıkesir-2, Silivri, Küre, Bursa DGKÇ… Bunlar radyal kolların başındaki merkezler.

## 8. İleri yöntem: yük yeniden dağıtımıyla kaskad (Motter–Lai)
Yük L = merkezden geçen en kısa yol sayısı; kapasite C = (1+α)·L(0). Bir merkez düşer, yükler kalan ağda yeniden hesaplanır, kapasiteyi aşanlar düşer, aşan kalmayınca durur. G = ayakta kalan en büyük parça / başlangıç.
""")
kod("""
L0 = nx.betweenness_centrality(H, normalized=False)
osmanca = max(L0, key=L0.get)
r = kaskad.kaskad(H, L0, osmanca, alfa=0.25)
print(H.nodes[osmanca]["ad"], "| dalga boyutları:", [len(d) for d in r["dalgalar"]],
      "| düşen:", r["dusen_toplam"], "| G =", round(r["G"], 3))
""")
kod("""
if TAM_CALISTIR:
    kd = kaskad.kaskad_deneyleri(G, eklem.to_dict("records")); kd.pop("L0"); ozet = kd["ozet"]
else:
    ozet = json.loads((KOK / "results/analiz.json").read_text(encoding="utf-8"))["kaskad"]["ozet"]
pd.DataFrame({g: {a: v["G_ortalama"] for a, v in d.items()} for g, d in ozet.items()}).T.rename_axis("başlangıç grubu / α")
""")
kod("""
Image(filename=str(KOK / "figures/kaskad_dalgalar.png"), width=850)
""")
md("""
**Yorum.** Rastgele bir merkezin kaybı (α = 0,25) şebekenin %97'sini ayakta bırakıyor; en yüklü 10 merkezden biri düşerse ayakta kalan en büyük parça ortalama %32. Osmanca düşünce batı–doğu yükü güney koridoruna kayıyor (Erzin, Varsak, Yatağan, Seydişehir…): 1. dalgada 67, 2. dalgada 31 merkez düşüyor ve şebeke bölgesel adalara bölünüyor. Eklem noktalarından başlayan kaskadlar sınırlı (G = 0,84).

## Sonuç
Bölgeyi karanlıkta bırakan merkezler (eklem noktaları) radyal kollarda; ülke geneline yayılan arızayı başlatan merkezler Osmanca–Kurşunlu–Kayabaşı 380 kV koridorunda. **Sınırlar:** OSM eksik (hatların %26'sı gerilimsiz, 38 kopuk parça) ve Motter–Lai modeli gerçek AC güç akışı değildir; ayrıntı raporda.
""")

nb = {"cells": H, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                               "language_info": {"name": "python", "version": "3.13"}},
      "nbformat": 4, "nbformat_minor": 5}
(KOK / "notebooks").mkdir(exist_ok=True)
(KOK / "notebooks/analiz.ipynb").write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("notebooks/analiz.ipynb yazıldı:", len(H), "hücre")
