# Ninova Notifier

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html)
[![CI](https://github.com/farukyo/ninovaNotifier/actions/workflows/ci.yml/badge.svg)](https://github.com/farukyo/ninovaNotifier/actions)
[English](README_EN.md)

Ninova Notifier, ITU Ninova üzerindeki akademik hareketleri Telegram'a taşıyan bir takip botudur.
Notlar, ödevler, dosyalar ve duyurular düzenli olarak taranır; değişiklik olduğunda kullanıcıya bildirim gönderilir.

## Neler Yapıyor?

- Çok kullanıcılı çalışma: Her kullanıcı kendi Ninova hesabını ayrı takip eder.
- Oturum ve hız optimizasyonu: Gereksiz login tekrarlarını azaltır.
- Bildirim sistemi: Yeni not, ödev, duyuru ve dosya güncellemelerinde uyarı verir.
- Dosya erişimi: Ders dosyalarını Telegram üzerinden listeleyip indirmeye izin verir.
- İstatistik ekranı: Admin panelinden anlık kaynak kullanımı ve sistem durumunu gösterir.
- Ek entegrasyonlar: Arı24 haber/etkinlik takibi ve SKS yemekhane menüsü desteği.

## Teknik Özet

- Python: 3.12+
- Bot: pytelegrambotapi
- Ağ/Scraping: requests, BeautifulSoup4
- Güvenlik: cryptography
- Veri/yardımcılar: sqlalchemy, numpy, scipy, matplotlib
- Paket yönetimi: uv
- Kalite araçları: ruff, pytest, detect-secrets

## Hızlı Kurulum

1. Bağımlılıkları kur:

```bash
uv sync
```

2. Ortam dosyasını oluştur:

```bash
cp .env.example .env
```

PowerShell kullanıyorsanız:

```powershell
Copy-Item .env.example .env
```

3. En az şu değişkenleri doldur:

- TELEGRAM_TOKEN
- ADMIN_ID

4. Botu başlat:

```bash
uv run main.py
```

## Geliştirici Akışı

```bash
uv sync --dev
uv run ruff check .
uv run ruff format .
uv run pytest -v
```

## Release Süreci

Versiyon artırımı normal commit ile otomatik yapılmaz.
Release, GitHub Actions üzerinden manuel tetiklenir.

- Workflow: .github/workflows/release.yml
- Seçenekler: patch/minor/major veya doğrudan version
- Sonuç: pyproject.toml güncellenir, tag oluşturulur, GitHub Release açılır

## Proje Dosyaları

- Uygulama başlangıcı: main.py
- Bot handler'ları: bot/handlers
- Servis katmanı: services
- Ortak yardımcılar: common
- İş akışları: .github/workflows

## Lisans

Bu proje GPLv3 lisansı ile dağıtılır. Ayrıntı için LICENCE dosyasına bakın.
