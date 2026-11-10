"""AI 연동(로그인) 관리.

이 앱이 AI 서비스(Codex·Gemini)를 쓰려면, 사용자가 **앱 안에서 직접 연결**해야 한다.
이 PC에 이미 있는 로그인·환경 변수를 몰래 가져다 쓰지 않는다(다른 사람이 이 앱으로 내 토큰을 쓰는 일을 막기 위해).

- Gemini: 키를 앱에서 입력 → 윈도우 사용자 계정으로 암호화(DPAPI)해 data/connections.json 에 저장. 화면·로그·API 응답에 키는 나오지 않는다.
- Codex : 앱 전용 로그인 폴더(data/codex_home, CODEX_HOME)를 따로 쓴다. 앱의 [로그인]이 `codex login` 창을 연다.
- 예외(기본 꺼짐, 사용자가 직접 켜야 함): "이 PC의 기존 Codex 로그인 쓰기", "환경 변수 GEMINI_API_KEY 쓰기"
- Claude: 이 앱은 Claude를 호출하지 않는다(사용량 파일을 읽기만 함) → 로그인이 필요 없다.
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

_ENTROPY = b"ai-team-console/v1"


# ── 윈도우 DPAPI: 이 PC의 이 사용자 계정만 풀 수 있게 암호화 ──
def _dpapi(data: bytes, protect: bool):
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob(b):
        buf = ctypes.create_string_buffer(b, len(b))
        return BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

    inp, _keep1 = blob(data)
    ent, _keep2 = blob(_ENTROPY)
    out = BLOB()
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(inp), None, ctypes.byref(ent), None, None, 0, ctypes.byref(out))
    if not ok:
        return None
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def env_gemini_key():
    k = os.environ.get("GEMINI_API_KEY")
    if k:
        return k
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return winreg.QueryValueEx(key, "GEMINI_API_KEY")[0] or None
    except (OSError, ImportError):
        return None


def _home():
    return Path(os.environ.get("USERPROFILE") or Path.home())


def node_installed():
    return bool(shutil.which("node"))


def claude_installed():
    return bool(shutil.which("claude")) or any((_home() / ".local" / "bin" / n).exists() for n in ("claude", "claude.exe"))


def claude_logged_in():
    """Claude Code에 로그인했는지 '있는지'만 본다(내용·토큰은 읽지 않는다)."""
    if (_home() / ".claude" / ".credentials.json").exists():
        return True
    try:
        return '"oauthAccount"' in (_home() / ".claude.json").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def open_terminal(cmd: str) -> bool:
    """새 터미널 창에서 명령을 연다(윈도우만). 다른 OS는 False — 화면에 보여 주는 명령을 사용자가 직접 실행한다."""
    if sys.platform != "win32":
        return False
    subprocess.Popen(["powershell", "-NoProfile", "-NoExit", "-Command", cmd], creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    return True


def codex_installed():
    if shutil.which("codex"):
        return True
    npm = Path(os.environ.get("APPDATA", "")) / "npm"
    return (npm / "codex.ps1").exists() or (npm / "codex.cmd").exists() or any((Path(p) / "codex").exists() or (Path(p) / "codex.exe").exists() for p in os.environ.get("PATH", "").split(os.pathsep) if p)


class Connections:
    def __init__(self, data_dir):
        self.dir = Path(data_dir)
        self.file = self.dir / "connections.json"
        self.codex_home = self.dir / "codex_home"
        self._lock = threading.Lock()

    def _load(self):
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self, cfg):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(cfg), encoding="utf-8")
        try:
            os.chmod(self.file, 0o600)
        except OSError:
            pass

    # ── Gemini ──
    def gemini_key(self):
        cfg = self._load().get("gemini", {})
        if cfg.get("key"):
            raw = base64.b64decode(cfg["key"])
            plain = _dpapi(raw, protect=False) if cfg.get("protected") else raw
            return plain.decode("utf-8") if plain else None
        if cfg.get("use_env"):
            return env_gemini_key()
        return None

    def save_gemini(self, key: str):
        with self._lock:
            cfg = self._load()
            enc = _dpapi(key.encode("utf-8"), protect=True)
            g = {"use_env": cfg.get("gemini", {}).get("use_env", False)}
            if enc is not None:
                g.update(key=base64.b64encode(enc).decode(), protected=True)
            else:                                   # 윈도우가 아니면 암호화 수단이 없다 → 파일 권한(600)으로만 보호(경고 표시)
                g.update(key=base64.b64encode(key.encode("utf-8")).decode(), protected=False)
            cfg["gemini"] = g
            self._save(cfg)

    def clear_gemini(self):
        with self._lock:
            cfg = self._load()
            cfg["gemini"] = {"use_env": cfg.get("gemini", {}).get("use_env", False)}
            self._save(cfg)

    def set_gemini_env(self, on: bool):
        with self._lock:
            cfg = self._load()
            cfg.setdefault("gemini", {})["use_env"] = bool(on)
            self._save(cfg)

    # ── Codex ──
    def codex_app_login(self) -> bool:
        return (self.codex_home / "auth.json").exists()

    def codex_system_login(self) -> bool:
        return (Path(os.environ.get("USERPROFILE") or Path.home()) / ".codex" / "auth.json").exists()

    def set_codex_system(self, on: bool):
        with self._lock:
            cfg = self._load()
            cfg.setdefault("codex", {})["use_system"] = bool(on)
            self._save(cfg)

    def codex_env(self):
        """Codex 호출에 쓸 환경 변수. 연결이 없으면 None(호출하지 않는다)."""
        if self.codex_app_login():
            return {"CODEX_HOME": str(self.codex_home)}
        if self._load().get("codex", {}).get("use_system") and self.codex_system_login():
            return {}
        return None

    def codex_login_start(self):
        self.codex_home.mkdir(parents=True, exist_ok=True)
        home = str(self.codex_home).replace("'", "''")
        cmd = f"$env:CODEX_HOME='{home}'; Write-Host 'Codex 로그인 — 안내를 따라 로그인한 뒤 이 창을 닫으세요.'; codex login"
        return open_terminal(cmd)

    def claude_login_start(self):
        """Claude Code를 새 창으로 연다. 처음이면 안내에 따라 로그인한다(이 앱은 로그인 값을 읽지 않는다)."""
        return open_terminal("Write-Host 'Claude Code — 로그인 안내가 나오면 따라 하고, 끝나면 이 창을 닫으세요.'; claude")

    def codex_logout(self):
        a = self.codex_home / "auth.json"
        if a.exists():
            a.unlink()

    # ── 상태(키·토큰 값은 절대 담지 않는다) ──
    def status(self):
        cfg = self._load()
        g = cfg.get("gemini", {})
        saved = bool(g.get("key"))
        env_on = bool(g.get("use_env")) and bool(env_gemini_key())
        c = cfg.get("codex", {})
        app_ok = self.codex_app_login()
        sys_ok = bool(c.get("use_system")) and self.codex_system_login()
        return {
            "gemini": {"connected": saved or env_on, "source": "saved" if saved else ("env" if env_on else None), "protected": bool(g.get("protected")) if saved else None,
                       "use_env": bool(g.get("use_env")), "env_available": bool(env_gemini_key())},
            "codex": {"connected": app_ok or sys_ok, "source": "app" if app_ok else ("system" if sys_ok else None), "use_system": bool(c.get("use_system")),
                      "system_available": self.codex_system_login(), "cli_installed": codex_installed()},
            "claude": {"connected": None, "installed": claude_installed(), "logged_in": claude_logged_in(),
                       "note": "이 앱은 Claude를 직접 호출하지 않아요(사용량 기록을 읽기만 함). 앱에서 로그인할 필요는 없습니다."},
            "env": {"platform": sys.platform, "node": node_installed(), "can_open_terminal": sys.platform == "win32"},
        }
