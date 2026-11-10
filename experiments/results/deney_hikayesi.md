# Deneylerin sırası ve sebepleri

Bu belge, Kia Soul üzerinde başlayıp araçlar arası teste kadar uzanan model
çalışmasını baştan sona anlatır: her aşamada hangi soru soruldu, neden, ne
yapıldı, ne çıktı ve bir sonraki adıma neden geçildi. Sayılar gerçek HCRL 2019
verisinden alınmıştır. Ayrıntılar ve tekrar çalıştırma komutları her deneyin
kendi raporundadır; kısa güncel durum için
[oturum belgesinin özeti](oturum_deney_ve_bulgular.md) okunabilir.

## Kısa sonuç

1. Veri temizdir; hat, ham CSV ile satır satır aynı sonucu verir.
2. Görülmemiş saldırı türünü bulmak sınıflandırıcı için yanlış bir sorudur:
   DoS ve Replay'de sonuç 0'dır.
3. Bilinen türlerde skorlar 0,99-1,00'dir; ancak bu test dosyaları eğitim
   kayıtlarının zamanda devamıdır, yani aynı sürüşün sonraki dakikalarıdır.
4. Replay, ID'nin düzenli ritmine bakan özelliklerle büyük ölçüde ayrılır
   (Sonata'da F1 0,877).
5. Shortcut learning vardır: Kia'da eğitilen ID ve içerik kullanan modeller,
   başka bir araçta (Spark) temiz sürüşün %10-20'sine saldırı der. ID'siz ritim
   modeli bu oranı %0,34'e indirir. DoS ise bütün modellerde ID 0 kuralıyla
   yakalanır.

## Aşama 1: Veri ve hazırlık

**Soru:** Veri güvenilir mi, hat doğru çalışıyor mu?

- HCRL 2019 Car-Hacking Challenge: 3 araç (Kia Soul, Hyundai Sonata,
  Chevrolet Spark), 37 CSV, yaklaşık 8,46 milyon CAN mesajı. Her satır bir
  mesajdır: zaman, CAN ID, DLC, en fazla 8 byte ve normal/saldırı etiketi.
- Saldırı türü dosya adından gelir: `Flooding` = DoS, `Fuzzy` = Injection,
  `Malfunction` = Spoofing, `Replay` = Replay. Spark'ta Replay yoktur.
- Normal trafikteki ID sayısı: Kia 45, Sonata 27, Spark 83. Kia ile Sonata 22
  ID paylaşır; Spark diğerleriyle yalnız 3 ID paylaşır.
- 37 dosyanın tamamı bağımsız bir script ile sayıldı: belgelenen bütün sayılar
  doğrulandı, bozuk satır, geriye giden zaman veya dosya kopyası yoktur. 48.164
  DoS mesajının tamamı ID 0'dır.
- İlk çalışma aracı Kia Soul'dur, çünkü dört saldırı türünün hepsi yalnız bu
  araçta vardır: 16 dosya, 4.342.470 mesaj.
- 8 byte'tan kısa mesajların (Kia'da 6 ID) eksik byte'ları -1 ile doldurulur;
  0 gerçek bir byte değeriyle karışırdı.
- Model, saldırı türünü değil, her mesajın normal mi saldırı mı olduğunu
  tahmin eder.

Önceden yapılmış bir decision tree denemesi (üç araç, dosya bazlı beş fold)
ilk shortcut işaretini vermişti: ID ile DoS F1 0,96, ID olmadan 0. ID
çıkarılınca Injection 0,43'ten 0,72'ye, Spoofing 0,82'den 0,94'e çıkıyordu.

## Aşama 2: Görülmemiş saldırı türü

**Soru:** Bir saldırı türü eğitimden tamamen çıkarılırsa model onu bulur mu?

Decision tree (derinlik 6), girdi CAN ID, DLC ve byte'lar. İlk deneme rastgele
seçilen iki kaydı validation olarak kullanıyordu; bu kayıtlarda DoS ve Replay
yoktu ve Injection'ın başka bir kaydı eğitimdeydi. Bu yüzden değerlendirme
hazır `unseen_*` bölmelerine taşındı.

| Eğitimden çıkarılan tür | Yakalanan saldırı | F1 |
|---|---|---:|
| DoS | 0 / 16.072 | 0 |
| Injection | 76.713 / 141.164 | 0,70 |
| Spoofing | 37.447 / 71.980 | 0,68 |
| Replay | 0 / 155.640 | 0 |

Accuracy DoS'ta bile 0,87 görünür; saldırı oranı düşük olduğundan bu veride
yanıltıcıdır. Bu yüzden recall, precision, F1 ve yanlış alarm raporlanır.

Teşhis ([rapor](kia_unseen_diagnosis.md)):
- DoS: eğitimde ID 0 yalnız 14 satırda vardır; tamamı sıfır olan byte'lar
  normal trafikte yaygındır.
- Replay: test saldırı mesajlarının %80'i eğitimdeki bir normal mesajın birebir
  kopyasıdır. İçerikle ayrım mümkün değildir.

## Aşama 3: Model ve özellik denemeleri

**Soru:** Daha güçlü model veya zamanlama bilgisi sonucu değiştirir mi?

- Kayıt bazlı iç validation kuruldu; her fold iki sınıfı da içerir. Ayarlar
  yalnız bu validation'da seçildi (derinlik 3 veya 6). Dışarıda tutulan tür bu
  validation'da da yoktur.
- XGBoost (100 ağaç) decision tree ile aynı sonucu verdi: DoS 0, Replay 0,
  Injection 0,53, Spoofing 0,69 ([rapor](kia_xgboost_baseline.md)). Sorun
  model değil, sorudur.
- Zamanlama eklendi (`iat_id`: aynı ID'nin önceki mesajından geçen süre;
  `iat_bus`: hattaki önceki mesajdan geçen süre)
  ([rapor](kia_xgboost_timing.md)):

| Tür | Zamanlamasız F1 | Zamanlamalı F1 |
|---|---:|---:|
| DoS | 0 | 0,957 |
| Injection | 0,533 | 0,287 |
| Spoofing | 0,692 | 0,508 |
| Replay | 0 | 0 |

  Zamanlama bir türe yarar, diğerine zarar verir; her yerde üstün tek bir
  özellik yoktur ([ablation](kia_validation_ablation.md)).
- Bilinen tür, başka kayıt: aynı türün diğer kaydı eğitimdeyken bir kayıt
  tamamen ayrıldı ([rapor](kia_known_attack.md)). Injection 0,97 / 1,00 ile
  kayıtlar arasında taşınır; Spoofing 0,67 / 0,64 / 0 ile kayda göre çok
  değişir.
- CatBoost ile karşılaştırmada sıralama kayda göre değişti; genel bir kazanan
  yoktur. 130 saldırılı Spoofing kaydında hiçbir model saldırı yakalamadı;
  bunların 63'ü normal bir mesajla birebir aynıdır
  ([teşhis](kia_spoofing_diagnosis.md)).

## Aşama 4: Sorunun yeniden tanımı

**Soru:** Skorlar yöntemden mi, parametreden mi düşük?

- Üç model ve iki derinlik aynı biçimde başarısız oluyor; aynı modeller
  saldırı türünü daha önce gördüğünde 0,97-1,00 alıyor. Neden yöntemdir.
- Aynı kaydın ilk %60'ında eğitip son %40'ında test edince F1 1,000 çıkar:
  hat sağlamdır, model gördüğü saldırıyı öğrenir.
- Replay'de 8 ms altındaki aralıklarda mesajların yarısı normal, yarısı
  saldırıdır: araya giren kopya, arkasındaki gerçek mesajın aralığını da
  kısaltır.
- Injection aslında iki farklı saldırıdır: final kayıtta aracın kendi 45 ID'si,
  preliminary kayıtta 2.048 rastgele ID kullanılır.
- Görülmemiş türü bulmak bir anomaly detection sorusudur; elimizdeki model ise
  sınıflandırıcıdır. Bu veri seti kendi sorusuyla, yani bilinen türlerin yeni
  dosyalarda bulunmasıyla değerlendirilmeye karar verildi. Anomaly detection
  için Kia'nın temiz sürüşü yaklaşık 5 dakikadır.
- Normal satırların 1/5'e örneklenmesi denendi; validation'da yanlış alarmı
  47.845'ten 94.172'ye çıkardığı için kullanılmadı.

## Aşama 5: Release testi

**Soru:** Bilinen saldırı türleri, eğitimde kullanılmamış dosyalarda bulunur mu?

Model 9 Kia eğitim kaydıyla eğitildi; ayarlar validation'da donduruldu ve 7
release dosyası bir kez ölçüldü ([rapor](kia_release_test.md)). Varyantlar
kısayol sorusunu ölçmek için seçildi: A (ID + byte), B (ID'siz), C (A +
`iat_id`), D (B + `iat_id`), F (bus yükü dahil hepsi).

| Tür | A | B | C | F |
|---|---:|---:|---:|---:|
| DoS | 1,000 | 0,000 | 1,000 | 0,980 |
| Injection | 0,99 | 0,98 | 0,99-1,00 | 0,98-1,00 |
| Spoofing | 1,00 | 0,98-1,00 | 1,00 | 1,00 |
| Replay | 0,006 | 0 | 0,445 | 0,912 |

Değerler dondurulmuş eşikteki F1'dir; iki dosyalı türlerde iki dosyanın aralığı
verilmiştir. 170 saldırılı Spoofing dosyasında A-D 0 aldı.

- DoS bir ID 0 kuralıdır: ID çıkarılınca 1'den 0'a düşer.
- F'nin Replay sonucu bus yükünden gelir ve saniyede 73 yanlış alarm üretir;
  bu özellik mesajı değil kaydı anlatır.
- ID'yi gizlemek yetmez: normal mesajların %97,1'inde ID, byte'lardan
  bellidir.

**Sonradan bulunan sınır:** Her release dosyası bir eğitim kaydının zamanda
doğrudan devamıdır (aradaki boşluk 0,2-0,6 ms). Bu yüzden 0,99-1,00 "aynı
sürüşün sonraki dakikaları" demektir. Başka kayıtlar arası skorlar daha
düşüktür (Aşama 3).

## Aşama 6: Replay ve ritim

**Soru:** Tek mesaja bakarak ayrılamayan Replay, mesaj akışında ayrılır mı?

- Saldırı 10 saniye açık, 10 saniye kapalı gelir; bütün ID'lere saldırılır ve
  her ID'nin akışına yaklaşık 1,33 periyotta bir eski bir kopya girer.
- Gerçek mesajlar sabit ritimde gelir; kopya ritmin dışına düşer. Bir mesajın
  aynı ID'nin iki önceki mesajına uzaklığı, gerçek mesajda tam bir periyot,
  kopyada küsurlu bir değerdir.
- Özellikler araçtan bağımsızdır: ID ve byte kullanılmaz; süreler ID'nin aynı
  aracın temiz sürüşünden ölçülen periyoduna bölünür.
- Ayarlar Kia'da seçildi, Hyundai Sonata'da bir kez test edildi
  ([rapor](replay_rhythm_test.md)):

| Model | Sonata Replay F1 | Temiz Sonata sürüşünde yanlış alarm/sn |
|---|---:|---:|
| Önceki mesaja süre ve sayım | 0,620 | 57,7 |
| + ritim | 0,863 | 0,8 |
| + içerik değişimi | 0,877 | 0,3 |

Sınırlar: Sonata replay dosyası özellikler tasarlanmadan önce etiketleriyle
incelenmişti, bu yüzden test yarı görülmüştür. Saldırı anlarında yanlış alarm
saniyede 221'dir.

## Aşama 7: Shortcut learning, araçlar arası test

**Soru:** Modeller saldırıyı mı öğreniyor, yoksa Kia'ya özgü bir ipucunu mu?

Bir kısayol, işe yaramadığı yerde görünür. Spark Kia ile yalnız 3 ID paylaştığı
için Kia'dan ezberlenen ID ve içerik Spark'ta işe yaramaz. Dört model Kia'da
eğitildi, dört hipotez testten önce yazıldı ve Spark ile Sonata bir kez ölçüldü.
DoS için ayrıca saldırı mesajlarının ID'si 0'dan normal bir ID'ye çevrildi
([rapor](shortcut_transfer_test.md)).

| Model | Temiz Spark sürüşünde saldırı denen mesaj | Spark Injection F1 | Spark Spoofing F1 | ID değişince DoS recall |
|---|---:|---:|---:|---:|
| A: ID + byte | %20,2 | 0,417 | 0,585 | 0,000 |
| B: byte | %15,1 | 0,468 | 0,670 | 0,000 |
| C: A + zamanlama | %9,7 | 0,498 | 0,629 | 0,035 |
| T: ID'siz ritim | %0,34 | 0,980 | 0,824 | 0,138 |

- ID ve içerik kullanan modeller Kia'nın normal trafiğini ezberler; başka
  araçta tanımadıkları içeriğe saldırı der. Kısayol, kaçırılan saldırı olarak
  değil, yanlış alarm olarak ortaya çıkar.
- ID'siz ritim modeli Injection ve Spoofing'de başka araca taşınır.
- DoS bütün modellerde ID 0'a dayanır; ritim modeli de ID 0'ı "bilinmeyen ID"
  olarak tanır. Eğitimde normal bir ID ile yapılmış taşma örneği yoktur.
- Hipotezlerden ikisi doğrulandı (ID'siz içerik modeli daha az düşer; ritim
  modeli ID'li modeli geçer). F1 düşüşüne dayanan hipotez, etki yanlış alarm
  olarak çıktığı için doğrulanmadı; ritim modelinin ID değişikliğine dayanacağı
  hipotezi de doğrulanmadı.

## Aşama 8: DoS kısayolunu gidermek

**Soru:** DoS, ID 0'a bakmadan yakalanabilir mi?

Eğitimde normal bir ID ile yapılmış taşma örneği olmadığı için en basit çözüm
denendi: Kia DoS kaydının, saldırı mesajlarına normal bir ID verilmiş bir
kopyası eğitime eklendi. Model, ayar ve test dosyaları önceki deneyle aynıdır;
bu yüzden sonuç aynı dosyalara ikinci bakıştır ([rapor](dos_id_swap_training.md)).

| Model | ID'si değiştirilmiş DoS recall, Spark | Sonata | Temiz Spark sürüşünde saldırı denen mesaj |
|---|---:|---:|---:|
| A: ID + byte | 0 → 0 | 0 → 0 | %20,2 → %25,2 |
| C: A + zamanlama | 0,035 → 0,111 | 0,020 → 0,020 | %9,7 → %8,4 |
| T: ID'siz ritim | **0,138 → 1,000** | **0,126 → 1,000** | %0,34 → %0,31 |

Ritim modeli taşmayı artık zamanlamasından tanır; ID ve içerik kullanan
modellerin girdilerinde taşma hızını anlatan bir bilgi olmadığı için onlar
bundan faydalanmaz.

## Yöntemde yapılan düzeltmeler

| İlk durum | Düzeltme | Etkisi |
|---|---|---|
| Rastgele iki kayıtla validation | Hazır `unseen_*` bölmeleri | Görülmemiş tür gerçekten ölçüldü |
| Ayar test verisine bakarak seçilecekti | Ayarlar yalnız validation'da seçildi | Test kirlenmedi |
| İç fold'larda bazı türlerin tamamı validation'daydı | Validation'daki türler eğitimde de bulunacak şekilde yeniden kuruldu | Seçim bilinen türler üzerinden yapıldı |
| Release dosyaları yeni kayıt sanıldı | Eğitim kayıtlarının devamı olduğu gösterildi | Release skorları "aynı sürüş" olarak okundu |
| Sonata replay testi temiz sanıldı | Önceden incelendiği belirtildi | "Yarı görülmüş test" olarak raporlandı |
| Hipotezler sonradan yorumlanabilirdi | Son testte hipotezler testten önce yazıldı | Doğrulanmayan hipotezler olduğu gibi raporlandı |

## Veri kullanımı ve modeller

- 37 dosyanın 29'u kullanıldı: Kia'nın 16 dosyası, Sonata ve Spark'ın 13
  eğitim kaydı. Kullanılmayan 8 dosya Sonata ve Spark'ın release dosyalarıdır;
  bunlar da eğitim kayıtlarının devamı olduğundan temiz test sayılmaz.
- Denenen modeller: decision tree, XGBoost, CatBoost. Model türü sonuçları
  özellik seçiminden çok daha az etkiledi.
- Denenmeyenler: Random Forest, SVM, sinir ağları ve RNN, anomaly detection.

## Açık konular

- DoS'un ID'den bağımsız yakalanmasını sentetik olmayan bir saldırıyla
  doğrulamak (yalnız ritim modelinde, sentetik ID değişikliğiyle gösterildi).
- Ritim modelinin olasılıklarının kalibrasyonu (dondurulmuş eşik 0,028).
- Değerlendirme ölçütü (F1 veya recall ağırlıklı F) ve mesaj ya da pencere
  bazlı değerlendirme.
- Hiç kullanılmamış bir test için ikinci bir veri seti (CAN-MIRGU, ROAD).
