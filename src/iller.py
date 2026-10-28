"""Türkiye'nin 81 ilinin yaklaşık merkez koordinatları (il merkezi, enlem/boylam).

Topluluklara ve trafo merkezlerine coğrafi bir etiket vermek için kullanılır:
her trafo merkezi, kendisine en yakın il merkezine atanır. Bu kaba bir
yaklaşımdır (il sınırlarını değil merkez noktalarını kullanır); raporda
"yaklaşık il" olarak belirtilmelidir.
"""

ILLER = {
    "Adana": (37.00, 35.32), "Adıyaman": (37.76, 38.28), "Afyonkarahisar": (38.76, 30.54),
    "Ağrı": (39.72, 43.05), "Aksaray": (38.37, 34.03), "Amasya": (40.65, 35.83),
    "Ankara": (39.93, 32.86), "Antalya": (36.89, 30.71), "Ardahan": (41.11, 42.70),
    "Artvin": (41.18, 41.82), "Aydın": (37.85, 27.85), "Balıkesir": (39.65, 27.89),
    "Bartın": (41.63, 32.34), "Batman": (37.88, 41.13), "Bayburt": (40.26, 40.23),
    "Bilecik": (40.14, 29.98), "Bingöl": (38.88, 40.50), "Bitlis": (38.40, 42.11),
    "Bolu": (40.74, 31.61), "Burdur": (37.72, 30.29), "Bursa": (40.19, 29.06),
    "Çanakkale": (40.15, 26.41), "Çankırı": (40.60, 33.62), "Çorum": (40.55, 34.95),
    "Denizli": (37.78, 29.09), "Diyarbakır": (37.91, 40.24), "Düzce": (40.84, 31.16),
    "Edirne": (41.68, 26.56), "Elazığ": (38.68, 39.22), "Erzincan": (39.75, 39.49),
    "Erzurum": (39.90, 41.27), "Eskişehir": (39.78, 30.52), "Gaziantep": (37.07, 37.38),
    "Giresun": (40.91, 38.39), "Gümüşhane": (40.46, 39.48), "Hakkari": (37.58, 43.74),
    "Hatay": (36.20, 36.16), "Iğdır": (39.92, 44.04), "Isparta": (37.76, 30.55),
    "İstanbul": (41.01, 28.98), "İzmir": (38.42, 27.14), "Kahramanmaraş": (37.58, 36.94),
    "Karabük": (41.20, 32.62), "Karaman": (37.18, 33.22), "Kars": (40.60, 43.10),
    "Kastamonu": (41.38, 33.78), "Kayseri": (38.73, 35.49), "Kırıkkale": (39.85, 33.52),
    "Kırklareli": (41.73, 27.22), "Kırşehir": (39.15, 34.16), "Kilis": (36.72, 37.12),
    "Kocaeli": (40.77, 29.94), "Konya": (37.87, 32.48), "Kütahya": (39.42, 29.98),
    "Malatya": (38.35, 38.31), "Manisa": (38.61, 27.43), "Mardin": (37.31, 40.74),
    "Mersin": (36.81, 34.64), "Muğla": (37.22, 28.36), "Muş": (38.74, 41.49),
    "Nevşehir": (38.62, 34.71), "Niğde": (37.97, 34.68), "Ordu": (40.98, 37.88),
    "Osmaniye": (37.07, 36.25), "Rize": (41.02, 40.52), "Sakarya": (40.78, 30.40),
    "Samsun": (41.29, 36.33), "Siirt": (37.93, 41.94), "Sinop": (42.03, 35.15),
    "Sivas": (39.75, 37.02), "Şanlıurfa": (37.16, 38.79), "Şırnak": (37.52, 42.46),
    "Tekirdağ": (40.98, 27.51), "Tokat": (40.31, 36.55), "Trabzon": (41.00, 39.72),
    "Tunceli": (39.11, 39.55), "Uşak": (38.68, 29.41), "Van": (38.49, 43.38),
    "Yalova": (40.66, 29.27), "Yozgat": (39.82, 34.81), "Zonguldak": (41.46, 31.80),
}

# İllerin coğrafi bölgeleri (topluluk adlandırmasında kullanılır)
BOLGELER = {
    "Marmara": ["İstanbul", "Edirne", "Kırklareli", "Tekirdağ", "Çanakkale", "Kocaeli",
                "Yalova", "Sakarya", "Bilecik", "Bursa", "Balıkesir"],
    "Ege": ["İzmir", "Manisa", "Aydın", "Denizli", "Muğla", "Afyonkarahisar", "Kütahya", "Uşak"],
    "Akdeniz": ["Antalya", "Isparta", "Burdur", "Adana", "Mersin", "Hatay", "Osmaniye",
                "Kahramanmaraş"],
    "İç Anadolu": ["Ankara", "Konya", "Kayseri", "Eskişehir", "Sivas", "Kırıkkale", "Aksaray",
                   "Karaman", "Kırşehir", "Niğde", "Nevşehir", "Yozgat", "Çankırı"],
    "Karadeniz": ["Samsun", "Trabzon", "Ordu", "Giresun", "Rize", "Artvin", "Zonguldak",
                  "Bartın", "Karabük", "Kastamonu", "Sinop", "Amasya", "Tokat", "Çorum",
                  "Bolu", "Düzce", "Gümüşhane", "Bayburt"],
    "Doğu Anadolu": ["Erzurum", "Erzincan", "Kars", "Ağrı", "Iğdır", "Ardahan", "Van", "Muş",
                     "Bitlis", "Bingöl", "Tunceli", "Elazığ", "Malatya", "Hakkari"],
    "Güneydoğu Anadolu": ["Gaziantep", "Şanlıurfa", "Diyarbakır", "Mardin", "Batman", "Siirt",
                          "Şırnak", "Adıyaman", "Kilis"],
}
IL_BOLGE = {il: b for b, iller in BOLGELER.items() for il in iller}
assert len(ILLER) == 81 and len(IL_BOLGE) == 81


def en_yakin_il(lat, lon):
    """Verilen noktaya en yakın il merkezinin adını döndürür (düzlemsel yaklaşık)."""
    import math
    best, bd = None, 1e18
    c = math.cos(math.radians(39.0))
    for il, (a, b) in ILLER.items():
        d = (lat - a) ** 2 + ((lon - b) * c) ** 2
        if d < bd:
            best, bd = il, d
    return best
