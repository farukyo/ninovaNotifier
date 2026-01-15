# 🎓 Ninova Grade & Academic Tracking Bot

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html) [![CI](https://github.com/farukyo/ninovaNotifier/actions/workflows/ci.yml/badge.svg)](https://github.com/farukyo/ninovaNotifier/actions) [English Version](README_EN.md)

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
- **📈 Başarı Grafiği:** Notlarınızı çan eğrisi üzerinde görselleştirerek sınıf içindeki konumunuzu (Z-Score) gösterir.

### 🔔 Akıllı Bildirim Sistemi

- **Anlık Bildirimler:** Yeni not, duyuru, ödev veya dosya güncellemeleri için anında uyarı gönderir.
- **Ödev Hatırlatıcıları:** Ödev teslim tarihinden **24 saat** ve **3 saat** önce otomatik "Son Çağrı" bildirimleri gönderir.

### 📂 Dosya ve İçerik Erişimi

- **Gelişmiş Dosya Gezgini:** Karmaşık ve iç içe geçmiş klasör yapılarını destekler.
- **Doğrudan İndirme:** Kullanıcıların ders materyallerini doğrudan Telegram üzerinden indirmesine olanak tanır.

### 🐝 Arı24 Entegrasyonu

- **📰 Haberler:** İTÜ ile ilgili güncel haberleri takip edin. Yeni bir haber olduğunda **tüm kullanıcılara** otomatik bildirim gönderilir.
- **📅 Etkinlikler:** Kampüsteki tüm kulüp etkinliklerin keşfedin ve yaklaşan etkinlikleri listeleyin.
- **🔔 Kulüp Aboneliği:** İlgilendiğiniz kulüplere abone olarak sadece onların etkinliklerinden haberdar olun.
- **☀️ Günlük Bülten:** Her sabah 08:00'de o günün ve önümüzdeki haftanın etkinliklerini özet olarak alın.

### 🔔 Akıllı Bildirim Sistemi

- **Anlık Bildirimler:** Yeni not, duyuru, ödev veya dosya güncellemeleri için anında uyarı gönderir.
- **Ödev Hatırlatıcıları:** Ödev teslim tarihinden **24 saat** ve **3 saat** önce otomatik "Son Çağrı" bildirimleri gönderir.
- **Arı24 Bildirimleri:** Haberler ve abone olunan kulüp etkinlikleri için anlık bildirimler.

### 📂 Dosya ve İçerik Erişimi

- **Gelişmiş Dosya Gezgini:** Karmaşık ve iç içe geçmiş klasör yapılarını destekler.
- **Doğrudan İndirme:** Kullanıcıların ders materyallerini doğrudan Telegram üzerinden indirmesine olanak tanır.

### 🍴 Yemekhane Menü Duyuruları

- **Otomatik Duyurular:** Her gün **11:00** (Öğle Yemeği) ve **16:30** (Akşam Yemeği) saatlerinde İTÜ SKS yemekhane menüsünü otomatik olarak paylaşır.
- **Dinamik Veri Çekme:** Menü verilerini doğrudan İTÜ BIBD API üzerinden çekerek güncel ve temiz veri sağlar.
- **Akıllı Durum Yönetimi:** Duyuruların her gün ve her öğün için sadece bir kez gönderilmesini sağlar.
- **🔄 Anlık Güncelleme:** Telegram üzerinden tek tuşla o anki yemek menüsünü güncelleyebilirsiniz.

---

## 🛠 Teknik Yığın

- **Dil:** Python 3.14+
- **Bot Çatısı:** `pytelegrambotapi`
- **Kazıyıcı:** `requests` & `BeautifulSoup4`
- **Güvenlik:** `cryptography` (Fernet)
- **Test:** `pytest` & `pytest-cov`
- **Paket Yöneticisi:** `uv`
- **Linting:** `ruff`

### Proje Yapısı

```text
├── main.py                          # Uygulama giriş noktası ve Dashboard
├── bot/
│   ├── instance.py                  # Bot instance ve global değişkenler
│   ├── keyboards.py                 # Reply klavyeleri
│   ├── utils.py                     # Bot yardımcıları
│   └── handlers/
│       ├── admin/                   # Admin komut ve callback'leri
│       │   ├── commands.py
│       │   ├── callbacks.py
│       │   ├── course_management.py
│       │   ├── course_functions.py  # Ders yönetim yardımcıları
│       │   └── ...
│       └── user/                    # Kullanıcı komut ve callback'leri
│           ├── commands.py          # Ana import dosyası
│           ├── auth_commands.py     # Kullanıcı adı/şifre
│           ├── course_commands.py   # Ders yönetimi
│           ├── grade_commands.py    # Not/ödev listeleme
│           ├── general_commands.py  # Yardım, durum, arama
│           ├── ari24_commands.py    # Arı24 entegrasyonu
│           └── callbacks.py         # Inline callback handler'lar
├── services/
│   ├── ninova/                      # Ninova kazıma servisleri
│   │   ├── auth.py
│   │   ├── scraper.py
│   │   ├── scanner.py
│   │   └── file_utils.py
│   ├── sks/                         # Yemekhane menü servisi
│   │   ├── scraper.py
│   │   └── announcer.py
│   ├── ari24/                       # Arı24 servisi
│   │   └── client.py
│   └── calendar/                    # Akademik takvim
├── common/
│   ├── config.py                    # Yapılandırma ve sabitler
│   ├── cache.py                     # Dosya önbellekleme
│   └── utils.py                     # Genel yardımcılar
├── tests/                           # Unit ve entegrasyon testleri
└── .github/workflows/ci.yml         # GitHub Actions CI
```

---

## 🚀 Kurulum ve Çalıştırma

### 1. Gereksinimler

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) paket yöneticisi

### 2. Bağımlılıkları Yükleme

```bash
uv sync
```

### 3. Yapılandırma

`.env.example` dosyasını `.env` olarak kopyalayın:

```bash
cp .env.example .env
```

Gerekli değişkenler:
- `TELEGRAM_TOKEN`: BotFather'dan aldığınız API anahtarı
- `ADMIN_ID`: Yönetimsel işlemler için Telegram Sohbet ID'niz

### 4. Botu Başlatma

```bash
uv run main.py
```

---

## 🧑‍💻 Geliştirici Rehberi

### Geliştirme Ortamı Kurulumu

```bash
# Bağımlılıkları ve dev araçlarını yükle
uv sync --dev

# Pre-commit hook'larını etkinleştir
uv run pre-commit install
```

### Kod Kalite Araçları

```bash
# Linting
uv run ruff check .

# Otomatik düzeltme
uv run ruff check . --fix

# Formatlama
uv run ruff format .
```

### Testleri Çalıştırma

```bash
# Tüm testler
uv run pytest tests/ -v

# Coverage raporu
uv run pytest tests/ --cov=. --cov-report=html
```

### Pre-commit Hooks

Projede aşağıdaki pre-commit hook'ları yapılandırılmıştır:

- **detect-secrets**: Gizli bilgi tarama (Token leaks vb.)
- **detect-private-key**: Private key tespiti

### Ruff Kuralları

Aktif lint kuralları (`pyproject.toml`):

| Kod | Açıklama |
|-----|----------|
| E, W | pycodestyle hataları ve uyarıları |
| F | pyflakes (unused import vb.) |
| I | isort (import sıralaması) |
| B | flake8-bugbear (yaygın bug kalıpları) |
| C4 | flake8-comprehensions |
| UP | pyupgrade (Python modernizasyonu) |
| RET | flake8-return |
| ARG | flake8-unused-arguments |

### CI/CD

GitHub Actions ile her push ve PR'da otomatik olarak:
- Ruff lint kontrolü
- Ruff format kontrolü
- Pytest ile tüm testler çalıştırılır

---

## � Yol Haritası (TODO)

Proje için planlanan gelecek özellikler ve geliştirmeler [TODO.md](TODO.md) dosyasında takip edilmektedir.

---

## �📄 Lisans

Bu proje GNU General Public License sürüm 3 (GPLv3) altında lisanslanmıştır. Ayrıntılı lisans metni `LICENCE` dosyasında bulunmaktadır.
