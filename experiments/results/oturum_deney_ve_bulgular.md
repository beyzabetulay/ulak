# ULAK — Oturumda yapılan çalışmalar ve bulgular

Bu belge, Kia Soul üzerinde yapılan deneyleri ve bu oturumda incelenen konuları
bir araya getirir. Modellerin sonuçları yerel HCRL 2019 Challenge kayıtlarından
alınmış **gerçek veri gözlemleridir**. Yazılım kontrol testleri ise yapay küçük
örnekler kullanır; bu testlerin geçmesi modelin gerçek saldırıları yakaladığını
göstermez. Sonuçların ayrıntıları ve tekrar çalıştırma komutları, bağlantı verilen
ayrı raporlarda bulunur.

## Kısa özet: ne öğrendik

Bölümler zaman sırasıyla yazıldı ve eski bölümlerdeki bazı sonuçlar sonraki
bölümlerde düzeltildi. Güncel durum bu özettir; ayrıntı için §15a ve §15b,
terimler için §2. §15 ve öncesi, o anki bilgiyle yazılmış geçmiş kayıttır.
Bütün çalışmanın aşama aşama, sebepleriyle anlatımı:
[deneylerin sırası ve sebepleri](deney_hikayesi.md).

1. **`unseen_*` sonuçlarındaki %0'lar hata değil.** Sınıflandırıcıya hiç
   görmediği saldırı türü soruldu; hat doğru çalışıyor
   ([teşhis](kia_unseen_diagnosis.md), §15a).
2. **DoS'u yakalayan şey ID kısayolu.** ID çıkarılınca DoS recall 1,000'den
   0,000'a düşüyor; ID'siz modele `iat_id` eklenince 0,977'ye çıkıyor
   ([release testi](kia_release_test.md)).
3. **ID'yi gizlemek yetmiyor.** Normal mesajların %97,1'inde (DLC, byte'lar)
   ID'yi belli ediyor; `id_masked` "ID açıkça verilmedi" demek.
4. **`bus_count_100ms` kayıt kısayolu.** Replay'i %92 yakalıyor ama saldırı
   kaydındaki normal mesajları da işaretliyor (saniyede 73 yanlış alarm).
5. **Release dosyaları yeni kayıt değil.** Her biri bir eğitim kaydının
   zamanda devamı; release'teki 0,99-1,00 "aynı sürüşün sonraki dakikaları"
   demek. Başka kayıtta skorlar daha düşük ve türe göre çok değişiyor
   (aşağıdaki tablo; iç fold'larda tüm türler birlikte F1 0,375-0,859).
6. **Replay'i ritim çözüyor.** Kopya, ID'nin düzenli ritminin dışına düşüyor.
   Sonata'da sadece aralık ve sayımla F1 0,620, iki/üç önceki mesaja olan süre
   eklenince 0,877. Kia release replay dosyasında release testindeki 0,445'ten
   0,903'e. Sonata dosyasına tasarımdan önce bakıldığı için yarı görülmüş test;
   saldırı anlarında yanlış alarm hâlâ yüksek ([replay ritim testi](replay_rhythm_test.md)).
7. **Kısayol başka araçta yanlış alarm olarak çıkıyor.** Kia'da eğitilip
   Spark'ta (Kia ile 3 ortak ID) bir kez test edildi: ID ve byte kullanan
   modeller temiz Spark sürüşünün %10-20'sine saldırı diyor (saniyede
   222-464 yanlış alarm); ID'siz ritim modeli %0,34. Ritim modeli Spark'ta
   Injection'da F1 0,98, Spoofing'de 0,82. DoS'ta ID 0 ezberi kanıtlandı: DoS
   mesajlarına normal bir ID verilince ID'li modellerin recall'ı 1,0'dan
   0-0,035'e düşüyor; ritim modeli de 0,13'e düşüyor (büyük ihtimalle o da
   "bilinmeyen ID" ipucuna dayanıyor). Ön kayıtlı 4 hipotezden 2'si tuttu
   ([araçlar arası test](shortcut_transfer_test.md)).
8. **DoS kısayolu ritim modelinde giderildi.** Eğitime Kia DoS kaydının ID'si
   normal bir ID'ye çevrilmiş bir kopyası eklendi; başka bir şey değişmedi.
   Ritim modeli, ID'si değiştirilmiş DoS'u Spark'ta %13,8 yerine %100,
   Sonata'da %12,6 yerine %100 yakalıyor; temiz sürüşte yanlış alarm artmadı.
   ID ve içerik kullanan modeller bundan faydalanmadı. Aynı test dosyalarına
   ikinci bakış ([rapor](dos_id_swap_training.md)).
9. **Sonraki adım** (§15'teki eski "sonraki adım"ın yerine geçer; README'deki
   Future Work yalnız ikinci veri setlerini anlatır): henüz belirlenmedi;
   sonuçların hocaya sunulması önerilir.

### Saldırı türüne göre güncel durum

F1, saldırı mesajları için. "Aynı sürüş" release dosyasıdır (eğitim kaydının
devamı); "başka kayıt", aynı türün diğer kaydı eğitimdeyken bir kaydın tamamen
dışarıda bırakıldığı testtir ([bilinen saldırı](kia_known_attack.md), XGBoost
depth 6, eşik 0,5).

| Tür | Aynı sürüş (release, varyant C) | Başka kayıt | Ne kadar güvenilir |
|---|---|---|---|
| DoS | 1,000 | Spark 0,989 / Sonata 0,962 (ritim); ID değiştirilmiş kopyayla eğitilince ID'si değişen DoS'ta da 0,961 / 0,937 | Orta: ritim modelinde ID kısayolu giderildi (ikinci bakış, sentetik değişiklik); ID'li modeller hâlâ ID 0'a bağlı |
| Injection | 0,990 / 0,997 | Kia 0,968 / 0,997; Spark 0,98, Sonata 0,77-0,93 (ritim) | Orta: ritim araçlar arası taşınıyor; ID'li modeller başka araçta çok yanlış alarm veriyor |
| Spoofing | 1,000 / 0,996; 170 saldırılı dosyada 0 | Kia 0,666 / 0,640 / 0 (130 saldırı); Spark 0,82, Sonata 0,85-0,89 (ritim) | Düşük-orta: Kia içinde kayda göre çok değişiyor; ritim başka araçta dayanıyor |
| Replay | 0,445 (C); ritim modeli R2 ile 0,903 | Sonata 0,877 (ritim modeli, yarı görülmüş) | Düşük-orta: Sonata yarı görülmüş test, tek Kia kaydı, iki araçta aynı saldırı düzeni, saldırı anlarında saniyede 221,5 yanlış alarm |

### Hangi dosya nerede kullanıldı

Ham dosyalar `car_track_*` klasörlerindedir (37 dosya: Kia 16, Sonata 9 eğitim,
Spark 4 eğitim; 8 release dosyası Sonata veya Spark).

| Deney | Eğitim | Ayar seçimi | Test |
|---|---|---|---|
| Release sınıflandırma ([rapor](kia_release_test.md)) | 9 Kia eğitim kaydı | aynı 9 kayıt, 2 iç fold (DoS ve Replay hep eğitimde) | 7 Kia release dosyası |
| Replay ritim ([rapor](replay_rhythm_test.md)) | Kia final_2nd `Replay_dataset`, Kia preliminary `Attack_free` | aynı iki kaydın ilk ve ikinci yarısı | Sonata final_2nd `Replay_dataset`, Sonata preliminary `Attack_free` (temiz sürüş yanlış alarmı), Kia final_2nd release `File_4` |
| Araçlar arası kısayol ([rapor](shortcut_transfer_test.md)) | 9 Kia eğitim kaydı | release ile aynı 2 iç fold | Spark preliminary `Flooding`, `Fuzzy`, `Malfunction`, `Attack_free` ikinci yarısı; Sonata `Flooding`, `Fuzzy` (preliminary, final_1st), `Malfunction` (preliminary, final_1st, final_2nd), preliminary `Attack_free`; iki `Flooding` kaydının ID'si değiştirilmiş kopyası |

Ritim deneyinde ID periyotları Kia ve Sonata'nın final_1st `Attack_free`
kayıtlarından ölçülür; bu iki dosya eğitim ya da test satırı olarak kullanılmaz.
Araçlar arası testte periyotlar Spark `Attack_free`'nin ilk yarısından ve
Sonata final_1st `Attack_free`'den ölçülür.

**Hiç kullanılmayan veri:** sadece 8 Sonata/Spark release dosyası (eğitim
kayıtlarının devamı oldukları için temiz test sayılmazlar).

## 1. Projenin sorusu

ULAK, CAN hattındaki her mesaj için normal mi saldırı mı olduğunu tahmin etmeye
çalışıyor. Bunun yanında modelin saldırı davranışını mı öğrendiği, yoksa örneğin
belirli bir CAN ID'yi ezberleyerek kolay bir **shortcut** mı kullandığı araştırılıyor.

İki farklı soru önemlidir:

1. **Bilinen saldırı, yeni kayıt:** Aynı saldırı türünün başka bir kaydı eğitimde
   bulunurken model ayrılmış kaydı tanıyabiliyor mu?
2. **Görülmemiş saldırı türü:** Bir saldırı türünün bütün kayıtları eğitim dışında
   bırakıldığında model bu türü tanıyabiliyor mu?

Bu iki deneyin eğitim verileri farklıdır; skorlar aynı testin sonuçları değildir.
Hiçbir sonuç tek başına farklı bir araçta, oturumda veya gerçek kullanımda aynı
başarıyı garanti etmez.

## 2. Veri ve kavramlar

Kia Soul alt kümesinde 16 kaynak dosyadan **4.342.470 CAN mesajı** vardır:
3.673.516 normal (%84,6), 668.954 saldırı (%15,4). Bu toplam hem eğitim hem
release bölümlerini içerir; tümü her deneyde eğitim için kullanılmaz.
[Veri özeti](../../reports/kia_soul_summary.md)

Her satır bir mesajdır. `label_bin` 0 için normal, 1 için saldırıdır. Normal
mesajlar çoğunlukta olduğu için tek başına accuracy yanıltıcıdır. Örneğin her
mesaja normal diyen bir model saldırıları hiç yakalamadan yüksek accuracy alabilir.

- **Recall:** Gerçek saldırıların ne kadarının yakalandığı.
- **Precision:** Saldırı denilen mesajların ne kadarının gerçekten saldırı olduğu.
- **F1:** Precision ve recall'u birlikte değerlendiren skor.
- **FPR:** Normal mesajların ne kadarına yanlışlıkla saldırı dendiği.
- **AUPRC:** Eşikten bağımsız sıralama skoru; model saldırıları normal
  mesajların önüne ne kadar iyi diziyor (1 kusursuz). Son iki deneyde ayar
  seçimi buna göre yapıldı.
- **OOF (out-of-fold):** Her satırın, o satırı eğitimde görmemiş fold modeliyle
  tahmin edilmesi. Karar eşiği bu tahminlerde F1'i en yükseğe çıkaran değer
  olarak donduruldu ("OOF-F1 eşiği").
- **`unseen_*` / `official`:** Dış bölmeler. `unseen_*` bir saldırı türünün tüm
  kayıtlarını eğitimden çıkarır; `official` HCRL eğitim klasörlerinde eğitip
  release dosyalarında test eder ([split açıklaması](../../splits/README.md)).
- **Seen-type fold:** Validation'daki her saldırı türünün iç eğitimde de
  bulunduğu iç fold.
- **Tek seferlik koruma:** Test komutu, seçim dosyasının sha256'sı tutmazsa ya
  da daha önce çalıştırılmışsa (`*_attempt.json` ya da sonuç dosyası varsa)
  reddeder. Bilinçli tekrar için ne silineceği raporların Reproduction
  bölümünde.

Bir kayıt saldırı içerse bile içindeki bütün mesajlar saldırı değildir. Saldırı
türü dosya/kayıt bağlamını, `label_bin` ise tek mesajın etiketini anlatır.

## 3. Oturum öncesinde mevcut olan temel düzen

Nihal'in veri hattı mesajları hazırlıyor, ham kayıt kimliğini `recording_id`
olarak koruyor ve Kia için bölme manifesti üretiyordu. Aynı kayıt eğitim ve test
arasında paylaşılmıyordu. Manifest dört `unseen_*` saldırı bölmesini ve ayrıca
HCRL'nin `official` bölümünü tanımlar. [Split açıklaması](../../splits/README.md)

İlk Kia decision tree modeli `max_depth=6`, `random_state=42` kullanıyordu.
Girdi CAN ID, DLC ve `byte_0..7`; eksik byte'lar -1 ile dolduruluyordu.
Zamanlama bu ilk modelde yoktu. Model saldırı türünü değil normal/saldırı
ikili etiketini tahmin ediyordu.

Oturum öncesindeki kayıtlı dış test sonuçları:

| Eğitimden çıkarılan saldırı | Saldırı recall | Saldırı F1 | Normal mesajlarda yanlış alarm |
|---|---:|---:|---:|
| DoS | %0 | 0,000 | 0 / 103.928 |
| Injection | %54,3 | 0,703 | 437 / 462.836 |
| Spoofing | %52,0 | 0,684 | 117 / 708.908 |
| Replay | %0 | 0,000 | 0 / 410.698 |

Bu ağaç ayarları yeni iç validation düzeniyle seçilmemişti. Aynı testteki
sonraki XGBoost modelleriyle karşılaştırırken model seçimi süreçleri farklıdır.
Precision, model hiç saldırı tahmini yapmadığında matematiksel olarak tanımsızdır.

Ayrı bir eski deneyde tüm araçların eğitim bölümünde `source_file` bazlı beş
fold'lu decision tree ve ID maskesi denenmişti. Bu, Kia'nın iç validation'ı ile
aynı deney değildir. Nihal'in daha sonraki belgeleri aynı dosya adının farklı
klasörlerde tekrarlanması nedeniyle `recording_id` kullanılmasını önerir.
[Eski shortcut raporu](shortcut_baseline.md), [veri bulguları](../../FINDINGS.md)

## 4. Mevcut Kia hatalarının ilk teşhisi

Oturum öncesindeki [DoS ve Replay teşhisi](kia_unseen_diagnosis.md) şunları
gösteriyordu:

- DoS dışarıda tutulduğunda, ilgili test saldırılarının kullandığı ID 0'dan
  eğitimde başka bir saldırı kaydında yalnız 14 örnek vardır. Tamamen sıfır
  byte'lı içerik normal trafikte de yaygındır. Bu, hatayla tutarlıdır; ağacın
  hatasının kesin nedeni olarak kanıtlanmamıştır.
- Replay test saldırı mesajlarının yaklaşık %80'i, eğitimdeki bir normal mesajla
  ID, DLC ve byte'lar açısından birebir aynıdır. Normal test mesajlarında da
  oran yaklaşık %82'dir. Tek mesaj içeriğiyle ayrım zorlaşabilir; zamanlama
  aday ek bilgidir, tek olası çözüm olduğu kanıtlanmamıştır.

## 5. Bu oturumda validation düzeni

İlk Kia notebook'unda ayrı bir iç validation veya hiperparametre araması yoktu.
Önce mevcut dış eğitim bölmelerine kayıt bazlı beş iç fold oluşturuldu. Gerçek
veride 25 fold'un 6'sında saldırı mesajı yoktu; çünkü `GroupKFold` her fold'a
saldırı kaydı koymayı garanti etmiyordu.

Sonra kayıtları bölmeden her fold'da iki sınıf bulunacak dört fold'a geçildi.
`unseen_spoofing` dış eğitiminde yalnız dört saldırı içeren kayıt olduğundan,
bütün dış bölmeler için ortak beş fold bu koşulla mümkün değildir. Yeni
üretici her dış eğitim bölmesinde önce iki sınıf içeren kayıtları ayrı fold'lara
koyar, sonra satır sayısını dengelemeye çalışır. Bölme oluştururken yalnız
eğitim etiketleri kullanılır. Gerçek veride 20 iç fold'un tümünde iki sınıf
ve kayıt ayrımı doğrulandı. Bazı fold'larda yalnız 130 saldırı vardır.

Önemli: Dışarıda tutulan saldırı türü iç validation'da **yoktur**. Örneğin
`unseen_injection` iç validation F1'i, Injection tespit skoru değildir.
Kayıtların ayrı olması bağımsız toplama oturumları olduğunu kanıtlamaz.
Manifestler girdi ve dış manifest hash'lerini tutar; tek tek eski index
dosyaları kendi hash'leriyle bağlanmış değildir.

Kod: [validation üreticisi](../../splits/make_kia_validation.py). Üretilen
manifest ve indexler yereldir; ham veri ve üretilmiş çıktılar commit edilmez.

## 6. Zamanlamasız XGBoost baseline

Kia decision tree ile aynı ID/DLC/byte girişleri kullanıldı. XGBoost için 100
ağaç, öğrenme hızı 0,1, derinlik 3 ve 6, seed 42, sınıf ağırlığı yok ve eşik
0,5 kullanıldı. Her dış deneyde dört iç fold'un ortalama saldırı F1'iyle iki
derinlikten biri seçildi; model dış eğitimde yeniden eğitilip dış testte ölçüldü.
Resmî release testi çalıştırılmadı.

| Dışarıda tutulan saldırı | Seçilen derinlik | Recall | F1 | Yanlış alarm |
|---|---:|---:|---:|---:|
| DoS | 6 | %0 | 0,000 | 0 / 103.928 |
| Injection | 3 | %36,8 | 0,533 | 1.907 / 462.836 |
| Spoofing | 3 | %52,9 | 0,692 | 10 / 708.908 |
| Replay | 6 | %0 | 0,000 | 0 / 410.698 |

Sadece iki derinlik ve sabit eşik denendiği için bu, XGBoost'un genel kapasitesi
hakkında kesin bir sıralama değildir. [Ayrıntılı baseline](kia_xgboost_baseline.md)

## 7. Zamanlama eklendiğinde ne oldu?

`iat_id`, aynı ID'li önceki mesajdan; `iat_bus`, hattaki herhangi bir önceki
mesajdan geçen süredir. İkisi kayda özel geçmişten hesaplanır. Standart
özelliklere ikisi eklendi; `bus_count_100ms` eklenmedi. Aynı iki XGBoost
derinliğinden iç validation'a göre seçim yapıldı.

| Dış test | Zamanlamasız recall / F1 | İki zamanlama özelliği recall / F1 | Zamanlamalı yanlış alarm |
|---|---:|---:|---:|
| DoS | %0 / 0,000 | %94,2 / 0,957 | 428 / 103.928 |
| Injection | %36,8 / 0,533 | %18,4 / 0,287 | 13.558 / 462.836 |
| Spoofing | %52,9 / 0,692 | %35,0 / 0,508 | 2.009 / 708.908 |
| Replay | %0 / 0,000 | %0 / 0,000 | 0 / 410.698 |

DoS'ta 16.072 saldırının 15.140'ı yakalandı. Bu tek kayıttaki iyileşme bütün
DoS biçimlerine genellenemez. Spoofing'de zamanlamayla seçilen derinlik de
3'ten 6'ya değiştiğinden düşüş yalnız zamanlamaya bağlanamaz.
[Zamanlama raporu](kia_xgboost_timing.md)

Örneğin Replay dışarıda bırakıldığında derinlik 6 zamanlamalı modelin iç
fold'lardaki ortalama eğitim F1'i yaklaşık 1,000, validation F1'i 0,588 idi.
Bu eğitim ve validation kayıtlarının dağılımları farklı olduğundan fark zayıf
aktarımı gösterir; tek başına belirli bir ezberleme mekanizmasını kanıtlamaz.

## 8. Injection hatalarını inceleme

Zamanlamasız ve iki zamanlama özellikli seçilmiş XGBoost modelleri aynı
eğitim/test bölmelerinde yeniden çalıştırıldı; confusion count'lar önceki
sonuçlarla birebir eşleşti. 141.164 test saldırısının durumu:

| Durum | Saldırı mesajı |
|---|---:|
| İki model de kaçırdı | 76.973 |
| Eski model yakaladı, zamanlamalı model kaçırdı | 38.258 |
| Eski model kaçırdı, zamanlamalı model yakaladı | 12.246 |
| İki model de yakaladı | 13.687 |

Eski modelin normal dediği 13.430 normal mesaja zamanlamalı model saldırı dedi.
Kaybedilen saldırılarda ortanca `iat_id` yaklaşık 15,9 ms, yeni yakalananlarda
3,8 ms idi. Zamanlamalı modelin ilk ağacı yaklaşık 7,87 ms `iat_id` bölmesi
kullanıyordu. Bu tek ağaç bütün topluluğun kararını açıklamaz. CAN ID 66'da
yakalama oranı eski modelde %68,4, zamanlamalı modelde %14,8 idi.

Testteki Injection saldırılarının hiçbirinin ID+DLC+8 byte birleşimi eğitimdeki
normal bir mesajla birebir eşleşmedi. Bu, kısmi benzerlik veya başka sınırlamaları
dışlamaz. Bu teşhis oturumda geçici kodla hesaplandı; ham örnekler kaydedilmedi.

## 9. Zamanlama özelliklerini ayrı ayrı deneme

A: ID/DLC/byte; B: A + `iat_id`; C: A + `iat_bus`; D: A + iki zamanlama
özelliği. Aynı kayıt bazlı iç validation'da decision tree derinlik 6 ve
XGBoost derinlik 3/6 karşılaştırıldı. Örneğin Injection dışarıda tutulduğunda:

| Model / özellik | Derinlik | Ortalama iç fold F1 | Birleştirilmiş normal FPR |
|---|---:|---:|---:|
| XGBoost A | 3 | 0,005 | %2,82 |
| XGBoost B | 3 | 0,456 | %0,91 |
| XGBoost C | 6 | 0,059 | %3,34 |
| XGBoost D | 3 | 0,346 | %0,90 |
| Decision tree B | 6 | 0,483 | %2,62 |

Bu satırların validation'ında Injection bulunmaz. F1 dört fold'un ağırlıksız
ortalamasıdır; FPR normal frame'ler birleştirilerek hesaplanmıştır. Tek özellik
her dış bölmede üstün değildi. [Tüm fold'lar](kia_validation_ablation.md)

### Sınıf ağırlığı ve eşik

XGBoost B, derinlik 3 için eğitimde pozitif sınıf ağırlığı 1 ve 3; validation
eşiği 0,3/0,5/0,7 denendi. Injection dışı validation'da ağırlık 1/eşik 0,5
ortalama F1 0,456 ve FPR %0,91; ağırlık 3/eşik 0,7 F1 0,458 ve FPR %0,91 idi.
Bu 0,002 fark güvenilir üstünlük kanıtı değildir. Ağırlık 1/eşik 0,3 daha yüksek
birleştirilmiş recall (%42,5) ama daha fazla FPR (%2,67) verdi. İşletim için
kabul edilebilir yanlış alarm bütçesi tanımlanmadı.

Sonrasında validation'da aday görülen B, derinlik 3, ağırlık 1, eşik 0,5,
önceden görülmüş Injection dış testinde bir kez değerlendirildi:

| Özellik | Recall | F1 | Normal yanlış alarm |
|---|---:|---:|---:|
| A: zamanlamasız | %36,8 | 0,533 | 1.907 / 462.836 |
| B: yalnız `iat_id` | %26,9 | 0,377 | 22.082 / 462.836 |
| D: iki zamanlama | %18,4 | 0,287 | 13.558 / 462.836 |

B'nin validation kazancı bu görülmemiş Injection kaydına taşınmadı. Bu testler
zaten incelendiği için keşif niteliğindedir; son bağımsız performans değildir.

## 10. Bilinen saldırıyı başka kayıtta deneme

Injection'ın iki, Spoofing'in üç saldırı kaydı vardır. Her seferinde bir kayıt
tamamen ayrılıp aynı türün diğer kaydı/kayıtları dahil kalan eğitim kayıtlarıyla
eğitim yapıldı. DoS ve Replay'in birer saldırı kaydı olduğundan bu protokolle
değerlendirilemedi. Üç sabit model raporlandı: tree derinlik 6, XGBoost
derinlik 3 ve 6. Girdi zamanlamasız ID/DLC/byte; XGBoost 100 ağaç, hız 0,1.

| Ayrılan kayıt | Saldırı sayısı | Tree F1 | XGBoost 3 F1 | XGBoost 6 F1 |
|---|---:|---:|---:|---:|
| Injection final-first | 119.551 | 0,724 | 0,907 | 0,968 |
| Injection preliminary | 21.613 | 0,736 | 0,974 | 0,997 |
| Spoofing final-first | 130 | 0,000 | 0,000 | 0,000 |
| Spoofing final-second | 67.080 | 0,000 | 0,666 | 0,666 |
| Spoofing preliminary | 4.770 | 0,546 | 0,978 | 0,640 |

Injection final-first'te XGBoost 6 recall %98,8, normal FPR %1,89; tree recall
%57,0, FPR %0,11 idi. Spoofing preliminary'de XGBoost 3 sıfır yanlış alarm
verirken derinlik 6 5.324 normal frame'i yanlış işaretledi. Bunlar aynı
modelin evrensel olarak iyi veya kötü olduğunu kanıtlamaz: kayıt sayısı az,
kayıtlar daha önce incelendi ve bağımsız oturum oldukları doğrulanmadı.
[Bilinen saldırı raporu](kia_known_attack.md)

### CatBoost ile aynı düzen

Aynı kayıtlar ve birebir aynı eğitim/test satırlarıyla CatBoost derinlik 3 ve 6
denendi. Ayarlar iç validation'daki CatBoost ile aynıdır: 100 iterasyon, hız 0,1,
`Plain` boosting, seed 42, eşik 0,5, sayısal ID. Kazanan seçilmedi.

| Ayrılan kayıt | XGBoost 3 / 6 F1 | CatBoost 3 / 6 F1 | CatBoost 3 / 6 normal FPR |
|---|---:|---:|---:|
| Injection final-first | 0,907 / 0,968 | 0,838 / 0,951 | %1,07 / %1,66 |
| Injection preliminary | 0,974 / 0,997 | 0,949 / 0,988 | %0,21 / %0,04 |
| Spoofing final-first | 0,000 / 0,000 | 0,000 / 0,000 | %0 / %0 |
| Spoofing final-second | 0,666 / 0,666 | 0,000 / 0,000 | %0,11 / %0,02 |
| Spoofing preliminary | 0,978 / 0,640 | 0,941 / 0,990 | %0,10 / %0 |

Injection'da CatBoost iyi aktarım gösterdi ama aynı derinlikteki XGBoost'un
biraz altında kaldı. Preliminary Spoofing'de CatBoost derinlik 6 sıfır yanlış
alarmla F1 0,990 aldı; XGBoost derinlik 6 burada 5.324 yanlış alarm vermişti.
Final-second Spoofing'de ise CatBoost 67.080 saldırının hiçbirini yakalamadı;
XGBoost'un iki derinliği tam yarısını (33.540) yakalamıştı. Bu farkın nedeni
incelenmedi. 130 saldırılı kayıtta dört boosting varyantı da 0/130 yakaladı.
Sıralama kayda göre değişiyor; beş ilişkili ve daha önce incelenmiş kayıttan
genel bir kazanan çıkarılamaz.

## 11. Spoofing: 130 kaçırılan saldırı ve yanlış alarmlar

İki XGBoost modeli yeniden eğitildi; confusion count'lar önceki deneyle eşleşti.
Final-first kaydındaki 130 saldırı ID 790 ve 1087'de, her birinden 65 adettir.
130 mesaj 55 farklı ID+DLC+byte birleşimi içerir:

- 63 saldırı mesajının birleşimi eğitimdeki normal bir mesajla birebir aynıydı.
- 61 saldırı mesajı kendi test kaydındaki bir normal mesajla aynı girdiye sahipti.
  Bu sayılar örtüşebilir ve toplanmaz.
- Bu girdiler aynı olduğunda deterministik, yalnız içerik gören bir model aynı
  tahmini yapmak zorundadır. Bu, etiketlerin yanlış olduğunu kanıtlamaz ve bütün
  130 hatayı da tek başına açıklamaz.

Preliminary Spoofing kaydında derinlik 6'nın 5.324 yanlış alarmının 5.210'u
ID 1087, 114'ü ID 24 idi. Bu 5.324 mesaj 64 farklı girdi birleşiminden oluşur.
ID 1087 normal test mesajlarında `byte_4` 120; aynı ID'nin normal eğitim
mesajlarında 70–116 aralığındaydı. Kayda özgü içerik farkı hipotezdir; hatanın
kesin nedenini kanıtlamaz. DBC doğrulaması olmadan byte'a fiziksel anlam verilmez.
[Ayrıntılı Spoofing teşhisi](kia_spoofing_diagnosis.md)

## 12. Aynı içerikte zamanlama ve sıra

130 mesajın bulunduğu kayıt üzerinde, sadece mevcut ve geçmişe dayalı sıra
özellikleri betimsel olarak incelendi; model eğitilmedi. Önceki aynı-ID payload'a
göre değişen bit sayısı ve tekrar durumu hesaplandı.

| Grup | Mesaj | Ortanca aynı-ID aralığı | Ortanca değişen bit |
|---|---:|---:|---:|
| Aynı içerik normalde de görülen saldırılar | 61 | 4,54 ms | 8 |
| Bu saldırı içerikleriyle eşleşen normal mesajlar | 736 | 10,00 ms | 2 |

736 kontrol, 61 saldırıyla bire bir eşleştirilmiş çiftler değildir. Her iki
etikette görülen 38 ayrı içerik birleşiminin 38'inde saldırıların ortanca
aynı-ID aralığı daha kısa, 37'sinde değişen bit ortancası daha yüksekti.
Bu bir kayıt ve az sayıdaki gözleme dayalı keşiftir; başarı metriği veya
anlamlılık testi değildir. Sıralama timestamp'e dayanır; canlı geliş sırasının
geçerliliği ayrıca doğrulanmalıdır. [Sıra analizi](kia_spoofing_sequence.md)

## 13. Sıra özellikleri ve CatBoost validation deneyi

XGBoost'a ID/DLC/byte + `iat_id` yanında önceki aynı-ID payload'a göre değişen
bit sayısı ve tekrar göstergesi eklendi. Tekrar göstergesi değişen bit sayısı
sıfır olduğunda 1 olduğundan ayrı bir bilgi kaynağı değildir. Aynı kayıt bazlı
iç validation'da XGBoost derinlik 3/6; ayrıca aynı sayısal ID gösterimiyle
CatBoost derinlik 3/6 denendi. İkisi 100 ağaç, 0,1 öğrenme hızı, eşik 0,5,
seed 42 kullandı; CatBoost `Plain` boosting kullandı. İç algoritma ve diğer
varsayılanlar farklıdır. CatBoost'un kategorik ID ve ordered boosting özellikleri
bu deneyde denenmedi.

| Dışarıda tutulan tür | XGBoost + `iat_id` F1, derinlik 3/6 | XGBoost + sıra F1, 3/6 | CatBoost + `iat_id` F1, 3/6 |
|---|---:|---:|---:|
| DoS | 0,668 / 0,560 | 0,572 / 0,656 | 0,508 / 0,674 |
| Injection | 0,456 / 0,270 | 0,305 / 0,225 | 0,493 / 0,373 |
| Spoofing | 0,413 / 0,472 | 0,717 / 0,650 | 0,332 / 0,421 |
| Replay | 0,372 / 0,541 | 0,590 / 0,393 | 0,347 / 0,382 |

Bunlar dört iç fold'un ağırlıksız ortalamasıdır; satırdaki dış saldırı türü
validation'da yoktur. Injection dışı düzende derinlik 3 için normal FPR sırasıyla
%0,91, %0,47 ve %1,09 idi. İncelenen 130 Spoofing saldırısının bulunduğu fold'da
üç varyant ve iki derinlik de 0/130 yakaladı. Özellikler bu kayıt incelendikten
sonra seçildiği için aynı kayıt bağımsız test sayılmaz. Yeni dış test çalıştırılmadı.
[Sıra ve CatBoost raporu](kia_sequence_catboost_validation.md)

## 14. Dış HCRL reposu incelemesi

İncelenen [2024tm05004-beep/HCRL](https://github.com/2024tm05004-beep/HCRL)
reposunun yerel kopyası `6e25a9c` commit'indeydi. Bu repo HCRL'nin **Car-Hacking
Dataset** verisini; ULAK ise **2019 In-Vehicle Network Intrusion Detection
Challenge** verisini kullanır. Önceki konuşmada ikisini aynı veri kümesi olarak
tanımlamak hatalıydı. İsimleri ve saldırı türleri benzese de skorlar doğrudan
karşılaştırılamaz.

Repo XGBoost, CAN ID, DLC, aynı-ID zaman aralığı, payload entropisi, son
mesajlarda zaman ortalaması/standart sapması ve farklı ID sayısı kullanıyor.
Notebook pencere boyutu 50. İddia edilen çok sınıflı modele rağmen incelenen
hedef kodu `Flag == T` ile **normal/saldırı ikili sınıflandırması** yapıyor.
Ek olarak 3-sigma ve autoencoder tabanlı telematik proxy katmanı var; DBC
olmadan proxy'ler gerçek hız/RPM olarak kabul edilmemeli.

Teknik rapor %99,38 TPR, %0,00 FPR, 0,9969 F1 ve 100 mesajda 6,10 ms bildiriyor.
Bu değerler bağımsız olarak yeniden üretilmedi: yerel kopyada `Data/` yok ve
notebook çıktıları boş. Birleştirme kodu kaynak başına ilk 50.000 satırı alırken
notebook birleştirilmiş verinin ilk 100.000 satırını, grafik scripti ilk 20.000
satırını kullanıyor. Mevcut confusion-matrix görseli DoS başlığıyla 1.733 normal
ve 258 saldırının tamamını doğru gösteriyor; bu, rapordaki %99,38 TPR ile aynı
sonuç değil. Farklı çalıştırmalar olabilir; kaynak izleri yeterli değildir.

Transfer edilebilir adaylar: payload entropisi, geçmiş 50/100 mesajda farklı ID
sayısı, zaman aralığının pencere ortalaması ve standart sapması. Bunlar ayrı
ayrı, kayıt sınırları ve geçmişe nedensellik korunarak denenmelidir. Dış
repo sonucu aynı test protokolünü veya görülmemiş Replay başarısını göstermez.

## 15. Son durum, sınırlar ve sonraki adım (ilk oturum)

Bu bölüm ilk oturumun sonundaki durumdur; Replay ve release sonuçları ile
sonraki adım §15a, §15b ve baştaki özetle güncellendi.

- Decision tree, XGBoost ve sınırlı CatBoost karşılaştırmaları hazırdır. Bir
  modelin genel olarak en iyi olduğu sonucuna varılamaz.
- DoS için zamanlamalı XGBoost bir dış kayıtta yüksek recall verdi; Replay
  dışarıda bırakılan testte denenmiş içerik ve zamanlama modelleri 0 yakaladı.
- Bilinen Injection'ın farklı kaydında XGBoost güçlüydü; tamamen görülmemiş
  Injection aynı başarıyı vermedi. Eğitim kümesinin içeriği ve büyüklüğü de
  değiştiğinden fark sadece saldırı türüne maruz kalmanın nedensel etkisi değildir.
- Validation'da 130 örnekli fold ve az sayıda kayıt vardır. İç içe mesajlar
  bağımsız örnek sayılmaz; dosya ayrımı oturum bağımsızlığı garantisi değildir.
- Dış `unseen_*` sonuçları ve 130 Spoofing mesajı tekrar tekrar incelenmiştir;
  bunlar artık el değmemiş nihai test değildir. Özellikler incelenen kayıt
  üzerinden önerildiği için bu kayıttaki sonuçlarla nihai başarı iddiası yapılamaz.
- CatBoost bilinen saldırı/farklı kayıt düzeninde karşılaştırıldı (§10); sonuç
  kayda göre değişti. Final-second Spoofing'de CatBoost'un 0 ve XGBoost'un tam
  %50 recall vermesinin nedeni açık bir teşhis adayıdır. Bağımsız kayıt veya
  ikinci veri kümesi kullanmak mantıklı sonraki adımdır. Dış
  repodaki entropi ve pencere özellikleri de kontrollü ayrı deneylerdir; henüz
  bu oturumda uygulanmadılar.

## 15a. Sonraki oturum: soru değişti, release testi (9 Kasım)

- Hat kontrol edildi: ham CSV ile parquet satır satır aynı. Aynı kaydın ilk
  %60'ında eğitilip son %40'ında test edilen XGBoost; DoS, Injection ve iki
  Spoofing kaydında F1 1,000 aldı. `unseen_*` sonuçlarındaki %0'lar bir hata
  değil, sınıflandırıcıya hiç görmediği saldırı mekanizmasını sormanın sonucu.
- Replay kaydında 8 ms altındaki `iat_id` aralıklarında mesajların yaklaşık
  yarısı normal, yarısı saldırı: araya giren replay mesajı arkasındaki gerçek
  mesajın aralığını da kısaltıyor. Tek mesajla ayrım bu yüzden sınırlı.
- Soru değiştirildi: tüm eğitim kayıtlarında eğitip HCRL release dosyalarında
  aynı saldırı türlerini yakalamak. Ayarlar yalnız görülen-tür iç fold'larında
  seçildi, release testi bir kez çalıştırıldı.
- Sonuç (aynı sürüşün devamında, aşağıdaki maddeye bakın): DoS, Injection ve
  iki büyük Spoofing dosyasında F1 0,99-1,00; 170 saldırılı Spoofing dosyası
  kaçırıldı. ID
  çıkarılınca DoS 1,000'den 0,000'a düşüyor (ID kısayolu). `bus_count_100ms`
  Replay'i %92 yakalıyor ama saniyede 73 yanlış alarmla (kayıt kısayolu).
  Replay içerikle %0,3, `iat_id` ile %25-29 yakalanıyor.
- Sonradan bulundu: her release dosyası bir eğitim kaydının zamanda doğrudan
  devamı (aradaki boşluk 0,2-0,6 ms; 7 çift). Release testi bu yüzden aynı
  sürüşün sonraki dakikalarını ölçüyor, yeni kaydı değil. Farklı kayıtlar
  arası skor yalnız iç fold'larda var: F1 0,375-0,859, FPR en çok %9,4.
- Ayrıntılar ve sınırlar: [release testi](kia_release_test.md).

## 15b. Replay için ritim özellikleri (9 Kasım)

- Replay'de saldırı 10 sn açık, 10 sn kapalı geliyor; tüm ID'lere saldırılıyor
  ve saldırı sırasında her ID'nin akışına yaklaşık 1,33 periyotta bir (10 ms'lik
  ID'de yaklaşık 13 ms) eski bir kopya giriyor. Kopyadan sonraki gerçek mesaj da kısa aralık gördüğü için
  tek aralık ayırmıyor; ama gerçek mesajlar ritmi koruyor. İki önceki aynı-ID
  mesajına süre gerçek mesajda tam periyot, kopyada küsurlu (örneğin 1,3).
- Özellikler araçtan bağımsız: ID ve ham byte yok, süreler aracın temiz
  sürüşünden ölçülen ID periyoduna bölünüyor. Ayarlar yalnız Kia replay
  kaydının iki yarısında seçildi; Hyundai Sonata replay kaydında bir kez
  test edildi.
- Sonuç (dondurulmuş eşik): Sonata'da F1 0,877, temiz Sonata sürüşünde
  saniyede 0,3 yanlış alarm. Sadece aralık ve sayımla F1 0,620. Kia release
  replay dosyasında (ikinci bakış) 0,445'ten 0,903'e.
- İçerik (değişen bit) az katkı veriyor (+0,01-0,02); Sonata kopyaları çoğu
  zaman gerçeğiyle aynı.
- Saldırı anlarında yanlış alarm hâlâ yüksek: Sonata'da saniyede 221,5
  (saldırı araları 1,7).
- Sınırlar: Sonata replay dosyasına özellik tasarımından önce etiketleriyle
  bakıldı (yarı görülmüş test); Kia File_4 eğitim kaydının devamı; tek Kia
  replay kaydı; iki araçta aynı saldırı düzeni; temiz sürüş kaydı gerekiyor. Ayrıntılar: [replay ritim testi](replay_rhythm_test.md).

## 16. Tekrar çalıştırma ve çalışma ağacı

- Deney bağımlılıkları: `pip install -r experiments/requirements.txt`.
- Kia veri ve dış bölme: `python prepare_kia_soul.py`, ardından
  `python build_features.py --input kia_soul_dataset.csv --prefix kia_soul_features`
  ve `python splits/make_kia_splits.py`.
- İç fold: `python splits/make_kia_validation.py`.
- XGBoost ve özellik deneyleri: [çalıştırma açıklaması](../kia_decision_tree/XGBOOST.md).
- Bilinen saldırı: `python experiments/kia_known_attack.py`; CatBoost için
  `--models catboost_depth3 catboost_depth6 --output experiments/kia_decision_tree/local_outputs/known_attack_catboost.json`.
- Spoofing teşhisi: `python experiments/kia_spoofing_diagnosis.py`, sonra
  `python experiments/kia_spoofing_sequence.py`.
- CatBoost/sıra: `python experiments/kia_validation_ablation.py --model catboost --variant iat_id`
  ve `python experiments/kia_validation_ablation.py --model xgboost --variant sequence`.
- Release sınıflandırma (Kia parquet ve dış bölme gerekir):
  `python splits/make_kia_validation.py --seen-types --fold official`, ardından
  `python experiments/kia_release_test.py select` ve yazdırılan sha256 ile
  `python experiments/kia_release_test.py release --selection-sha256 <sha256>`.
- Replay ritim (yalnız ham `car_track_*` klasörleri gerekir, parquet gerekmez):
  `python experiments/replay_rhythm_test.py select`, ardından
  `python experiments/replay_rhythm_test.py test --selection-sha256 <sha256>`.

İlk oturumun XGBoost/CatBoost deneylerinde Python 3.14.5, NumPy 2.4.6, pandas
2.3.3, scikit-learn 1.9.0; release ve ritim deneylerinde Python 3.12.3, NumPy
2.5.4, pandas 3.1.0, scikit-learn 1.9.1. Her ikisinde XGBoost 3.4.1, CatBoost
1.2.10. Sürümler her deneyin çıktı dosyasına da yazılır. Son kontrolde depodaki
85 yapay/izolasyon testinin tümü geçti (`python -m unittest discover -s tests -t .`).

Deneylerin ayrıntılı sonuç dosyaları `experiments/kia_decision_tree/local_outputs/`
altında yerel ve Git tarafından yoksayılmıştır; yeni bir klonda bu klasör boştur
ve karşılaştırma için deney yeniden çalıştırılıp rapordaki tablolarla
kıyaslanır. Veri ve ham kayıtlar commit edilmez.
