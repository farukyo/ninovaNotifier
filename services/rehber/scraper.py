import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from common.http_logging import http_request
from common.log_context import log_with_context

logger = logging.getLogger("rehber")


class RehberScraper:
    BASE_URL = "https://rehber.itu.edu.tr"

    def __init__(self, session):
        """
        :param session: Kullanıcının Ninova girişinde açılmış requests.Session() nesnesi
        """
        self.session = session

        # Configure retry strategy specifically for Rehber requests if needed
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
            backoff_factor=1,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def is_logged_in(self):
        """Rehber sistemine giriş yapılıp yapılmadığını kontrol eder."""
        try:
            resp = http_request(
                logger,
                self.session,
                "GET",
                self.BASE_URL,
                action="rehber_session_check",
                timeout=10,
            )
            return "Çıkış" in resp.text or "/Account/Logout" in resp.text
        except Exception:
            return False

    def login_to_rehber(self, username, password):
        """
        Rehber'e girisv3.itu.edu.tr SSO üzerinden giriş yapar.
        Başarılıysa True, başarısızsa False döner.
        """
        try:
            # 1. Rehber login sayfasına git -> girisv3'e yönlendirecek
            login_url = f"{self.BASE_URL}/Account/Login?ReturnUrl=https://rehber.itu.edu.tr/"
            resp = http_request(
                logger,
                self.session,
                "GET",
                login_url,
                action="rehber_login_page",
                timeout=15,
                allow_redirects=True,
            )

            # girisv3.itu.edu.tr login sayfasına yönlenmeli
            if "girisv3.itu.edu.tr" not in resp.url:
                # Bazen SSO doğrudan rehber anasayfasına dönebilir.
                if "rehber.itu.edu.tr" in resp.url and (
                    "Çıkış" in resp.text or "/Account/Logout" in resp.text
                ):
                    log_with_context(
                        logger,
                        "info",
                        "Rehber SSO: Oturum zaten acik, login adimi atlandi.",
                        action="rehber_login",
                    )
                    return True
                log_with_context(
                    logger,
                    "info",
                    f"Rehber SSO: Beklenmeyen URL, anonim devam edilecek: {resp.url}",
                    action="rehber_login",
                )
                return False

            soup = BeautifulSoup(resp.text, "html.parser")

            # 2. Login formunun hidden field'larını al
            form_data = {}
            for hidden in soup.find_all("input", {"type": "hidden"}):
                name = hidden.get("name")
                value = hidden.get("value", "")
                if name:
                    form_data[name] = value

            # 3. Kullanıcı adı ve şifre alanlarını ekle
            # girisv3.itu.edu.tr için kesinleşmiş field isimleri:
            form_data["ctl00$ContentPlaceHolder1$tbUserName"] = username
            form_data["ctl00$ContentPlaceHolder1$tbPassword"] = password
            form_data["ctl00$ContentPlaceHolder1$btnLogin"] = "Giriş / Login"

            # 4. Formu POST et
            form_tag = soup.find("form")
            post_url = resp.url
            if form_tag and form_tag.get("action"):
                action = form_tag["action"]
                post_url = urljoin(resp.url, action)

            resp2 = http_request(
                logger,
                self.session,
                "POST",
                post_url,
                action="rehber_login_submit",
                data=form_data,
                allow_redirects=True,
                timeout=15,
            )

            # Başarı kontrolü: rehber.itu.edu.tr'ye geri dönmeli ve "Çıkış" butonu görünmeli.
            if "rehber.itu.edu.tr" in resp2.url and (
                "Çıkış" in resp2.text or "/Account/Logout" in resp2.text
            ):
                log_with_context(
                    logger,
                    "info",
                    "Rehber SSO: Giris basarili!",
                    action="rehber_login",
                )
                return True

            log_with_context(
                logger,
                "warning",
                f"Rehber SSO: Giris basarisiz. Son URL: {resp2.url}",
                action="rehber_login",
            )
            return False

        except Exception as e:
            log_with_context(
                logger,
                "error",
                f"Rehber SSO login error: {e}",
                action="rehber_login",
                exc_info=True,
            )
            return False

    def search_person(self, first_name: str, last_name: str):
        """
        Ad ve Soyad bilgisi ile İTÜ Rehberde arama yapar.
        :return: Kişilerin liste halinde sözlükleri
        """
        first_name = first_name.strip()
        last_name = last_name.strip()

        url_search = f"{self.BASE_URL}/Rehber/Search"
        url_home = f"{self.BASE_URL}/"

        try:
            res = http_request(
                logger,
                self.session,
                "GET",
                url_home,
                action="rehber_search_home",
                timeout=10,
            )
            soup = BeautifulSoup(res.text, "html.parser")

            token_input = soup.find("input", {"name": "__RequestVerificationToken"})
            req_token = token_input["value"] if token_input else ""

            data = {
                "firstName": first_name,
                "lastName": last_name,
                "identityType": "0",
                "__RequestVerificationToken": req_token,
            }

            post_res = http_request(
                logger,
                self.session,
                "POST",
                url_search,
                action="rehber_search",
                data=data,
                timeout=15,
            )
            results = self._parse_search_results(post_res.text)

            # Eğer giriş yapılmışsa, detay sayfalarına gidip eksik e-posta/telefon/ek bilgileri çekelim
            if self.is_logged_in():
                for person in results:
                    detail_url = person.get("detail_url")
                    if detail_url:
                        detail = self.get_person_detail(detail_url)
                        if detail.get("email"):
                            person["email"] = detail["email"]
                        if detail.get("phone"):
                            person["phone"] = detail["phone"]
                        if detail.get("extras"):
                            person["extras"] = detail["extras"]

            return results

        except Exception as e:
            log_with_context(
                logger,
                "error",
                f"Rehber search error: {e}",
                action="rehber_search",
                exc_info=True,
            )
            return []

    def get_person_detail(self, detail_path: str):
        """
        Kişinin detay sayfasını açarak E-posta, Telefon vb. bilgilerini çeker.
        Giriş yapılmış session gerektirir.
        """
        try:
            url = detail_path
            if not url.startswith("http"):
                url = f"{self.BASE_URL}{detail_path}"

            res = http_request(
                logger,
                self.session,
                "GET",
                url,
                action="rehber_detail",
                timeout=10,
            )
            soup = BeautifulSoup(res.text, "html.parser")

            detail = {"email": "", "phone": "", "extras": {}}

            # Detay tablosunu bul ve parse et
            table = soup.find("table")
            if table:
                # Header'ları temizleyelim (boşlukları ve '*' işaretini siliyoruz)
                headers = []
                for th in table.find_all("th"):
                    h = " ".join(th.text.strip().replace("*", "").split())
                    headers.append(h)

                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if not cells:
                        continue
                    row_data = [c.text.strip() for c in cells]

                    # Header'larla eşleştir
                    for i, val in enumerate(row_data):
                        if i < len(headers):
                            h = headers[i]
                            h_lower = h.lower()

                            if not val or val == "-" or val == "0":
                                continue

                            if "e-posta" in h_lower or "email" in h_lower:
                                detail["email"] = val
                            elif "cep" in h_lower and "telefon" in h_lower:
                                detail["phone"] = val
                            elif "birim" not in h_lower and "bölüm" not in h_lower:
                                detail["extras"][h] = val

            # E-posta alternatif: mailto linkinden
            if not detail["email"]:
                email_tag = soup.find("a", href=lambda h: h and "mailto:" in h)
                if email_tag:
                    detail["email"] = email_tag.text.strip()

            return detail
        except Exception as e:
            log_with_context(
                logger,
                "error",
                f"Rehber detail error: {e}",
                action="rehber_detail",
                exc_info=True,
            )
            return {"email": "", "phone": "", "extras": {}}

    def _parse_search_results(self, html: str):
        """
        Arama sonuç tablosunu parse eder.
        """
        soup = BeautifulSoup(html, "html.parser")
        results = []

        table = soup.find("table")
        if not table:
            return results

        rows = table.find_all("tr")
        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            person = {
                "title": cells[0].text.strip(),
                "name": cells[1].text.strip(),
                "unit": cells[2].text.strip(),
                "department": cells[3].text.strip(),
                "email": "",
                "phone": "",
            }

            # data-link attribute'ü (detay sayfası yolu)
            data_link = row.get("data-link", "")
            if data_link:
                person["detail_url"] = data_link

            # Link tag (detay sayfası yolu yedeği)
            if not data_link:
                link_tag = cells[1].find("a")
                if link_tag and link_tag.get("href"):
                    person["detail_url"] = link_tag["href"]

            results.append(person)

        return results
