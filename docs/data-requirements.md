# İlk veri paketi

## İlk performans tahmini için gerekli

- **Konfigürasyon:** sabit kanat düzeni; elektrikli/yakıtlı itki; temiz/flaplı
  durum; analiz edilen modelde gövde, kuyruk ve diğer parçaların kapsamı.
- **Geometri/referanslar:** kanat referans alanı S (m²), açıklık b (m), MAC (m),
  Flow5 katsayılarının referans alanı/uzunlukları ve moment referans noktası.
- **Kütle:** uçuşa hazır toplam kütle (kg), CG konumu ve koordinat tanımı;
  batarya/yakıt/yük kütleleri ve varsa değişimleri.
- **Aerodinamik:** mümkünse CSV/TXT tam uçak polar tablosu: alpha, CL, toplam CD,
  Cm; varsa CDi/CDv ayrımı, elevator/flap açısı, trim bilgisi. Her analiz için
  hız, Reynolds sayısı, irtifa/yoğunluk, viskoz ayarı ve geçerlilik aralığı.
  Birden fazla hız/Re noktası tercih edilir. CLmax/stall sınırı için deney veya
  güvenilir ayrı veri gerekir; doğrusal panel çözümünden güvenilir stall beklenmez.
- **İtki:** motor ve pervane modelleri, pervane çapı/pitch, adet, besleme gerilimi,
  sürekli/kısa süreli güç-akım-RPM limitleri. Tercihen hız/RPM/gaz seviyesine göre
  itki, tork/şaft gücü ve elektrik giriş gücü haritası. Yalnız statik itki,
  hareketli uçuşta maksimum hız ve güç tüketimini belirlemez.
- **Enerji:** elektriklide hücre/seri-paralel düzeni, nominal gerilim, Ah veya Wh,
  kullanılabilir kapasite, deşarj/gerilim düşümü bilgisi, kesme ve rezerv;
  aviyonik ve diğer sürekli yükler. Yakıtlıda kullanılabilir yakıt ve motorun
  güç/RPM/irtifaya göre yakıt tüketimi haritası.
- **Koşullar:** hedef irtifa, sıcaklık veya yoğunluk, rüzgâr; hedef rezerv,
  hız/yapısal limitler. Eksiklerde kullanılan varsayımlar açıkça raporlanır.

Harita yoksa üretici verisi veya test noktalarından belirsizliği belirtilmiş
yaklaşık model kurulabilir. Sadece motorun etiket gücü ya da bataryanın nominal
Wh değeriyle hassas menzil veya maksimum hız sonucu vaat edilmez.

## Dinamik uçuş modeli için sonraki paket

- Boyutsuz stabilite türevleri ve bunların hesaplandığı trim noktası, hız,
  alpha, yoğunluk, referanslar, eksen/işaret ve normalizasyon tanımları.
- Ixx, Iyy, Izz ve ilgili çapraz ataletler (kg m²), CG ve atalet eksenleri.
- Kontrol türevleri, yüzey hareket sınırları ve servo dinamiği; varsa itki
  hattı/CG ofseti ve motor dinamiği.

Stabilite türevleri bir trim noktasının çevresindeki yerel değişimleri verir;
geniş hız/açı aralığındaki CL–CD polarının veya enerji/itki modelinin yerini tutmaz.

## Sonuçların tanımı

- Maksimum hız: koşullar ve sürekli güç limiti belirtilmiş TAS; gerekirse IAS.
- Maksimum hızda menzil/endurance: rezerv sonrası kullanılabilir enerjiyle,
  o hızda sürdürülebilir operasyon için; kısa süreli güç sınırı ayrıca ele alınır.
- Cruise: kullanıcı seçimi veya menzil/zaman/enerji hedefiyle önerilen hız.
- Maksimum menzil ve endurance: ayrı optimizasyonlar; itki verimi ve yardımcı
  yükler dahil. Maksimum L/D ile minimum faydalı güç tek başına bu sonuçlar değildir.
- Tırmanış: başlangıçta kararlı fazla güç yaklaşımı, sonra enerji ve kütle değişimi
  içeren görev simülasyonu. İlk sürüm tam 6 serbestlik dereceli dinamik model değildir.
- İdeal profil: tanımlı hedef, rota, irtifa sınırları, kalkış/tırmanış/seyir/iniş
  segmentleri ve rezerv ile sınırlı; görev tanımsızken tek bir optimum yoktur.
