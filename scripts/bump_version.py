import re
import sys
from pathlib import Path

def bump_version():
    # Commit mesajını oku (Git, mesajın olduğu dosya yolunu argüman olarak gönderir)
    commit_msg = ""
    if len(sys.argv) > 1:
        msg_file = Path(sys.argv[1])
        if msg_file.exists():
            commit_msg = msg_file.read_text(encoding="utf-8").lower()

    toml_path = Path("pyproject.toml")
    if not toml_path.exists():
        sys.exit(0)

    content = toml_path.read_text(encoding="utf-8")
    pattern = r'(version\s*=\s*")(\d+\.\d+\.\d+)(")'
    match = re.search(pattern, content)
    
    if not match:
        sys.exit(0)

    prefix, version_str, suffix = match.groups()
    major, minor, patch = map(int, version_str.split('.'))
    
    # Mantık: major > feat (minor) > fix (patch)
    if "major:" in commit_msg:
        major += 1
        minor = 0
        patch = 0
    elif "feat:" in commit_msg:
        minor += 1
        patch = 0
    else:
        # fix: varsa veya hiçbir şey yoksa patch artırılır
        patch += 1

    new_version = f"{major}.{minor}.{patch}"
    new_version_string = f'{prefix}{new_version}{suffix}'
    new_content = content.replace(match.group(0), new_version_string)

    toml_path.write_text(new_content, encoding="utf-8")
    print(f"Versiyon güncellendi: {version_str} -> {new_version}")

if __name__ == "__main__":
    bump_version()
