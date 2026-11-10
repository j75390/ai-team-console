"""로컬 로그인 모듈.

- 비밀번호는 PBKDF2-SHA256(+무작위 솔트)으로 해시해 data/auth.json에만 저장한다. 원문은 어디에도 남기지 않는다.
- 로그인 성공 시 무작위 세션 토큰을 발급한다(서버 메모리에만 보관 → 서버를 끄면 모두 로그아웃).
- 연속 실패는 잠시 잠근다(무차별 대입 방지).
- 첫 실행(계정이 없을 때)에만 사용자가 직접 계정을 만든다. 기본 계정·기본 비밀번호는 없다.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

ITER = 240_000
SESSION_TTL = 8 * 3600          # 8시간
MAX_FAILS = 5                   # 연속 5번 틀리면
LOCK_SEC = 60                   # 60초 동안 잠금
NAME_RE = re.compile(r"^[A-Za-z0-9_.\-가-힣]{3,32}$")


class AuthError(Exception):
    pass


class Auth:
    def __init__(self, data_dir: Path):
        self.file = Path(data_dir) / "auth.json"
        self.sessions = {}      # token -> 만료 시각
        self.fails = 0
        self.locked_until = 0.0
        self._lock = threading.Lock()

    # ── 계정 ──
    def has_user(self) -> bool:
        return self.file.exists()

    def username(self):
        try:
            return json.loads(self.file.read_text(encoding="utf-8")).get("user")
        except (OSError, ValueError):
            return None

    @staticmethod
    def _hash(password: str, salt: bytes, iters: int) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)

    def setup(self, username: str, password: str, confirm: str):
        if self.has_user():
            raise AuthError("이미 계정이 있어요.")
        if not NAME_RE.match(username or ""):
            raise AuthError("아이디는 3~32자의 한글·영문·숫자·_.- 만 쓸 수 있어요.")
        if len(password or "") < 8:
            raise AuthError("비밀번호는 8자 이상이어야 해요.")
        if password != confirm:
            raise AuthError("비밀번호 확인이 달라요.")
        salt = os.urandom(16)
        rec = {"user": username, "salt": salt.hex(), "iter": ITER, "hash": self._hash(password, salt, ITER).hex(),
               "created": time.strftime("%Y-%m-%d")}
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(rec), encoding="utf-8")

    # ── 로그인 ──
    def login(self, username: str, password: str):
        """성공하면 세션 토큰을, 실패하면 None을 돌려준다. 잠금 중이면 AuthError."""
        with self._lock:
            now = time.time()
            if now < self.locked_until:
                raise AuthError(f"로그인 시도가 너무 많아요. {int(self.locked_until - now) + 1}초 뒤에 다시 해 주세요.")
        try:
            rec = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise AuthError("계정 정보를 읽을 수 없어요.") from None
        salt = bytes.fromhex(rec["salt"])
        got = self._hash(password or "", salt, int(rec.get("iter", ITER)))             # 아이디가 틀려도 같은 시간 동안 계산
        ok = hmac.compare_digest(got, bytes.fromhex(rec["hash"])) and hmac.compare_digest((username or "").encode(), rec["user"].encode())
        with self._lock:
            if not ok:
                self.fails += 1
                if self.fails >= MAX_FAILS:
                    self.fails = 0
                    self.locked_until = time.time() + LOCK_SEC
                return None
            self.fails = 0
            token = secrets.token_urlsafe(32)
            self.sessions[token] = time.time() + SESSION_TTL
            return token

    def check(self, token) -> bool:
        if not token:
            return False
        with self._lock:
            exp = self.sessions.get(token)
            if not exp:
                return False
            if exp < time.time():
                self.sessions.pop(token, None)
                return False
            return True

    def logout(self, token):
        with self._lock:
            self.sessions.pop(token, None)
