# Python çekirdeği: çalışan yetenekler ve sınırlar

## Kurulum ve çalışma

Python 3.11+, NumPy 2.x, SciPy 1.14+ / 1.x. `pip install -e .` ile `flightlab`
komutu kurulur. Bulut ortamında `.venv` mevcut kurulu NumPy/SciPy kullanılarak
hazırlandı; editable paket ve CLI bu ortamda çalıştırıldı. Yeni makinede
standart venv + pip kurulumu kullanılabilir. Çalışma dizini depo köküdür.

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/flightlab --help
```

Windows karşılıkları `.venv\Scripts\python.exe` ve
`.venv\Scripts\flightlab.exe` olur. Gerçek 72 sonuç henüz alınmadı; testler
ve örnek çıktılar bunun yerine uçuş doğrulaması sayılmaz.

## Veri alımı

```sh
flightlab inspect results.zip \
  --manifest data/analysis-manifests/T1-72-manifest.csv \
  --plane 'M-600-ThinSurf-acılar' \
  --fit-check --reference-template data/analysis-templates/T1-user-template.xml \
  --report outputs/polar-audit.json
```

`results.zip` gerçek analizler geldiğinde kullanılacak girdidir. Aynı komut
ZIP yerine sonuç klasörüyle çalışır. Tek manifest ZIP içindeyse `--manifest`
gerekmez. Kullanıcının gönderdiği manifest depoda ayrıca korunmuştur.

Eşleştirme dosya adına güvenmek yerine CSV'nin analiz adıyla yapılır. Uçak
adı istenirse doğrulanır, yanlış hız, yinelenen analiz, bozuk CSV, eksik
polar ve alfa noktaları raporlanır. Eksik sonuçlar log gerektirmeden veri
üzerinden saptanır. Rapor `--strict` modunda eksik/kullanılamaz polar için
başarısız çıkış kodu üretir. Kaynak dosyalar değiştirilmez; ZIP çıkarılmaz.

Tanımsız yardımcı oranlar (negatif CL'de `1/sqrt(CL)` gibi) veri satırının
atılmasına yol açmaz. Temel CL, CD, Cm, alpha, kontrol ve hız sonlu olmalıdır.
Yanlış/hatalı girdiler raporlanır ve fit dışında kalır; orijinal dosya korunur.
Mach>0.65 girdileri fit içinde kalır ve uyarı taşır.

## Aerodinamik interpolasyon

`PolarFamily` girdileri CL, log(Re), Mach; çıktıları toplam CD, Cm ve alpha.
Reynolds sayısı, gerçek sıcaklıktan Sutherland viskozitesiyle hesaplanır.
Referans alanı ve MAC kullanıcının analiz XML'inden açık birim çarpanlarıyla
alınır; .dat veya 2D polar dosyaları gerekmez.

Üç eksen aralıklarıyla ölçeklenip Delaunay üçgenlemesi/tetrahedron ağı kurulur;
çıktı barycentrik parça parça doğrusaldır. CD'ye ayrıca 0.5–3.0 çarpanı
uygulanır. Katsayıların pozitif ağırlıklı kombinasyonu yüksek dereceli
polinom taşmasına yol açmaz. Aynı CL/Re/Mach'ta farklı sonuç veren örnekler
sessizce ortalanmaz; farklı stall dalı/kontrol durumu araştırılmalıdır.
Tam aynı tekrarlar yalnız matematik ağı için birleştirilir, kaynakta korunur.

`AeroCoefficients.contributors` analiz adı, orijinal nokta indeksi ve ağırlığı
taşır. Mevcut sorgu veya kullanılan kaynak Mach>0.65 ise sonuç uyarı taşır.
Eksik aile ve alfa kapsamı da belirtilir. Uyarı bir kesme sınırı değildir.

Varsayılan, veri hacminin (convex hull) dışına çıkınca hata vermektir; ayrı
min/max aralıklarda bulunmak her kombinasyonun kapsandığı anlamına gelmez.
`evaluate(..., extrapolation='nearest')` yalnız açıkça istenirse en yakın
örneği verir ve tahmini güvenilmez olarak işaretler. Standart uçuş API'si
ve hız araması bu fallback'i otomatik kullanmaz.

```sh
flightlab query results.zip \
  --reference-template data/analysis-templates/T1-user-template.xml \
  --cl 0.2 --speed 150 --altitude 3000 --drag-factor 1.2 \
  --report outputs/query.json
```

Sorgunun gerçekten kapsanıp kapsanmadığı sonuçlar geldiğinde belirlenir.
Gerçek sonuçlarda aynı fiziksel ayarların korunduğu da kontrol edilmelidir;
CSV tek başına tüm solver/transition ayarlarını kodlamaz.

## Düz uçuş ve hız araması

`level_point` güncel kütleden CL, CD, alpha, sürükleme, gerekli itki, RPM,
yakıt debisi ve anlık özgül menzil (m/kg) hesaplar. Rüzgâr sıfırdır; düz
uçuşta GS=TAS. İtki uçuş hızına paralel varsayılır, ayrı trim drag yoktur.

`search_level_speed` üç hedefi destekler:

- `maximum_speed`: mevcut model ve veri kapsamındaki hız üst adayı.
- `minimum_fuel_flow`: sabit ağırlıkta en az yakıt debisi adayı.
- `maximum_specific_range`: sabit ağırlıkta en yüksek V/fuel_flow adayı.

Önce örneklenmiş uygulanabilir aralıklar bulunur, sınırlar ve yerel minimumlar
sayısal olarak iyileştirilir. Bu, global optimum kanıtı değildir. Hız sonucu
itki yerine arama veya veri sınırına takılmışsa `limiting_condition` bunu
belirtir; bu durum gerçek maksimum hız diye sunulmaz. Tek anlık nokta
görev menzili/endurance sonucu değildir. RPM rölanti altına indirilmez ve
kendiliğinden motor kapatma modeli eklenmez.

Mevcut gerçek T2 + RPM grafiğiyle yalnız **deneysel referans önizlemesi**:

```sh
flightlab preview --fuel 12 --reserve 2 --report outputs/reference-preview.json
```

Buradaki rezerv örnek girdidir, kullanıcı için zorunlu/önerilen rezerv değildir.
JSON açıkça deneysel olarak sınıflanır. Referans T2'nin Reynolds/Mach aktarımı
ve motorun irtifa/Mach düzeltmelerinin eksikliği tüm sonuçlarda belirtilir.
Grafik yakıtı esas alınır; CSV yakıtı veya gizli itki eşlemesi kullanılmaz.

## Uçuş integratörü

`trajectory.simulate` durumu `(t, x, h, V, gamma, fuel)`; kontrolü süreli
`ControlSegment(duration_s, krpm, load_factor)` dizisidir. `n=L/(m*g)`:

    dx/dt = V*cos(gamma)
    dh/dt = V*sin(gamma)
    dV/dt = (T-D)/m - g*sin(gamma)
    dgamma/dt = g*(n-cos(gamma))/V
    dfuel/dt = -fuel_flow

RK4'ün her alt aşamasında m=yakıt dışı kütle+kalan yakıt, atmosfer, gereken
CL, CD, itki ve tüketim yeniden hesaplanır. Varsayılan zaman adımı 0.5 s;
kapsam sınırına yaklaşan deneme adımları küçültülür. Motorun beyan ettiği
global yakıt debisi üst sınırı, RK aşamalarının rezervin altına atlamasını
engeller; yanlış üst sınır hata sayılır. Son yakıtta 1e-8 kg tolerans vardır.
Hedef yatay mesafe geçişi son zaman adımında bisection ile bulunur.

75 m/s yatay GS alt sınırı, 300 m/s TAS üst sınırı, 11 normal yük sınırı ve
CLmax birlikte uygulanır. Stall limiti, negatif yük veya veri kapsamı ihlali
`model_or_envelope_failure` olarak döner; başarılı varış diye sayılmaz.
Rezerv, mesafe hedefi ve kontrol dizisinin tamamlanması ayrı bitişlerdir.

Bu bir pitch/trim veya 6-DOF çözümü değildir. Alpha ve Cm aerodinamik modelde
mevcuttur; θ=gamma+alpha tanısı kurulabilir ama tutum dinamiği çözülmez.
90 m/s katapult çıkış hızı ve 10° pitch kayıttadır; gamma'yı otomatik 10°
almıyoruz. Başlangıç gamma/alpha eşlemesi ve hedef son uçuş durumu sonraki
A→B optimizasyonunda ayrıca kurulmalıdır. Katapult ray dinamiği, paraşüt
açılması ve paraşüt sonrası hareket hesaplanmaz.

## Doğrulananlar ve kalan işler

Testler: gerçek CSV biçimi ve birimler; ZIP/manifest eşleşmesi; tüm örneklerde
ve bağımsız iç noktalarda analitik affine CL/log(Re)/Mach fonksiyonu;
uyarılar ve kapsam dışı sorgular; sürükleme/itki çarpanlarının bağımsızlığı;
analitik parabolik polarda hız optimumları; değişen kütlede analitik hızlanma;
balistik hareket/enerji korunumu; rezerv ve mesafe olayları.

Gerçek 72 sonuçla fit, ara nokta/holdout doğrulaması, maksimum RPM itki
haritasının kısmi RPM ve grafik yakıtıyla eşlemesi, tam minimum süre/yakıt
A→B optimizasyonu ve gerçek uçuş doğrulaması henüz tamamlanmamıştır.
Mevcut motor haritası 9144 m'ye, analiz matrisi 10500 m'ye kadar; 10668 m
kabiliyet hedefi bu bilgilerle doğrulanmış sayılmaz.
