# Ninova Notifier

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html)
[![CI](https://github.com/farukyo/ninovaNotifier/actions/workflows/ci.yml/badge.svg)](https://github.com/farukyo/ninovaNotifier/actions)
[English](readme_en.md)

ITU Ninova'daki akademik değişiklikleri Telegram üzerinden takip eden bir bot. Not, ödev, duyuru ve dosya güncellemelerinde anında bildirim gönderir.

## Özellikler

- Not, ödev, duyuru ve dosya değişikliklerinde bildirim
- Ders dosyalarını Telegram'dan listeleme ve indirme
- Çok kullanıcılı destek — herkes kendi hesabını takip eder
- SKS yemekhane menüsü ve Arı24 haber/etkinlik entegrasyonu
- Admin paneli: sistem durumu ve kaynak kullanımı

## Kurulum

**Gereksinimler:** Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
# 1. Bağımlılıkları kur
uv sync

# 2. Ortam dosyasını oluştur
cp secrets/.env.example secrets/.env

# 3. secrets/.env dosyasını düzenle (değişkenler aşağıdaki tabloda)

# 4. Botu başlat
uv run main.py
```

> Bot token'ı [@BotFather](https://t.me/BotFather)'dan, Telegram ID'ni [@userinfobot](https://t.me/userinfobot)'tan alabilirsin.

### Ortam değişkenleri (`secrets/.env`)

| Değişken | Zorunlu | Açıklama |
|---|---|---|
| `TELEGRAM_TOKEN` | Evet | BotFather'dan alınan bot token'ı (`TOKEN` da kabul edilir). Tanımlı değilse bot başlamaz. |
| `ADMIN_TELEGRAM_ID` | Hayır | Admin kullanıcı ID'si. Birden fazla admin için virgülle ayır: `111,222`. Admin paneli sadece bu kullanıcılarla **özel sohbette** çalışır. |
| `ENCRYPTION_KEY` | Hayır | Ninova şifrelerini şifrelemek için Fernet anahtarı. Verilmezse `secrets/.encryption_key` otomatik oluşturulur. |

> ⚠️ **Şifreleme anahtarını yedekle.** `ENCRYPTION_KEY` veya `secrets/.encryption_key` kaybolursa kayıtlı tüm Ninova şifreleri çözülemez ve kullanıcıların yeniden giriş yapması gerekir.

Kontrol aralığı (5 dk) şu an ortam değişkeni değil, `core/config.py` içindeki `CHECK_INTERVAL` sabitidir.

## Geliştirici Kurulumu

```bash
# Geliştirme bağımlılıklarıyla kur
uv sync --dev

# Git hook'larını kur (ruff + gizli bilgi taraması her commit'te çalışır)
uv run pre-commit install

# Lint ve format
uv run ruff check .
uv run ruff format .

# Testleri çalıştır (gerçek token veya Ninova erişimi gerekmez)
uv run pytest -q

# Tek bir test dosyasını çalıştır
uv run pytest tests/test_storage.py -v

# Gizli bilgi taraması (CI ile aynı)
uv run detect-secrets-hook --baseline .secrets.baseline $(git ls-files)
```

`secrets/` ve `data/` dizinleri `.gitignore`'dadır — asla commit'leme.

## Proje Yapısı

```
main.py                 # Giriş noktası: Telegram polling thread'i + periyodik kontrol döngüsü
                        # (not/ödev/dosya/duyuru karşılaştırma ve bildirimler)
bot/
  instance.py           # TeleBot nesnesi ve global hata yakalayıcı
  handlers/user/        # Kullanıcı komutları ve callback'leri
  handlers/admin/       # Admin paneli (duyuru, yedek, log, ders yönetimi)
  keyboards/            # Reply/inline klavyeler
  callback_parsing.py   # callback_data ayrıştırma, indirme butonu token'ları
core/
  config.py             # Ortam değişkenleri, şifreleme, sabitler
  storage.py            # users.json / ninova_data.json için kilitli, atomik okuma-yazma
  http_client.py        # Kullanıcı başına requests.Session havuzu
  error_tracker.py      # Ardışık Ninova hatalarını sayar, admin/kullanıcıyı bilgilendirir
  scheduler.py          # Sınırlı arka plan görev kuyruğu
  ttl_cache.py          # Dış servis sonuçları için kısa süreli önbellek
  logger.py             # JSON log dosyaları, token maskeleme
services/
  ninova/               # Giriş (auth.py) ve scraping (scraper.py)
  sks/                  # Yemekhane menüsü ve duyurusu
  ari24/                # Arı24 haber/etkinlik/kulüpler
  rehber/               # İTÜ Rehber araması
  calendar/             # Akademik takvim
tests/                  # pytest testleri
```

Çalışma zamanında oluşan dosyalar (hepsi `.gitignore`'da):

| Dosya | İçerik |
|---|---|
| `data/users.json` | Kullanıcılar, şifrelenmiş Ninova şifreleri, takip edilen dersler |
| `data/ninova_data.json` | Derslerin son kaydedilen hali (değişiklik tespiti buna göre yapılır) |
| `data/error_tracker.json`, `data/file_cache.json`, `data/*_state.json` | Hata sayaçları, Telegram dosya önbelleği, Arı24/SKS/bülten durumları |
| `logs/app_YYYY-MM-DD.log` | JSON satırları halinde günlük loglar (30 gün tutulur) |

## CI/CD ve Deploy

> ⚠️ **`main`'e yapılan her push canlıya gider.** PR'ları önce locale çekip deneyin.

`.github/workflows/ci.yml`:

1. **Lint:** ruff check, ruff format ve gizli bilgi taraması.
2. **Test:** Python 3.12 ve 3.14 üzerinde pytest.
3. **Patch bump & lock sync** (sadece `main` push'unda): patch sürümü artırılır, `uv.lock` güncellenir, `chore(release): vX.Y.Z [skip ci]` commit'i ve tag'i `main`'e push'lanır, GitHub Release oluşturulur.
4. **Deploy** (sadece `main` push'unda, `production` environment'ı): SSH ile VPS'e bağlanılır ve şu adımlar çalışır:
   - `data/` ve `secrets/` `~/ninova-backups/` altına yedeklenir (son 20 yedek tutulur).
   - `git pull --ff-only`, `uv sync` ve `pm2 restart ninova-bot` çalışır.
   - 20 saniye sonra bot online değilse ya da kendiliğinden yeniden başlıyorsa önceki commit'e otomatik dönülür ve job başarısız olur.

Gerekli repo secret'ları: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_APP_PATH`. Her deploy'un onay beklemesini istersen: **Settings → Environments → production → Required reviewers**.

Minor/major sürüm için: **Actions → Release → Run workflow** (`.github/workflows/release.yml`). Bu workflow testleri çalıştırır ve tag + GitHub Release oluşturur. Deploy etmez.

Sunucu kapalıyken merge edilirse deploy job'u başarısız olur. Sunucu açıldığında şunu elle çalıştır:

```bash
cd <uygulama dizini> && git pull --ff-only origin main && ~/.local/bin/uv sync && pm2 restart ninova-bot
```

## SSS

**Bot başlamıyor, ne yapmalıyım?**
`secrets/.env` dosyasının var olduğunu ve `TELEGRAM_TOKEN` değerinin doğru olduğunu kontrol et. Hata ayrıntıları `logs/` altındaki günlük log dosyasında ve `pm2 logs ninova-bot` çıktısında görünür.

**Bildirimler ne sıklıkla geliyor?**
Kontrol döngüsü yaklaşık 5 dakikada bir çalışır. Ödev detay sayfaları Ninova'yı yormamak için daha seyrek yenilenir: teslimi devam eden ödevlerde 30 dakikada bir, süresi geçmişlerde günde bir. Ödev listesinde bir değişiklik olduğunda (ör. teslim ettiğinde) ise hemen yenilenir.

**Ninova şifrem nerede saklanıyor?**
Fernet ile şifrelenmiş olarak `data/users.json` içinde saklanır. Anahtar `ENCRYPTION_KEY` ortam değişkeninden veya `secrets/.encryption_key` dosyasından okunur.

**Birden fazla kullanıcı aynı botu kullanabilir mi?**
Evet. Her kullanıcı "🔐 Giriş Yap" ile kendi Ninova hesabını bağlar ve bağımsız olarak takip edilir.

**Botu locale çalıştırırken dikkat etmem gereken bir şey var mı?**
Aynı token'la iki bot aynı anda çalışamaz (Telegram birini reddeder). Sunucudaki bot açıksa locale test için ayrı bir test botu (BotFather'dan) kullan.

**Yeni bir özellik eklemek istiyorum.**
Fork'la, feature branch'i aç, testleri yaz ve PR gönder. Kod stili için `ruff` kullanılıyor.

## Lisans

GPLv3. Ayrıntılar için [LICENCE](LICENCE) dosyasına bak.
