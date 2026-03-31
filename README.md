# Ninova Notifier

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html)
[![CI](https://github.com/farukyo/ninovaNotifier/actions/workflows/ci.yml/badge.svg)](https://github.com/farukyo/ninovaNotifier/actions)
[English](README_EN.md)

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

# 3. secrets/.env dosyasını düzenle
#    TELEGRAM_TOKEN=...
#    ADMIN_TELEGRAM_ID=...

# 4. Botu başlat
uv run main.py
```

> Bot token'ı [@BotFather](https://t.me/BotFather)'dan, Telegram ID'ni [@userinfobot](https://t.me/userinfobot)'tan alabilirsin.

## Geliştirici Kurulumu

```bash
# Geliştirme bağımlılıklarıyla kur
uv sync --dev

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Testleri çalıştır
uv run pytest -v

# Tek bir test dosyasını çalıştır
uv run pytest tests/test_foo.py -v

# Gizli tarama
uv run detect-secrets scan --baseline .secrets.baseline
```

Pre-commit hook'ları ilk kurulumda otomatik devreye girer. `secrets/` ve `data/` dizinleri `.gitignore`'dadır — asla commit'leme.

## Proje Yapısı

```
main.py              # Giriş noktası; polling + arka plan döngüsü
bot/
  handlers/          # Telegram komut ve callback handler'ları
  keyboards.py       # Inline klavye şablonları
services/
  ninova/            # Ninova oturum açma ve scraping
  sks/               # Yemekhane menüsü
  ari24/             # Haberler ve etkinlikler
common/
  config.py          # Ortam değişkenleri ve global ayarlar
  session.py         # HTTP oturum havuzu
  cache_manager.py   # LRU + TTL önbellek
  background_tasks.py# Paralel kullanıcı kontrolü
```

## Release

Versiyon artırımı normal commit'lerde otomatik yapılmaz. Release GitHub Actions üzerinden manuel tetiklenir.

- Workflow: `.github/workflows/release.yml`
- Girdi: `patch` / `minor` / `major` veya doğrudan versiyon numarası
- Çıktı: `pyproject.toml` güncellenir, tag oluşturulur, GitHub Release açılır

## SSS

**Bot başlamıyor, ne yapmalıyım?**
`secrets/.env` dosyasının var olduğunu ve `TELEGRAM_TOKEN` ile `ADMIN_TELEGRAM_ID` değerlerinin doğru girildiğini kontrol et.

**Bildirimler ne sıklıkla geliyor?**
Varsayılan kontrol aralığı 5 dakikadır. `CHECK_INTERVAL` ortam değişkeniyle saniye cinsinden değiştirilebilir.

**Ninova şifrem nerede saklanıyor?**
Şifreler Fernet şifrelemesiyle `data/` dizininde saklanır. Şifreleme anahtarı `secrets/.encryption_key` dosyasındadır.

**Birden fazla kullanıcı aynı botu kullanabilir mi?**
Evet. Her kullanıcı `/start` komutuyla kendi Ninova hesabını bağlar ve bağımsız olarak takip edilir.

**Yeni bir özellik eklemek istiyorum.**
Fork'la, feature branch'i aç, testleri yaz ve PR gönder. Kod stili için `ruff` kullanılıyor.

## Lisans

GPLv3. Ayrıntılar için [LICENCE](LICENCE) dosyasına bak.
