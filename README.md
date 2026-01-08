# 🎓 Ninova Grade & Academic Tracking Bot

[EN](readme_en.md)  [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html)

ITU Ninova'daki notlarınızı, ödevlerinizi, duyurularınızı ve ders dosyalarınızı gerçek zamanlı izleyen ve Telegram üzerinden bildirim gönderen bir akademik asistan bottur.

---

## ✨ Öne Çıkan Özellikler

### 👥 Kullanıcı Yönetimi

- **Çoklu Kullanıcı Desteği:** Tek bir bot örneği üzerinden birden fazla kullanıcı kendi akademik verilerini bağımsız olarak takip edebilir.
- **Güvenli Doğrulama:** Ninova kimlik bilgileriniz yerel olarak saklanmadan önce AES-256 ile şifrelenir.
- **Oturum Yönetimi:** Kullanıcı bazlı oturum önbellekleme ile gereksiz giriş trafiği ve "çok fazla istek" sorunları azaltılır.

### 🔔 Akıllı Bildirim Sistemi

- **Anlık Bildirimler:** Yeni not, duyuru, ödev veya dosya güncellemeleri için anında uyarı gönderir.
- **Ödev Hatırlatıcıları:** Ödev teslim tarihinden **24 saat** ve **3 saat** önce otomatik "Son Çağrı" bildirimleri gönderir.

### 📂 Dosya ve İçerik Erişimi

- **Gelişmiş Dosya Gezgini:** Karmaşık ve iç içe geçmiş klasör yapılarını destekler.
- **Doğrudan İndirme:** Kullanıcıların ders materyallerini doğrudan Telegram üzerinden indirmesine olanak tanır.
- **Akıllı Arama:** Kaydedilmiş duyurular içinde anahtar kelimeye dayalı arama imkanı sağlar.

### 🤖 Otomasyon ve Arayüz

- **Otomatik Ders Keşfi:** `otoders` komutuyla Ninova'daki tüm derslerinizi otomatik olarak bulur ve ekler.
- **Etkileşimli Menü:** Kullanıcı dostu Reply ve Inline klavyelerle hızlı gezinme sağlar.
- **Rich Terminal UI:** Adminler için `rich` destekli gösterge paneliyle canlı istatistikler ve ilerleme çubukları gösterir.

---

## 🛠 Teknik Yığın

Proje, modern Python uygulama pratikleriyle modüler bir yapıda inşa edilmiştir:

- **Dil:** Python 3.14+
- **Bot Çatısı:** `pytelegrambotapi` (Async uyumlu)
- **Kazıyıcı:** `requests` & `BeautifulSoup4`
- **Güvenlik:** `cryptography` (Fernet)
- **Arayüz:** `rich` (Terminal Gösterge Paneli)
- **Paket Yöneticisi:** `uv`

### Proje Yapısı

```text
├── main.py              # Uygulama giriş noktası ve Gösterge Paneli
├── bot/                 # Telegram bot mantığı
│   ├── handlers/        # Komut ve callback handler'ları
│   └── keyboards.py     # Klavye arayüzleri
├── services/            # Temel servisler
│   └── ninova/          # Ninova kazıma ve kimlik doğrulama mantığı
├── common/              # Ortak yapılandırmalar ve yardımcılar
├── data/                # Veri saklama (JSON tabanlı)
└── logs/                # Sistem günlükleri
```

---

## 🚀 Kurulum ve Çalıştırma

### 1. Gereksinimler

Sisteminizde Python 3.14+ ve `uv` yüklü olmalıdır.

### 2. Bağımlılıkları Yükleme

```bash
uv sync
```

### 3. Yapılandırma

`.env.example` dosyasını `.env` olarak kopyalayın ve gerekli bilgileri doldurun:

- `TELEGRAM_TOKEN`: BotFather'dan aldığınız API anahtarı.
- `ADMIN_ID`: Yönetimsel işlemler için Telegram Sohbet ID'niz.

### 4. Botu Başlatma

Sistemi başlatmak için:

```bash
uv run main.py
```

---

## 📄 Lisans

Bu proje GNU General Public License sürüm 3 (GPLv3) altında lisanslanmıştır. Ayrıntılı lisans metni `LICENCE` dosyasında bulunmaktadır.
