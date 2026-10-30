# Aerodinamik veri için sonraki Flow5 analizi

İş bölümü: analizler kullanıcının mevcut Flow5 projesinde ve mevcut 2D polar
interpolasyon veri tabanıyla alınır. FlightLab Python tarafı yalnız 3D analiz
sonuçları ve bunların koşullarını işler. 2D profil koordinatları veya 2D polar
dosyalarının kullanıcıdan yüklenmesi bu iş akışının gereksinimi değildir.
Bağımsız XML batch paketi opsiyoneldir; ana iş akışının önkoşulu değildir.

Son durum: yeni deniz seviyesi ISA T2 poları seçildi. Kullanıcı talebiyle
etkin CLmax=0.75944; bu belgede geçen önceki 0.9 hedefi artık istenmiyor.
Yeni tarama önkoşulu yoktur. [Güncel veri](sea-level-polar-audit.md).

**Güncelleme:** Kullanıcının sağladığı 55 noktalı T2 poları ilk referans
modeli için yeterlidir. Aşağıdaki Type 1 taraması artık başlangıç önkoşulu
değil, Reynolds/hız etkisini bağımsız doğrulamak için sonraki iyileştirmedir.
Mevcut veri ve koşul uyuşmazlığı: [T2 kontrol raporu](t2-polar-audit.md).

## Stabilite türevleri neye yeter?

Boyutsuz türevler belirli trim noktasının etrafındaki yerel değişimleri verir.
Referans değerler, normalizasyon, eksenler ve ataletlerle birlikte doğrusal
dinamik model kurulabilir; yakın çevrede kaba performans yaklaşımı da yapılabilir.
Tek noktaya ait türevlerle geniş aralıkta doğrulanmış sürükleme, maksimum hız,
menzil ve endurance eğrileri belirlenemez.

Örneğin CD = CD* + a·(alpha-alpha*) + b·(V-V*) + k·(alpha-alpha*)²
ailesinde k'nın her değeri aynı noktada aynı CD'yi ve aynı birinci türevleri
verir, fakat noktanın uzağında farklı sürükleme üretir. İlave varsayımlar k'yı
seçebilir, ancak bu seçim yeni analiz verisi yerine geçmez. Ayrıca gövde ekseni
CX/CZ türevleri eksen dönüşümü olmadan CL/CD eğimleri diye okunamaz.

## İlk istenen tarama

- Mevcut tam uçak geometrisi, aynı gövde/kuyruk kapsamı, aynı referanslar.
- Sabit hızlı alpha taraması (Flow5 Type 1 / fixed-speed polar): ilk aşamada
  50, 70 ve 100 m/s için ayrı polarlar.
- Deniz seviyesi ISA: sıcaklık 15 °C, yoğunluk yaklaşık 1.225 kg/m³;
  dinamik viskozite yaklaşık 1.7894e-5 Pa·s, kinematik yaklaşık 1.4607e-5 m²/s.
  Arayüzün hangi viskoziteyi istediğini ve birimini kontrol et.
- Başlangıç alpha aralığı −4° ila +12°, adım 0.5°. Bu bir stall öngörüsü
  değildir; CLmax=0.9 kullanıcı girdisiyle ayrıca sınırlandırılır. Gerekiyorsa
  CL kapsamına göre tarama genişletilir; yakınsamayan noktalar işaretlenir.
- Viskoz hesap için gerekli profil poları/Re kapsamı sağlanmalı; eksik viskoz
  sonuçlar toplam sürükleme diye kabul edilmemeli. Gövde/ek sürükleme kapsamı
  ve kullanılan katsayı tanımları korunmalı.
- Kullanıcı tercihi: tüm alpha/hız taramalarında elevator sapması sabit tutulur;
  gerçek sapma değeri dosya/ayarlarla belirtilir, bilinmiyorsa sıfır varsayılmaz.
  Cm=0 trim koşulu aranmaz ve ayrı trim sürüklemesi eklenmez. Bu, trim etkisinin
  küçük olduğu doğrulanmış bir sonuç değil, kabul edilen model varsayımıdır.
  Poların içinde zaten bulunan kuyruk/elevator sürüklemesi aynen korunur.
  Cm tanı amaçlı saklanır; Cm≠0 olan noktalar bu sebeple elenmez.
  Mevcut kapsamda ilave elevator/trim taraması istenmez.
- Tüm noktaları CSV olarak ver: alpha, CL, CD, Cm, hız, varsa CD_viscous,
  CD_induced, kontrol ayarları. Ayrıca analiz tanımını/ayar görüntülerini,
  S_ref, b_ref, c_ref, moment referansı ve solver/viskoz seçeneklerini ver.

Bu hızlar ilk düşük Mach veri paketi içindir. 300 m/s deniz seviyesinde yaklaşık
Mach 0.88'dir; bu bir izin verilen hız sınırı, doğrulanmış ulaşılabilir hız veya
Flow5 modelinin doğruluğunun kanıtı değildir. Düşük Mach poları bu hıza kadar
uzatılamaz. Yüksek hız sonuçları için sıkıştırılabilirlik/dalga sürüklemesi
geçerliliği ayrıca ele alınmalıdır; ilk üç polar bütün hız zarfını doğrulamaz.

Güncel kullanıcı kabulü: Flow5 katsayıları Mach 0.65'e kadar güvenilir kabul
edilir. Üstündeki kaynak verileri ve hesaplar korunur; yalnızca güvenilmez
uyarısı eklenir. Tüm 55 T2 noktası aktiftir. Bu eşik 300 m/s sert uçak hız
limitiyle karıştırılmaz. Kaynak ortamı 7000 m, ISA ofseti −45 °C, gerçek
sıcaklık −75.5 °C olarak son hesaplayıcı ekranıyla açıklığa kavuşmuştur.

## Uygulama girdileri ve yükleme

Varsayılan ortam: 0 m, ISA 15 °C, rüzgârsız. İrtifa ve yerel dış hava sıcaklığı
kullanıcı girdisidir; sıcaklık belirtilmezse o irtifadaki ISA sıcaklığı kullanılır.
Basınç ISA basınç irtifasından hesaplanır; yerel sıcaklık yoğunluk ve ses hızını
değiştirir. İlk atmosfer modeli −500–11000 m aralığıyla sınırlıdır.

Mevcut referans yükleme 32.1 kg ve bunun içinde 12 kg yakıt var. Aynı motor,
yük ve donanım için yakıt dışı kütle 20.1 kg. Kullanıcı toplam yüklü yakıtı
ve bunun içindeki rezervi seçer:

    m_initial = 20.1 + fuel_initial
    m(t) = 20.1 + fuel_remaining(t)
    fuel_remaining(t) = fuel_initial - integral(fuel_flow dt)

Rezerv toplam yakıta ikinci kez eklenmez; referans 12 kg da tekrar eklenmez.
Hesap rezervde durur, rezerv uçakta kalır ve ağırlığa dahildir. Bilinmeyen
depo kapasitesi bu referans 12 kg'a eşit varsayılmaz.

Mevcut modül yakıt kütlesi ve buna bağlı kararlı uçuş CL/sürükleme/güç hesabını
günceller. Yakıt tükenirken CG/atalet ve trim değişimi henüz çözülmez; toplam
atalet ekranı tek başına depo içi yakıt dağılımını belirlemez. Tam uçuş görevi,
trim ve irtifa/sıcaklığa bağlı motor modeli henüz tamamlanmamıştır.

Sınırlar: CLmax=0.9, TAS≤300 m/s, sürekli motor devri≤97 kRPM. Motor grafik
aralığı daha dar ise dar olan sınır uygulanır (~96.5 kRPM). Bu değerler
kullanıcı beyanıdır, modelin her koşulda doğrulandığı anlamına gelmez.
