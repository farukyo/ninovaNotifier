# 🎓 Ninova Not & Akademik Takip Botu

İTÜ Ninova üzerindeki notlarınızı, ödevlerinizi, duyurularınızı ve ders dosyalarınızı anlık olarak takip eden, güncellemelerde Telegram üzerinden bildirim gönderen gelişmiş bir akademik asistan botudur.

---

## ✨ Özellikler

- 👥 **Çoklu Kullanıcı Desteği:** Tek bir bot üzerinden birden fazla kişi kendi akademik verilerini bağımsız takip edebilir.
- 🔔 **Akıllı Bildirimler:**
  - Yeni not girişi veya mevcut not güncellemeleri.
  - Yeni eklenen dosyalar veya mevcut dosyalardaki değişiklikler.
  - Ödev teslim tarihi değişiklikleri veya teslim durumu (submitted) güncellemeleri.
  - **Yeni Duyuru Bildirimi:** Sınıfa eklenen duyurular, dış menü metinlerinden arındırılmış temiz bir formatla anında iletilir.
- 📊 **Gelişmiş Analiz:**
  - Ağırlıklı ortalama hesabı ve sınıf ortalaması kıyaslaması.
  - İTÜ T-Skoru sistemine dayalı **Harf Notu Tahmini**.
- 📂 **Dosya Yönetimi:**
  - Recursive (iç içe) klasör yapısını destekler.
  - Dosyaları indirmeden önce önizleme ikonuyla (📕, 📦, 🐍 vb.) listeler.
  - Telegram üzerinden tek tıkla dosya indirme imkanı.
  - Türkçe karakterli dosya isimleri için otomatik düzeltme desteği.
- 🕒 **Ödev Hatırlatıcı:** Yaklaşan ödevler için son **24 saat** ve **3 saat** kala otomatik hatırlatma bildirimleri.
- 🤖 **Kapsamlı Telegram Arayüzü:**
  - `/otoders`: Tüm dersleri Ninova'dan otomatik bulur ve ekler.
  - `/dersler`: İnteraktif butonlar ile ders detaylarına (Not/Ödev/Dosya) hızlı erişim.
- 🛡️ **Stabilite:** Telegram "409 Conflict" hataları ve Ninova oturum düşmelerine karşı otomatik kurtarma mekanizmaları. Oturumlar kullanıcı bazlı önbelleğe alınarak gereksiz giriş trafiği önlenir.

---

## 🚀 Kurulum

### 1. Gereksinimler

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) (Önerilen hızlı paket yöneticisi)

### 2. Bağımlılıkları Yükleyin

```bash
uv sync
```

### 3. Yapılandırma

Bir `.env` dosyası oluşturun ve bot token'ınızı ekleyin:

```env
TELEGRAM_TOKEN=your_bot_token_here
```

### 4. Çalıştırma

Sistemi başlatmak için:

```bash
uv run main.py
```

---

## 🤖 Kullanıcı Rehberi

Botu başlattıktan sonra Telegram üzerinden `/start` göndererek şu adımları izleyin:

1. 🔑 `/username`: Ninova kullanıcı adınızı girin.
2. 🔒 `/password`: Ninova şifrenizi girin.
3. 🪄 `/otoders`: Tüm derslerinizi otomatik olarak tarayıp takip listesine ekleyin.
4. 📖 `/dersler`: İnteraktif menü üzerinden tüm işlemlerinizi halledin.

### Temel Komutlar

| Komut | Açıklama |
|---|---|
| `/menu` | Ana menüyü gösterir. |
| `/dersler` | İnteraktif ders yönetim menüsünü açar. |
| `/otoders` | Tüm dersleri Ninova'dan otomatik çeker ve ekler. |
| `/ekle` | Yeni bir dersi manuel olarak ekler. |
| `/sil` | Takip edilen bir dersi listeden kaldırır. |
| `/liste` | Takip ettiğiniz ders linklerini gösterir. |
| `/notlar` | Tüm derslerin güncel notlarını özetler. |
| `/odevler` | Yaklaşan ödevleri listeler. |
| `/search <kelime>` | Duyurularda kelime arar. |
| `/kontrol` | Hemen bir güncelleme kontrolü başlatır. |
| `/durum` | Botun çalışma süresi ve takip istatistiklerini gösterir. |
| `/username` | Ninova kullanıcı adını ayarlar. |
| `/password` | Ninova şifresini ayarlar. |
| `/ayril` | Tüm verilerinizi sistemden kalıcı olarak siler (Onaylı). |

---

## 👑 Yönetici (Admin) Rehberi

Sistem yöneticisi için özel interaktif `/admin` paneli mevcuttur.

### Yönetim Komutları (Sadece Admin)

| Komut | Açıklama |
|---|---|
| `/admin` | Tüm yönetim araçlarını içeren interaktif buton panelini açar. |
| `/duyuru` | Tüm kayıtlı kullanıcılara toplu mesaj gönderir. |
| `/msg` | Kullanıcı listesinden birini seçerek doğrudan özel mesaj gönderir. |
| `/restart` | Botu uzaktan yeniden başlatır (Update sonrası kodu tazelemek için). |
| `/stats` | Veritabanı dosya boyutlarını ve aktif oturum sayılarını gösterir. |
| `/backup` | `users.json` ve `ninova_data.json` yedeğini Telegram'dan gönderir. |
| `/detay` | Tüm kullanıcıların ID ve Ninova kullanıcı adlarını listeler. |
| `/optout` | Seçilen bir kullanıcıyı ve verilerini sistemden zorla siler. |
| `/logs` | Sistemdeki son log kayıtlarını (hata/işlem) listeler. |
| `/force_check` | Tüm kullanıcılar için tarama döngüsünü hemen tetikler. |
| `/force_otoders` | Tüm kullanıcıların ders listesini Ninova'dan kuvvetle yeniden çeker ve günceller. |

---

## 📁 Proje Yapı Taşları

```
ninovaNotifier/
├── main.py                   # Ana uygulama başlangıç noktası
├── bot/                      # Telegram bot modülü
│   ├── instance.py           # Bot instance + runtime state
│   ├── keyboards.py          # Klavye yapıları
│   ├── utils.py              # Bot yardımcı fonksiyonları
│   └── handlers/             # Komut ve callback handler'ları
│       ├── user/             # Kullanıcı akışları
│       │   ├── commands.py
│       │   └── callbacks.py
│       └── admin/            # Admin panel ve işlemleri
│           ├── commands.py
│           ├── callbacks.py
│           ├── services.py
│           ├── helpers.py
│           └── course_management.py
├── common/                   # Ortak config + yardımcılar
│   ├── config.py
│   ├── utils.py
│   └── grading.py
├── services/                 # Entegrasyon/servis katmanı
│   └── ninova/               # Ninova scraping modülü
│       ├── auth.py           # Giriş ve oturum yönetimi
│       ├── scraper.py        # Veri çekme fonksiyonları
│       ├── file_utils.py     # Dosya indirme
│       └── scanner.py        # Periyodik tarama motoru
├── data/                     # Yerel veri dosyaları
│   ├── users.json
│   └── ninova_data.json
└── logs/                     # Log çıktıları
    └── app.log
```

---

## ⚖️ Lisans

Bu proje sadece eğitim amaçlıdır. Ninova sisteminin kullanım koşullarına uyulması kullanıcının sorumluluğundadır.
