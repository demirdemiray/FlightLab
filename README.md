# FlightLab

Flow5 aerodinamik çıktılarından uçuş performansı hesaplamak için Python çekirdeği.
Arayüz daha sonra aynı çekirdeği kullanacak. İç birimler SI; veri kaynağındaki
birimler ve katsayı referansları içe aktarımda açıkça kaydedilecek.

## Şu an çalışan bölüm

Güncel çekirdek: çoklu 3D polar ZIP/klasör okuyucusu ve manifest eşleştirmesi,
CL–log(Re)–Mach interpolasyonu (CD/Cm/alpha ve kaynak izleri), yakıtla
hafifleyen 2D noktasal uçuş integratörü, düz uçuş hız optimizasyonu ve JSON
çıktılı komut satırı arayüzü. Gerçek 72 CSV henüz gelmedi; çoklu model şu an
sentetik veriyle doğrulanmıştır. Tam A→B uçuş profili optimizasyonu ve
irtifa/Mach etkili motor–RPM eşlemesi henüz tamamlanmamıştır.
[API ve doğrulama kapsamı](docs/python-core.md).

Sınırlı CL aralığında parabolik polar kullanarak düz, sabit irtifalı uçuşun CL,
CD, gerekli itki ve faydalı itki gücü hesabı. Bu güç bataryadan çekilen güç değildir.
Flow5 CSV okuyucusu başlıkları, birimleri ve tüm sayısal sütunları korur;
başlıkla ilk noktanın aynı satırda olduğu çıktıyı da destekler.
Trim çözümü ve tam görev optimizasyonu yoktur; motor referans modelleri aşağıda
açıklanmıştır. Kullanıcı tercihiyle sabit elevator poları kullanılacak ve ayrı
trim sürüklemesi eklenmeyecektir. Poların içerdiği kuyruk/elevator sürüklemesi
korunur; Cm=0 koşulu aranmaz. Bu kabul, trim etkisinin doğrulanmış ölçümü değildir.
Gerçek uçak için tamamlanmış görev performansı henüz üretilmez. Seçili
aerodinamik referans artık 55 noktalı T2 polarıdır; CL→CD tablosu hazırdır.

```python
from flightlab.flow5 import read_flow5_csv

polar = read_flow5_csv("T7-TriUniform-ThinSurf.csv")
print(polar.points[0]["CL"], polar.points[0]["CD"])
```

Okuyucu eksik/hizası bozuk alanları ve sonlu olmayan temel CL/CD/Cm/hız
değerlerini reddeder. Negatif CL'de tanımsız olabilen yardımcı oranlar NaN/Inf
olarak korunur ve kalite raporunda belirtilir. Kaynak değerleri
otomatik SI dönüşümü yapmadan korur (ör. CoG_x cm). Gamma'nın birimi dosyada
belirtilmediği için okuyucu birim varsaymaz. Tek nokta bir polar eğrisi değildir;
dosyanın adı tek başına analiz türü, trim veya viskoz ayarları için kanıt sayılmaz.

Flow5 geometri XML dosyaları `flightlab.geometry.read_flow5_geometry` ile
okunabilir. Okuyucu açık birim çarpanlarını uygulayıp kesitleri, profil adlarını,
noktasal kütleleri ve beyan edilen toplam kütleyi çıkarır. Düz, simetrik, iki
taraflı kanat için yerel planform alanı, açıklık, MAC ve AR hesaplanır. Bu alan
poların referans alanı olarak otomatik atanmaz. Gövdenin NURBS çözümü, yüzeylerin
uzaysal yerleşimi/dönüşü, tam uçak CG ve atalet hesabı henüz uygulanmamıştır;
AutoInertia alanlarındaki önbellek değerleri doğrulanmış toplam atalet sayılmaz.

Python 3.11+, NumPy ve SciPy kullanılır. Temiz kurulum:

```sh
cd /workspace/FlightLab
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/flightlab --help
```

## Geliştirme sırası

1. Gelen gerçek T1 CSV paketini manifestle denetle, çoklu interpolasyonu kur
   ve gerçek sonuçlarla veri kapsamı/ara nokta doğrulamasını yap.
2. Maksimum RPM irtifa/Mach itki haritasıyla RPM–yakıt referans grafiğinin
   çalışma noktası eşlemesini açık varsayımlarla tamamla.
3. Uçuş integratörünü doğrulanmış modellerle bağla; katapult çıkışı ve görev
   sonu sınırlarıyla minimum süre/minimum yakıt A→B profil optimizasyonu ekle.
4. Belirsizlik ve ölçümle doğrulama, sonra arayüz.

Maksimum hız kullanılabilir ve gerekli itkinin kesişiminden, uygulanabilir uçuş
zarfı ve sürekli güç limitleri içinde bulunacak. Menzil ve endurance enerji/yakıt
tüketimi üzerinden hesaplanacak. Tek bir evrensel “ideal cruise” veya “ideal
profil” varsayılmayacak: amaç, rezerv, irtifa, rüzgâr ve görev şartları belirtilecek.

Veri gereksinimleri: [docs/data-requirements.md](docs/data-requirements.md).

## Uçak ve motor kataloğu

`data/catalog.json` uçak ve motorları bağımsız kimliklerle tutar. İlk uçak
`m600-thinsurf-acilar`: verilen geometri, polar, 32,1 kg yüklü kütle, CG ve
ekran görüntüsündeki CG etrafı ataletler bu kayda bağlıdır. CG için CSV'nin
daha hassas değerleri kullanılır; ataletler ekranın gösterdiği hassasiyettedir.
AMT Titan 392 N, verilen sütun biçimli motor haritasıyla kataloğa eklenmiştir.

```python
from flightlab.catalog import load_catalog

catalog = load_catalog("data/catalog.json")
aircraft = catalog.aircraft["m600-thinsurf-acilar"]
configuration = catalog.select(aircraft.id, "amt-titan-392n", thrust_factor=0.8)
engine = configuration.jet_model()
reference = engine.at_krpm(96.5)  # yaklaşık 319 N (çarpan 0.8); 69.2 kg/h
```

Motor seçimi bir eşleştirmedir, fiziksel uyumluluk onayı değildir. Mevcut kütle
5 kg motor ve 12 kg yakıt içerir; başka motor seçildiğinde bunlar tekrar eklenmez
veya otomatik değiştirilmez. Farklı yükleme, motor yerleşimi ve yakıt seviyesi
için CG/atalet yeniden hesaplama sonraki aşamadır. Ixy/Iyz bilinmiyor; Ixz'nin
Flow5 tensor işaret tanımı henüz doğrulanmadı. Mevcut kayıt 6-DOF çözümüne hazır
bir atalet tensörü olarak değerlendirilmez.

### Turbojet haritası ve itki çarpanı

**Seçili yakıt kaynağı: grafik.** Kullanıcı tercihi `fuel_source: rpm_graph`
olarak kaydedilmiştir. `configuration.jet_model()` bu motor için RPM grafik
modelini döndürür; CSV yakıt debisine otomatik dönüş yapılmaz. Eski harita
yalnız `configuration.source_jet_map_model()` ile kaynak inceleme amacıyla
açılabilir. Aşağıdaki CSV açıklamaları bu ham kaynağa aittir. RPM ile uçuş
koşullarını eşleyen model henüz olmadığı için seçili model irtifa/Mach sorgusu
sunmaz; CSV yakıtını veya doğrulanmamış bir düzeltmeyi kullanarak bunu gizlemez.

`thrust_factor` varsayılan **1.0**, izin verilen aralık **0.6–1.0**.
`T_effective = thrust_factor * T_map`; aynı çalışma noktasında yakıt debisi
değişmez. Çarpan gaz kolu veya termodinamik verim değildir. Gerekli itki için
başka bir motor çalışma noktası seçildiğinde tüketim ayrıca değişebilir.

Dosya uzantısı CSV olsa da içerik boşluklarla ayrılmış, sütunları Case olan
bir tablodur. Net itki `F_Net (kN)` alanından N'ye çevrilir; yakıt doğrudan
`Wf_3_4 (kg/sec)` alanından alınır. SFC ayrı yuvarlatıldığı için yeniden yakıt
hesabında kullanılmaz. 392 N model adına göre yeniden ölçekleme yapılmaz.

Case 0 ayrı deniz seviyesi statik referanstır: 400 N, 0.015 kg/s. Cases 1–120,
10 irtifa × 12 Mach noktasıdır. İrtifa başlığı `Altitude (-)` olduğundan kaynak
birimi açık değildir; katalogda metre olarak yorumlandığı kaydedilmiştir.
Bu yorumla aralık −304.8–9144 m ve Mach 0–1.1'dir. `at_conditions` bu tam
ızgarada bilineer interpolasyon yapar; tekil Case 0 referansını interpolasyona
katmaz ve sınırların dışına extrapolasyon yapmaz. Ham referans `at_case(0)`
ile ayrıca kullanılabilir.

Veri kullanıcı talebine göre doğru kabul edilir. Çalışma noktalarının tümünde
yanma çıkış sıcaklığı yaklaşık 1200 K; gaz kolu haritası ve sürekli çalışma
limitleri belirtilmemiştir. Bu yüzden veri kendi başına kısmi gaz tüketimini
veya sürekli tam gaz performansını doğrulamaz. Motor haritasının Mach kapsamı
uçağın o Mach'a ulaşabileceği ya da aerodinamik polarının geçerli olduğu
anlamına gelmez.

### Grafiklerden RPM referans modeli

Verilen üç grafik `rpm_graphs.json` dosyasında ayrı kaynak olarak saklanan
yaklaşık noktalara dönüştürülmüştür. Görsellerin kendisi bu dosyada yer almaz;
elle tahmin edilmiş işaretçi merkezleri, eksen kalibrasyonu, kaynak birimleri
ve okuma belirsizliği notları yer alır. Kayıttaki ondalık hane sayısı ölçüm
hassasiyeti değildir. Ayrıntılı kontrol: [grafik okuma raporu](docs/engine-graph-audit.md).

```python
reference = configuration.reference_rpm_model()
output = reference.at_krpm(71.1)  # bin devir/dakika; normal RPM değil
rpm = reference.krpm_for_thrust(100)  # seçili çarpan dahil gerekli kRPM
checks = reference.tsfc_consistency()
```

RPM eğrileri parça parça doğrusal interpolasyonla kullanılır; polinomla
taşma veya sınır dışı uzatma yapılmaz. Yakıt ve itki farklı RPM noktalarında
okunduğundan her biri kendi ekseninde enterpole edilir. TSFC grafiği bağımsız
kontroldür, yakıtın yerine geçmez. Çarpan aynı RPM'de yalnız itkiyi azaltır;
aynı itki hedeflenirse RPM ve tüketim artabilir. Rölanti altında gereken itki
için sıfır yakıt veya motor kapatma varsayılmaz; aralık dışı hata üretilir.

Bu modelde görüntülerde belirtilmeyen uçuş/atmosfer koşulları varsayılmaz.
Önceki irtifa–Mach haritasıyla otomatik birleştirme yapılmaz. Benzer ~400 N
referans itkilerde grafik ~69 kg/h, önceki CSV 54 kg/h verir; aynı çalışma
koşulu oldukları belirlenmeden hibrit bir kısmi gaz uçuş haritası kurulmaz.

## Ortam ve değişen yakıt yükü

Görev güncellemesi: katapult kalkış, yüksek irtifada paraşütle kurtarma;
seyir hedefi 650 km/h yer hızı, irtifa kabiliyeti hedefi 35000 ft / 10668 m.
Normal yük üst sınırı 11, minimum sabit-kanat uçuş **yer hızı 75 m/s**.
Rüzgârsız tırmanışta yer hızı V*cos(gamma) üzerinden denetlenir. Katapult
çıkış hızı 90 m/s, pitch açısı 10°; pitch uçuş yolu açısına eşit varsayılmaz.
Paraşüt açılma ve sonrası kullanıcı talebiyle kapsam dışı. Güncel ağırlıkla
CLmax ve yük faktörü birlikte denetlenir. Bu sınırlar katapult/paraşüt geçiş
fiziklerinin uygulandığı anlamına gelmez. Motor itki CSV'sinin sabit maksimum
RPM'de üretildiği kaydedildi. [Görev kapsamı ve eksikler](docs/mission-requirements.md).

`FlightConditions` varsayılan 0 m/ISA/rüzgârsızdır. İrtifa ve yerel sıcaklık
seçilebilir; rüzgâr her zaman sıfırdır. İlk atmosfer modeli −500–11000 m
basınç irtifasında ISA basıncı ve seçilen sıcaklıktan kuru hava yoğunluğunu
ve ses hızını hesaplar. Bu girdiler henüz motorun sıcaklık/irtifa düzeltmesini
oluşturmaz.

```python
from flightlab.mission import FlightConditions

conditions = FlightConditions(altitude_m=0, temperature_c=15)
air = conditions.atmosphere()
plan = aircraft.fuel_plan(initial_fuel_kg=6, reserve_fuel_kg=1)
# Mevcut sabit donanımla başlangıç: 20.1 + 6 = 26.1 kg
# Rezerve gelindiğinde: 20.1 + 1 = 21.1 kg
```

`integrate_fuel_until_reserve` her adımda güncel kütleyi yakıt debisi
fonksiyonuna iletir ve son adımı rezervde kısaltır. `level_flight_at_fuel`
güncel ağırlıkla CL, sürükleme ve gerekli gücü yeniden hesaplar; uçak
CLmax/hız sınırları ile poların kendi geçerlilik aralığını ayrı uygular.
Bunlar bir tam görev simülasyonu veya CG/atalet güncellemesi değildir.
Motor sürekli devir sınırı 97 kRPM olarak kayıtlıdır; grafik sınırı ~96.5
kRPM olduğu için üstüne extrapolasyon yapılmaz.

Sonraki Flow5 taraması ve model sınırları:
[analiz talebi](docs/flow5-analysis-request.md).

## Seçili T2 poları

```python
polar = aircraft.aerodynamic_model()
cd = polar.drag_coefficient(0.20361)  # 0.034267, seçili deniz seviyesi kaynak noktası
```

Seçili kaynak son deniz seviyesi ISA T2 dosyasıdır: 0 m, 15 °C,
rho≈1.225 kg/m³. Önceki soğuk/irtifa poları ayrı dosyada korunur. CL aralığı
0.019545–0.75944; kullanıcı talebiyle etkin uçak CLmax=0.75944'tür.
Bu, son yakınsayan noktanın model sınırı olarak seçilmesidir; fiziksel stall
ölçümü değildir. Önceki 0.9 kabulünün yerine geçer.
T2 bir Reynolds/Mach haritası değildir; başka koşullara CL–CD
aktarımı yaklaşık model varsayımıdır. İlk model için ek Type 1 analizi artık
önkoşul değildir. Ayrıntılar: [güncel T2 kontrolü](docs/sea-level-polar-audit.md).

## Sürükleme çarpanı ve Mach güvenilirliği

```python
configuration = catalog.select("m600-thinsurf-acilar", "amt-titan-392n",
                               drag_factor=1.2, thrust_factor=0.8)
polar = configuration.aerodynamic_model()
```

`drag_factor` varsayılan 1.0, sınırları 0.5–3.0. Toplam CD, sürükleme ve
gerekli faydalı güç bu katsayıyla ölçeklenir; gerekli CL değişmez. Kaynak CSV
değiştirilmez ve motor itki çarpanı bağımsızdır. Uçak kaydının
`aircraft.aerodynamic_model()` metodu ölçekli olmayan tabloyu, seçili
`configuration.aerodynamic_model()` ise çarpanı uygulanmış tabloyu verir.
Gelecek arayüz için slider tanımı `data/ui-controls.json` içinde (adım 0.01)
hazırdır; henüz görsel arayüz yoktur.

Kullanıcı kabulüyle Flow5 güvenilirlik eşiği **Mach 0.65**. Tüm 55 nokta
aktif modelde korunur. Yeni kaynak sıcaklığı 15 °C ile hesaplanan kaynak Mach'ı
bu eşiği aşan 1 nokta ve buna dayanan interpolasyonlar güvenilmez uyarısı
taşır. `TabulatedPolar.source_mach` her noktanın Mach'ını,
`warnings_for_cl` kullanılan kaynak noktalarının uyarısını sağlar.
`level_flight_at_fuel` sonucundaki `mach` ve `warnings`, mevcut uçuş Mach'ını
ve hem kaynak hem uçuş güvenilirlik uyarılarını içerir. Mach>0.65 hesaplamayı
durdurmaz; 300 m/s uçak hız limiti ve tablo CL aralığı ayrı korunur.

Sıcaklık girdisinde gerçek sıcaklık ile ISA ofseti birbirinden ayrıdır:

```python
conditions = FlightConditions(altitude_m=7000, temperature_offset_c=-45)
# Gerçek sıcaklık -75.5 °C; rho≈0.723715 kg/m³; a≈281.834 m/s
# Eşdeğeri: FlightConditions(altitude_m=7000, temperature_c=-75.5)
```

Gerçek sıcaklık ve ofset aynı anda verilemez. Kaynak dosyalar değiştirilmez.

## Flow5 T1 toplu analiz dosyaları

**Runtime bildirimi:** Kullanıcının Windows/Flow5 7.57 kurulumunda Alt+F7
batch yolu Calculate anında çöküyor. XML üretim testlerinin geçmesi solver
uyumluluğunu doğrulamaz. Tam matrisi çalıştırmadan normal XML içe aktarma +
tek nokta denemesi ve gerekirse F7 / Batch analysis (1) yolu doğrulanmalıdır.
[Teşhis adımları](docs/flow5-batch-crash.md).

**Güncel yol: açık projede GUI XML batch.** Kullanıcının mevcut profil/polar
veri tabanıyla çalışmak için aşağıdaki komut yeterlidir; geometri veya 2D
veriler yeniden yüklenmez:

```sh
PYTHONPATH=src python3 -m flightlab.batch --gui \
  --template data/analysis-templates/T1-user-template.xml \
  --output outputs/FlightLab-T1-GUI-72
```

Paket `analyses_72/` (72 tanım), `smoke_2/` (iki deneme), `manifest.csv`,
orijinal şablon ve `KULLANIM.txt` içerir. `--include-10700` ile 81 tanım
istenebilir. GUI paketinde yalnız analiz adı, hız, yoğunluk ve kinematik
viskozite değiştirilir. PROJECTED referans modu ve Use_plane_inertia=true
dahil diğer ayarlar korunur; 2D veri dosyası veya proje yükleme scripti gerekmez.

Mevcut Flow5 projesini aç: **Batch analysis (2), Alt+F7**. Bu yol resmi main
kaynakta `xplaneactions.cpp` ve `batchxmldlg.cpp` üzerinden doğrulandı.
Analiz Actions > Change directory ile önce `smoke_2`, sonra `analyses_72`
klasörü seçilir. Uçak ve analizler seçilir. Alfa aralığı batch ekranının
**T12** sekmesinde −4…14°, adım 0.25° olarak ayrıca ayarlanır. Analiz XML'leri
tarama aralığı taşımaz; tek çoklu-polar XML kökü uydurulmaz. Calculate ile
önce iki test analizi gerçek Flow5 sürümünde doğrulanır. Bu ortamda Flow5
çalıştırılmadı; yalnız üretim ve ayar koruma testleri yapıldı.

### Ayrı, bağımsız komut satırı paketi (eski opsiyonel yol)

**Kapsam açıklaması:** Bu bağımsız batch paketi isteğe bağlı bir yardımcıdır;
FlightLab Python hesaplamalarının veya 3D CSV içe aktarımının önkoşulu değildir.
Kullanıcı analizleri kendi Flow5 projesindeki mevcut, hassas 2D polar veri
tabanıyla çalıştırır. FlightLab'e 3D sonuç CSV'leri ve analiz koşulları verilir;
2D koordinat/polar dosyalarının paylaşılması istenmez. Aşağıdaki asset
gereksinimleri yalnız bu ayrı, proje dışı solver çalıştırma yoluna aittir.

Kullanıcının `T1-user-template.xml` analiz tanımından 72 T1 XML ve iki
çalışmalık smoke/tam matris script şablonları üretilebilir:

```sh
PYTHONPATH=src python3 -m flightlab.batch \
  --template data/analysis-templates/T1-user-template.xml \
  --geometry data/aircraft/m600-thinsurf-acilar/geometry.xml \
  --output outputs/flow5-batch-72
```

İsteğe bağlı `--include-10700` ile 81 analiz üretilir. Mevcut çıktı dizinine
üzerine yazılmaz. Kaynak XML/CSV korunur. Hızlar 50:25:250 m/s, irtifalar
0:1500:10500 m, alfa −4:0.25:14 derecedir. ISA yoğunluğu ve Sutherland
viskozitesi kullanılır. TRIUNIFORM, NCrit=8, mevcut viskoz interpolasyon,
kuyruk/flap ayarları, gövde sürüklemesi ve ek sürükleme kaynağı korunur.
Script uyumluluğu için referanslar CUSTOM olarak aynı dışa aktarılmış
değerlere, yükleme ise mevcut açık Inertia bloğuna sabitlenir. Paket orijinal
şablonu da içerir; bu iki uyumluluk ayarı paket README'sinde belirtilir.

**Bu ortamda Flow5 yoktur; solver doğrulaması yapılmamıştır.** XML üretimi,
ayarların korunması, atmosfer, matris ve yerel yol hazırlığı test edilmiştir.
Paketteki `required-assets.json` dört özgün profil .dat dosyasını belirtir.
`XFoil_OnTheFly=false` olduğu için mevcut 2D profil polarları da XFoil metin
formatında gereklidir; benzer adlı profiller veya farklı viskoz yöntemle
yerine konmaz. Bunlar verilmeden paket çalışmaya hazır sayılmaz.

Kullanıcı paketi kendi bilgisayarına açıp profil/polarları yerleştirir,
`python prepare.py` ile yerel yolları oluşturur. Flow5 sürüm/işletim sistemi
uyumluluğu iki analizlik smoke ile denenir; GUI'de aynı tanımla karşılaştırılıp
nonempty sonuçlar ve doğru ayarlar doğrulanınca full script çalıştırılır.
Çıkış kodu sıfır olması tek başına analizlerin başarılı olduğunu göstermez.
