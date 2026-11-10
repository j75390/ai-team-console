"""AI 팀 관제 화면 서버 (로컬 전용).

- 화면: http://127.0.0.1:8765/
- 기록: runs.jsonl (한 줄에 한 번의 요청)
- 리뷰어 호출은 CLAUDE.md 규칙과 같다:
    Gemini = gemini-review.ps1, Codex = codex exec --sandbox read-only
  파일 수정은 하지 않는다. 키는 읽지도 출력하지도 않는다.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                # python -I(격리 모드)에서는 자기 폴더가 경로에 안 들어가므로 직접 추가
import pages  # noqa: E402
from auth import Auth, AuthError  # noqa: E402
from connect import Connections  # noqa: E402
DATA = Path(os.environ.get("AI_CONSOLE_DATA") or HERE / "data")   # 개인 기록(호출 내용·이벤트·계정)은 전부 여기에만 — 깃에 올리지 않는 폴더
DATA.mkdir(exist_ok=True)
for _n in ("runs.jsonl", "events.jsonl", "models.json"):          # 예전 위치의 파일이 있으면 data 폴더로 옮김
    if (HERE / _n).exists() and not (DATA / _n).exists():
        (HERE / _n).replace(DATA / _n)
AUTH = Auth(DATA)
CONN = Connections(DATA)                      # AI 연동(로그인) — 앱 안에서 연결한 것만 쓴다
SKIP_VALIDATE = bool(os.environ.get("AI_CONSOLE_SKIP_VALIDATE"))   # 시험용: Gemini 키를 Google에 확인하지 않고 저장
DEMO = bool(os.environ.get("AI_CONSOLE_DEMO"))          # 데모 모드(가짜 사용량) — 스크린샷·시연용
RUNS = DATA / "runs.jsonl"
HOST, PORT = "127.0.0.1", int(os.environ.get("AI_CONSOLE_PORT") or 8765)
TIMEOUT_SEC = 300
MAX_OUT = 12000
LOCK = threading.Lock()
STATE = {}  # run_id -> {"prompt","started","who":{name:{"status","output","sec"}}}

TOOLS = Path(os.environ["USERPROFILE"]) / ".claude" / "tools" / "gemini-review.ps1"

REVIEWERS = ("codex", "gemini")
CODEX_CMD = ('[Console]::OutputEncoding=[Text.Encoding]::UTF8; '
             '$null | codex exec --sandbox read-only --skip-git-repo-check {model}$env:AI_PROMPT')
GEMINI_DEFAULT = "gemini-3.5-flash"
MODEL_FILE = DATA / "models.json"           # 화면에서 고른 모델(data 폴더에만 저장, 전역 설정은 건드리지 않음)
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")  # 모델 이름은 환경변수로만 넘기므로 형식만 점검
HOME = Path(os.environ["USERPROFILE"])
_cache = {}


def load_sel():
    try:
        return json.loads(MODEL_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def codex_default():
    try:
        m = re.search(r'^model\s*=\s*"([^"]+)"', (HOME / ".codex" / "config.toml").read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def codex_options():
    try:
        d = json.loads((HOME / ".codex" / "models_cache.json").read_text(encoding="utf-8"))
        return [{"id": m["slug"], "name": m.get("display_name") or m["slug"]}
                for m in d.get("models", []) if m.get("visibility") == "list"]
    except (OSError, ValueError, KeyError):
        return []


class NotConnected(RuntimeError):
    """이 AI는 앱에서 연결(로그인)되지 않았다 — 외부 서비스를 부르지 않고 바로 멈춘다."""


def gemini_key():
    """앱에서 연결한 Gemini 키만 쓴다(환경 변수는 사용자가 연동 화면에서 켠 경우에만)."""
    return CONN.gemini_key()


def gemini_default():
    return os.environ.get("GEMINI_MODEL") or GEMINI_DEFAULT


def gemini_options():
    """Google에 모델 목록을 물어본다(10분 캐시). 실패하면 빈 목록."""
    hit = _cache.get("gem")
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    key, out = gemini_key(), []
    if key:
        try:
            req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                                         headers={"x-goog-api-key": key})
            with urllib.request.urlopen(req, timeout=15) as r:
                for m in json.loads(r.read().decode("utf-8")).get("models", []):
                    mid = m.get("name", "").replace("models/", "")
                    skip = ("tts", "image", "live", "audio", "embedding", "computer-use", "robotics", "native", "customtools")
                    if (mid.startswith("gemini-") and "generateContent" in m.get("supportedGenerationMethods", [])
                            and not any(s in mid for s in skip)):
                        out.append({"id": mid, "name": m.get("displayName") or mid})
        except Exception:  # noqa: BLE001  (키가 섞일 수 있는 메시지는 버린다)
            out = []
    _cache["gem"] = (time.time(), out)
    return out


def claude_model():
    try:
        return json.loads((HOME / ".claude" / "settings.json").read_text(encoding="utf-8")).get("model")
    except (OSError, ValueError):
        return None


CLAUDE_OPTIONS = [
    {"id": "opus", "name": "Opus (별칭, 최신)"}, {"id": "sonnet", "name": "Sonnet (별칭, 최신)"},
    {"id": "haiku", "name": "Haiku (별칭, 최신)"},
    {"id": "claude-fable-5-1", "name": "Fable 5.1"}, {"id": "claude-opus-5-5", "name": "Opus 5.5"},
    {"id": "claude-sonnet-5-5", "name": "Sonnet 5.5"}, {"id": "claude-haiku-5-5", "name": "Haiku 5.5"},
]


def set_claude_model(model):
    """~/.claude/settings.json 의 "model" 항목만 바꾼다(다른 항목은 그대로). 처음 한 번 백업을 만든다."""
    f = HOME / ".claude" / "settings.json"
    data = json.loads(f.read_text(encoding="utf-8"))   # 읽을 수 없으면 아무것도 쓰지 않고 오류
    bak = f.with_name("settings.json.bak-aiteam")
    if not bak.exists():
        bak.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    if model:
        data["model"] = model
    else:
        data.pop("model", None)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def current_model(ai):
    if ai == "claude":
        return claude_model()
    sel = load_sel().get(ai)
    if sel:
        return sel
    return codex_default() if ai == "codex" else gemini_default()


def models_info():
    sel = load_sel()
    return {
        "codex": {"current": current_model("codex"), "default": codex_default(), "chosen": sel.get("codex"),
                  "options": codex_options(), "changeable": True},
        "gemini": {"current": current_model("gemini"), "default": gemini_default(), "chosen": sel.get("gemini"),
                   "options": gemini_options(), "changeable": True},
        "claude": {"current": claude_model(), "options": CLAUDE_OPTIONS, "changeable": True,
                   "note": "고른 값은 ~/.claude/settings.json 에 저장돼 새로 여는 Claude Code 세션부터 적용됩니다. "
                           "지금 대화 중인 세션은 그 창에서 /model 로 바꿔야 해요."},
    }


def parse_retry_delay(body, header=None):
    """Gemini 429 응답에서 '몇 초 뒤 재시도' 값을 찾는다(없으면 None). 키·본문은 저장하지 않는다."""
    try:
        for d in json.loads(body).get("error", {}).get("details", []):
            if str(d.get("@type", "")).endswith("RetryInfo"):
                m = re.match(r"([\d.]+)s", str(d.get("retryDelay", "")))
                if m:
                    return float(m.group(1))
    except (ValueError, AttributeError):
        pass
    m = re.search(r"retry in ([\d.]+)s", body or "", re.I)
    if m:
        return float(m.group(1))
    if header and str(header).strip().isdigit():
        return float(header)
    return None


class GeminiLimit(RuntimeError):
    """요청 한도 초과(429). reset_at = 다시 시도할 수 있는 시각(ISO, UTC) 또는 None."""

    def __init__(self, delay):
        self.reset_at = None
        msg = "요청 한도를 초과했습니다. 잠시 후 다시 시도하세요."
        if delay:
            at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            self.reset_at = at.isoformat()
            local = at.astimezone().strftime("%H:%M:%S")
            msg = f"요청 한도를 초과했습니다. 약 {int(delay + .5)}초 뒤({local}) 다시 시도할 수 있어요."
        super().__init__(msg)


def call_gemini(prompt, model):
    """Gemini REST를 직접 호출해 (답, 총 토큰)을 돌려준다. 키는 헤더로만 쓰고 어디에도 남기지 않는다."""
    key = gemini_key()
    if not key:
        raise NotConnected("Gemini가 연결되지 않았어요. 상단 '연동'에서 키를 입력하세요.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    hints = {400: "요청 형식이 잘못되었거나 모델 이름을 확인하세요.", 401: "API 키가 올바르지 않습니다.",
             403: "API 키 권한이 없거나 해당 API가 활성화되지 않았습니다.", 404: f"모델 '{model}'을 찾을 수 없습니다.",
             429: "요청 한도를 초과했습니다. 잠시 후 다시 시도하세요."}
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, data=body, method="POST", headers={
                "Content-Type": "application/json; charset=utf-8", "x-goog-api-key": key})
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.loads(r.read().decode("utf-8"))
            parts = (j.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            if not text:
                raise RuntimeError("Gemini 응답에 텍스트가 없습니다.")
            return text, (j.get("usageMetadata") or {}).get("totalTokenCount")
        except urllib.error.HTTPError as e:
            delay = None
            if e.code == 429:                                         # 응답에 "N초 뒤 재시도" 정보가 있으면 읽는다
                try:
                    body_txt = e.read().decode("utf-8", "replace")
                except Exception:  # noqa: BLE001
                    body_txt = ""
                delay = parse_retry_delay(body_txt, e.headers.get("Retry-After") if e.headers else None)
            if e.code in (429, 500, 502, 503, 504) and attempt < 3 and (delay is None or delay <= 10):
                time.sleep(delay if delay else 2 ** (attempt + 1))
                continue
            if e.code == 429:
                raise GeminiLimit(delay) from None
            raise RuntimeError(f"Gemini API 호출 실패 (HTTP {e.code}): " + hints.get(e.code, "서버 오류입니다.")) from None
        except urllib.error.URLError:
            raise RuntimeError("Gemini API에 연결할 수 없습니다.") from None


NOISE = re.compile(r"^(hook:|Reading additional input|OpenAI Codex v|workdir:|model:|provider:|approval:|"
                   r"sandbox:|reasoning|session id:|-{4,}$|user$|tokens used)", re.I)


def clean(text):
    """Codex 머리말·훅 줄 같은 군더더기를 걷어낸다(답 본문은 그대로)."""
    return "\n".join(ln for ln in text.splitlines() if not NOISE.match(ln.strip())).strip()


def limit_message(text):
    """사용 한도 오류면 읽기 쉬운 한 줄로, 아니면 None."""
    if "usage limit" not in text.lower():
        return None
    m = re.search(r"try again at ([^\n]*?(?:AM|PM))", text.replace("\r", ""))
    return "사용 한도를 다 썼습니다." + (f" {m.group(1)} 이후 다시 시도할 수 있어요." if m else "")


def run_one(run_id, who):
    entry = STATE[run_id]["who"][who]
    entry["status"] = "running"
    t0 = time.time()
    model = current_model(who)
    entry["model"] = model
    prompt = STATE[run_id]["prompt"]
    if who == "gemini":
        try:
            text, tokens = call_gemini(prompt, model)
            entry["output"], entry["status"] = text.strip()[:MAX_OUT], "done"
            if tokens:
                entry["tokens"] = tokens
        except RuntimeError as e:
            entry["output"], entry["status"] = str(e), "failed"
            if isinstance(e, NotConnected):
                entry["reason"] = "noconn"
            if "한도를 초과" in str(e):
                entry["reason"] = "limit"
                if getattr(e, "reset_at", None):
                    entry["reset_at"] = e.reset_at
        except Exception as e:  # noqa: BLE001
            entry["output"], entry["status"] = f"호출 실패: {type(e).__name__}", "failed"
        entry["sec"] = round(time.time() - t0, 1)
        return finish_if_all(run_id)
    cenv = CONN.codex_env()                                  # 연결(로그인)이 없으면 Codex를 부르지 않는다
    if cenv is None:
        entry["output"], entry["status"], entry["reason"] = "Codex가 연결되지 않았어요. 상단 '연동'에서 로그인하세요.", "failed", "noconn"
        entry["sec"] = 0
        return finish_if_all(run_id)
    env = dict(os.environ, AI_PROMPT=prompt, **cenv)
    flag = ""
    if model and MODEL_RE.match(model):
        env["AI_MODEL"] = model
        flag = "-m $env:AI_MODEL "
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", CODEX_CMD.format(model=flag)],
            capture_output=True, env=env, timeout=TIMEOUT_SEC)
        out = p.stdout.decode("utf-8", "replace").strip()
        err = p.stderr.decode("utf-8", "replace").strip()
        raw = out or err
        lim = limit_message(out + "\n" + err)
        if lim:
            entry["output"], entry["status"], entry["reason"] = lim, "failed", "limit"
        else:
            tk = re.search(r"tokens used\s*\n?\s*([\d,]+)", out + "\n" + err, re.I)
            if tk:
                entry["tokens"] = int(tk.group(1).replace(",", ""))
            entry["output"] = clean(raw)[:MAX_OUT]
            entry["status"] = "done" if p.returncode == 0 and out else "failed"
    except subprocess.TimeoutExpired:
        entry["output"] = f"{TIMEOUT_SEC}초 안에 답이 없어 중단했습니다."
        entry["status"] = "failed"
    except Exception as e:  # noqa: BLE001
        entry["output"] = f"호출 실패: {type(e).__name__}"
        entry["status"] = "failed"
    entry["sec"] = round(time.time() - t0, 1)
    finish_if_all(run_id)


def finish_if_all(run_id):
    with LOCK:
        s = STATE[run_id]
        if s.get("saved") or any(w["status"] in ("wait", "running") for w in s["who"].values()):
            return
        s["saved"] = True
        rec = {"id": run_id, "prompt": s["prompt"], "started": s["started"], "who": s["who"]}
        with RUNS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def start_run(prompt, who_list):
    run_id = uuid.uuid4().hex[:8]
    STATE[run_id] = {"prompt": prompt, "started": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "who": {w: {"status": "wait", "output": "", "sec": 0} for w in who_list}}
    for w in who_list:  # 동시에(병렬로) 호출
        threading.Thread(target=run_one, args=(run_id, w), daemon=True).start()
    return run_id


def claude_state():
    """햄스터 mod가 5초마다 쓰는 Claude 사용량 파일을 읽어 일부만 돌려준다(읽기 전용)."""
    if DEMO:                                       # 데모 모드: 실제 사용량 대신 가짜 값(스크린샷·시연용)
        now_ms = time.time() * 1000
        return {"ok": True, "working": False, "tokens": 412000, "window": 1000000, "percent": 41, "five_hour": 36, "seven_day": 22, "usd": 12.4,
                "reset_five_hour": datetime.fromtimestamp(time.time() + 3*3600 + 20*60, timezone.utc).isoformat(),
                "reset_seven_day": datetime.fromtimestamp(time.time() + 4*86400 + 5*3600, timezone.utc).isoformat()}
    f = Path.home() / ".claude" / "hamster-state.json"            # 있으면(햄스터가 켜져 있으면) 그 값을 우선 사용
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        now = time.time() * 1000
        if now - d.get("at", 0) < 60000:
            lim = {x.get("kind"): x.get("percentUsed") for x in d.get("limits", [])}
            rst = {x.get("kind"): x.get("resetsAt") for x in d.get("limits", [])}
            return {"ok": True, "working": d.get("eatUntil", 0) > now, "source": "hamster",
                    "tokens": d.get("tokens"), "window": d.get("window"), "percent": d.get("percent"),
                    "five_hour": lim.get("five_hour"), "seven_day": lim.get("seven_day"), "usd": d.get("usd"),
                    "reset_five_hour": rst.get("five_hour"), "reset_seven_day": rst.get("seven_day")}
    except (OSError, ValueError):
        pass
    return claude_local_usage()                                        # 없으면 어느 PC에서든 Claude Code 기록(~/.claude/projects)에서 직접 계산


_tx_cache = {}          # 파일 경로 -> (수정시각, 크기, [(시각, 토큰, 메시지id)])
_cu_cache = {"at": 0, "val": {"ok": False}}


def _parse_tx(path):
    out = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"output_tokens"' not in line:
                    continue
                try:
                    r = json.loads(line)
                    m = r.get("message") or {}
                    u = m.get("usage")
                    if r.get("type") != "assistant" or not u:
                        continue
                    ts = datetime.fromisoformat(str(r.get("timestamp", "")).replace("Z", "+00:00")).timestamp()
                    ctx = (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
                    used = (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
                    out[m.get("id") or r.get("uuid")] = (ts, used, ctx)
                except (ValueError, TypeError, AttributeError):
                    continue
    except OSError:
        return []
    return [(t, u, c, i) for i, (t, u, c) in out.items()]


def claude_local_usage():
    """Claude Code가 이 PC에 남기는 대화 기록(~/.claude/projects/**/*.jsonl)에서 사용량을 센다. 로그인·네트워크 필요 없음(읽기 전용).
    한도 '퍼센트'는 서비스 쪽 값이라 알 수 없어서 토큰 수와 (추정) 초기화 시각만 준다."""
    now = time.time()
    if now - _cu_cache["at"] < 30:
        return _cu_cache["val"]
    root = Path.home() / ".claude" / "projects"
    rows = []
    try:
        for p in root.rglob("*.jsonl"):
            try:
                st = p.stat()
            except OSError:
                continue
            if now - st.st_mtime > 7 * 86400:
                continue
            key = str(p)
            c = _tx_cache.get(key)
            if not c or c[0] != st.st_mtime or c[1] != st.st_size:
                c = (st.st_mtime, st.st_size, _parse_tx(p))
                _tx_cache[key] = c
            rows += c[2]
    except OSError:
        pass
    rows = [r for r in rows if now - r[0] <= 7 * 86400]
    if not rows:
        val = {"ok": False}
    else:
        rows.sort()
        h5 = [r for r in rows if now - r[0] <= 5 * 3600]
        last = rows[-1]
        ctx = last[2]
        win = 1000000 if ctx > 200000 else 200000
        iso = lambda t: datetime.fromtimestamp(t, timezone.utc).isoformat()  # noqa: E731
        val = {"ok": now - last[0] < 7 * 86400, "working": now - last[0] < 20, "source": "local", "tokens": ctx, "window": win,
               "percent": min(100, round(ctx * 100 / win)), "five_hour": None, "seven_day": None, "usd": None,
               "tokens_5h": sum(r[1] for r in h5), "tokens_7d": sum(r[1] for r in rows),
               "reset_five_hour": iso(h5[0][0] + 5 * 3600) if h5 else None, "reset_seven_day": iso(rows[0][0] + 7 * 86400)}
    _cu_cache.update(at=now, val=val)
    return val


def conn_status():
    """연동 상태(키 값 없음). 데모 모드에서는 스크린샷용으로 모두 연결된 것처럼 보인다."""
    st = CONN.status()
    if DEMO and not os.environ.get("AI_CONSOLE_DEMO_NOCONN"):         # NOCONN: 연결 안 된 모습을 찍을 때
        for k in ("gemini", "codex"):
            st[k]["connected"], st[k]["source"] = True, "demo"
    return st


def connections():
    """각 CLI가 연결돼 있는지만 확인한다(키 값은 읽지 않고 있는지 여부만)."""
    s = conn_status()                                         # '연결'은 이 앱에서 로그인·키 입력을 마친 것만 뜻한다
    return {"codex": s["codex"]["connected"], "gemini": s["gemini"]["connected"], "claude": claude_state().get("ok", False)}


def _user_env(name):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return bool(winreg.QueryValueEx(k, name)[0])
    except OSError:
        return False


EVENTS = DATA / "events.jsonl"


def read_events(limit=80):
    if not EVENTS.exists():
        return []
    lines = EVENTS.read_text(encoding="utf-8").splitlines()[-limit:]
    out = []
    for ln in reversed(lines):
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out


def history(limit=60):
    if not RUNS.exists():
        return []
    lines = RUNS.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(x) for x in reversed(lines)]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _ok_host(self):
        return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        if getattr(self, "_cookie", None):
            self.send_header("Set-Cookie", self._cookie)
            self._cookie = None
        self.end_headers()
        self.wfile.write(data)

    def _token(self):
        m = re.search(r"(?:^|;\s*)ai_session=([A-Za-z0-9_\-]+)", self.headers.get("Cookie", ""))
        return m.group(1) if m else None

    def _authed(self):
        return AUTH.check(self._token())

    def _redirect(self, where):
        self.send_response(302)
        self.send_header("Location", where)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        if getattr(self, "_cookie", None):
            self.send_header("Set-Cookie", self._cookie)
            self._cookie = None
        self.end_headers()

    def _html(self, code, html):
        self._send(code, html, "text/html; charset=utf-8")

    def do_GET(self):
        if not self._ok_host():
            return self._send(403, "{}")
        path = self.path.split("?")[0]
        if (DEMO or os.environ.get("AI_CONSOLE_DEMO_LOGIN")) and path == "/demo-login":             # 데모 모드 전용(가짜 데이터 서버에서만 존재): 스크린샷용 자동 로그인
            token = AUTH.login("demo", "demo-only-1234")
            if token:
                nxt = (parse_qs(self.path.partition("?")[2]).get("next") or [""])[0]
                self._cookie = f"ai_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600"
                return self._redirect("/?theme=" + nxt if re.fullmatch(r"[a-z]{3,12}", nxt) else "/")
        if path == "/api/alive":                       # 창이 열려 있는지 알리는 신호(내용 없음, 로그인 불필요)
            global LAST_PING
            LAST_PING = time.time()
            return self._send(200, "{}")
        # ── 로그인 관문: 계정이 없으면 첫 설정, 로그인하지 않았으면 로그인 화면 ──
        if path == "/setup":
            return self._redirect("/login") if AUTH.has_user() else self._html(200, pages.setup_page())
        if path == "/login":
            if not AUTH.has_user():
                return self._redirect("/setup")
            return self._redirect("/") if self._authed() else self._html(200, pages.login_page())
        if not self._authed():
            if path.startswith("/api/"):
                return self._send(401, json.dumps({"error": "로그인이 필요해요."}, ensure_ascii=False))
            return self._redirect("/login" if AUTH.has_user() else "/setup")
        if path == "/api/me":
            return self._send(200, json.dumps({"user": AUTH.username()}, ensure_ascii=False))
        if path == "/api/connect":
            return self._send(200, json.dumps(conn_status(), ensure_ascii=False))
        if path == "/":
            return self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/api/claude":
            return self._send(200, json.dumps(claude_state(), ensure_ascii=False))
        if path == "/api/events":
            return self._send(200, json.dumps(read_events(), ensure_ascii=False))
        if path == "/api/models":
            return self._send(200, json.dumps(models_info(), ensure_ascii=False))
        if path == "/api/connections":
            return self._send(200, json.dumps(connections(), ensure_ascii=False))
        if path == "/api/history":
            return self._send(200, json.dumps(history(), ensure_ascii=False))
        if path.startswith("/api/run/"):
            s = STATE.get(path.rsplit("/", 1)[-1])
            return self._send(200 if s else 404, json.dumps(s or {}, ensure_ascii=False))
        self._send(404, "{}")

    def _connect(self, body):
        act = str(body.get("action", ""))
        err = lambda msg, code=400: self._send(code, json.dumps({"error": msg}, ensure_ascii=False))  # noqa: E731
        if act == "gemini_save":
            key = str(body.get("key", "")).strip()
            if not re.fullmatch(r"[A-Za-z0-9_\-]{20,200}", key):
                return err("키 형식이 올바르지 않아요(공백 없이 영문·숫자·_- 로 된 20자 이상).")
            if not SKIP_VALIDATE:                                       # 저장하기 전에 Google에 물어 진짜 키인지 확인
                try:
                    req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1", headers={"x-goog-api-key": key})
                    urllib.request.urlopen(req, timeout=15).read()
                except urllib.error.HTTPError as e:
                    return err("이 키는 쓸 수 없어요(Google이 거절했어요). 키를 다시 확인하세요." if e.code in (400, 401, 403) else f"키를 확인하지 못했어요(HTTP {e.code}).")
                except Exception:  # noqa: BLE001
                    return err("Google에 연결하지 못해 키를 확인하지 못했어요. 인터넷을 확인하세요.", 502)
            CONN.save_gemini(key)
            _cache.pop("gem", None)
        elif act == "gemini_clear":
            CONN.clear_gemini()
            _cache.pop("gem", None)
        elif act == "gemini_env":
            CONN.set_gemini_env(bool(body.get("on")))
            _cache.pop("gem", None)
        elif act == "codex_login":
            if not CONN.status()["codex"]["cli_installed"]:
                return err("codex 명령을 찾지 못했어요. Codex CLI를 먼저 설치하세요.")
            if not CONN.codex_login_start():
                return err("이 PC에서는 터미널을 자동으로 열 수 없어요. 화면의 명령을 터미널에 직접 붙여넣어 실행하세요.")
        elif act == "claude_login":
            if not CONN.status()["claude"]["installed"]:
                return err("claude 명령을 찾지 못했어요. Claude Code를 먼저 설치하세요.")
            if not CONN.claude_login_start():
                return err("이 PC에서는 터미널을 자동으로 열 수 없어요. 터미널에서 claude 를 직접 실행하세요.")
        elif act == "codex_logout":
            CONN.codex_logout()
        elif act == "codex_system":
            CONN.set_codex_system(bool(body.get("on")))
        else:
            return err("알 수 없는 요청이에요.")
        return self._send(200, json.dumps(conn_status(), ensure_ascii=False))

    def _auth_post(self):
        """로그인·첫 설정·로그아웃 (폼 전송). 비밀번호는 로그에도 화면에도 남기지 않는다."""
        n = min(int(self.headers.get("Content-Length", 0) or 0), 4096)
        form = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode("utf-8", "replace")).items()}
        if self.path == "/logout":
            AUTH.logout(self._token())
            self._cookie = "ai_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"
            return self._send(200, "{}")
        if self.path == "/setup":
            if AUTH.has_user():
                return self._redirect("/login")
            try:
                AUTH.setup(form.get("username", ""), form.get("password", ""), form.get("confirm", ""))
            except AuthError as e:
                return self._html(400, pages.setup_page(str(e)))
            return self._redirect("/login")
        if not AUTH.has_user():
            return self._redirect("/setup")
        try:
            token = AUTH.login(form.get("username", ""), form.get("password", ""))
        except AuthError as e:
            return self._html(429, pages.login_page(str(e)))
        if not token:
            return self._html(401, pages.login_page("아이디 또는 비밀번호가 맞지 않아요."))
        self._cookie = f"ai_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800"
        return self._redirect("/")

    def do_POST(self):
        if not self._ok_host() or self.headers.get("Origin", "http://127.0.0.1") not in (
                f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"):
            return self._send(403, "{}")
        if self.path in ("/login", "/setup", "/logout"):
            return self._auth_post()
        if not self._authed():
            return self._send(401, json.dumps({"error": "로그인이 필요해요."}, ensure_ascii=False))
        if self.path not in ("/api/review", "/api/model", "/api/event", "/api/connect"):
            return self._send(404, "{}")
        n = min(int(self.headers.get("Content-Length", 0)), 60000)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._send(400, "{}")
        if self.path == "/api/connect":                                # AI 연동(로그인): 키·토큰 값은 응답에 담지 않는다
            return self._connect(body)
        if self.path == "/api/event":                                  # 관제실 이벤트 로그 저장(화면에서 한 조작 기록)
            rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "tag": str(body.get("tag", ""))[:20], "text": str(body.get("text", ""))[:200],
                   "target": str(body.get("target") or "")[:12], "sim": bool(body.get("sim"))}
            with LOCK, EVENTS.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            return self._send(200, "{}")
        if self.path == "/api/model":
            ai, model = body.get("ai"), str(body.get("model", "")).strip()
            if ai not in REVIEWERS + ("claude",) or (model and not MODEL_RE.match(model)):
                return self._send(400, json.dumps({"error": "모델 이름 형식이 올바르지 않습니다."}, ensure_ascii=False))
            if ai == "claude":
                try:
                    set_claude_model(model)
                except (OSError, ValueError):
                    return self._send(500, json.dumps({"error": "settings.json을 읽거나 쓸 수 없습니다."}, ensure_ascii=False))
                return self._send(200, json.dumps({"current": claude_model()}))
            sel = load_sel()
            if model:
                sel[ai] = model
            else:
                sel.pop(ai, None)          # 빈 값 = 기본값으로 되돌리기
            MODEL_FILE.write_text(json.dumps(sel, ensure_ascii=False, indent=1), encoding="utf-8")
            return self._send(200, json.dumps({"current": current_model(ai)}))
        prompt = str(body.get("prompt", "")).strip()
        who = [w for w in body.get("who", []) if w in REVIEWERS]
        if not prompt or not who:
            return self._send(400, json.dumps({"error": "요청 내용과 리뷰어를 골라 주세요."}, ensure_ascii=False))
        self._send(200, json.dumps({"id": start_run(prompt, who)}))


LAST_PING = time.time()
IDLE_QUIT_SEC = int(os.environ.get("AI_CONSOLE_IDLE") or 180)


def _autoquit():
    """앱 창을 닫으면(신호가 끊기면) 서버도 스스로 끈다 — 런처로 켠 경우에만."""
    while True:
        time.sleep(15)
        if time.time() - LAST_PING > IDLE_QUIT_SEC:
            os._exit(0)


if __name__ == "__main__":
    print(f"AI 팀 관제 화면: http://{HOST}:{PORT}/")
    if os.environ.get("AI_CONSOLE_AUTOQUIT"):
        threading.Thread(target=_autoquit, daemon=True).start()
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
