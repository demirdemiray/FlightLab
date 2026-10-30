# Kullanıcının Flow5 7.57 batch çöküşü

Gözlem: Windows'ta Batch analysis (2) / Alt+F7, smoke analizleri seçiliyken
Calculate'a basar basmaz log görünmeden uygulama kapanıyor. Solver burada
kurulu olmadığı için çöküş yeniden üretilemedi. Neden doğrulanmış değildir.

XML üretim kontrolü: örnek deniz seviyesi/100 m/s XML'inde, kullanıcının
şablonuna göre yalnız Polar_Name, Fixed_Velocity, Fluid/Density ve
Fluid/Viscosity farklıdır. Bunun XML'in tüm Flow5 sürümlerinde çalışacağını
kanıtladığı iddia edilmez. Tam 72 analiz, başlangıç yolu doğrulanana kadar
çalıştırılmamalıdır. Veri veya viskoz seçenekleri rastgele değiştirilmez.

## Daraltma ve alternatif yol

1. Mevcut projeyi bir kopyada aç. Alt+F7 yolunu şimdilik kullanma.
2. `Import analyses from xml` ile yalnız `T1_h00000_V100.xml` dosyasını
   normal analiz listesine al. XML'i geometri içe aktarma menüsüyle yükleme.
3. Aynı analizi normal tek analiz ekranında yalnız alpha=2° için çalıştır.
   İçe aktarmada mı, hesaplamaya basınca mı, yoksa bir sonuçtan sonra mı
   kapandığını ayrı kaydet. Fiziksel ve viskoz ayarlar aynı kalsın.
4. Bu çalışırsa diğer smoke XML'ini de normal yoldan içe aktar. F7 / Batch
   analysis (1) içinde yalnız bu iki poları seçip önce dar bir alfa aralığıyla
   dene. Sonuç doğrulanmadan tüm matrise geçme.

Resmi main kaynakta `XPlane::onImportAnalysesFromXML` açık projedeki uçağı
bulup flap uyumluluğunu kontrol ederek analizleri ekler. Batch analysis (1)
mevcut polarları kullanır; Batch analysis (2) ise XML tanımlarını kendi
başlangıç yolunda ekler. Bu farklılık alternatif yolu gerekçelendirir,
ancak çöküşün flap kaynaklı olduğunu veya alternatifin 7.57'de mutlaka
çalışacağını kanıtlamaz. Menü adları kaynak kodundan kontrol edilmiştir.

Alternatif de başarısızsa kullanıcının oluşturduğu gerçek tek XML, çöküş
aşaması ve varsa Windows Application Error kaydıyla teşhis sürdürülmelidir.
Ana projeyi yeniden oluşturmak, polar veri tabanını silmek, inviscid moda
geçmek veya koordinatları değiştirmek bu teşhisin parçası değildir.
