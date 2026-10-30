# Motor grafikleri: okuma ve tutarlılık kaydı

**Seçim:** Kullanıcı talebiyle aktif yakıt kaynağı RPM–yakıt grafiğidir.
Katalogdaki `fuel_source` değeri `rpm_graph`; seçili motor modeli CSV yakıt
değerlerini kullanmaz. CSV orijinal kaynak incelemesi için korunur.

Kaynak: kullanıcının paylaştığı üç grafik. Ham sayısal ölçüm tablosu değildir.
İşaretçi merkezleri ve eksen sınırları görselden elle tahmin edilmiştir.
Grafik çizgisinin eğriliği kesin bir fonksiyon olarak kabul edilmez.

## Birimler

- x: kRPM = 1000 devir/dakika.
- Yakıt: g/dakika; kg/s için 60000, kg/saat için 0.06 katsayısı.
- İtki: kgf; N için 9.80665 katsayısı. Bu alan kg uçak kütlesi değildir.
- TSFC: kg/(kgf·saat) = (g/dakika × 0.06) / kgf.
- SI TSFC (kg/(N·s)) için grafik TSFC değeri 9.80665 × 3600 ile bölünür.

## Yaklaşık referans sonuçları

| kRPM | İtki (N) | Yakıt (kg/saat) |
|---:|---:|---:|
| 30.5 | 11.5 | 11.4 |
| 40.6 | 28.0 | 16.7 |
| 50.8 | 55.3 | 20.8 |
| 61.0 | 100.0 | 26.0 |
| 71.2 | 152.7 | 31.6 |
| 81.4 | 242.1 | 42.1 |
| 91.4 | 350.8 | 60.1 |
| 96.5 | 399.2 | 69.2 |

## Bağımsız TSFC karşılaştırması

Her eğri aynı RPM değerine ayrı ayrı enterpole edilir. Aşağıdaki farklar
kapatılmamış, eğriler TSFC grafiğine uydurulmamıştır.

| kRPM | Yakıt/itkiden TSFC | Grafikten TSFC | Göreli fark |
|---:|---:|---:|---:|
| 30.5 | 9.70 | 9.00 | 7.8% |
| 40.6 | 5.85 | 5.69 | 2.7% |
| 50.7 | 3.72 | 3.66 | 1.7% |
| 60.9 | 2.56 | 2.49 | 2.8% |
| 71.1 | 2.04 | 2.00 | 1.8% |
| 81.3 | 1.71 | 1.69 | 1.1% |
| 91.4 | 1.68 | 1.66 | 1.1% |
| 96.5 | 1.70 | 1.66 | 2.4% |

Düşük RPM noktasında çok küçük itki, grafik okumasındaki küçük mutlak hatayı
büyük göreli hataya dönüştürür. Nominal okuma payları kRPM ±0.3, yakıt ±10 g/dakika,
itki ±0.2 kgf, TSFC ±0.1 kg/(kgf·saat) olarak kaydedilmiştir; bunlar
mühendislik okuma tahminleridir, doğrulanmış hata sınırları veya güven aralığı değildir.
Bu belirsizlikler performans çözümüne henüz yayılmamıştır.

## Kaynakların ayrılması

Grafik üst ortak sınırında (~96.5 kRPM): ~399 N ve ~69.2 kg/saat.
Önceki irtifa–Mach CSV Case 0: 400 N ve 54 kg/saat. Tüketimler yaklaşık %28 farklıdır.
Bunu gidermek için gizli ölçek uygulanmamıştır. Grafiklerin atmosfer/uçuş koşulları,
güç limiti ve CSV ile rejim eşleşmesi bilinmiyor. Kullanıcı verileri doğru kabul
edilir; bu, ayrı kaynakların aynı koşulda olduğu anlamına gelmez.

RPM modelinin ortak geçerlilik aralığı ~30.5–96.5 kRPM. İrtifa veya Mach etkisi
bu modele eklenmemiştir. Genel uçuşta kısmi gaz tüketimi için eşleme hâlâ gereklidir.
Tam uçak performansı için çok noktalı aerodinamik polarlar da henüz eksiktir.

## İtki çarpanı

Varsayılan 1.0, aralık 0.6–1.0. Aynı RPM için T = k·T_ref; yakıt değişmez.
Dolayısıyla aynı RPM için etkin TSFC, referans TSFC / k olur. Sabit gerekli
itki çözülüyorsa daha yüksek RPM gerekebilir ve buna bağlı yakıt tüketimi artar.
Çarpan gaz kolu, termodinamik verim veya yakıt tasarrufu çarpanı değildir.
