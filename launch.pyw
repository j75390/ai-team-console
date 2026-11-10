"""앱처럼 실행: 서버를 보이지 않게 켜고, 주소창 없는 앱 창(Chrome/Edge --app)으로 연다.

더블클릭(또는 바로가기)으로 실행한다. 창을 닫으면 몇 분 뒤 서버도 스스로 꺼진다.
콘솔 창이 뜨지 않도록 .pyw 로 만들었다(pythonw 가 실행).
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORT = int(os.environ.get("AI_CONSOLE_PORT") or 8765)
URL = f"http://127.0.0.1:{PORT}"


def server_up():
    try:
        urllib.request.urlopen(URL + "/api/alive", timeout=1).read()
        return True
    except Exception:
        return False


def find_browser():
    pf, pf86, local = os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""), os.environ.get("LOCALAPPDATA", "")
    cands = [Path(pf) / "Google/Chrome/Application/chrome.exe", Path(pf86) / "Google/Chrome/Application/chrome.exe",
             Path(local) / "Google/Chrome/Application/chrome.exe", Path(pf86) / "Microsoft/Edge/Application/msedge.exe",
             Path(pf) / "Microsoft/Edge/Application/msedge.exe"]
    for c in cands:
        if c.exists():
            return str(c)
    return shutil.which("chrome") or shutil.which("msedge")


def main():
    if not server_up():
        py = Path(sys.executable)
        exe = py.with_name("python.exe") if py.name.lower() == "pythonw.exe" and py.with_name("python.exe").exists() else py
        env = dict(os.environ, AI_CONSOLE_AUTOQUIT="1")
        flags = 0x08000000 | 0x00000008          # CREATE_NO_WINDOW | DETACHED_PROCESS (콘솔 창 없이 따로 실행)
        subprocess.Popen([str(exe), "-I", str(HERE / "server.py")], cwd=str(HERE), env=env, creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            if server_up():
                break
            time.sleep(.25)
    browser = find_browser()
    if browser:
        subprocess.Popen([browser, f"--app={URL}", "--window-size=1500,920"])
    else:
        webbrowser.open(URL)


if __name__ == "__main__":
    main()
