"""AI 연동(로그인) 시험 — 연결하지 않으면 호출되지 않고, 키는 어디에도 평문으로 남지 않는지 확인한다.
임시 폴더·다른 포트에서 서버를 따로 띄운다(실제 data 폴더·실제 로그인은 건드리지 않음). 외부 서비스에는 연결하지 않는다.
실행: python -X utf8 -I tests/test_connect.py
"""
import base64
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
PORT = 8795
BASE = f"http://127.0.0.1:{PORT}"
ENV_KEY = "ENVKEY" + "x" * 30                       # 환경 변수에 일부러 넣어 두는 가짜 키(앱이 몰래 쓰면 안 된다)
SAVE_KEY = "TESTKEY" + "y" * 28                     # 연동 화면에서 저장해 보는 가짜 키
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def call(op, method, path, data=None, headers=None, as_json=False):
    if as_json:
        body, hdr = json.dumps(data or {}).encode(), {"Content-Type": "application/json"}
    else:
        body, hdr = (urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data), {}
    if method == "POST":
        hdr["Origin"] = BASE
    hdr.update(headers or {})
    try:
        r = op.open(urllib.request.Request(BASE + path, data=body, method=method, headers=hdr), timeout=15)
        return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="aiconn_test_"))
    env = dict(os.environ, AI_CONSOLE_PORT=str(PORT), AI_CONSOLE_DATA=str(tmp), AI_CONSOLE_SKIP_VALIDATE="1", GEMINI_API_KEY=ENV_KEY)
    env.pop("AI_CONSOLE_DEMO", None)
    srv = subprocess.Popen([sys.executable, "-I", str(ROOT / "server.py")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(BASE + "/setup", timeout=1)
                break
            except Exception:
                time.sleep(.25)
        anon = urllib.request.build_opener(NoRedirect())
        call(anon, "POST", "/setup", {"username": "tester", "password": "test-pass-1234", "confirm": "test-pass-1234"})
        jar = http.cookiejar.CookieJar()
        me = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPCookieProcessor(jar))
        call(me, "POST", "/login", {"username": "tester", "password": "test-pass-1234"})

        s, _ = call(anon, "POST", "/api/connect", {"action": "gemini_clear"}, as_json=True)
        check("로그인 전에는 연동 설정을 못 바꾼다(401)", s == 401, str(s))
        s, _ = call(me, "POST", "/api/connect", {"action": "gemini_clear"}, {"Origin": "http://evil.example"}, as_json=True)
        check("다른 사이트(Origin)의 연동 변경 요청은 거절(403)", s == 403, str(s))

        s, b = call(me, "GET", "/api/connect")
        st = json.loads(b)
        check("환경 변수에 키가 있어도 처음에는 '연결 안 됨'(몰래 쓰지 않는다)", s == 200 and st["gemini"]["connected"] is False and st["gemini"]["env_available"] is True)
        check("Codex도 처음에는 '연결 안 됨'(이 PC의 기존 로그인을 쓰지 않는다)", st["codex"]["connected"] is False and st["codex"]["use_system"] is False)
        check("Claude는 로그인이 필요 없다는 안내", st["claude"]["connected"] is None and "직접 호출하지" in st["claude"]["note"])

        check("설치·로그인 안내용 상태가 있다(Claude 설치/로그인 여부, 이 PC 종류)", isinstance(st["claude"]["installed"], bool) and isinstance(st["claude"]["logged_in"], bool) and "platform" in st["env"])
        check("상태에 토큰·키 값은 없다(있는지 여부만)", "sk-" not in json.dumps(st) and ENV_KEY not in json.dumps(st))

        # ── 연결 없이 호출하면 외부 서비스를 부르지 않고 바로 멈춘다 ──
        s, b = call(me, "POST", "/api/review", {"prompt": "시험", "who": ["codex", "gemini"]}, as_json=True)
        rid = json.loads(b)["id"]
        t0, run = time.time(), {}
        while time.time() - t0 < 10:
            run = json.loads(call(me, "GET", f"/api/run/{rid}")[1])
            if all(w["status"] not in ("wait", "running") for w in run["who"].values()):
                break
            time.sleep(.2)
        w = run["who"]
        check("연결 없이 호출하면 Codex·Gemini 모두 '연결 필요'로 실패", all(w[k]["status"] == "failed" and w[k].get("reason") == "noconn" for k in ("codex", "gemini")), str({k: w[k].get("reason") for k in w}))
        check("외부 호출 없이 즉시 끝난다(5초 안)", time.time() - t0 < 5, f"{time.time() - t0:.1f}s")
        check("실패 안내에 '연동'이 들어 있다", "연동" in w["gemini"]["output"] and "연동" in w["codex"]["output"])

        # ── Gemini 키 저장 ──
        s, _ = call(me, "POST", "/api/connect", {"action": "gemini_save", "key": "짧은키"}, as_json=True)
        check("잘못된 형식의 키는 거절(400)", s == 400, str(s))
        s, b = call(me, "POST", "/api/connect", {"action": "gemini_save", "key": SAVE_KEY}, as_json=True)
        st = json.loads(b)
        check("키를 저장하면 '연결됨(저장)'", s == 200 and st["gemini"]["connected"] and st["gemini"]["source"] == "saved")
        check("응답 어디에도 키가 없다", SAVE_KEY not in b and ENV_KEY not in b)
        stored = (tmp / "connections.json").read_text(encoding="utf-8")
        check("저장 파일에 키 평문이 없다", SAVE_KEY not in stored and base64.b64encode(SAVE_KEY.encode()).decode() not in stored)
        if sys.platform == "win32":
            check("윈도우에서는 암호화(DPAPI)되어 저장된다", st["gemini"]["protected"] is True)
        s, b = call(me, "GET", "/api/connect")
        check("상태 조회에도 키가 없다", SAVE_KEY not in b)
        s, b = call(me, "POST", "/api/connect", {"action": "gemini_clear"}, as_json=True)
        check("연결 해제하면 다시 '연결 안 됨'", json.loads(b)["gemini"]["connected"] is False)
        check("해제 뒤 저장 파일에서 키가 사라진다", "key" not in json.loads((tmp / "connections.json").read_text(encoding="utf-8")).get("gemini", {}))

        # ── 환경 변수·기존 로그인 사용은 사용자가 직접 켠 경우에만 ──
        s, b = call(me, "POST", "/api/connect", {"action": "gemini_env", "on": True}, as_json=True)
        st = json.loads(b)
        check("'환경 변수 쓰기'를 켜면 그때부터 연결됨(env)", st["gemini"]["connected"] and st["gemini"]["source"] == "env" and ENV_KEY not in b)
        s, b = call(me, "POST", "/api/connect", {"action": "gemini_env", "on": False}, as_json=True)
        check("다시 끄면 연결 안 됨", json.loads(b)["gemini"]["connected"] is False)
        s, b = call(me, "POST", "/api/connect", {"action": "codex_system", "on": True}, as_json=True)
        st = json.loads(b)
        check("'이 PC의 Codex 로그인 쓰기'는 켜도 실제 로그인이 있을 때만 연결", st["codex"]["use_system"] is True and st["codex"]["connected"] == st["codex"]["system_available"])
        s, b = call(me, "POST", "/api/connect", {"action": "codex_system", "on": False}, as_json=True)
        check("끄면 다시 연결 안 됨", json.loads(b)["codex"]["connected"] is False)
        s, _ = call(me, "POST", "/api/connect", {"action": "does_not_exist"}, as_json=True)
        check("알 수 없는 요청은 거절(400)", s == 400, str(s))
        # ── 암호화한 키를 다시 꺼내면 원래 키로 복원된다(저장만 되고 못 쓰는 일이 없게) ──
        sys.path.insert(0, str(ROOT))
        from connect import Connections
        c = Connections(Path(tempfile.mkdtemp(prefix="aiconn_rt_")))
        c.save_gemini(SAVE_KEY)
        check("암호화해 저장한 키를 꺼내면 원래 키와 같다", c.gemini_key() == SAVE_KEY)
        other = Connections(Path(tempfile.mkdtemp(prefix="aiconn_none_")))
        check("연결하지 않은 곳에서는 키가 나오지 않는다(환경 변수 무시)", other.gemini_key() is None)
        check("연결하지 않으면 Codex 환경도 없다(None)", other.codex_env() is None)
    finally:
        srv.terminate()
        try:
            srv.wait(5)
        except Exception:
            srv.kill()
    ok = sum(results)
    print(f"\n{ok}/{len(results)} 통과")
    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    main()
