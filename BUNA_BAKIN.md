# BUNA BAKIN

Data tarafında yaptıklarım, sizin bilmeniz gerekenler ve sıradakiler.
Detaylar `FINDINGS.md`'de.

## Veri hazır

- Veri seti: HCRL Car-Hacking Challenge 2019. 3 araç (Hyundai Sonata, Kia Soul, Chevrolet Spark), 37 CSV dosyası, 8,46 milyon CAN mesajı. Repoda yok, README'deki linkten indirilip proje köküne konması gerekiyor.
- Pipeline'ı çalıştırmak için:
  ```bash
  python prepare_data.py     # -> combined_dataset.csv
  python build_features.py   # -> features_train.parquet, features_test.parquet
  ```
- Hedef sütun `label_bin`: 0 = normal, 1 = saldırı. Train setinde %87 normal, %13 saldırı var.
- Feature'lar:
  - `can_id_dec`
  - `dlc`
  - `byte_0..7`: eksik byte'lar NaN, 0 değil
  - `iat_id`: aynı ID'nin bir önceki mesajından bu yana geçen süre
  - `iat_bus`: bus'taki bir önceki mesajdan bu yana geçen süre
  - `bus_count_100ms`: son 100 ms'de bus'tan geçen mesaj sayısı
- **Modele asla girmemesi gereken sütunlar:** `vehicle`, `attack_type`, `source_file`, `source_folder`, `recording_id`, `split`. Bunlar mesajın içinden değil dosya adından geliyor, modele verilirse model hile yapmış olur.
- Bir dosyayı gruplamak gerektiğinde `source_file` değil `recording_id` kullanın. Dosya adları klasörler arasında tekrar ediyor, örneğin `File_1.csv` üç farklı klasörde var.

## AI / ML için

Baseline sonuçları `experiments/results/shortcut_baseline.md` dosyasında. Kullanılan model depth-6 bir decision tree, değerlendirme dosya bazlı 5-fold ile yapıldı:

| Durum | Sonuç |
|---|---|
| Sadece CAN ID ile | DoS F1 0.999. Bütün DoS mesajları ID `0000` ile geliyor |
| ID çıkarılınca | DoS F1 0. Model DoS'u sadece ID'den tanıyordu |
| ID + byte'lar ile | Replay F1 ≈ 0. Replay mesajlarının içeriği meşru, sadece zamanlama ele veriyor |

- Zamanlama feature'ları yeni eklendi ve henüz hiçbir modelde denenmedi. Saldırı mesajlarında `iat_id` belirgin şekilde düşük: normalde 10 ms, DoS'ta 0.7 ms, Spoofing'te 2.3 ms, Replay'de 5.6 ms.
- Dikkat: `bus_count_100ms` Replay kayıtlarındaki normal mesajlarda da yüksek çıkıyor. Bu feature tek mesajı değil kaydın genelini anlatıyor olabilir, yani shortcut adayı.
- Hazır split'ler `splits/` klasöründe, kullanımı `splits/README.md`'de anlatılıyor. Şu an leave-one-vehicle-out bölmesi var (2 araçla eğit, 1 araçla test et), ID'li ve ID'siz iki varyantıyla.
- Bu split'te ID'yi ezberleyen bir model başarısız olur, çünkü Spark diğer iki araçla sadece 3 ortak ID kullanıyor. Ayrıca Spark'ta Replay verisi yok.
- Satırları rastgele bölmeyin, dosya bazında bölün. Aynı ID 10 ms'de bir neredeyse aynı içerikle geliyor, rastgele bölmede bu mesajlar train'den test'e sızar.
- Accuracy kullanmayın, precision / recall / F1 raporlayın.
- HCRL'in kendi test dosyalarında araç ve saldırı türü bilgisi yok. Bu yüzden araç ya da saldırı bazlı analizler sadece train verisinde yapılabiliyor.

**Sizden öğrenmem gerekenler:**
- Mesaj bazlı mı, pencere bazlı mı çalışacaksınız?
- Hangi feature gruplarını maskeleyeceksiniz?
- "Yüzeysel" (ID + zamanlama) ve "derin" (+ payload) feature setleri işinize yarar mı?

## Security için

Veri setindeki saldırılar:

| Tür | Veride nasıl görünüyor | Gerçekçi mi? |
|---|---|---|
| DoS / Flooding | ID `0000` ile bus'ı boğuyor | Değil. Bir saldırgan başka bir ID seçebilir |
| Fuzzy / Injection | Rastgele ID'ler, 11-bit aralığın tamamı (2.048 ID) | Kısmen. Akıllı bir saldırgan sadece aracın geçerli ID'lerini kullanır |
| Spoofing / Malfunction | Gerçek bir ID, sahte içerik | Evet |
| Replay | Eski mesajlar tekrar gönderiliyor | Evet, ama sadece zamanlamayla tespit edilebiliyor |

**Bakilmasi gerekenler:**
- Simüle ettiğiniz senaryolar bu 4 türle örtüşüyor mu, eksik olan var mı?
- "Akıllı saldırgan" verisi üretebilir misiniz? Örneğin `0000` dışında bir ID ile DoS, ya da sadece geçerli ID'lerle Fuzzy. Shortcut testinin en güçlü kanıtı bu olur.
- Ürettiğiniz veri `timestamp, can_id, dlc, data, label` formatına uyarsa doğrudan pipeline'a girer.

## Backend

- Durum: Sadece iskelet var. FastAPI'de `/health` ve `/` endpoint'leri tanımlı, model ya da veri bağlantısı yok.
- Çalıştırmak için `docker compose up --build`. API http://localhost:8001 adresinde, dokümantasyonu `/docs` altında. Kod `backend/app/` içinde ve container'a bağlı olduğu için değişiklikler otomatik yükleniyor.
- Model hazır olunca eklenmesi gerekenler:
  - `/predict`: CAN mesajı alıp normal mi saldırı mı olduğunu döndüren endpoint
  - Veri istatistikleri endpoint'i
  - Modeli container'a yükleme

## Sıradaki işlerim

1. Saldırı türü bazlı bölme: bir saldırı türü hiç eğitimde görülmeyecek, sadece testte olacak.
2. Split'leri ve baseline deneyini `recording_id`'ye geçirmek, baseline'ı zamanlama feature'larıyla tekrar çalıştırmak.
3. Kayan pencerede farklı ID sayısı feature'ı.
4. Bütün adımları tek komutla çalıştıran bir pipeline ve veri versiyonlama.
5. İkinci bir veri seti (ROAD ya da CAN-MIRGU) ekleyip bulguların sadece HCRL'e özgü olup olmadığını test etmek. (Veri setini buldum.)
