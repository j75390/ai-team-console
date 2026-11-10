"""로그인·첫 설정 화면(외부 파일·CDN 없이 이 파일만으로 그려진다)."""
from html import escape

_CSS = """
:root{color-scheme:dark} *{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(ellipse at 50% 40%,#0a1424,#03060c 70%);
 color:#e8eef7;font-family:"Pretendard","Malgun Gothic",system-ui,sans-serif}
.card{width:min(380px,92vw);background:rgba(13,20,32,.85);border:1px solid rgba(90,120,160,.25);border-radius:14px;padding:30px 28px}
.logo{display:flex;align-items:center;gap:10px;font-weight:800;letter-spacing:.14em;font-size:13px;color:#7f90a8}
.dot{width:9px;height:9px;border-radius:50%;background:#34e0b0;box-shadow:0 0 10px #34e0b0}
h1{margin:14px 0 4px;font-size:22px;letter-spacing:-.02em} p{margin:0 0 18px;color:#7f90a8;font-size:13px;line-height:1.6}
label{display:block;font-size:12px;color:#7f90a8;margin:12px 0 5px}
input{width:100%;background:#070d17;border:1px solid rgba(90,120,160,.3);border-radius:8px;color:#e8eef7;padding:11px 12px;font:inherit}
input:focus{outline:none;border-color:#34e0b0;box-shadow:0 0 0 3px rgba(52,224,176,.14)}
button{width:100%;margin-top:18px;background:#34e0b0;color:#03140e;border:0;border-radius:8px;padding:12px;font:inherit;font-weight:800;cursor:pointer}
.err{margin-top:14px;padding:10px 12px;border-radius:8px;background:rgba(255,92,108,.1);border:1px solid rgba(255,92,108,.4);color:#ff9aa4;font-size:13px}
.note{margin-top:16px;font-size:11.5px;color:#4c5b72;line-height:1.6}
"""


def _page(title, heading, sub, fields, button, action, error=None, note=""):
    err = f'<div class="err">{escape(error)}</div>' if error else ""
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>{_CSS}</style></head><body>
<form class="card" method="post" action="{action}" autocomplete="off">
<div class="logo"><span class="dot"></span>AI TEAM CONSOLE</div><h1>{escape(heading)}</h1><p>{escape(sub)}</p>
{fields}{err}<button type="submit">{escape(button)}</button><div class="note">{note}</div></form>
<script>setInterval(function(){{fetch('/api/alive').catch(function(){{}})}},20000);fetch('/api/alive').catch(function(){{}});</script></body></html>"""


def login_page(error=None):
    f = ('<label>아이디</label><input name="username" required autofocus autocomplete="username">'
         '<label>비밀번호</label><input name="password" type="password" required autocomplete="current-password">')
    return _page("로그인 · AI 팀 관제", "로그인", "로그인해야 관제 화면이 열려요.", f, "로그인", "/login", error,
                 "이 화면은 이 PC에서만 열립니다. 비밀번호를 잊으면 data 폴더의 auth.json을 지우고 다시 설정하세요.")


def setup_page(error=None):
    f = ('<label>아이디 (3~32자)</label><input name="username" required autofocus autocomplete="off">'
         '<label>비밀번호 (8자 이상)</label><input name="password" type="password" required minlength="8" autocomplete="new-password">'
         '<label>비밀번호 확인</label><input name="confirm" type="password" required minlength="8" autocomplete="new-password">')
    return _page("처음 설정 · AI 팀 관제", "처음 설정", "이 앱을 쓸 계정을 만들어요. 한 번만 하면 됩니다.", f, "계정 만들기", "/setup", error,
                 "비밀번호는 해시(PBKDF2)로만 이 PC의 data 폴더에 저장되고, 원문은 어디에도 남지 않아요. 복구할 수 없으니 잘 기억해 두세요.")
