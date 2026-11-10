"""개인정보 점검 도구 시험 — 일부러 나쁜 내용을 넣은 임시 폴더로, 점검이 제대로 잡아내는지 확인한다.
실행: python -I tests/test_privacy.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "tools" / "check_privacy.py"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def run(folder, *extra):
    r = subprocess.run([sys.executable, "-X", "utf8", "-I", str(CHECK), str(folder), *extra], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def main():
    # ── 깨끗한 폴더 ──
    clean = Path(tempfile.mkdtemp(prefix="priv_clean_"))
    (clean / "a.md").write_text("그냥 문서입니다. 예시 주소는 user@example.com 입니다.", encoding="utf-8")
    (clean / "b.py").write_text('PATH = "%USERPROFILE%/x"  # <사용자이름> 자리표시자는 괜찮다\n', encoding="utf-8")
    code, out = run(clean)
    check("깨끗한 폴더는 통과(종료 코드 0)", code == 0, out.strip().splitlines()[-1] if out.strip() else "")

    # ── 나쁜 폴더 ──
    bad = Path(tempfile.mkdtemp(prefix="priv_bad_"))
    (bad / "data").mkdir()
    (bad / "data" / "auth.json").write_text("{}", encoding="utf-8")
    (bad / "runs.jsonl").write_text("{}", encoding="utf-8")
    (bad / "shortcut.lnk").write_bytes(b"x")
    # 가짜 유출 값은 조각을 이어 붙여 만든다 — 이 시험 파일 자체가 점검에 걸리지 않게 하려는 것
    fake = {
        "path": "C:" + "\\Users\\" + "SomeRealName" + "\\Desktop",
        "mail": "someone" + "@gmail" + ".com",
        "gkey": "AI" + "za" + "SyA1234567890abcdefghijklmnopqrstuv",
        "gh": "gh" + "p_" + "abcdefghijklmnopqrstuvwxyz0123456789",
        "pem": "-----BEGIN RSA " + "PRIVATE KEY-----",
        "ip": "192." + "168." + "0.12",
    }
    (bad / "notes.md").write_text(
        f"내 폴더는 {fake['path']} 입니다.\n연락처 {fake['mail']}\n키 {fake['gkey']}\n토큰 {fake['gh']}\n{fake['pem']}\n서버 {fake['ip']}\n", encoding="utf-8")
    code, out = run(bad)
    check("나쁜 폴더는 실패(종료 코드 1)", code == 1)
    for label, needle in [("data 폴더", "data"), ("auth.json", "auth.json"), ("runs.jsonl", "runs.jsonl"), ("바로가기(.lnk)", ".lnk"), ("사용자 경로", "사용자 경로"),
                          ("이메일", "이메일"), ("Google 키", "Google"), ("GitHub 토큰", "GitHub 토큰"), ("비공개 키", "비공개 키"), ("사설 IP", "사설 IP")]:
        check(f"잡아낸다: {label}", needle in out)

    # ── 사설 낱말 목록 ──
    terms = ROOT / "tools" / "private_terms.txt"
    existed = terms.exists()
    backup = terms.read_text(encoding="utf-8") if existed else None
    try:
        terms.write_text("비밀낱말테스트\n", encoding="utf-8")
        word = Path(tempfile.mkdtemp(prefix="priv_word_"))
        (word / "c.md").write_text("여기에 비밀낱말테스트 가 들어 있어요", encoding="utf-8")
        code, out = run(word)
        check("사설 낱말 목록의 낱말을 잡아낸다", code == 1 and "비밀낱말테스트" in out)
    finally:
        if existed:
            terms.write_text(backup, encoding="utf-8")
        else:
            terms.unlink(missing_ok=True)

    # ── --tracked: git 이 추적하지 않는 파일(.gitignore)은 검사에서 제외 ──
    repo = Path(tempfile.mkdtemp(prefix="priv_git_"))
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".gitignore").write_text("data/\n", encoding="utf-8")
    (repo / "data").mkdir()
    (repo / "data" / "auth.json").write_text("{}", encoding="utf-8")
    (repo / "ok.md").write_text("괜찮은 문서", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    code, out = run(repo, "--tracked")
    check("--tracked: .gitignore 로 제외된 data/ 는 문제 삼지 않는다", code == 0, out.strip().splitlines()[-1] if out.strip() else "")
    (repo / "leak.md").write_text("메일 me" + "@gmail" + ".com", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    code, out = run(repo, "--tracked")
    check("--tracked: 올라갈 파일의 이메일은 잡아낸다", code == 1 and "이메일" in out)

    ok = sum(results)
    print(f"\n{ok}/{len(results)} 통과")
    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    main()
