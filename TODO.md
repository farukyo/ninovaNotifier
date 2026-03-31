# 🚀 Gelecek Özellikler (Roadmap)

## Öncelikli Geliştirmeler

- [ ] **📅 Google Takvim Entegrasyonu** Vazgeçildi*
  - Ninova'daki ödevlerin bitiş tarihlerini Google Takvim'e tek tuşla ekleme.
  - Ödev yüklendiğinde/tamamlandığında takvimden otomatik silme veya işaretleme.
  - Ders programını takvime senkronize etme.(sonra)

- [ ] **🎓 GPA Simülatörü**
  - Derslerin kredi değerlerini (AKTS) çekme/tanımlama.
  - **Kaynak:** `https://obs.itu.edu.tr/public/DersPlan/` üzerinden ders kredileri kontrol edilebilir.
  - Tahmini harf notlarına göre dönem ve genel ortalama (AGNO) hesaplama simülasyonu.

- [ ] **📝 Sınav Takvimi (Final/Vize)**
  - OBS üzerinden sınav tarihlerini otomatik çekme.
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
  - **CRN Takibi:** Belirlenen CRN'lerde kontenjan açıldığında (0 -> 1) anlık bildirim.
  - **Önşart Kontrolü:** Seçilen CRN'lerin önşartlarının (ders planı verisiyle) otomatik kontrol edilmesi.

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

- [ ] **📅 İTÜ Program Entegrasyonu (ituprogram.com)**
  - Ders programı hazırlama ve paylaşma platformu ile entegrasyon.
  - Bot üzerinden hazır programı sorgulama veya takvime aktarma.

- [ ] **📌 Ninova Ekstraları**
  - Devamsızlık / Yoklama listesi durum takibi.
  - Mesaj ve tartışma panosunda (Forum) açılan yeni başlıkların bildirimi.

- [ ] **📌 OBS Entegrasyonları (Premium Özellikler)**
  - Resmi Sınav Programı: Vize/Final gün, saat, bina ve sıra numaralarının (Koltuk No) çekilmesi ve hatırlatıcı.
  - Ders Programı Asistanı: Sabah saatlerinde günlük ders programı özeti (Saat ve Sınıf).
  - Gerçek Transkript ve AGNO Analizi: Harf notlarını çekip güncel transkript analizini ve AGNO'yu canlı sağlamak.
  - CRN & Ders Kayıt Alarmı: Ders kayıt dönemlerinde istenen CRN'de kontenjan açıldığında anında uyarı. (Hızlı kapanmadan bot yetişecek).

- [ ] **📌 İTÜ Rehber Asistanı (rehber.itu.edu.tr)**
  - İTÜ personel dizininden hızlı iletişim bilgisi çekme: Bota `/rehber Ali Veli` yazıldığında E-posta adresi, Dahili Numara ve Ofis Oda Numarası getirilmesi.
