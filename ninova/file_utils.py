import os
from core.config import console
from ninova.auth import login_to_ninova


def download_file(session, url, filename, chat_id=None, username=None, password=None):
    """Dosyayı indirir."""
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

            safe_filename = "".join(
                [c for c in filename if c.isalnum() or c in "._- "]
            ).strip()
            filepath = os.path.join(os.getcwd(), safe_filename)
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return filepath
    except Exception as e:
        console.print(f"[bold red]Dosya indirme hatası: {e}")
    return None
