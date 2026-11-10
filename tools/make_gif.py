"""README용 시연 GIF 만들기 — 데모 서버(가짜 데이터)를 헤드리스 Chrome으로 띄워 디자인 3종을 차례로 보여 주는 GIF를 만든다.

실행: python tools/make_gif.py [출력폴더]   (Pillow 필요. 실제 계정·실제 기록은 쓰지 않는다)
"""
import base64
import io
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PORT, CDP = 8797, 9334
CHROME = next((p for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe") if Path(p).exists()), None)


class WS:
    """표준 라이브러리만 쓰는 아주 작은 웹소켓 클라이언트(Chrome 원격 제어용)."""

    def __init__(self, url):
        u = urllib.parse.urlparse(url)
        self.s = socket.create_connection((u.hostname, u.port), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.s.recv(1)
        self.n = 0

    def _read(self, n):
        b = b""
        while len(b) < n:
            c = self.s.recv(n - len(b))
            if not c:
                raise ConnectionError("closed")
            b += c
        return b

    def _recv(self):
        data = b""
        while True:
            h = self._read(2)
            fin, ln = h[0] & 0x80, h[1] & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._read(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._read(8))[0]
            data += self._read(ln)
            if fin:
                return data

    def call(self, method, params=None):
        self.n += 1
        msg = json.dumps({"id": self.n, "method": method, "params": params or {}}).encode()
        mask = os.urandom(4)
        hdr = bytes([0x81])
        if len(msg) < 126:
            hdr += bytes([0x80 | len(msg)])
        elif len(msg) < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack(">H", len(msg))
        else:
            hdr += bytes([0x80 | 127]) + struct.pack(">Q", len(msg))
        self.s.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(msg)))
        while True:
            r = json.loads(self._recv())
            if r.get("id") == self.n:
                return r.get("result", {})


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="aic_gif_"))
    data = tmp / "data"
    subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "demo_data.py"), str(data)], check=True, stdout=subprocess.DEVNULL)
    env = dict(os.environ, AI_CONSOLE_DATA=str(data), AI_CONSOLE_DEMO="1", AI_CONSOLE_PORT=str(PORT))
    srv = subprocess.Popen([sys.executable, "-I", str(ROOT / "server.py")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome = None
    frames = []
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/alive", timeout=1)
                break
            except Exception:  # noqa: BLE001
                time.sleep(.25)
        chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--remote-debugging-port={CDP}", f"--user-data-dir={tmp / 'profile'}", "--remote-allow-origins=*", "about:blank"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(40):
            try:
                tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{CDP}/json").read())
                break
            except Exception:  # noqa: BLE001
                time.sleep(.25)
        ws = WS(next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"])
        ws.call("Page.enable")
        ws.call("Emulation.setDeviceMetricsOverride", {"width": 1500, "height": 850, "deviceScaleFactor": 1, "mobile": False})
        for theme, n in (("solar", 14), ("ocean", 14), ("mission", 14)):
            ws.call("Page.navigate", {"url": f"http://127.0.0.1:{PORT}/demo-login?next={theme}"})
            time.sleep(4.5)
            for _ in range(n):
                r = ws.call("Page.captureScreenshot", {"format": "png"})
                im = Image.open(io.BytesIO(base64.b64decode(r["data"]))).convert("RGB")
                frames.append(im.resize((900, int(im.height * 900 / im.width)), Image.LANCZOS))
                time.sleep(.12)
    finally:
        if chrome:
            chrome.terminate()
        srv.terminate()
        shutil.rmtree(tmp, ignore_errors=True)
    if len(frames) < 10:
        sys.exit("화면을 충분히 모으지 못했어요.")
    imgs = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    target = out / "demo-themes.gif"
    imgs[0].save(target, save_all=True, append_images=imgs[1:], duration=260, loop=0, optimize=True)
    print("저장:", target, round(target.stat().st_size / 1e6, 2), "MB,", len(frames), "장")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/images")
