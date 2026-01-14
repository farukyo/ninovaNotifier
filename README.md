# 🎓 Ninova Grade & Academic Tracking Bot

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html) [English Version](readme_en.md)  

ITU Ninova'daki notlarınızı, ödevlerinizi, duyurularınızı ve ders dosyalarınızı gerçek zamanlı izleyen ve Telegram üzerinden bildirim gönderen bir akademik asistan bottur.

---

## ✨ Öne Çıkan Özellikler

### 👥 Kullanıcı Yönetimi

- **Çoklu Kullanıcı Desteği:** Tek bir bot örneği üzerinden birden fazla kullanıcı kendi akademik verilerini bağımsız olarak takip edebilir.
- **Güvenli Doğrulama:** Ninova kimlik bilgileriniz yerel olarak saklanmadan önce AES-256 ile şifrelenir.
- **Oturum Yönetimi:** Kullanıcı bazlı oturum önbellekleme ile gereksiz giriş trafiği ve "çok fazla istek" sorunları azaltılır.

### 📊 Gelişmiş Not İstatistikleri

- **Sınıf Analizi:** Her ders için sınıf ortalamasını ve standart sapmayı otomatik olarak hesaplar.
- **Veri Kapsamı:** Hesaplamaların hangi oranda veriye dayandığını göstererek doğruluk payını belirtir.

### 🔔 Akıllı Bildirim Sistemi

- **Anlık Bildirimler:** Yeni not, duyuru, ödev veya dosya güncellemeleri için anında uyarı gönderir.
- **Ödev Hatırlatıcıları:** Ödev teslim tarihinden **24 saat** ve **3 saat** önce otomatik "Son Çağrı" bildirimleri gönderir.

### 📂 Dosya ve İçerik Erişimi

- **Gelişmiş Dosya Gezgini:** Karmaşık ve iç içe geçmiş klasör yapılarını destekler.
- **Doğrudan İndirme:** Kullanıcıların ders materyallerini doğrudan Telegram üzerinden indirmesine olanak tanır.

### 🤖 Otomasyon ve Geliştirici Araçları

- **Kapsamlı Testler:** `pytest` ile %90+ test kapsamına (coverage) sahiptir.
- **Rich Terminal UI:** Adminler için canlı istatistikler ve ilerleme çubukları gösterir.

---

## 🛠 Teknik Yığın

Proje, modern Python uygulama pratikleriyle modüler bir yapıda inşa edilmiştir:

- **Dil:** Python 3.14+
- **Bot Çatısı:** `pytelegrambotapi` (Async uyumlu)
- **Kazıyıcı:** `requests` & `BeautifulSoup4`
- **Güvenlik:** `cryptography` (Fernet)
- **Test:** `pytest` & `pytest-cov`
- **Paket Yöneticisi:** `uv`

### Proje Yapısı

```text
├── main.py              # Uygulama giriş noktası ve Gösterge Paneli
├── bot/                 # Telegram bot mantığı ve handler'lar
├── services/            # Ninova kazıma ve kimlik doğrulama
├── common/              # Ortak yardımcılar (şifreleme, cache vb.)
├── scripts/             # Geliştirici araçları (versiyonlama betiği)
├── tests/               # Unit ve entegrasyon testleri
├── data/                # Veri saklama (JSON - ignore edilir)
└── logs/                # Sistem günlükleri (ignore edilir)
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
