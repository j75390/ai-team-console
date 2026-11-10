"""로그인 흐름 시험 — 임시 폴더·다른 포트에서 서버를 따로 띄워 확인한다(실제 data 폴더는 건드리지 않음).
실행: python -I tests/test_auth.py
"""
import http.cookiejar
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8799
BASE = f"http://127.0.0.1:{PORT}"
results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def opener(jar=None):
    h = [NoRedirect()]
    if jar is not None:
        h.append(urllib.request.HTTPCookieProcessor(jar))
    return urllib.request.build_opener(*h)


def call(op, method, path, data=None, headers=None):
    body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
    hdr = {"Origin": BASE} if method == "POST" else {}          # 브라우저는 POST에 Origin을 항상 붙인다
    hdr.update(headers or {})
    req = urllib.request.Request(BASE + path, data=body, method=method, headers=hdr)
    try:
        r = op.open(req, timeout=10)
        return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")


def main():
    tmp = tempfile.mkdtemp(prefix="aiconsole_test_")
    env = dict(os.environ, AI_CONSOLE_PORT=str(PORT), AI_CONSOLE_DATA=tmp)
    srv = subprocess.Popen([sys.executable, "-I", str(ROOT / "server.py")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(BASE + "/setup", timeout=1)
                break
            except Exception:
                time.sleep(.25)
        anon = opener()
        s, h, _ = call(anon, "GET", "/")
        check("계정이 없으면 /가 /setup으로 보낸다", s == 302 and h.get("Location") == "/setup", f"{s} {h.get('Location')}")
        s, _, _ = call(anon, "GET", "/api/history")
        check("로그인 전 API는 401", s == 401, str(s))
        s, _, _ = call(anon, "POST", "/setup", {"username": "x", "password": "y", "confirm": "y"}, {"Origin": "http://evil.example"})
        check("다른 사이트(Origin)에서 온 설정 요청은 거절", s == 403, str(s))
        s, _, b = call(anon, "POST", "/setup", {"username": "tester", "password": "short", "confirm": "short"})
        check("8자 미만 비밀번호는 거절", s == 400 and "8자" in b, str(s))
        s, _, b = call(anon, "POST", "/setup", {"username": "tester", "password": "test-pass-1234", "confirm": "different-1234"})
        check("비밀번호 확인이 다르면 거절", s == 400, str(s))
        s, h, _ = call(anon, "POST", "/setup", {"username": "tester", "password": "test-pass-1234", "confirm": "test-pass-1234"})
        check("올바르게 설정하면 /login으로 이동", s == 302 and h.get("Location") == "/login", f"{s} {h.get('Location')}")
        raw = (Path(tmp) / "auth.json").read_text(encoding="utf-8")
        check("비밀번호 원문이 저장 파일에 없다", "test-pass-1234" not in raw and '"hash"' in raw)
        s, _, _ = call(anon, "GET", "/setup")
        check("계정이 생긴 뒤 /setup은 다시 못 연다", s == 302)
        s, _, _ = call(anon, "POST", "/setup", {"username": "evil", "password": "another-pass-99", "confirm": "another-pass-99"})
        check("계정이 있는데 다시 설정(덮어쓰기)은 거절", s == 302 and json.loads(raw)["user"] == "tester")
        s, _, b = call(anon, "POST", "/login", {"username": "tester", "password": "wrong-password"})
        check("틀린 비밀번호는 401", s == 401, str(s))
        jar = http.cookiejar.CookieJar()
        me = opener(jar)
        s, h, _ = call(me, "POST", "/login", {"username": "tester", "password": "test-pass-1234"})
        sc = h.get("Set-Cookie", "")
        check("로그인 성공 → 쿠키 발급(HttpOnly, SameSite=Strict)", s == 302 and "HttpOnly" in sc and "SameSite=Strict" in sc, f"{s}")
        s, h, b = call(me, "GET", "/")
        check("로그인 후 / 는 화면이 열린다", s == 200 and "TRINITY" in b, str(s))
        s, _, b = call(me, "GET", "/api/me")
        check("/api/me 가 아이디를 알려 준다", s == 200 and json.loads(b)["user"] == "tester")
        s, _, _ = call(me, "GET", "/api/history")
        check("로그인 후 API 허용", s == 200, str(s))
        s, _, _ = call(me, "POST", "/api/event", json.dumps({"tag": "T", "text": "x"}).encode(),
                       {"Content-Type": "application/json", "Origin": "http://evil.example"})
        check("다른 사이트(Origin)에서 온 요청은 로그인돼 있어도 거절", s == 403, str(s))
        s, h, _ = call(me, "POST", "/logout", {}, {"Origin": BASE})
        check("로그아웃", s == 200, str(s))
        s, _, _ = call(me, "GET", "/api/history")
        check("로그아웃 뒤 API는 다시 401", s == 401, str(s))
        # 잠금: 연속 5번 틀리면 잠깐 막힘
        codes = [call(anon, "POST", "/login", {"username": "tester", "password": f"bad{i}"})[0] for i in range(6)]
        check("연속 실패하면 잠금(429)", 429 in codes, str(codes))
        s, _, _ = call(anon, "POST", "/login", {"username": "tester", "password": "test-pass-1234"})
        check("잠금 중에는 맞는 비밀번호도 막는다", s == 429, str(s))
    finally:
        srv.terminate()
        try:
            srv.wait(5)
        except Exception:
            srv.kill()
    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)}/{len(results)} 통과")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
