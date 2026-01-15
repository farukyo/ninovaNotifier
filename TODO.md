# 🚀 Gelecek Özellikler (Roadmap)

## Öncelikli Geliştirmeler

- [ ] **📅 Google Takvim Entegrasyonu** [🟡] Vazgeçildi*
  - Ninova'daki ödevlerin bitiş tarihlerini Google Takvim'e tek tuşla ekleme.
  - Ödev yüklendiğinde/tamamlandığında takvimden otomatik silme veya işaretleme.
  - Ders programını takvime senkronize etme.(sonra)

- [ ] **🎓 GPA Simülatörü** [🟡]
  - Derslerin kredi değerlerini (AKTS) çekme/tanımlama.
  - **Kaynak:** `https://obs.itu.edu.tr/public/DersPlan/` üzerinden ders kredileri kontrol edilebilir.
  - Tahmini harf notlarına göre dönem ve genel ortalama (AGNO) hesaplama simülasyonu.

- [ ] **📝 Sınav Takvimi (Final/Vize)** [🟡]
  - OBS üzerinden sınav tarihlerini otomatik çekme.
  - Sınav yaklaştığında hatırlatma bildirimi.

- [ ] **📢 SKS & Bölüm Duyuruları** [🟢]
  - İTÜ SKS ve fakülte/bölüm web sitelerinden duyuruların takibi.
  - Yeni duyuru yayınlandığında anlık bildirim.

- [ ] **🚪 Boş Sınıf Bulucu** [🟡]
  - Dersliklerin haftalık programını analiz etme.
  - Anlık olarak boş olan ve çalışılabilecek sınıfları listeleme.

- [ ] **🚌 Ring Saatleri** [🟢]
  - İTÜ kampüs içi ve kampüsler arası ring sefer saatleri.
  - (Opsiyonel) Canlı konum entegrasyonu (mümkünse).

- [ ] **🔔 Akademik Takvim Bildirimleri** [🟢]
  - Önemli akademiktakvim tarihlerini (ders kaydı, dersten çekilme vb.) 1 gün ve 1 hafta önceden otomatik bildirme.
  - Takvimdeki değişiklikleri periyodik kontrol ederek kullanıcıya duyurma.

- [ ] **🏹 SIS Kayıt Yardımcısı & Kontenjan Takibi** [🔴]
  - **Ders Planı Analizi:** `https://obs.itu.edu.tr/public/DersPlan/` üzerinden alınmış/alınmamış derslerin ve kredilerin takibi.
  - **CRN Takibi:** Belirlenen CRN'lerde kontenjan açıldığında (0 -> 1) anlık bildirim.
  - **Önşart Kontrolü:** Seçilen CRN'lerin önşartlarının (ders planı verisiyle) otomatik kontrol edilmesi.

- [ ] **🤖 Staj Bilgi Botu (AI Q&A)** [🔴]
  - Mevzuat verilerini (`sis.itu.edu.tr`) kullanarak staj kuralları hakkında öğrencilerin sorularını yanıtlama. https://ikm.itu.edu.tr/staj-merkezi/
  - Staj raporu formatı, tarihler ve sigorta gibi konularda anlık bilgi desteği.

- [ ] **📝 NotKutusu & HocaMetre Entegrasyonu** [🟡]
  - NotKutusu üzerinden ders notu arama ve HocaMetre üzerinden hoca yorumlarını görüntüleme. AI ile yorumlama

- [ ] **📰 Kampüs Nabzı (ARI24 Entegrasyonu)** [🟢]
  - Haber Duyuruları: ARI24 üzerinden en son İTÜ haberlerinin (başlık, özet ve resim) anlık bildirimi.
  - Kulüp Etkinlik Keşfeti: `/etkinlik` komutu ile yaklaşan etkinliklerin resimli olarak listelenmesi.
  - Kulüp Aboneliği: Kullanıcıların ilgilendiği kulüpleri seçip sadece o kulübün etkinliklerine abone olması.
  - Resimli Paylaşım: Etkinlik detaylarının afiş/resim ile birlikte Telegram üzerinden zengin içerikli gönderilmesi.

- [ ] **📧 İTÜ Webmail Asistanı** [🟡]
  - IMAP üzerinden yeni e-posta bildirimleri ve gelen kutusu özeti.

- [ ] **🎫 İTÜ Yardım (Ticket) Takibi** [🟡]
  - yardim.itu.edu.tr üzerindeki bilet durumlarının takibi ve anlık bildirim.

- [ ] **🪐 İTÜ Kepler Entegrasyonu** [🔴]
  - Yeni nesil SIS (Kepler) üzerinden devamsızlık, yoklama ve ders programı takibi.

- [ ] **📅 İTÜ Program Entegrasyonu (ituprogram.com)** [🟢]
  - Ders programı hazırlama ve paylaşma platformu ile entegrasyon.
  - Bot üzerinden hazır programı sorgulama veya takvime aktarma.
