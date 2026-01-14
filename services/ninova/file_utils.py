import os
from common.config import console
from .auth import login_to_ninova


import io

def download_file(session, url, filename, chat_id=None, username=None, password=None, to_buffer=False):
    """
    Ninova'dan dosya indirir.
    
    :param session: requests.Session nesnesi
    :param url: İndirilecek dosyanın URL'i
    :param filename: Dosya adı (varsayılan)
    :param chat_id: Kullanıcı ID
    :param username: Ninova kullanıcı adı
    :param password: Ninova şifresi
    :param to_buffer: True ise (BytesIO, filename) döner, değilse dosya yolu döner.
    :return: (BytesIO, filename) veya filepath veya None
    """
    try:
        response = session.get(url, stream=True, timeout=30, allow_redirects=False)
        if response.status_code == 302:
            if login_to_ninova(session, chat_id, username, password):
                response = session.get(
                    url, stream=True, timeout=30, allow_redirects=False
                )
            else:
                return None

        if response.status_code == 200:
            cd = response.headers.get("Content-Disposition")
            if cd and "filename=" in cd:
                if 'filename="' in cd:
                    filename = cd.split('filename="')[1].split('"')[0]
                else:
                    filename = cd.split("filename=")[1].split(";")[0].strip()
            
            # Clean filename
            filename = "".join([c for c in filename if c.isalnum() or c in "._- "]).strip()

            if to_buffer:
                buffer = io.BytesIO()
                for chunk in response.iter_content(chunk_size=8192):
                    buffer.write(chunk)
                buffer.seek(0)
                return buffer, filename
            else:
                filepath = os.path.join(os.getcwd(), filename)
                with open(filepath, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return filepath
                
    except Exception as e:
        console.print(f"[bold red]Dosya indirme hatası: {e}")
    return None
