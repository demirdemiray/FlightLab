# Seçili deniz seviyesi ISA poları

Kaynak: kullanıcının son T2-TriUniform-ThinSurf.csv yüklemesi. Önceki aynı
adlı soğuk/irtifa analizi üzerine yazılmadı; ayrı `polars/sea-level-isa`
dizininde tutulur ve uçak kataloğunda seçili kaynak olarak işaretlenir.

- Kullanıcının bildirdiği ortam: 0 m, ISA 15 °C.
- Katsayı/kuvvet kontrolü: rho≈1.225 kg/m³ ile geometrik 0.3208322 m² alan
  dosyadaki kuvvetlerle uyuşur. Viskozite ayarı CSV'de yoktur; nominal ISA
  kinematik viskozitesi metadata'da varsayım olarak açıkça kaydedilir.
- 55 nokta, alpha −1.25…12.25°, CL 0.019545…0.75944.
- CD 0.016773…0.30829; hız 45.936…286.34 m/s; kütle 32.1 kg.
- Tüm noktalar korunur; kaynak Mach>0.65 olan 1 nokta uyarı taşır.
- En yüksek tablosal L/D≈5.942, alpha=2°, CL=0.20361,
  CD=0.034267, kaynak hızı 88.714 m/s. Bu, tek başına menzil/endurance optimumu değildir.

Kullanıcı talebiyle etkin model CLmax değeri son yakınsayan noktanın
CL=0.75944 değeridir; önceki 0.9 kabulünün yerine geçer. Yakınsamanın daha
sonra sağlanmadığı kullanıcı tarafından bildirilmiştir; loglar verilmemiştir.
Sayısal yakınsamama fiziksel stall kanıtı sayılmaz, ancak bu modelde açıkça
seçilmiş bir uçuş zarfı sınırıdır. CL veya sürükleme bu sınırın ötesine uzatılmaz.

32.1 kg, ISA deniz seviyesi ve bu CLmax ile düz uçuş minimum hız tahmini
yaklaşık 45.93 m/s'dir. Bu yalnız modelden türeyen lift-limit hızıdır;
uçuş testinden ölçülmüş stall hızı veya operasyonel emniyet hızı değildir.
Yakıt azaldıkça aynı hesap güncel ağırlıkla yeniden yapılır.

Sabit elevator ve ek trim sürüklemesinin ihmal edilmesi kabulü sürer.
Ham CL/CD/Cm ve bütün satırlar korunur. Önceki kaynak için
[soğuk/irtifa polar kontrolü](t2-polar-audit.md) geçerlidir.
