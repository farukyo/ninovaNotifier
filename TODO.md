# 🛠️ Teknik Borç ve Stabilite

> PR #3 (stabilite, veri bütünlüğü, güvenlik, yük, CI/CD ve mimari temizlik) sonrası kalan işler.
> Ayrıntılı gerekçeler için PR #3 açıklamasına ve `.claude/commands` altındaki komutlara bakın.

## 🚀 Canlıya Alma (PR #3 merge edildi, deploy bekliyor)

- [ ] Branch'i locale çekip dene: "🔐 Giriş Yap" (doğru/yanlış şifre), "🔄 Kontrol", bildirimdeki "📥 İndir".
- [ ] Sunucu açılınca deploy et (yedek + sağlık kontrolü + otomatik geri alma bu yoldan çalışır):
  - `production` environment'ında Required reviewers açıksa: Actions → bekleyen deploy → **Approve and deploy**
    (onay 30 gün bekler).
  - Açık değilse deploy job'u sunucuya bağlanamayıp başarısız olur: Actions → son `main` CI çalıştırması →
    **Re-run failed jobs**. Alternatif elle komut README'de.
- [ ] İlk deploy'da CI log'unu kontrol et: `~/ninova-backups/` altında yedek, "Deploy OK." satırı.
- [ ] Sunucuda `python3` olduğunu doğrula (yoksa sağlık kontrolü uyarı verip atlanır).
- [ ] Sunucudaki git dizininin temiz olduğunu doğrula (deploy `git pull --ff-only` kullanıyor).
- [ ] (Opsiyonel) Settings → Environments → `production` → Required reviewers: her deploy onay beklesin.
- [ ] `ENCRYPTION_KEY` / `secrets/.encryption_key` yedeğini sunucu dışında sakla.

## 🔴 Yüksek Öncelik (küçük işler, sonraki PR)

- [ ] **Kalan eski-kopya (stale) URL yazmaları → `modify_user`**
  - `bot/handlers/user/course_commands.py` (oto ders), `bot/handlers/admin/callbacks.py` (admin forceoto),
    `bot/handlers/user/callbacks.py` (elle ders ekleme): uzun taramadan sonra eski listeyle `update_user_data(..., "urls", ...)`.
    Tarama sırasında silinen ders geri gelebilir. `list(set(...))` ders sırasını da karıştırıyor.
  - Araç: `/stale-write-scan`
- [ ] **Kaçışsız HTML** — ders/ödev adları (`grade_commands.py`), kullanıcı adları, takvim olayları,
      dosya tarayıcısı (`bot/utils.py`). `&` veya `<` içeren bir ad mesajın hiç gitmemesine yol açar.
  - Araç: `/html-escape-audit`
- [ ] **Kullanıcıya ham hata metni (`str(e)`) gönderilmesin** (6 yer: `general_commands.py:425`,
      grafik hatası `callbacks.py`, admin servisleri…). Kullanıcıya genel mesaj, ayrıntı `logger.exception` ile loga.

## 🟠 Orta Öncelik

- [ ] **Dosya indirme sınırları** (`services/ninova/file_utils.py`): boyut kontrolü yok (Telegram 50 MB),
      dosya tamamen bellekte tutuluyor, stream edilen yanıt kapatılmıyor, dosya adı caption'da kaçırılmıyor.
- [ ] **Admin onayları**: yedek alma (`users.json` şifreli parolalarla Telegram'a gidiyor) ve yeniden başlatma
      tek dokunuşla çalışıyor. Onay adımı + yedekte parola alanlarını çıkarma.
- [ ] **Grafik modülü** (`services/visualization.py`): pyplot thread-safe değil, hata durumunda figure sızıntısı;
      sadece `norm` için `scipy` bağımlılığı (`math.erf` ile değiştirilebilir).
- [ ] **Log temizliği** sadece başlangıçta çalışıyor; uzun süren süreçte eski loglar birikiyor.
- [ ] **Scheduler**: `submit` exception fırlatırsa semafor izni geri verilmiyor (`core/scheduler.py`).
- [ ] **Eski/erişilemeyen dersler**: 302 yönlendirmesi login dışına gidiyorsa `SESSION_ERROR` sayılıp kullanıcıya
      yanlışlıkla "şifreni kontrol et" gidebilir (doğrulanmadı — gerçek sayfa lazım).

## 🧪 Test

- [ ] **Gerçek Ninova sayfalarıyla parser testleri** — tarayıcıdan "Farklı kaydet → HTML" ile kaydet, `/ninova-fixture`
      ile anonimleştirip teste çevir: not sayfası, ödev listesi, ödev detayı, dosyalar, duyuru, erişimi kalmamış eski ders.
- [ ] **Coverage %43 → hedef %60+** — en düşükler: handler'lar (%11–18), Rehber/takvim/Arı24 servisleri,
      `visualization.py` (%0). Araç: `/test-gap <modül>`.
- [ ] CI'da coverage raporu ve kademeli eşik.

## 🔵 Uzun Vade (mimari)

- [ ] Çok uzun fonksiyonları böl: `handle_admin_callbacks` (~330 satır, sözlük tabanlı dağıtıcı),
      `compare_course_data` (~385 satır, bölüm başına fonksiyon), `trigger_auto_add_courses`, `get_grades`.
- [ ] JSON dosyalarından **SQLite**'a geçiş (kullanıcı başına satır, transaction; veri ezme sınıfı hatalar kökten biter).
- [ ] Veri modelleri için dataclass/TypedDict + kademeli `mypy`.
- [ ] Scraping'de "çek" ve "ayrıştır" adımlarını ayır (test edilebilirlik).
- [ ] Kontrol döngüsü süresini ölç/logla; aralığı aşarsa uyar. Gerekirse kullanıcılar arası paralellik.
- [ ] Python sürüm hedefini netleştir (`.python-version` 3.14, `requires-python >=3.12`).

---

# 🚀 Gelecek Özellikler (Roadmap)

## Öncelikli Geliştirmeler

- [ ] **🎓 GPA Simülatörü & Transkript Analizi**
  - Derslerin kredi değerlerini (AKTS) çekme/tanımlama.
  - **Kaynak:** `https://obs.itu.edu.tr/public/DersPlan/` üzerinden ders kredileri kontrol edilebilir.
  - Tahmini harf notlarına göre dönem ve genel ortalama (AGNO) hesaplama simülasyonu.
  - (OBS) Gerçek transkriptteki harf notlarını çekip güncel AGNO analizini canlı sağlama.

- [ ] **📝 Sınav Takvimi (Final/Vize)**
  - OBS üzerinden resmi sınav programını otomatik çekme: gün, saat, bina ve sıra numarası (koltuk no).
  - Sınav yaklaştığında hatırlatma bildirimi.

- [ ] **📢 SKS & Bölüm Duyuruları**
  - İTÜ SKS ve fakülte/bölüm web sitelerinden duyuruların takibi.
  - Yeni duyuru yayınlandığında anlık bildirim.

- [ ] **🚪 Boş Sınıf Bulucu**
  - Dersliklerin haftalık programını analiz etme.
  - Anlık olarak boş olan ve çalışılabilecek sınıfları listeleme.

- [ ] **🚌 Ring Saatleri**
  - İTÜ kampüs içi ve kampüsler arası ring sefer saatleri.
  - (Opsiyonel) Canlı konum entegrasyonu (mümkünse).

- [ ] **🏹 SIS Kayıt Yardımcısı & Kontenjan Takibi**
  - **Ders Planı Analizi:** `https://obs.itu.edu.tr/public/DersPlan/` üzerinden alınmış/alınmamış derslerin ve kredilerin takibi.
  - **CRN Takibi:** Belirlenen CRN'lerde kontenjan açıldığında (0 -> 1) anlık bildirim (kayıt döneminde hızlı kapanmadan yetişecek şekilde).
  - **Önşart Kontrolü:** Seçilen CRN'lerin önşartlarının (ders planı verisiyle) otomatik kontrol edilmesi.

- [ ] **📅 Ders Programı Asistanı**
  - Sabah saatlerinde günlük ders programı özeti (saat ve sınıf).
  - İTÜ Program (ituprogram.com) entegrasyonu: hazır programı sorgulama veya bota aktarma.

- [ ] **🤖 Staj Bilgi Botu (AI Q&A)** [🔴]
  - Mevzuat verilerini (`sis.itu.edu.tr`) kullanarak staj kuralları hakkında öğrencilerin sorularını yanıtlama. https://ikm.itu.edu.tr/staj-merkezi/
  - Staj raporu formatı, tarihler ve sigorta gibi konularda anlık bilgi desteği.

- [ ] **📝 NotKutusu & HocaMetre Entegrasyonu** [🟡]
  - NotKutusu üzerinden ders notu arama ve HocaMetre üzerinden hoca yorumlarını görüntüleme. AI ile yorumlama

- [ ] **📧 İTÜ Webmail Asistanı**
  - IMAP üzerinden yeni e-posta bildirimleri ve gelen kutusu özeti.

- [ ] **🎫 İTÜ Yardım (Ticket) Takibi**
  - yardim.itu.edu.tr üzerindeki bilet durumlarının takibi ve anlık bildirim.

- [ ] **🪐 İTÜ Kepler Entegrasyonu**
  - Yeni nesil SIS (Kepler) üzerinden devamsızlık, yoklama ve ders programı takibi.

- [ ] **📌 Ninova Ekstraları**
  - Devamsızlık / Yoklama listesi durum takibi.
  - Mesaj ve tartışma panosunda (Forum) açılan yeni başlıkların bildirimi.

## ✅ Tamamlananlar

- [x] **📌 İTÜ Rehber Asistanı** — personel dizininden e-posta, dahili numara ve birim bilgisi ("📞 İTÜ Rehber" menüsü).

## ❌ Vazgeçilenler

- **📅 Google Takvim Entegrasyonu** — ödev bitiş tarihlerini Google Takvim'e ekleme / ders programı senkronizasyonu.
