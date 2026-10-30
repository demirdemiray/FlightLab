# T2 polar kontrolü

Bu belge korunan eski soğuk/irtifa analizine aittir. Güncel seçili kaynak
[deniz seviyesi ISA polarıdır](sea-level-polar-audit.md); etkin CLmax artık
kullanıcı talebiyle 0.75944'tür. Aşağıdaki eski 0.9 ifadesi tarihsel kabuldür.

Kullanıcı dosyası: T2-TriUniform-ThinSurf.csv. Uçak adı mevcut geometriyle aynı.
55 nokta, alpha −1.25…12.25° (0.25° adım), CL 0.019545…0.75944,
CD 0.016768…0.30637, hız 59.763…372.53 m/s. Kütle 32.1 kg;
kaldırma tüm noktalarda yaklaşık 314.9 N. Değişken hız/sabit kaldırma
verisi ilk CL–CD referans modeli için yeterli bir veri paketidir; ilk aşamada
ilave Type 1 taraması şart değildir.

Ekran görüntüsünden yoğunluk 0.723714 kg/m³, kinematik viskozite
1.8048e-5 m²/s olarak saklanır. Son hesaplayıcı görüntüsüyle koşul açıklığa
kavuştu: 7000 m, ISA sıcaklık ofseti −45 °C, gerçek sıcaklık −75.5 °C.
Bu koşulda basınç 41060.717 Pa, yoğunluk 0.7237154 kg/m³ ve ses hızı
281.834 m/s'dir; kaynak yoğunluğuyla uyuşur. Önceki −30 °C yorumu geçersizdir.
Hesaplayıcının dinamik viskozitesi 1.32270e-5 Pa·s ve yoğunluğu, yaklaşık
1.82765e-5 m²/s kinematik viskozite verir; Flow5 ekranındaki değerden yaklaşık
%1.27 farklıdır. İki kaynak ayrı korunur; Flow5 viskozitesi değiştirilmez.

Kaynak yoğunluğuyla S = Lift / (0.5*rho*V²*CL) tüm noktalarda yaklaşık
0.320805…0.320856 m²; geometrik kanat alanı 0.3208322 m² ile yuvarlama
duyarlılığında uyuşur. CD_viscous + CD_induced, toplam CD ile yuvarlama
duyarlılığında uyuşur. Ham CD aynen kullanılır; ek trim sürüklemesi yoktur.

Örnek: alpha=2°, CL=0.20361, CD=0.034191, L/D=5.9552,
hız=115.42 m/s. Bu nokta dosyada en yüksek L/D'ye sahiptir; doğrudan
en iyi cruise, en uzun menzil veya endurance sonucu diye sunulmaz.

## Modelde kullanım

Uçağın seçili performans poları artık T2'dir. `aircraft.aerodynamic_model()`
parça parça doğrusal CL→CD tablosu döndürür. Tüm 55 nokta hem ham dosyada hem
aktif tabloda korunur; CL aralığı 0.019545…0.75944'tür. −75.5 °C kaynak
sıcaklığıyla 5 nokta Mach 0.65 üstündedir; bu noktalar silinmez, güvenilmez
olarak işaretlenir. İnterpolasyon bu noktalardan birini kullanırsa uyarı taşınır.
Noktalarda kaynak CD tam korunur;
CL aralık dışındaysa hata verilir. Tek noktalı T7 stabilite dosyası arşivlenir.
`polar_metadata_file` yoğunluk/viskoziteyi ve kaynak koşullarını belirtir;
salt CL→CD nesnesi bir atmosfer veya Reynolds düzeltmesi yapmaz.

T2'de CL, hız, Reynolds ve Mach birlikte değişir. Aynı CL'yi farklı kütle,
yoğunluk veya sıcaklıkta kullanmak, CD'nin bu değişimlerden bağımsız kabul
edildiği bir referans yaklaşımıdır. Bunun doğruluğu bu dosyayla tek başına
doğrulanamaz. Deniz seviyesi çıktıları bu aktarım varsayımını belirtmelidir.

CLmax uçak limiti 0.9 olsa da tabloda 0.75944 üstü sürükleme yoktur;
bu boşluk doldurulmaz. Kaynakta 300 m/s'yi aşan hızlar bulunması uçak hız
limitini değiştirmez. Mach 0.65 bir güvenilirlik eşiğidir, hesap kesme sınırı
değildir. Mevcut uçuş Mach'ı veya kullanılan kaynak noktası bu eşiği aşarsa
sonuç hesaplanır ama güvenilmez uyarısı taşır. Sert TAS limiti 300 m/s'dir;
tablonun CL kapsamı ayrıca geçerlidir. Veri dışında CL extrapolasyonu yapılmaz.

Gamma/Vz gibi türetilmiş kaynak sütunları gerçek tırmanış veya iniş görevi
olarak kullanılmaz. Kaynak Lift ve Drag kontrolleriyle katsayılar doğrulanır;
itki/enerji dengesi görev çözümünde ayrıca kurulmalıdır.
