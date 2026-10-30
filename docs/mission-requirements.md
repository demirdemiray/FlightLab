# Görev gereksinimleri

Kullanıcı beyanları uçak kataloğunda `mission_requirements` ve `limits`
alanlarına bağlıdır; bunlar hesapla doğrulanmış performans sonuçları değildir.

| Parametre | Değer / durum |
|---|---|
| Kalkış | Katapult |
| Kurtarma | Havada, yüksek irtifada paraşüt açılması |
| Seyir yer hızı hedefi | 650 km/h = 180.55556 m/s |
| İrtifa kabiliyet hedefi | 35000 ft = 10668 m |
| Minimum sabit kanat uçuş yer hızı | 75 m/s yatay groundspeed, kullanıcı doğruladı |
| Normal yük faktörü üst sınırı | 11, n=L/(m*g) olarak modelleniyor |
| Önceki maksimum TAS sınırı | 300 m/s korunuyor |
| Etkin CLmax | 0.75944, kullanıcı seçimi |
| Rüzgâr | Her zaman sıfır |
| Motor CSV rejimi | Kullanıcı doğruladı: sabit maksimum RPM'de irtifa/Mach itki haritası |

Rüzgârsız düz seyirde yer hızı=TAS. Tırmanışta yatay yer hızı V*cos(gamma)
olur; yer hızı hedefi her uçuş fazında doğrudan TAS yerine konmaz.
35kft ISA sıcaklığı −54.342 °C, 650 km/h seyir Mach'ı yaklaşık 0.60888.

11g yük faktörü, sabit bir izin verilen dikey ivme veya her durumda erişilen
manevra değildir. CLmax ve mevcut dinamik basınç ayrıca uygulanır; gereken
CL = n*m*g/(q*S). Katapult boyuna ivmesi ve paraşüt açılma yükü ayrı fizik
modelleridir; mevcut normal yük kontrolü bunları doğrulamaz. Negatif yük zarfı
belirtilmediğinden ilk pozitif-yük modeli negatif n kabul etmez.

75 m/s operasyonel minimumu yatay yer hızıdır ve sabit kanat uçuş fazına
aittir. Rüzgârsız modelde GS=V*cos(gamma); tırmanışta 75 m/s TAS ile
karıştırılmaz. Katapult rayında başlangıçtan veya paraşüt altında bu hızı
zorunlu tutmayız. Aerodinamik kaldırma
sınırı daha yüksek bir minimum doğurabilir: 32.1 kg, 35kft ISA ve mevcut
CLmax ile yaklaşık 82.5 m/s. Bu bir model hesabıdır, ölçülmüş stall hızı değildir.

## Henüz belirtilmeyen sınır koşulları

- Katapult çıkış hızı 90 m/s ve burun açısı (pitch) 10° olarak verildi.
  Bu 90 m/s çıkış hızının yönünü gamma=10° diye varsaymayız. Pitch=gamma+alpha;
  uçuş yolu açısı/rail yönü ve kalkış irtifası ayrıca belirlenmelidir.
- Gerekiyorsa katapult ivme/strok/zaman profili; ilk görev modeli ray çıkışında başlayabilir.
- Görev sonu hava durumu için irtifa/hız kısıtları gerektiğinde kullanıcı belirler.
  Paraşüt açılma fiziği ve paraşüt sonrası hareket kapsam dışıdır; kullanıcıda
  ayrı modeli vardır. Paraşüt alanı, açılma süresi ve iniş verisi istenmez.
- Örnek görev mesafesi, başlangıç yakıtı, rezerv ve A/B konumları.

İlk noktasal kütle optimizasyonu katapult çıkışında başlar ve paraşüt
açılmasından hemen önce tanımlı son uçuş durumunda biter. Paraşüt açılması
ve sonrası simüle edilmez (`model_parachute=false`). Katapult ray dinamiği de
veri olmadan hesaplanmış sayılmaz.
Görev ve motor modelleri henüz bu gereksinimlerle tamamlanmış değildir.

## Mevcut veri kapsamının hedefle ilişkisi

72 T1 matrisi 10500 m'de biter; 10668 m hedefi bunun 168 m üzerindedir.
Hedefi veri içi interpolasyonla değerlendirmek için ileride 10700 m satırı
eklenebilir. Kaynak motor CSV'sinin irtifa ekseni metre yorumu altında
9144 m'de biter; üst irtifada motor davranışı henüz veriden belirlenmiş değildir.
Maksimum RPM haritasını, grafiklerden gelen daha düşük RPM yakıt/itki
eğrileriyle bağlamak da bağımsız çalışma noktası eşleme varsayımı gerektirir.
35kft'ye erişim ve orada sürekli uçuş kabiliyeti mevcut bilgilerle doğrulanmaz.
