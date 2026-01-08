import re
import logging
from bs4 import BeautifulSoup
from common.config import console
from .auth import LoginFailedError, login_to_ninova

logger = logging.getLogger("ninova")


def get_announcements(session, base_url):
    """
    Sınıf duyurularını çeker.

    Ninova'nın HTML yapısından duyuruları parse eder:
    - Başlık ve link
    - Tarih ve yazar
    - İçerik önizlemesi

    :param session: requests.Session nesnesi
    :param base_url: Ders ana sayfa URL'i
    :return: Duyuru listesi (dict), boş liste hata durumunda

    HTML yapısı:
    <div class="duyuruGoruntule">
        <h2><a href="/Sinif/.../Duyuru/590536">Title</a></h2>
        <div class="tarih"><span class="tarih">03 Ocak 2026 16:53</span></div>
        <div class="icerik">Content preview...</div>
        <div class="tarih"><span class="tarih">Author Name</span></div>
    </div>
    """
    url = f"{base_url}/Duyurular"
    try:
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        announcements = []

        # duyuruGoruntule div'lerini bul
        ann_divs = soup.find_all("div", class_="duyuruGoruntule")

        for ann_div in ann_divs:
            try:
                # Başlık ve link
                h2 = ann_div.find("h2")
                if not h2:
                    continue
                a_tag = h2.find("a")
                if not a_tag:
                    continue

                title = a_tag.get_text(strip=True)
                href = a_tag.get("href", "")
                link = (
                    f"https://ninova.itu.edu.tr{href}" if href.startswith("/") else href
                )
                ann_id = href.split("/")[-1] if href else ""

                # Tarih ve yazar (tarih div'leri)
                tarih_divs = ann_div.find_all("div", class_="tarih")
                date_str = ""
                author = ""

                if len(tarih_divs) >= 1:
                    date_span = tarih_divs[0].find("span", class_="tarih")
                    if date_span:
                        date_str = date_span.get_text(strip=True)

                if len(tarih_divs) >= 2:
                    author_span = tarih_divs[-1].find("span", class_="tarih")
                    if author_span:
                        author = author_span.get_text(strip=True)

                # İçerik önizlemesi
                content_div = ann_div.find("div", class_="icerik")
                content_preview = (
                    content_div.get_text(strip=True) if content_div else ""
                )

                announcements.append(
                    {
                        "id": ann_id,
                        "title": title,
                        "url": link,
                        "author": author,
                        "date": date_str,
                        "content": content_preview,
                    }
                )
            except Exception as e:
                logger.debug(f"Duyuru parse hatası: {e}")
                continue

        return announcements
    except Exception as e:
        console.print(f"[bold red]Duyuru çekme hatası: {e}")
        return []


def get_announcement_detail(session, url):
    """
    Duyuru içeriğini detay sayfasından çeker.

    Duyurunun tam içeriğini almak için duyuru detay sayfasını parse eder.

    :param session: requests.Session nesnesi
    :param url: Duyuru detay sayfasının URL'i
    :return: Duyuru içeriği (string), boş string hata durumunda

    HTML yapısı:
    <div class="duyuruGoruntule">
        <div class="icerik">Full content here...</div>
    </div>
    """
    try:
        response = session.get(url, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Önce duyuruGoruntule içindeki icerik div'ini dene
            duyuru_div = soup.find("div", class_="duyuruGoruntule")
            if duyuru_div:
                content_div = duyuru_div.find("div", class_="icerik")
                if content_div:
                    for junk in content_div.find_all(["script", "style"]):
                        junk.decompose()

                    # Normalize anchor hrefs to absolute URLs and preserve anchors
                    for a in content_div.find_all("a", href=True):
                        href = a.get("href", "")
                        if href.startswith("/"):
                            a["href"] = f"https://ninova.itu.edu.tr{href}"

                    # Build HTML fragment from content_div while keeping basic formatting
                    # Replace <strong>/<em> with <b>/<i> for Telegram HTML compatibility
                    html = "".join(str(child) for child in content_div.contents)
                    html = html.replace("<strong>", "<b>").replace("</strong>", "</b>")
                    html = html.replace("<em>", "<i>").replace("</em>", "</i>")
                    return html.strip()

            # Eski format için yedek
            content_div = soup.find(
                "div", {"id": "ctl00_ContentPlaceHolder1_divIcerik"}
            )
            if content_div:
                for junk in content_div.find_all(["script", "style"]):
                    junk.decompose()
                return content_div.get_text("\n", strip=True)
    except Exception as e:
        console.print(f"[bold red]Duyuru detayı çekme hatası: {e}")
    return ""


def get_assignment_detail(session, url):
    """
    Ödev detay sayfasından tarih ve teslim bilgilerini çeker.

    Ödevin başlangıç tarihi, bitiş tarihi ve teslim durumunu parse eder.

    :param session: requests.Session nesnesi
    :param url: Ödev detay sayfasının URL'i
    :return: Ödev detayları dict'i (start_date, end_date, is_submitted) veya None

    HTML yapısı:
    - Tarihler: <span class="title_field">Teslim Bitişi</span><span class="data_field">26 Aralık 2025 23:59</span>
    - Teslim edilmiş: id="ctl00_ContentPlaceHolder1_lbOdevDosyalar" veya "Yüklediğiniz ödev" metni
    - Teslim edilmemiş: href içinde "OdevGonder" veya "Ödevi Yükle" butonu
    """
    try:
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        result = {
            "start_date": "",
            "end_date": "",
            "is_submitted": False,
        }

        # Tarih bilgilerini çek
        # title_field ve data_field span'larını bul
        title_fields = soup.find_all("span", class_="title_field")
        for title_span in title_fields:
            title_text = title_span.get_text(strip=True).lower()
            # Sonraki sibling data_field
            data_span = title_span.find_next_sibling("span", class_="data_field")
            if not data_span:
                # Bazen aynı parent içinde değil
                next_elem = title_span.find_next("span", class_="data_field")
                if next_elem:
                    data_span = next_elem

            if data_span:
                value = data_span.get_text(strip=True)
                if "başlangıç" in title_text or "start" in title_text:
                    result["start_date"] = value
                elif (
                    "bitiş" in title_text or "end" in title_text or "due" in title_text
                ):
                    result["end_date"] = value

        # Teslim durumunu kontrol et
        page_text = soup.get_text(" ", strip=True).lower()
        page_html = str(soup)

        # Teslim edilmiş göstergeleri
        submitted_indicators = [
            "lbOdevDosyalar" in page_html,  # İndirme linki var
            "yüklediğiniz ödev" in page_text,
            "dosyalarını indirin" in page_text,
            "teslim edildi" in page_text,
            "gönderildi" in page_text,
        ]

        # Teslim edilmemiş göstergeleri
        not_submitted_indicators = [
            "OdevGonder" in page_html,  # Yükleme butonu var
            "ödevi yükle" in page_text,
        ]

        # Eğer submitted göstergesi varsa ve not_submitted yoksa -> submitted
        if any(submitted_indicators) and not any(not_submitted_indicators):
            result["is_submitted"] = True
        # Eğer not_submitted göstergesi varsa -> not submitted
        elif any(not_submitted_indicators):
            result["is_submitted"] = False
        # Her ikisi de varsa, OdevGonder'a öncelik ver (henüz yüklememiş)
        elif any(not_submitted_indicators):
            result["is_submitted"] = False

        return result
    except Exception as e:
        logger.debug(f"Ödev detay hatası: {e}")
        return None


def get_assignments(session, base_url):
    """Ödevleri çeker.

    Ninova ödev listesi HTML yapısı:
    <td>
        <h2><a href="/Sinif/.../Odev/241922">STM Experiment 4</a></h2>
        <strong>Teslim Başlangıcı : </strong>26 Aralık 2025 00:00<br />
        <strong>Teslim Bitişi : </strong>06 Ocak 2026 23:30<br />
        Ödevde istenen toplam <strong class="uyari">1</strong> adet dosyanın
        <strong class="uyari">1</strong> adedini sisteme yüklediniz.
    </td>
    """
    url = f"{base_url}/Odevler"
    try:
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        assignments = []

        # gvOdevListesi table'ını veya data class'lı table'ı bul
        table = soup.find("table", id=re.compile(".*gvOdevListesi.*"))
        if not table:
            table = soup.find("table", class_="data")
        if not table:
            return []

        rows = table.find_all("tr")
        for row in rows:
            try:
                # Header satırını atla
                if row.find("th"):
                    continue

                cols = row.find_all("td")
                if not cols:
                    continue

                cell = cols[0]
                cell_text = cell.get_text(" ", strip=True)
                cell_html = str(cell)

                # Ödev adını ve URL'ini bul - h2 içindeki a tag'den
                name = ""
                assign_url = ""
                assign_id = ""

                h2 = cell.find("h2")
                if h2:
                    a_tag = h2.find("a", href=True)
                    if a_tag:
                        href = a_tag.get("href", "")
                        if "/Odev/" in href:
                            name = a_tag.get_text(strip=True)
                            assign_url = (
                                f"https://ninova.itu.edu.tr{href}"
                                if href.startswith("/")
                                else href
                            )
                            assign_id = href.split("/")[-1] if href else ""

                # h2'de bulunamadıysa tüm a tag'leri ara
                if not assign_id:
                    for a_tag in cell.find_all("a", href=True):
                        href = a_tag.get("href", "")
                        if "/Odev/" in href and "/OdevGonder" not in href:
                            text = a_tag.get_text(strip=True)
                            if text.lower() not in [
                                "ödevi görüntüle",
                                "görüntüle",
                                "view",
                                "detay",
                            ]:
                                if not name:
                                    name = text
                            assign_url = (
                                f"https://ninova.itu.edu.tr{href}"
                                if href.startswith("/")
                                else href
                            )
                            assign_id = href.split("/")[-1] if href else ""
                            break

                if not assign_id:
                    continue

                # Tarih bilgilerini çek
                start_date = ""
                end_date = ""

                # "Teslim Başlangıcı : 26 Aralık 2025 00:00"
                start_match = re.search(
                    r"Teslim\s*Başlangıcı\s*:\s*(\d{1,2}\s+\w+\s+\d{4}\s+\d{2}:\d{2})",
                    cell_text,
                    re.IGNORECASE,
                )
                if start_match:
                    start_date = start_match.group(1)

                # "Teslim Bitişi : 06 Ocak 2026 23:30"
                end_match = re.search(
                    r"Teslim\s*Bitişi\s*:\s*(\d{1,2}\s+\w+\s+\d{4}\s+\d{2}:\d{2})",
                    cell_text,
                    re.IGNORECASE,
                )
                if end_match:
                    end_date = end_match.group(1)

                # Teslim durumu - "X adedini sisteme yüklediniz"
                is_submitted = False

                # Pattern: "<strong class="uyari">N</strong> adedini sisteme yüklediniz"
                # N > 0 ise teslim edilmiş
                submitted_match = re.search(
                    r'<strong[^>]*class=["\']uyari["\'][^>]*>(\d+)</strong>\s*adedini\s*sisteme\s*yüklediniz',
                    cell_html,
                    re.IGNORECASE,
                )
                if submitted_match:
                    submitted_count = int(submitted_match.group(1))
                    is_submitted = submitted_count > 0
                else:
                    # Alternatif kontroller
                    if (
                        "yüklediniz" in cell_text.lower()
                        and "0 adedini" not in cell_text
                    ):
                        # "sisteme yüklediniz" var ama "0 adedini" yok
                        is_submitted = True
                    elif (
                        "teslim edildi" in cell_text.lower()
                        or "gönderildi" in cell_text.lower()
                    ):
                        is_submitted = True

                # OdevGonder linki varsa kontrol et (teslim edilmemiş olabilir)
                if "OdevGonder" in cell_html:
                    # Ama yükleme sayısı > 0 ise yine de teslim edilmiş sayılır
                    if not submitted_match or (
                        submitted_match and int(submitted_match.group(1)) == 0
                    ):
                        is_submitted = False

                assignments.append(
                    {
                        "id": assign_id,
                        "name": name or f"Ödev {assign_id}",
                        "url": assign_url,
                        "start_date": start_date or "-",
                        "end_date": end_date or "-",
                        "is_submitted": is_submitted,
                    }
                )
            except Exception as e:
                logger.debug(f"Ödev parse hatası: {e}")
                continue

        # Detay sayfalarından eksik bilgileri tamamla
        for assign in assignments:
            # Tarih veya teslim durumu eksikse detay sayfasını kontrol et
            if not assign["end_date"] or assign["end_date"] == "-":
                detail = get_assignment_detail(session, assign["url"])
                if detail:
                    if detail.get("start_date"):
                        assign["start_date"] = detail["start_date"]
                    if detail.get("end_date"):
                        assign["end_date"] = detail["end_date"]
                    # Teslim durumunu detay sayfasından al (daha güvenilir)
                    assign["is_submitted"] = detail.get("is_submitted", False)

        return assignments
    except Exception as e:
        console.print(f"[bold red]Ödev çekme hatası: {e}")
        return []


def get_class_files(
    session, base_url, sub_url=None, folder_prefix="", file_type="SinifDosyalari"
):
    """Sınıf veya ders dosyalarını çeker.

    HTML yapısı:
    <table class="data">
        <tr>
            <td><img src='/images/ds/folder.png' /><a href="...?g8223370">FolderName</a></td>
            <td>6 MB</td>
            <td>21 Kasım 2025 13:16</td>
        </tr>
        <tr>
            <td><img src='/images/ds/ikon-pdf.png' /><a href="...?g8223374">FileName.pdf</a></td>
            <td>7 MB</td>
            <td>23 Aralık 2025 08:20</td>
        </tr>
    </table>
    """
    if sub_url:
        url = sub_url
    else:
        url = f"{base_url}/{file_type}"

    try:
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")

        # dosyaSistemi div içindeki table'ı bul
        table = soup.find("table", class_="data")
        if not table:
            return []

        files = []
        rows = table.find_all("tr")

        for row in rows:
            try:
                # Header satırını atla
                if row.find("th"):
                    continue

                cols = row.find_all("td")
                if len(cols) < 3:
                    continue

                # İlk sütun: icon ve isim
                first_col = cols[0]
                img = first_col.find("img")
                a_tag = first_col.find("a")

                if not a_tag:
                    continue

                file_name = a_tag.get_text(strip=True)
                href = a_tag.get("href", "")

                # Icon'dan klasör mü dosya mı anla
                img_src = img.get("src", "").lower() if img else ""
                is_folder = "folder.png" in img_src

                # Boyut ve tarih
                size = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                date_str = cols[2].get_text(strip=True) if len(cols) > 2 else ""

                # URL oluştur
                if href.startswith("/"):
                    file_url = f"https://ninova.itu.edu.tr{href}"
                elif href.startswith("?"):
                    # Relative query string - mevcut URL'e ekle
                    base_page_url = url.split("?")[0]
                    file_url = f"{base_page_url}{href}"
                else:
                    file_url = href

                if is_folder:
                    # Klasöre recursive gir
                    sub_files = get_class_files(
                        session,
                        base_url,
                        file_url,
                        folder_prefix=f"{folder_prefix}{file_name}/",
                        file_type=file_type,
                    )
                    files.extend(sub_files)
                else:
                    # Dosya bilgisini ekle
                    files.append(
                        {
                            "name": f"{folder_prefix}{file_name}",
                            "url": file_url,
                            "date": date_str,
                            "size": size,
                        }
                    )
            except Exception as e:
                logger.debug(f"Dosya parse hatası: {e}")
                continue

        return files
    except Exception as e:
        console.print(f"[bold red]Dosya listesi çekme hatası: {e}")
        return []


def get_all_files(session, base_url):
    """Hem sınıf dosyalarını hem ders dosyalarını çeker."""
    all_files = []

    # Sınıf dosyaları
    sinif_files = get_class_files(session, base_url, file_type="SinifDosyalari")
    for f in sinif_files:
        f["source"] = "Sınıf"
    all_files.extend(sinif_files)

    # Ders dosyaları
    ders_files = get_class_files(session, base_url, file_type="DersDosyalari")
    for f in ders_files:
        f["source"] = "Ders"
    all_files.extend(ders_files)

    return all_files


def get_user_courses(session):
    """Kullanıcının ana sayfasından dersleri çeker.

    HTML yapısı (menuErisimAgaci div):
    <div class="menuErisimAgaci">
        <ul>
            <li><span>2024-25 Güz</span>
                <ul>
                    <li><span>BLG102E</span>
                        <ul>
                            <li><a href="/Sinif/35122.110739">C.1</a></li>
                        </ul>
                    </li>
                </ul>
            </li>
        </ul>
    </div>
    """
    try:
        # Önce Kampus, sonra Kampus1 dene
        resp = session.get("https://ninova.itu.edu.tr/Kampus", timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        tree_div = soup.find("div", {"class": "menuErisimAgaci"})
        if not tree_div:
            # Kampus1'i dene
            resp = session.get("https://ninova.itu.edu.tr/Kampus1", timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            tree_div = soup.find("div", {"class": "menuErisimAgaci"})

        if not tree_div:
            return []

        courses = []

        # Tüm Sinif linklerini bul
        links = tree_div.find_all("a", href=True)
        for a in links:
            href = a["href"]
            if "/Sinif/" not in href:
                continue

            # Base URL oluştur (query string ve alt sayfaları temizle)
            clean_url = f"https://ninova.itu.edu.tr{href.split('?')[0]}"
            for suffix in [
                "/Notlar",
                "/Duyurular",
                "/Odevler",
                "/SinifDosyalari",
                "/DersDosyalari",
            ]:
                if clean_url.endswith(suffix):
                    clean_url = clean_url[: -len(suffix)]
                    break

            # Ders adı ve kodunu al
            section_name = a.get_text(strip=True)  # C.1, C.2 gibi sınıf adı
            course_code = ""
            course_name = section_name

            # Üst <li> elementlerinden ders kodunu bul
            parent_li = a.find_parent("li")
            if parent_li:
                # Bir üst <li>'yi bul (ders kodu)
                grandparent_li = parent_li.find_parent("li")
                if grandparent_li:
                    code_span = grandparent_li.find("span", recursive=False)
                    if code_span:
                        course_code = code_span.get_text(strip=True)
                        # Bir üst <li>'den dönem bilgisi (opsiyonel)
                        semester_li = grandparent_li.find_parent("li")
                        if semester_li:
                            # Dönem bilgisini adı dahil etmiyoruz, sadece kod ve sınıf
                            pass

            # Final course name
            if course_code:
                course_name = f"{course_code} - {section_name}"

            # Duplicate kontrolü
            if clean_url not in [c["url"] for c in courses]:
                courses.append({"name": course_name, "url": clean_url})

        return courses
    except Exception as e:
        console.print(f"[bold red]Ders listesi çekme hatası: {e}")
        return []


def get_grades(session, base_url, chat_id, username, password):
    """Notları çeker. base_url artık /Notlar olmadan gelir.

    HTML yapısı (table.data):
    <table class="data">
        <tr>
            <th>Değerlendirme</th>
            <th>Not</th>
            <th>Ağırlık</th>
            <th>Ortalama</th>
            <th>Std. Sapma</th>
        </tr>
        <tr>
            <td>Vize 1</td>
            <td>85</td>
            <td>%20</td>
            <td>72.5</td>
            <td>12.3</td>
        </tr>
    </table>
    """
    url = f"{base_url}/Notlar"
    try:
        response = session.get(url, timeout=15, allow_redirects=False)
        if response.status_code == 302:
            console.print(f"[cyan]Oturum yenileniyor... ({chat_id})")
            if login_to_ninova(session, chat_id, username, password, quiet=True):
                response = session.get(url, timeout=15, allow_redirects=False)
                if response.status_code == 302:
                    raise LoginFailedError("Giriş başarısız.")
            else:
                raise LoginFailedError("Giriş başarısız.")

        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        course_name = "Bilinmeyen Ders"

        # Ders adını yol div'inden veya başlıktan al
        yol_div = soup.find("div", class_="yol")
        if yol_div:
            for link in yol_div.find_all("a"):
                href = link.get("href", "")
                if "/Sinif/" in href and "Notlar" not in href:
                    course_name = link.get_text(strip=True)
                    break

        # Alternatif: h1 veya h2'den ders adı
        if course_name == "Bilinmeyen Ders":
            h1 = soup.find("h1")
            if h1:
                course_name = h1.get_text(strip=True)

        grades_data = {
            "course_name": course_name,
            "grades": {},
            "assignments": [],
            "files": [],
            "announcements": [],
        }

        # Not tablosunu bul (table.data veya id'si rpGalileoNot olan spanların bulunduğu tablo)
        tables = soup.find_all("table", class_="data")
        if not tables:
            # Table class='data' olmayabilir, belki de standart tablo yapısı farklıdır
            # Tablo içindeki span id'leri 'ctl00_ContentPlaceHolder1_rpGalileoNot' ile başlıyor
            pass

        for table in tables:
            # Header var mı kontrol et
            header_row = table.find("tr")
            if not header_row or not header_row.find("th"):
                continue

            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all(["td", "th"])

                # Header satırını atla
                if cols and cols[0].name == "th":
                    continue

                if len(cols) < 2:
                    continue

                # İlk kolon not adı (içinde span ve script olabilir)
                name_col = cols[0]
                # İkinci kolon not değeri
                grade_col = cols[1]

                # Not Adı
                # <span id="eas109760">Midterm Exam</span>
                name_span = name_col.find("span", id=re.compile(r"^eas\d+"))
                if name_span:
                    key = name_span.get_text(strip=True)
                else:
                    key = name_col.get_text(strip=True)

                # Not Değeri
                value = grade_col.get_text(strip=True)

                # Ağırlık ve diğer detaylar Script içinde olabilir
                # new Tip(element, body, ... var body = '...' ... )
                weight = ""
                details = {}

                script_tag = name_col.find("script")
                if script_tag and script_tag.string:
                    js_content = script_tag.string
                    # body değişkenini parse et
                    # var body = '<strong>Not Yüzdesi </strong><span>%30,00</span><br style="clear:both;" />';
                    # body += '<strong>Ortalama </strong><span>41,29</span><br style="clear:both;" />';

                    # Regex ile değerleri çek
                    # Not Yüzdesi
                    w_match = re.search(
                        r"Not Yüzdesi\s*</strong>\s*<span>%?([\d,.]+)</span>",
                        js_content,
                    )
                    if w_match:
                        weight = w_match.group(1).replace(",", ".")

                    # Ortalama
                    avg_match = re.search(
                        r"Ortalama\s*</strong>\s*<span>([\d,.]+)</span>", js_content
                    )
                    if avg_match:
                        details["class_avg"] = avg_match.group(1)

                    # Standart Sapma
                    std_match = re.search(
                        r"Standart Sapma\s*</strong>\s*<span>([\d,.]+)</span>",
                        js_content,
                    )
                    if std_match:
                        details["std_dev"] = std_match.group(1)

                    # Öğrenci Sayısı
                    count_match = re.search(
                        r"Öğrenci Sayısı\s*</strong>\s*<span>(\d+)</span>", js_content
                    )
                    if count_match:
                        details["student_count"] = count_match.group(1)

                    # Sıralamanız
                    rank_match = re.search(
                        r"Sıralamanız\s*</strong>\s*<span>(\d+)</span>", js_content
                    )
                    if rank_match:
                        details["rank"] = rank_match.group(1)

                # Skip keywords...
                skip_keywords = ["ağırlıklı ortalamanız", "weighted average"]
                if any(kw in key.lower() for kw in skip_keywords):
                    continue

                if key and value:
                    grades_data["grades"][key] = {
                        "not": value,
                        "agirlik": weight,
                        "detaylar": details,
                    }

        # Base URL ile diğer verileri çek
        grades_data["assignments"] = get_assignments(session, base_url)
        grades_data["files"] = get_all_files(session, base_url)
        grades_data["announcements"] = get_announcements(session, base_url)
        return grades_data
    except LoginFailedError:
        raise
    except Exception as e:
        console.print(f"[bold red]Veri çekme hatası: {e}")
        return None
