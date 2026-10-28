"""4. adım — Rapor, poster ve sunum için şekilleri üretir (figures/*.png).

    python src/sekiller.py

results/ altındaki sonuç dosyalarını ve data/processed/grid.graphml'i okur; analizi yeniden
çalıştırmaz. Her şekil hem raporda hem sunumda kullanılabilecek boyuttadır.
"""
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

KOK = Path(__file__).resolve().parents[1]
FIG = KOK / "figures"
SON = KOK / "results"

MUREKKEP = "#18212b"
SOLUK = "#5b6875"
IZGARA = "#dfe4ea"
K380 = "#d0342c"
K154 = "#e08a1e"
K66 = "#2a9d8f"
KYOK = "#9aa6b2"
MOR = "#7b5cc4"
PALET = ["#3b6fd8", "#9c6b30", "#1f9d6b", "#e08a1e", "#8a4fd6", "#0f9fb3", "#c04a8f", "#7a8b2a"]
TOPLULUK_ADLARI = ["Trakya–İstanbul", "Doğu Marmara", "Konya–Antalya", "Orta Anadolu–Karadeniz",
                   "Afşin-Elbistan–Keban", "Diyarbakır–Mardin", "İzmir–Manisa", "Gaziantep–Şanlıurfa"]

plt.rcParams.update({
    "font.family": ["TeX Gyre Heros", "DejaVu Sans"], "font.size": 10.5,
    "axes.titlesize": 12.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelcolor": SOLUK, "xtick.color": SOLUK, "ytick.color": SOLUK,
    "axes.edgecolor": "#b8c2cc", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": IZGARA, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "figure.dpi": 110, "savefig.dpi": 220, "savefig.bbox": "tight", "savefig.facecolor": "white",
    "legend.frameon": False,
})
COS = math.cos(math.radians(39))


def kv_renk(kv):
    kv = int(kv) if kv not in (None, "") else -1
    return K380 if kv >= 300 else K154 if kv >= 100 else K66 if kv > 0 else KYOK


def yukle():
    G = nx.read_graphml(KOK / "data/processed/grid.graphml")
    H = G.subgraph(max(nx.connected_components(G), key=len)).copy()
    S = json.loads((SON / "analiz.json").read_text(encoding="utf-8"))
    return G, H, S


def _harita_ekseni(ax):
    ax.set_aspect(1 / COS)
    ax.set_xlim(25.6, 45.0); ax.set_ylim(35.7, 42.3)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])


def _kenarlar(ax, G, renk=None, lw=0.6, alpha=0.6, z=1):
    from matplotlib.collections import LineCollection
    seg, cs = [], []
    for u, v, d in G.edges(data=True):
        a, b = G.nodes[u], G.nodes[v]
        seg.append([(a["lon"], a["lat"]), (b["lon"], b["lat"])])
        cs.append(renk or kv_renk(d.get("gerilim_kv")))
    ax.add_collection(LineCollection(seg, colors=cs, linewidths=lw, alpha=alpha, zorder=z))


def _etiket(ax, x, y, metin, boyut=8.5, dx=0.12, dy=0.1, renk=MUREKKEP, ha="left"):
    import matplotlib.patheffects as pe
    ax.text(x + dx, y + dy, metin, fontsize=boyut, color=renk, ha=ha, va="bottom",
            fontfamily="TeX Gyre Heros Cn", fontweight="bold", zorder=10,
            path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])


def _kisa(ad):
    return (ad or "").replace(" Trafo Merkezi", "").replace(" TM", "").replace(" Transformatör Merkezi", "")


# ----------------------------------------------------------------------------- 1) gerilim haritası
def harita_gerilim(G):
    fig, ax = plt.subplots(figsize=(11, 5.4))
    _harita_ekseni(ax)
    _kenarlar(ax, G, lw=0.9, alpha=0.8)
    der = dict(G.degree())
    xs = [G.nodes[n]["lon"] for n in G]; ys = [G.nodes[n]["lat"] for n in G]
    ax.scatter(xs, ys, s=[3 + 2.2 * der[n] for n in G], c=MUREKKEP, alpha=0.75, lw=0, zorder=3)
    for n in sorted(G, key=lambda n: -der[n])[:10]:
        _etiket(ax, G.nodes[n]["lon"], G.nodes[n]["lat"], _kisa(G.nodes[n]["ad"]))
    ax.legend(handles=[Line2D([], [], color=K380, lw=2.5, label="380/400 kV"),
                       Line2D([], [], color=K154, lw=2.5, label="154 kV"),
                       Line2D([], [], color=K66, lw=2.5, label="66 kV"),
                       Line2D([], [], color=KYOK, lw=2.5, label="gerilim etiketi yok"),
                       Line2D([], [], marker="o", ls="", color=MUREKKEP, ms=6,
                              label="trafo merkezi (boy = bağlantı)")],
              loc="upper left", bbox_to_anchor=(0, 0.02), fontsize=9, ncol=3)
    ax.set_title(f"Türkiye iletim ağı: {G.number_of_nodes()} trafo merkezi, "
                 f"{G.number_of_edges()} bağlantı (OpenStreetMap)")
    fig.savefig(FIG / "harita_gerilim.png"); plt.close(fig)


# ----------------------------------------------------------------------------- 2) derece dağılımı
def derece(G, S):
    from collections import Counter
    d = np.array([k for _, k in G.degree()])
    c = Counter(d.tolist())
    k = np.array(sorted(c)); nk = np.array([c[i] for i in k])
    pl = S["derece_dagilimi"].get("powerlaw", {})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 3.8))
    a1.bar(k, nk, color="#3b6fd8", width=0.8)
    a1.set_xlabel("Derece k (bir merkezin bağlantı sayısı)"); a1.set_ylabel("Trafo merkezi sayısı")
    a1.set_title("Derece dağılımı")
    a1.annotate(f"tek hatla bağlı: %{100 * c[1] / len(d):.0f}\n(uç / radyal merkezler)",
                xy=(1, c[1]), xytext=(5, c[1] * 0.85), fontsize=9, color=SOLUK,
                arrowprops=dict(arrowstyle="-", color=SOLUK, lw=0.7))
    # CCDF log-log
    ks = np.sort(d[d > 0])
    ccdf = 1 - np.arange(len(ks)) / len(ks)
    a2.loglog(ks, ccdf, "o", ms=4, color="#3b6fd8", alpha=0.6, label="gözlem (CCDF)")
    if pl:
        xmin, alpha = pl["xmin"], pl["alpha"]
        x = np.linspace(xmin, ks.max(), 50)
        y0 = (ks >= xmin).mean()
        a2.loglog(x, y0 * (x / xmin) ** (1 - alpha), "--", color=K380,
                  label=f"güç yasası α={alpha:.2f}, k≥{xmin:.0f}")
        lam = 1 / (ks[ks >= xmin].mean() - xmin + 1e-9)
        a2.loglog(x, y0 * np.exp(-lam * (x - xmin)), ":", color=MUREKKEP, label="üstel (karşılaştırma)")
    a2.set_xlabel("Derece k (log)"); a2.set_ylabel("P(K ≥ k) (log)")
    a2.set_title("Log-log tamamlayıcı dağılım"); a2.legend(fontsize=8.5)
    fig.tight_layout(); fig.savefig(FIG / "derece_dagilimi.png"); plt.close(fig)


# ----------------------------------------------------------------------------- 3) topluluk haritası
def topluluk_haritasi(H):
    topl = json.loads((SON / "topluluklar.json").read_text(encoding="utf-8"))
    renk = {}
    for i, c in enumerate(topl):
        for n in c:
            renk[n] = PALET[i] if i < len(PALET) else "#b8c2cc"
    fig, ax = plt.subplots(figsize=(11, 5.4))
    _harita_ekseni(ax)
    _kenarlar(ax, H, renk="#cfd6de", lw=0.6, alpha=1)
    ax.scatter([H.nodes[n]["lon"] for n in H], [H.nodes[n]["lat"] for n in H], s=16,
               c=[renk[n] for n in H], lw=0.3, edgecolors="white", zorder=3)
    for i, c in enumerate(topl[:len(PALET)]):
        lon = np.median([H.nodes[n]["lon"] for n in c]); lat = np.median([H.nodes[n]["lat"] for n in c])
        _etiket(ax, lon, lat, f"{TOPLULUK_ADLARI[i]} ({len(c)})", boyut=9.5, dx=0, dy=0.25,
                renk=PALET[i], ha="center")
    ax.set_title(f"Louvain toplulukları: {len(topl)} topluluk, en büyük 8'i renkli")
    fig.savefig(FIG / "topluluklar.png"); plt.close(fig)


# ----------------------------------------------------------------------------- 4) tek hata noktaları
def tek_hata(H, S):
    ek = pd.read_csv(SON / "eklem_noktalari.csv").set_index("id")
    kp = pd.read_csv(SON / "kopruler.csv")
    fig, ax = plt.subplots(figsize=(11, 5.4))
    _harita_ekseni(ax)
    _kenarlar(ax, H, renk="#cfd6de", lw=0.6, alpha=1)
    # köprüler (10+ merkez koparan) kalın mor
    from matplotlib.collections import LineCollection
    seg = [[(H.nodes[r.u]["lon"], H.nodes[r.u]["lat"]), (H.nodes[r.v]["lon"], H.nodes[r.v]["lat"])]
           for r in kp.itertuples() if r.kopan_dugum >= 5]
    ax.add_collection(LineCollection(seg, colors=MOR, linewidths=2.2, zorder=2))
    normal = [n for n in H if n not in ek.index]
    ax.scatter([H.nodes[n]["lon"] for n in normal], [H.nodes[n]["lat"] for n in normal],
               s=6, c=KYOK, lw=0, zorder=3)
    e = ek.sort_values("kopan_dugum")
    ax.scatter([H.nodes[n]["lon"] for n in e.index], [H.nodes[n]["lat"] for n in e.index],
               s=12 + 9 * e.kopan_dugum, c=[K380 if k >= 10 else K154 for k in e.kopan_dugum],
               edgecolors="white", lw=0.5, zorder=4)
    yazilan = []
    for n, r in ek.sort_values("kopan_dugum", ascending=False).head(10).iterrows():
        x, y = H.nodes[n]["lon"], H.nodes[n]["lat"]
        if any(abs(x - a) < 0.6 and abs(y - b) < 0.3 for a, b in yazilan):
            continue  # çok yakın iki merkezin etiketleri üst üste binmesin
        yazilan.append((x, y))
        _etiket(ax, x, y, f"{_kisa(r['ad'])} ({r.kopan_dugum})", boyut=8.5)
    th = S["tek_hata_noktalari"]
    ax.legend(handles=[
        Line2D([], [], marker="o", ls="", color=K380, ms=9, label="eklem noktası, 10+ merkez koparır"),
        Line2D([], [], marker="o", ls="", color=K154, ms=6, label="eklem noktası (boy = kopan merkez)"),
        Line2D([], [], marker="o", ls="", color=KYOK, ms=4, label="yedekli merkez"),
        Line2D([], [], color=MOR, lw=2.2, label="köprü hat, 5+ merkez koparır")],
        loc="upper left", bbox_to_anchor=(0, 0.02), fontsize=9, ncol=3)
    ax.set_title(f"Tek hata noktaları: {th['eklem_noktasi_sayisi']} eklem noktası "
                 f"(%{100 * th['eklem_orani']:.0f}), {th['kopru_sayisi']} köprü hat")
    fig.savefig(FIG / "tek_hata_noktalari.png"); plt.close(fig)


def eklem_cubuk(S):
    ek = pd.read_csv(SON / "eklem_noktalari.csv").head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.barh([f"{_kisa(a)} ({i})" for a, i in zip(ek.ad, ek.il)], ek.kopan_dugum,
            color=[K380 if k >= 10 else K154 for k in ek.kopan_dugum])
    for y, v in enumerate(ek.kopan_dugum):
        ax.text(v + 0.2, y, str(v), va="center", fontsize=9, color=MUREKKEP)
    ax.set_xlabel("Düştüğünde ana şebekeden kopan trafo merkezi sayısı")
    ax.set_title("En kritik 12 eklem noktası"); ax.grid(axis="y", visible=False)
    fig.savefig(FIG / "eklem_cubuk.png"); plt.close(fig)


# ----------------------------------------------------------------------------- 5) dayanıklılık
def dayaniklilik(S):
    dy = S["dayaniklilik"]
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    ax.plot(dy["rastgele"]["x"], dy["rastgele"]["ebb_orani"], color="#3b6fd8", lw=2,
            label="rastgele arıza")
    ax.plot(dy["hedefli_betweenness"]["x"], dy["hedefli_betweenness"]["ebb_orani"], color=K380, lw=2,
            label="hedefli (en yüksek betweenness önce)")
    hx = np.array(dy["hedefli_betweenness"]["x"]); hy = np.array(dy["hedefli_betweenness"]["ebb_orani"])
    i = int(np.argmax(hy < 0.5))
    if hy[i] < 0.5:
        ax.annotate(f"%{100 * hx[i]:.0f} merkez gidince\nana parça yarıya iner", xy=(hx[i], hy[i]),
                    xytext=(hx[i] + 0.05, 0.25), fontsize=9, color=K380,
                    arrowprops=dict(arrowstyle="-", color=K380, lw=0.8))
    ax.set_xlabel("Devre dışı bırakılan trafo merkezi oranı")
    ax.set_ylabel("En büyük bağlı parçanın oranı")
    ax.set_xlim(0, 0.6); ax.set_ylim(0, 1.02); ax.legend()
    ax.set_title("Rastgele ve hedefli arızaya dayanıklılık")
    fig.savefig(FIG / "dayaniklilik.png"); plt.close(fig)


# ----------------------------------------------------------------------------- 6) null model
def null_model(S):
    nm = S["null_model"]
    dag = json.loads((SON / "null_model_dagilim.json").read_text(encoding="utf-8"))
    olculer = [("ortalama_kumelenme", "Ortalama kümelenme"), ("ortalama_en_kisa_yol", "Ortalama en kısa yol"),
               ("modularite", "Modülerlik (Louvain)"), ("derece_assortativity", "Derece benzeşimi")]
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.4))
    for ax, (k, ad) in zip(axes, olculer):
        for model, renk, et in (("configuration", "#3b6fd8", "configuration"), ("erdos_renyi", KYOK, "Erdős–Rényi")):
            ax.hist(dag[model][k], bins=18, color=renk, alpha=0.75, label=et)
        g = nm["gozlem"][k]
        ax.axvline(g, color=K380, lw=2.2, label="gözlenen ağ")
        z = nm["karsilastirma"]["configuration"][k]["z_skoru"]
        ax.set_title(ad, fontsize=11)
        ax.text(0.5, 0.97, f"z = {z:.0f}" if abs(z) >= 10 else f"z = {z:.1f}", transform=ax.transAxes,
                ha="center", va="top", fontsize=10.5, color=K380, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
        ax.set_ylim(0, ax.get_ylim()[1] * 1.25)
        ax.set_yticks([]); ax.grid(False)
    axes[0].legend(fontsize=8, loc="center right")
    fig.suptitle(f"Null model: {nm['tekrar']} configuration + {nm['tekrar']} Erdős–Rényi rastgele ağ "
                 "(z: configuration modele göre)", x=0.01, ha="left", fontweight="bold", fontsize=12)
    fig.tight_layout(); fig.savefig(FIG / "null_model.png"); plt.close(fig)


# ----------------------------------------------------------------------------- 7) Spearman
def spearman(S):
    sp = pd.DataFrame(S["merkeziyet"]["spearman"])
    ad = {"derece": "Derece", "betweenness": "Betweenness", "closeness": "Closeness",
          "eigenvector": "Eigenvector", "pagerank": "PageRank"}
    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    im = ax.imshow(sp.values, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(sp))); ax.set_xticklabels([ad[c] for c in sp.columns], rotation=35, ha="right")
    ax.set_yticks(range(len(sp))); ax.set_yticklabels([ad[c] for c in sp.index])
    for i in range(len(sp)):
        for j in range(len(sp)):
            v = sp.values[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=9,
                    color="white" if v > 0.6 else MUREKKEP)
    ax.grid(False); ax.set_title("Merkeziyetler arası Spearman ρ")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.savefig(FIG / "spearman.png"); plt.close(fig)


# ----------------------------------------------------------------------------- 8) kaskad
def kaskad_alfa(S):
    k = S["kaskad"]
    al = k["alfalar"]
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    for g, renk, ad in (("en_yuksek_betweenness", K380, "en yüklü 10 merkezden biri düşerse"),
                        ("en_kritik_eklem", MOR, "en kritik 10 eklem noktasından biri"),
                        ("rastgele", "#3b6fd8", "rastgele 20 merkezden biri")):
        y = [k["ozet"][g][str(a)]["G_ortalama"] for a in al]
        lo = [k["ozet"][g][str(a)]["G_min"] for a in al]
        ax.plot(al, y, "-o", color=renk, lw=2, label=ad)
        ax.fill_between(al, lo, y, color=renk, alpha=0.12, lw=0)
    ax.set_xlabel("Yedek kapasite payı α  (kapasite = (1+α) × başlangıç yükü)")
    ax.set_ylabel("Kaskad sonrası en büyük parça (G)")
    ax.set_ylim(0, 1.02); ax.set_xticks(al); ax.legend(fontsize=9, loc="lower right")
    ax.set_title("Zincirleme arıza: tek bir merkezin kaybı şebekeyi ne kadar küçültür?")
    ax.text(0.01, 0.02, "çizgi: ortalama · gölge: en kötü durum", transform=ax.transAxes,
            fontsize=8.5, color=SOLUK)
    fig.savefig(FIG / "kaskad_alfa.png"); plt.close(fig)


def kaskad_harita(H, anahtar="en_yuksek_yuk", dosya="kaskad_dalgalar.png"):
    ornek = json.loads((SON / "kaskad_ornek.json").read_text(encoding="utf-8"))[anahtar]
    dalgalar = ornek["dalgalar"]
    renkler = plt.cm.YlOrRd(np.linspace(0.45, 0.95, max(2, len(dalgalar) - 1)))
    fig, ax = plt.subplots(figsize=(11, 5.4))
    _harita_ekseni(ax)
    dusen = {v for d in dalgalar for v in d}
    _kenarlar(ax, H, renk="#cfd6de", lw=0.6, alpha=1)
    kalan = [n for n in H if n not in dusen]
    ax.scatter([H.nodes[n]["lon"] for n in kalan], [H.nodes[n]["lat"] for n in kalan], s=6, c=KYOK, lw=0, zorder=3)
    tut = []
    for i, d in enumerate(dalgalar[1:], 1):
        c = renkler[i - 1]
        ax.scatter([H.nodes[n]["lon"] for n in d], [H.nodes[n]["lat"] for n in d], s=26, color=c,
                   edgecolors="white", lw=0.4, zorder=4 + i)
        tut.append(Line2D([], [], marker="o", ls="", color=c, ms=7, label=f"{i}. dalga: {len(d)} merkez"))
    b = dalgalar[0][0]
    ax.scatter([H.nodes[b]["lon"]], [H.nodes[b]["lat"]], s=200, marker="X", color=MUREKKEP,
               edgecolors="white", lw=1.2, zorder=20)
    _etiket(ax, H.nodes[b]["lon"], H.nodes[b]["lat"], f"{_kisa(ornek['ad'])}: ilk arıza", boyut=10, dx=0.2)
    tut.insert(0, Line2D([], [], marker="X", ls="", color=MUREKKEP, ms=10, label="başlangıç"))
    ax.legend(handles=tut, loc="upper left", bbox_to_anchor=(0, 0.02), fontsize=9, ncol=3)
    ax.set_title(f"{_kisa(ornek['ad'])} düşerse (α = {ornek['alfa']}): {ornek['dusen_toplam']} merkez devre dışı, "
                 f"ayakta kalan en büyük parça %{100 * ornek['G']:.0f}")
    fig.savefig(FIG / dosya); plt.close(fig)


# ----------------------------------------------------------------------------- 9) yöntem şekli
def yontem_ornek():
    """Küçük örnek: eklem noktası, köprü ve yük yeniden dağıtımı (sunumda yöntemi anlatmak için)."""
    G = nx.Graph()
    G.add_edges_from([("A", "B"), ("B", "C"), ("C", "A"), ("C", "D"), ("D", "E"), ("E", "F"),
                      ("F", "D"), ("D", "G"), ("G", "H"), ("B", "I"), ("I", "J"), ("J", "E")])
    pos = {"A": (0, 1), "B": (1, 1.6), "C": (1, 0.4), "I": (2.2, 2.0), "J": (3.4, 1.6), "D": (2.2, 0.4),
           "E": (3.4, 0.9), "F": (3.4, -0.2), "G": (2.2, -0.9), "H": (3.4, -1.3)}
    eklem = set(nx.articulation_points(G)); kopru = {tuple(sorted(e)) for e in nx.bridges(G)}
    L0 = nx.betweenness_centrality(G, normalized=False)
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(12.5, 3.7))

    def ciz(ax, H, renk, baslik, yazi=None, kalin=()):
        for u, v in G.edges():
            canli = H.has_edge(u, v)
            ax.plot(*zip(pos[u], pos[v]), color=(MOR if tuple(sorted((u, v))) in kalin else "#9aa6b2")
                    if canli else "#e3e7ec", lw=3 if tuple(sorted((u, v))) in kalin else 1.6,
                    ls="-" if canli else "--", zorder=1)
        for n in G:
            ax.scatter(*pos[n], s=430, color=renk(n), edgecolors="white", lw=1.5, zorder=2)
            ax.text(*pos[n], n, ha="center", va="center", color="white", fontweight="bold", fontsize=10, zorder=3)
            if yazi:
                if yazi(n):
                    ax.text(pos[n][0] + 0.2, pos[n][1] - 0.2, yazi(n), ha="left", va="top", fontsize=8.5,
                            color=MUREKKEP, zorder=4,
                            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9))
        ax.set_title(baslik, fontsize=11); ax.axis("off"); ax.set_xlim(-0.5, 4.3); ax.set_ylim(-1.8, 2.4)

    ciz(a1, G, lambda n: K380 if n in eklem else "#3b6fd8",
        "1) Eklem noktası ve köprü", kalin=kopru)
    a1.text(-0.4, -1.75, "Kırmızı (D, G): düşerse ağ bölünür.\nMor hatlar (D–G, G–H): köprü; kesilirse G/H kopar.",
            fontsize=8.5, color=MUREKKEP)
    ciz(a2, G, lambda n: "#3b6fd8", "2) Yük = geçen en kısa yol sayısı",
        yazi=lambda n: f"L={L0[n]:.0f}")
    H = G.copy(); H.remove_node("C")
    L1 = nx.betweenness_centrality(H, normalized=False)
    kap = {n: 1.25 * L0[n] for n in G}
    asan = {n for n in H if L1[n] > kap[n] + 1e-9}
    ciz(a3, H, lambda n: "#e3e7ec" if n == "C" else (K380 if n in asan else "#3b6fd8"),
        "3) C düşer, yük yeniden dağılır (α=0,25)",
        yazi=lambda n: "" if n == "C" else f"{L1[n]:.0f}/{kap[n]:.1f}")
    a3.text(-0.4, -1.75, "Yazı: yeni yük / kapasite. Kırmızı: kapasiteyi aşıp\nikinci dalgada düşenler.",
            fontsize=8.5, color=MUREKKEP)
    fig.tight_layout(); fig.savefig(FIG / "yontem_ornek.png"); plt.close(fig)
    return {"eklem": sorted(eklem), "kopru": sorted(kopru), "L0": L0, "asan": sorted(asan)}


def main():
    FIG.mkdir(exist_ok=True)
    G, H, S = yukle()
    harita_gerilim(G)
    derece(G, S)
    topluluk_haritasi(H)
    tek_hata(H, S)
    eklem_cubuk(S)
    dayaniklilik(S)
    null_model(S)
    spearman(S)
    kaskad_alfa(S)
    kaskad_harita(H, "en_yuksek_yuk", "kaskad_dalgalar.png")
    kaskad_harita(H, "en_hasarli", "kaskad_en_hasarli.png")
    print(yontem_ornek())
    print("Şekiller →", FIG)


if __name__ == "__main__":
    main()
