"""스크린샷 촬영 — 데모 서버(가짜 데이터)를 헤드리스 Chrome으로 찍는다. 실제 화면·실제 데이터는 쓰지 않는다.

사용법: python -I tools/shoot.py <결과 폴더>
  1) 임시 폴더에 데모 데이터를 만들고 데모 서버를 다른 포트로 띄운다
  2) 헤드리스 Chrome이 로그인 → 디자인별 화면을 PNG로 저장한다
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8796                      # 데모 서버(연결된 것처럼 보임)
PORT_NOCONN = 8793               # 데모 서버(연결 안 된 모습 — 연동 창이 자동으로 열림)
CHROME = next((p for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                           r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe") if Path(p).exists()), None)
SHOTS = [  # (파일 이름, 경로, 테마, 화면을 띄워 두는 시간(ms), 서버 포트)
    ("01_login", "/login", None, 2500, PORT),
    ("02_solar", "/?theme=solar", "solar", 7000, PORT),
    ("03_ocean", "/?theme=ocean", "ocean", 7000, PORT),
    ("04_control_room", "/?theme=mission", "mission", 9000, PORT),
    ("05_connect", "/?theme=ocean", "ocean", 7000, PORT_NOCONN),
]


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not CHROME:
        sys.exit("Chrome/Edge를 찾지 못했어요.")
    tmp = Path(tempfile.mkdtemp(prefix="aic_shoot_"))
    data = tmp / "data"
    subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "demo_data.py"), str(data)], check=True, stdout=subprocess.DEVNULL)
    env = dict(os.environ, AI_CONSOLE_DATA=str(data), AI_CONSOLE_DEMO="1", AI_CONSOLE_PORT=str(PORT))
    srv = subprocess.Popen([sys.executable, "-I", str(ROOT / "server.py")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    env2 = dict(env, AI_CONSOLE_PORT=str(PORT_NOCONN), AI_CONSOLE_DEMO_NOCONN="1")
    srv2 = subprocess.Popen([sys.executable, "-I", str(ROOT / "server.py")], env=env2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for port in (PORT, PORT_NOCONN):
            for _ in range(40):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/api/alive", timeout=1)
                    break
                except Exception:
                    time.sleep(.25)
        profile = tmp / "profile"
        for name, path, theme, budget, port in SHOTS:
            url = f"http://127.0.0.1:{port}" + ("/demo-login" if theme else path)
            args = [CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", "--window-size=1700,950", "--hide-scrollbars",
                    f"--timeout={budget}", f"--screenshot={out / (name + '.png')}"]
            if theme:                                                  # 로그인 쿠키는 세션 유지가 안 되므로 테마 지정은 주소 뒤 해시로 넘긴다
                url = f"http://127.0.0.1:{port}/demo-login?next={theme}"
            proc = subprocess.Popen(args + [url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                proc.wait(timeout=90)
            except subprocess.TimeoutExpired:
                proc.kill()                                            # 우리가 띄운 Chrome만 종료(다른 창은 건드리지 않음)
                print("시간 초과:", name)
            print("찍음:", name, (out / (name + ".png")).exists())
    finally:
        srv.terminate()
        srv2.terminate()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "screenshots")
