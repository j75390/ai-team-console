"""깃에 올릴 깨끗한 사본 만들기 — 개발하면서 생긴 기록(data, 로그, 바로가기, 개인 설정)이 없는 새 폴더를 만든다.

    python -I tools/make_release.py

release/ai-team-console/ 에 허용 목록(화이트리스트)에 있는 파일만 복사하고, 개인정보 점검을 돌린다.
이 폴더에서 `git init` 을 새로 하므로 '만들면서 쌓인 기록'이 올라가지 않는다(커밋은 날짜별로 직접 한다 — docs/GIT_UPLOAD_PLAN.md).
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "release" / "ai-team-console"
FILES = ["server.py", "auth.py", "pages.py", "connect.py", "index.html", "launch.pyw", "README.md", ".gitignore", "assets/icon.ico",
         "tests/test_auth.py", "tests/test_privacy.py", "tests/test_connect.py", "docs/GIT_UPLOAD_PLAN.md", "docs/WBS.md", "docs/NOTICE.md",
         "tools/check_privacy.py", "tools/make_release.py", "tools/demo_data.py", "tools/shoot.py", "tools/make_gif.py", "tools/build_deliverables.py", "tools/private_terms.example.txt"]
DIRS = [("deliverables", {".7z", ".zip", ".html"}), ("docs/images", set())]          # 산출물(PDF·엑셀·PPT·스크린샷) — 압축 파일·임시 파일은 제외


def _unlock(func, path, _exc):
    import os
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)


def main():
    if DEST.exists():                      # 이미 git init 한 사본이면 .git(커밋 기록)은 그대로 두고 파일만 새로 채운다
        for child in DEST.iterdir():
            if child.name == ".git":
                continue
            shutil.rmtree(child, onerror=_unlock) if child.is_dir() else (child.chmod(0o666), child.unlink())
    DEST.mkdir(parents=True, exist_ok=True)
    missing = []
    for f in FILES:
        src = ROOT / f
        if not src.exists():
            missing.append(f)
            continue
        (DEST / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, DEST / f)
    for d, skip in DIRS:
        for p in (ROOT / d).rglob("*"):
            if p.is_file() and p.suffix.lower() not in skip and not p.name.startswith("_"):
                out = DEST / p.relative_to(ROOT)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, out)
    n = sum(1 for _ in DEST.rglob("*") if _.is_file())
    print(f"복사한 파일 {n}개 → {DEST}")
    if missing:
        print("없어서 건너뜀:", ", ".join(missing))
    print("\n── 개인정보 점검 ──")
    r = subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "check_privacy.py"), str(DEST)])
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
