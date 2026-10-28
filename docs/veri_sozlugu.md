# Veri sözlüğü

**Kaynak:** OpenStreetMap, Overpass API üzerinden (`power=substation` ve `power=line`, Türkiye alanı `ISO3166-1=TR`).
**Toplama tarihi:** 28.10.2026, 18:35–19:03 UTC (`data/raw/meta.json`).
**Lisans:** © OpenStreetMap katkıcıları, [Open Database License (ODbL) 1.0](https://www.openstreetmap.org/copyright). Bu depodaki türetilmiş veri (CSV, GraphML) de ODbL altındadır; kullanırken "© OpenStreetMap katkıcıları" atfı yapılmalıdır.
**Kişisel veri:** Yoktur. Düğümler kamu altyapısıdır (trafo merkezleri); OSM'de bu nesneleri çizen kullanıcıların adları indirilmemiştir.

## Ham veri (`data/raw/`)

| Dosya | İçerik |
|---|---|
| `substations.json` | Overpass JSON. `power=substation` olan node/way/relation nesneleri, etiketleri ve sınır kutusu (`bounds`). |
| `lines.json` | Overpass JSON (`src/colab_indir.py` ile indirildi). `power=line` yolları (way) ve bu yolların direk noktaları (node, enlem/boylam). Türkiye 3×4 = 12 karoya bölünerek indirildi; tekrar eden nesneler ayıklandı. |
| `meta.json` | İndirme zamanı, yöntem, lisans. |

## Ağ kurma kararları

| Karar | Seçim | Gerekçe |
|---|---|---|
| Düğüm | Trafo merkezi (`power=substation`); `substation=minor_distribution` hariç | Kart tanımı. Küçük dağıtım köşkleri iletim şebekesinin parçası değildir. |
| Kenar | İki trafo merkezini birleştiren iletim hattı | Kart tanımı. |
| Gerilim süzgeci | ≥ 66 kV ya da gerilim etiketi yok | Türkiye'de iletim 66/154/380 kV'tur; 34,5 kV ve altı dağıtımdır. Etiketsiz hatlar (1221 hat, %26) dışarıda kalsaydı ağ yapay olarak parçalanırdı; etiketsiz hatlar dahil edilmeden kurulan "sıkı ağ" da ayrıca kaydedildi (`grid_strict.graphml`). |
| Hat ucu → trafo eşleme | Hat ucu trafo merkezinin sınır kutusu içinde (50 m pay) ya da merkezine ≤ 300 m ise | OSM'de hatlar trafo alanının içinde biter ama çoğu zaman trafo nesnesiyle ortak nokta paylaşmaz. |
| Branşman (T-bağlantı) | Trafoya değmeyen hat parçaları direklerde birleşir; bu kümeye değen ≤ 3 trafo ikişer ikişer, daha fazlası hat uzunluğuna göre en küçük kapsayan ağaçla bağlanır | Tek bir hat birden çok merkeze dallanabilir; hepsini birbirine bağlamak sahte kenar üretirdi. |
| Paralel hatlar | Aynı iki merkez arasındaki hatlar tek kenarda birleştirilir (`hat_sayisi`) | Topolojik analizde iki merkez ya bağlıdır ya değildir. |
| Yön | Yönsüz | AC şebekede güç iki yönde de akabilir. |
| Ağırlık | Analizler ağırlıksız | Hat kapasitesi OSM'de yoktur; uzunluk ve gerilim yalnızca bilgi olarak saklanır. |
| Analiz kapsamı | En büyük bağlı bileşen (1072 merkez); temel ölçüler ayrıca tüm ağ (1193) için | Ana şebekeden kopuk 38 küçük parça çoğunlukla OSM'de eksik çizilmiş hatlardan kaynaklanır. |
| İl ataması | Trafo merkezine en yakın il merkezi | İl sınırı verisi kullanılmadı; büyük illerin sınırına yakın merkezler komşu ile atanabilir (ör. Kozan ve Ceyhan, Adana'ya bağlı ama Osmaniye merkezine daha yakın). Bu yüzden "yakın il" olarak adlandırılır. |

## `data/processed/nodes.csv` — düğüm listesi (1193 satır)

| Sütun | Anlamı |
|---|---|
| `id` | OSM nesne kimliği; ilk harf türü gösterir (`n` node, `w` way, `r` relation). |
| `ad` | OSM `name` etiketi (boş olabilir). |
| `isletmeci` | OSM `operator` etiketi (ör. TEİAŞ). |
| `tur` | OSM `substation` etiketi (transmission, distribution, generation, traction…; boş olabilir). |
| `lat`, `lon` | Trafo merkezinin merkezi (WGS84 derece). Alan olarak çizilenlerde sınır kutusunun ortası. |
| `il` | En yakın il merkezi (yaklaşık). |
| `bolge` | `il`'in coğrafi bölgesi. |
| `gerilim_kv` | Trafo etiketindeki en yüksek gerilim (kV); etiket yoksa bağlı hatların en yüksek gerilimi; hiçbiri yoksa -1. |
| `osm_url` | Nesnenin OpenStreetMap sayfası. |

## `data/processed/edges.csv` — kenar listesi (1543 satır)

| Sütun | Anlamı |
|---|---|
| `kaynak`, `hedef` | Bağlanan iki trafo merkezinin `id`'si. |
| `uzunluk_km` | İki merkez arasındaki en kısa hat güzergâhının uzunluğu (km). |
| `gerilim_kv` | Bu bağlantıdaki hatların en yüksek gerilimi (kV); bilinmiyorsa -1. |
| `hat_sayisi` | Bu bağlantıyı oluşturan OSM hat (way) sayısı. |
| `bransman` | 1: bağlantı birden çok OSM hat parçası birleştirilerek kuruldu (parçalı çizilmiş hat ya da T-branşman; 1.543 kenarın 1.094'ü); 0: tek parça doğrudan hat. |

## `results/` — analiz çıktıları

| Dosya | İçerik |
|---|---|
| `analiz.json` | Tüm sayısal sonuçlar (temel ölçüler, powerlaw, merkeziyet ilk 10 ve Spearman, topluluklar ve kararlılık, null model z-skorları, eklem/köprü özetleri, kaskad özetleri). |
| `merkeziyet.csv` | Düğüm başına derece, betweenness, closeness, eigenvector, PageRank, topluluk no, eklem noktası mı, kopardığı merkez sayısı, başlangıç yükü `yuk_L0`. |
| `eklem_noktalari.csv` | Her eklem noktası: düştüğünde oluşan parça sayısı, ana şebekeden kopan merkez sayısı ve bu merkezlerin illeri. |
| `kopruler.csv` | Her köprü hat: uçları, gerilim, uzunluk, kesilirse kopan merkez sayısı. |
| `kaskad_deneyleri.csv` | Her (başlangıç merkezi, α) için kaskad sonucu: dalga sayısı, düşen merkez, G. |
| `kaskad_ornek.json` | İki örnek kaskadın dalga dalga düşen merkezleri. |
| `null_model_dagilim.json` | 100 configuration + 100 Erdős–Rényi ağın ölçü dağılımları. |
| `topluluklar.json` | Louvain toplulukları (büyükten küçüğe, düğüm id listeleri). |
