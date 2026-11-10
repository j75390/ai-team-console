"""올리기 전 개인정보 점검.

    python -I tools/check_privacy.py <폴더>            (폴더 안 모든 파일)
    python -I tools/check_privacy.py <폴더> --tracked  (git이 추적 중인 파일만 — 커밋 전·푸시 전에 쓰기 좋음)

검사하는 것
  1) 올리면 안 되는 파일: data/, auth.json, runs.jsonl, events.jsonl, models.json, .env, 키 파일, .lnk, 압축 파일, __pycache__
  2) 글 파일 안의 의심 문자열: 내 PC 사용자 경로(드라이브 이름/Users/<사용자이름> 꼴), 이메일, API 키 모양(AIza… / sk-… / ghp_… / -----BEGIN), 사설 IP
  3) tools/private_terms.txt 에 적어 둔 낱말(실명·아이디·학원 이름 등, 한 줄에 하나) — 이 파일은 깃에 올라가지 않는다
  4) 폴더에 .git 이 있으면 커밋 작성자 이름·이메일을 보여 준다(실제 이메일이면 GitHub noreply 로 바꾸라고 알려 줌)
문제가 하나라도 있으면 종료 코드 1.
"""
import re
import subprocess
import sys
from pathlib import Path

BAD_NAMES = {"auth.json", "runs.jsonl", "events.jsonl", "models.json", "connections.json", ".env"}
BAD_DIRS = {"data", "codex_home", "__pycache__", ".venv", "venv"}
BAD_SUFFIX = {".lnk", ".pem", ".key", ".pfx", ".7z", ".zip", ".pyc"}
TEXT_SUFFIX = {".py", ".pyw", ".md", ".txt", ".html", ".js", ".json", ".jsonl", ".css", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".bat", ".ps1", ".gitignore", ""}
PATTERNS = [
    ("내 PC 사용자 경로", re.compile(r"[A-Za-z]:\\+Users\\+(?!<|%|Public|Default|All Users)[^\\\s\"'<>]+", re.I)),
    ("이메일", re.compile(r"[A-Za-z0-9._%+\-]+@(?!users\.noreply\.github\.com)[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    ("API 키 모양(Google)", re.compile(r"AIza[0-9A-Za-z_\-]{20,}")),
    ("API 키 모양(sk-)", re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
    ("GitHub 토큰", re.compile(r"\b(ghp_|github_pat_)[A-Za-z0-9_]{20,}")),
    ("비공개 키 블록", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("사설 IP", re.compile(r"\b(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)\b")),
]
ALLOW_EMAIL_DOMAINS = {"example.com", "example.org"}


def main(folder, tracked=False):
    root = Path(folder).resolve()
    if not root.is_dir():
        sys.exit(f"폴더가 없어요: {root}")
    terms = []
    pt = Path(__file__).resolve().parent / "private_terms.txt"
    if pt.exists():
        terms = [t.strip().lower() for t in pt.read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")]
    problems = []
    scanned = 0
    if tracked:                                   # --tracked: 깃이 추적 중인(올라갈) 파일만 검사
        out = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, timeout=30).stdout.splitlines()
        paths = [root / x for x in out if x]
    else:
        paths = sorted(root.rglob("*"))
    for p in paths:
        rel = p.relative_to(root)
        parts = set(rel.parts)
        if ".git" in parts:
            continue
        if p.is_dir():
            if p.name in BAD_DIRS:
                problems.append((str(rel), "올리면 안 되는 폴더"))
            continue
        if p.name in BAD_NAMES or p.suffix.lower() in BAD_SUFFIX or (parts & BAD_DIRS):
            problems.append((str(rel), "올리면 안 되는 파일"))
            continue
        if p.suffix.lower() not in TEXT_SUFFIX or p.stat().st_size > 3_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        low = text.lower()
        for label, rx in PATTERNS:
            for m in rx.finditer(text):
                if label == "이메일" and m.group(0).split("@")[-1].lower() in ALLOW_EMAIL_DOMAINS:
                    continue
                problems.append((f"{rel}", f"{label}: {m.group(0)[:60]}"))
        for t in terms:
            if t in low:
                problems.append((f"{rel}", f"사설 낱말 '{t}' 포함(tools/private_terms.txt)"))
    git_info = ""
    if (root / ".git").exists():
        try:
            out = subprocess.run(["git", "-C", str(root), "log", "--format=%an <%ae>"], capture_output=True, text=True, timeout=30).stdout.strip().splitlines()
            authors = sorted(set(out))
            git_info = "커밋 작성자: " + (", ".join(authors) if authors else "(커밋 없음)")
            for a in authors:
                if "@" in a and "users.noreply.github.com" not in a:
                    problems.append(("git 기록", f"커밋 작성자에 실제 이메일이 있어요: {a} → GitHub noreply 주소로 바꾸세요"))
        except Exception:  # noqa: BLE001
            git_info = "git 기록을 읽지 못했어요"
    print(f"검사한 글 파일 {scanned}개 · 사설 낱말 {len(terms)}개 사용")
    if git_info:
        print(git_info)
    if problems:
        print(f"\n문제 {len(problems)}건:")
        for where, what in problems:
            print(f"  - {where}: {what}")
        sys.exit(1)
    print("개인정보로 의심되는 것이 없어요.")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else ".", tracked="--tracked" in sys.argv)
