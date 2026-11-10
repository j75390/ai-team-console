"""산출물 생성: 번호가 붙은 PDF·엑셀 묶음과 PPT를 deliverables/ 에 만든다.

- PDF: HTML을 헤드리스 Chrome으로 인쇄해서 만든다
- 엑셀: openpyxl, PPT: python-pptx
- 스크린샷은 tools/shoot.py 가 가짜(데모) 데이터로 찍은 것만 쓴다(개인정보 없음)
실행: <python-pptx·openpyxl가 있는 python> tools/build_deliverables.py
"""
import html
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deliverables"
SHOT = OUT / "screenshots"
CHROME = next((p for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe") if Path(p).exists()), None)
E = html.escape

TITLE = "AI 팀 관제 (AI Team Console)"
PERIOD = "2026-11-09 ~ 2026-11-10 (개인 프로젝트)"

# ───────────────────────── 공통 데이터 ─────────────────────────
FR = [  # (ID, 구분, 기능명, 설명, 검증)
    ("FR-01", "리뷰", "리뷰 병렬 호출", "Codex·Gemini를 동시에 호출하고 답을 한 화면에 모아 보여 준다. 리뷰어는 읽기 전용(의견만 줌)", "Chrome에서 실제 호출 확인(Gemini 성공, Codex는 계정 한도로 실패 표시)"),
    ("FR-02", "리뷰", "호출 기록 저장·조회", "요청 문장·결과·시간·사용한 모델·토큰을 runs.jsonl에 저장하고 최근 기록을 보여 준다", "확인"),
    ("FR-03", "모델", "AI별 모델 선택", "AI(노드/카드)를 누르면 모델 목록·직접 입력·기본값 되돌리기. Codex는 호출 때만 -m, Gemini는 모델 이름 지정, Claude는 settings.json의 model만 변경(백업)", "Gemini·Codex 변경 확인, Claude 저장 확인"),
    ("FR-04", "사용량", "AI별 호출·시간·토큰", "이번 미션/오늘/전체 탭으로 호출 수·CLI 시간·토큰을 보여 준다. Gemini 토큰은 API 응답에서 읽음", "Gemini 토큰 확인, Codex 토큰은 성공 응답 미확인"),
    ("FR-05", "사용량", "Claude 한도 표시", "일일(5시간)·주간(7일) 남은 %와 초기화까지 남은 시간, 컨텍스트, 세션 토큰·비용(읽기 전용)", "확인"),
    ("FR-06", "사용량", "한도 소진 시각", "Codex 한도 소진 시 풀리는 시각, Gemini 429 응답의 재시도 시각을 카드에 표시", "Codex 확인 / Gemini는 가짜 응답으로 검증"),
    ("FR-07", "상태", "연결 상태", "Codex CLI·Gemini API·Claude Code 연결 여부 표시(키 값은 읽지 않음)", "확인"),
    ("FR-08", "화면", "디자인 3종 전환", "태양계 / 심해 / 관제실. 상단 '디자인' 드롭다운에서 고르고, 고른 값을 기억", "확인"),
    ("FR-09", "관제실", "이상 신호 탐지 레이더", "호출 실패·한도 소진·컨텍스트/한도 임계 초과·연결 끊김을 레이더 신호로 표시. 연습용 SIM 신호도 지나감", "확인"),
    ("FR-10", "관제실", "목표물 선택·명령", "신호 클릭 → 상세 패널(방위·거리·속도·도달 예상) + 명령(추적·식별·보류·재시도·해소·통과)", "확인"),
    ("FR-11", "관제실", "자동 처리·연출", "탐지→추적→식별→해소(정상 신호는 통과)를 자동 진행, ANALYZING 진행 링 + 입자 분해 + 도장", "확인"),
    ("FR-12", "관제실", "이벤트 기록", "상태 변경·명령·결과를 events.jsonl에 저장", "확인"),
    ("FR-13", "보안", "로그인", "첫 실행 때 계정 생성, 로그인해야 화면이 열림, 로그아웃, 연속 실패 잠금", "자동 시험 19개 통과"),
    ("FR-14", "실행", "앱처럼 실행", "바로가기 더블클릭 → 서버가 보이지 않게 켜지고 주소창 없는 앱 창으로 열림, 창을 닫으면 서버 자동 종료", "확인(서버 기동·자동 종료)"),
    ("FR-16", "보안", "AI 연동(로그인)", "Codex·Gemini는 앱의 '연동' 창에서 직접 연결해야 호출된다(Gemini 키 입력·암호화 저장, Codex 앱 전용 로그인). 연결 전에는 외부 호출 없이 멈춘다. 이 PC의 기존 로그인·환경 변수는 사용자가 켠 경우에만 사용", "자동 시험 26개 통과 / 실제 키·실제 Codex 로그인은 미확인"),
    ("FR-15", "시연", "데모 모드", "가짜 기록·가짜 사용량으로 동작해 스크린샷·시연에 개인 기록이 섞이지 않게 함", "확인"),
]
NFR = [
    ("NFR-01", "보안", "이 PC에서만 열림(127.0.0.1), Host·Origin 검사"),
    ("NFR-02", "보안", "비밀번호는 PBKDF2-SHA256(24만 회)+솔트 해시로만 저장, 원문 저장·로그 없음"),
    ("NFR-03", "보안", "세션 쿠키 HttpOnly·SameSite=Strict, 8시간 만료, 서버를 끄면 모두 로그아웃, 5회 실패 시 60초 잠금"),
    ("NFR-04", "개인정보", "호출 내용·이벤트·계정은 data/ 폴더에만 저장하고 깃에 올리지 않음"),
    ("NFR-05", "개인정보", "API 키는 저장·출력하지 않음(환경 변수에서 읽어 헤더로만 전송)"),
    ("NFR-06", "유지보수", "외부 파이썬 라이브러리 없이 표준 라이브러리만 사용"),
    ("NFR-08", "보안", "AI 키·토큰은 앱에서 입력한 것만 쓰고 윈도우 사용자 계정으로 암호화(DPAPI)해 data/에 저장. 화면·API 응답·로그에 키 값이 나오지 않음"),
    ("NFR-09", "개인정보", "환경 변수 키·이 PC의 기존 Codex 로그인은 기본 꺼짐(사용자가 연동 창에서 켜야 사용)"),
    ("NFR-07", "신뢰성", "실패·한도 상황을 숨기지 않고 사유와 함께 표시"),
]
API = [  # (메서드, 경로, 로그인, 설명)
    ("GET", "/", "필요", "관제 화면(index.html). 쿼리 ?theme=solar|ocean|mission 으로 디자인 지정"),
    ("GET", "/login", "-", "로그인 화면(계정이 없으면 /setup 으로 이동)"),
    ("POST", "/login", "-", "아이디·비밀번호 확인 → 세션 쿠키 발급, 5회 실패 시 60초 잠금(429)"),
    ("GET", "/setup", "-", "첫 실행 계정 설정 화면(계정이 이미 있으면 /login)"),
    ("POST", "/setup", "-", "계정 생성(아이디 3~32자, 비밀번호 8자 이상). 이미 계정이 있으면 거절"),
    ("POST", "/logout", "필요", "세션 삭제·쿠키 만료"),
    ("GET", "/api/alive", "-", "창이 열려 있다는 신호(없으면 런처 모드에서 서버 자동 종료)"),
    ("GET", "/api/me", "필요", "로그인한 아이디"),
    ("GET", "/api/claude", "필요", "Claude 사용량(컨텍스트·5시간·7일 한도·초기화 시각·토큰·비용)"),
    ("GET", "/api/connect", "필요", "AI 연동 상태(연결 여부·방식). 키·토큰 값은 담지 않음"),
    ("POST", "/api/connect", "필요", "연동 변경: gemini_save(키 확인 후 암호화 저장)·gemini_clear·gemini_env·codex_login(로그인 창 열기)·codex_logout·codex_system"),
    ("GET", "/api/models", "필요", "AI별 현재 모델·목록·변경 가능 여부"),
    ("GET", "/api/connections", "필요", "Codex·Gemini·Claude 연결 여부"),
    ("GET", "/api/history", "필요", "최근 호출 기록(최대 60건)"),
    ("GET", "/api/events", "필요", "저장된 이벤트 로그(최근 80건)"),
    ("GET", "/api/run/{id}", "필요", "진행 중·끝난 호출의 상태·결과"),
    ("POST", "/api/review", "필요", "리뷰 호출 시작(요청 문장·리뷰어 목록) → run id"),
    ("POST", "/api/model", "필요", "모델 선택/되돌리기(ai, model). 형식 검사 후 저장"),
    ("POST", "/api/event", "필요", "관제실 이벤트 한 줄 저장"),
]
DATA = [  # (파일, 필드, 설명)
    ("data/auth.json", "user, salt, iter, hash, created", "계정 1개. 비밀번호 원문 없음(해시)"),
    ("data/runs.jsonl", "id, prompt, started, who{codex|gemini: status, output, sec, model, tokens, reason, reset_at}", "한 줄에 한 번의 리뷰 호출"),
    ("data/events.jsonl", "ts, tag, text, target, sim", "관제실 이벤트 한 줄"),
    ("data/models.json", "codex, gemini", "화면에서 고른 모델(전역 설정은 건드리지 않음)"),
    ("data/connections.json", "gemini{key(암호화), protected, use_env}, codex{use_system}", "AI 연동 설정. 키는 DPAPI로 암호화"),
    ("data/codex_home/", "auth.json 등(Codex CLI가 만듦)", "앱 전용 Codex 로그인 폴더(CODEX_HOME)"),
]
AUTH_TESTS = [
    "계정이 없으면 /가 /setup으로 보낸다", "로그인 전 API는 401", "다른 사이트(Origin)에서 온 설정 요청은 거절", "8자 미만 비밀번호는 거절",
    "비밀번호 확인이 다르면 거절", "올바르게 설정하면 /login으로 이동", "비밀번호 원문이 저장 파일에 없다", "계정이 생긴 뒤 /setup은 다시 못 연다",
    "계정이 있는데 다시 설정(덮어쓰기)은 거절", "틀린 비밀번호는 401", "로그인 성공 → 쿠키 발급(HttpOnly, SameSite=Strict)", "로그인 후 /는 화면이 열린다",
    "/api/me가 아이디를 알려 준다", "로그인 후 API 허용", "다른 사이트(Origin) 요청은 로그인돼 있어도 거절", "로그아웃", "로그아웃 뒤 API는 다시 401",
    "연속 실패하면 잠금(429)", "잠금 중에는 맞는 비밀번호도 막는다",
]
CONNECT_TESTS = ["로그인 전에는 연동 설정을 못 바꾼다(401)", "다른 사이트(Origin)의 연동 변경 요청은 거절(403)", "환경 변수에 키가 있어도 처음에는 연결 안 됨(몰래 쓰지 않는다)",
                 "Codex도 처음에는 연결 안 됨(이 PC의 기존 로그인을 쓰지 않는다)", "Claude는 로그인이 필요 없다는 안내", "연결 없이 호출하면 Codex·Gemini 모두 연결 필요로 실패",
                 "외부 호출 없이 즉시 끝난다(5초 안)", "실패 안내에 연동이 들어 있다", "잘못된 형식의 키는 거절(400)", "키를 저장하면 연결됨(저장)", "응답 어디에도 키가 없다",
                 "저장 파일에 키 평문이 없다", "윈도우에서는 암호화(DPAPI)되어 저장된다", "상태 조회에도 키가 없다", "연결 해제하면 다시 연결 안 됨", "해제 뒤 저장 파일에서 키가 사라진다",
                 "환경 변수 쓰기를 켜면 그때부터 연결됨(env)", "다시 끄면 연결 안 됨", "이 PC의 Codex 로그인 쓰기는 실제 로그인이 있을 때만 연결", "끄면 다시 연결 안 됨",
                 "알 수 없는 요청은 거절(400)", "암호화해 저장한 키를 꺼내면 원래 키와 같다", "연결하지 않은 곳에서는 키가 나오지 않는다(환경 변수 무시)", "연결하지 않으면 Codex 환경도 없다(None)", "설치·로그인 안내용 상태가 있다(Claude 설치/로그인 여부, 이 PC 종류)", "상태에 토큰·키 값은 없다(있는지 여부만)"]
PRIVACY_TESTS = ["깨끗한 폴더는 통과", "나쁜 폴더는 실패(종료 코드 1)", "잡아낸다: data 폴더", "잡아낸다: auth.json", "잡아낸다: runs.jsonl", "잡아낸다: 바로가기(.lnk)", "잡아낸다: 사용자 경로",
                 "잡아낸다: 이메일", "잡아낸다: Google API 키 모양", "잡아낸다: GitHub 토큰", "잡아낸다: 비공개 키 블록", "잡아낸다: 사설 IP", "사설 낱말 목록의 낱말을 잡아낸다",
                 "--tracked: .gitignore 로 제외된 data/ 는 문제 삼지 않는다", "--tracked: 올라갈 파일의 이메일은 잡아낸다"]
TOTAL_TESTS = len(AUTH_TESTS) + len(PRIVACY_TESTS) + len(CONNECT_TESTS)

MANUAL = [  # (항목, 결과, 비고)
    ("Gemini 리뷰 호출·토큰 표시", "확인", "토큰 155~176, 응답 2~4초"),
    ("Codex 호출(한도 소진 응답 처리)", "확인", "성공 응답은 계정 한도 때문에 미확인"),
    ("Gemini 모델 변경 후 호출", "확인", "gemini-3.6-flash 로 변경해 호출 성공"),
    ("Claude 모델 저장(settings.json model만 변경·백업)", "확인", "다른 항목 그대로"),
    ("Claude 5시간·7일 한도 남은 %·초기화 시간 표시", "확인", "햄스터와 같은 값"),
    ("Codex 한도 소진 시각 표시", "확인", "응답 문구에서 시각 파싱"),
    ("Gemini 429 재시도 시각 표시", "가짜 응답으로 확인", "실제 429는 일으키지 못함"),
    ("디자인 3종 전환·기억", "확인", ""),
    ("관제실 신호 탐지→추적→식별→해소", "확인", "실제 이상(Codex 한도) 신호 포함"),
    ("관제실 재시도 명령(실제 재호출)", "확인", "한도로 실패 → 실패로 표시"),
    ("정상 신호 통과 승인→PASSED", "확인", "로그·카운터 확인"),
    ("앱 실행(서버 숨김 기동) / 창 닫으면 자동 종료", "확인", "자동 종료는 20초 설정으로 시험"),
    ("데모 모드 스크린샷(개인 기록 없음)", "확인", "가짜 기록·가짜 사용량"),
    ("깨끗한 사본(release/) 개인정보 점검", "확인", "의심 항목 없음, 나쁜 입력을 잡아내는 것은 자동 시험 15개로 확인"),
    ("연동 창: 연결 안 됨 표시·체크칸 비활성·카드 안내(화면)", "확인", "첫 방문에 연동 창이 자동으로 열림"),
    ("Gemini 실제 키 저장(Google 확인)·실제 호출", "미확인", "실제 키를 쓰지 않고 시험함(형식·암호화·해제는 확인)"),
    ("Codex 앱 로그인(codex login 창)", "미확인", "계정 로그인이 필요해 직접 해 보지 않음"),
    ("모바일·좁은 화면", "미확인", ""),
    ("Codex 토큰 표시", "미확인", "성공 응답이 있어야 확인 가능"),
    ("macOS·Linux", "미확인", "Windows에서만 시험"),
]
WBS = [  # (단계, 작업, 시작, 종료, 상태)
    ("기획", "목표·범위 정리, 영상 화면 구성 분석", "2026-11-09", "2026-11-09", "완료"),
    ("서버", "Python 서버, Codex/Gemini 병렬 호출, 호출 기록 저장", "2026-11-09", "2026-11-09", "완료"),
    ("화면", "3단 대시보드, AI별 사용량·토큰, 모델 선택", "2026-11-09", "2026-11-10", "완료"),
    ("디자인", "입자 우주 → 심해 → 관제실, 이후 태양계·심해·관제실 3종으로 정리", "2026-11-09", "2026-11-10", "완료"),
    ("관제실", "신호 탐지 레이더, 목표물 선택·명령, 자동 처리, 이벤트 로그", "2026-11-10", "2026-11-10", "완료"),
    ("한도 표시", "Claude 일일·주간 한도, Codex·Gemini 한도 시각", "2026-11-10", "2026-11-10", "완료"),
    ("보안", "로그인(첫 설정·세션·잠금), data 폴더 분리, 자동 시험 19개", "2026-11-10", "2026-11-10", "완료"),
    ("실행", "앱처럼 실행(런처·바로가기·자동 종료), 데모 모드", "2026-11-10", "2026-11-10", "완료"),
    ("산출물", "문서·엑셀·PPT, 스크린샷(가짜 데이터)", "2026-11-10", "2026-11-10", "완료"),
    ("공개 준비", "개인정보 점검 도구, 깨끗한 사본, 날짜별 업로드 계획", "2026-11-10", "2026-11-10", "완료"),
    ("업로드", "날짜별로 나누어 깃에 업로드(계획표 참고)", "2026-11-10", "2026-11-14", "예정"),
    ("후속", "Codex 성공 응답 확인(한도 해제 후), 검증기(VERIFIER) 단계 실제 동작", "미정", "미정", "예정"),
]


def pdf(name, body, landscape=True):
    htmlfile = OUT / "_tmp.html"
    css = """@page{size:A4 %s;margin:14mm}body{font-family:"Malgun Gothic","Noto Sans KR",sans-serif;color:#1b2430;font-size:12.5px;line-height:1.7}
h1{font-size:25px;margin:0 0 4px;color:#0f1b2d}h2{font-size:16px;margin:20px 0 6px;color:#0f6f69;border-left:4px solid #34e0b0;padding-left:8px}
.sub{color:#5b6b80;margin-bottom:14px}table{border-collapse:collapse;width:100%%;margin:8px 0;font-size:11.5px}th{background:#0f1b2d;color:#fff;text-align:left}
th,td{border:1px solid #cfd8e3;padding:5px 8px;vertical-align:top}tr:nth-child(even) td{background:#f5f8fb}.box{background:#f1f7f6;border:1px solid #cfe5e1;border-radius:6px;padding:10px 14px;margin:8px 0}
img{max-width:100%%;border:1px solid #cfd8e3;border-radius:4px}.cap{color:#5b6b80;font-size:11px;margin-bottom:10px}ul{margin:4px 0 4px 18px;padding:0}.tag{display:inline-block;background:#e4f6f5;color:#0b6f69;border-radius:4px;padding:0 6px;font-size:11px}
footer{margin-top:18px;color:#8a96a6;font-size:10.5px;border-top:1px solid #dde4ec;padding-top:6px}""" % ("landscape" if landscape else "portrait")
    htmlfile.write_text(f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{css}</style></head><body>{body}<footer>{E(TITLE)} · 개인 프로젝트 · 가상(데모) 데이터로 만든 화면</footer></body></html>', encoding="utf-8")
    target = OUT / name
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={target}", htmlfile.as_uri()],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    print("PDF", name, target.exists())
    prev = os.environ.get("AIC_PREVIEW")                    # 확인용: 같은 내용을 PNG로도 저장(PDF는 헤드리스에서 볼 수 없어서)
    if prev:
        Path(prev).mkdir(parents=True, exist_ok=True)
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--window-size=1500,1050", "--hide-scrollbars", f"--screenshot={Path(prev) / (name[:2] + '_' + name[3:6] + '.png')}", htmlfile.as_uri()],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)


def table(headers, rows):
    th = "".join(f"<th>{E(h)}</th>" for h in headers)
    tr = "".join("<tr>" + "".join(f"<td>{E(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tr>{th}</tr>{tr}</table>"


def img(fname, cap):
    p = SHOT / fname
    return f'<img src="{p.as_uri()}"><div class="cap">{E(cap)}</div>' if p.exists() else ""


DIAGRAM_CALLS = []   # svg_boxes 호출 기록(발표용 PPT에서 같은 데이터를 도형으로 다시 그린다)


def svg_boxes(w, h, boxes, arrows):
    """간단한 구성도: boxes=[(x,y,w,h,label,fill)], arrows=[(x1,y1,x2,y2,label)]"""
    DIAGRAM_CALLS.append((w, h, boxes, arrows))
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Malgun Gothic,sans-serif" font-size="12">',
         '<defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#5b6b80"/></marker></defs>']
    for x1, y1, x2, y2, lab in arrows:
        s.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#5b6b80" stroke-width="1.5" marker-end="url(#a)"/>')
        if lab:
            s.append(f'<text x="{(x1 + x2) / 2 + 4}" y="{(y1 + y2) / 2 - 4}" fill="#5b6b80" font-size="10.5">{E(lab)}</text>')
    for x, y, bw, bh, lab, fill in boxes:
        s.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="8" fill="{fill}" stroke="#0f1b2d" stroke-width="1.2"/>')
        for i, line in enumerate(lab.split("\n")):
            s.append(f'<text x="{x + bw / 2}" y="{y + bh / 2 + 4 + (i - (len(lab.split(chr(10))) - 1) / 2) * 15}" text-anchor="middle" fill="#0f1b2d">{E(line)}</text>')
    s.append("</svg>")
    return "".join(s)


ARCH = svg_boxes(900, 420, [
    (30, 170, 150, 70, "앱 창(Chrome --app)\nindex.html · Canvas", "#e4f6f5"),
    (300, 150, 190, 110, "server.py\nHTTP 127.0.0.1:8765\n로그인 관문 · API", "#dcecff"),
    (300, 20, 190, 60, "auth.py · pages.py\n로그인·세션·화면", "#fff3d6"),
    (620, 20, 250, 70, "Codex CLI\n(codex exec --sandbox read-only)", "#e8ffe9"),
    (620, 110, 250, 70, "Gemini REST API\n(키는 헤더로만)", "#e8f0ff"),
    (620, 200, 250, 70, "Claude 사용량 파일(읽기 전용)\nhamster-state.json", "#ffeee6"),
    (620, 290, 250, 70, "Claude 설정(model 항목만 변경)\nsettings.json + 백업", "#ffeee6"),
    (300, 320, 190, 80, "data/ (깃에 올리지 않음)\nauth·runs·events·models", "#f3e8ff"),
    (30, 320, 150, 60, "launch.pyw\n서버 숨김 기동", "#eef0f3"),
], [(180, 205, 300, 205, "HTTP/쿠키"), (395, 150, 395, 80, ""), (490, 190, 620, 55, "subprocess"), (490, 200, 620, 145, "HTTPS"), (490, 225, 620, 235, "읽기"), (490, 245, 620, 325, "쓰기"),
    (395, 260, 395, 320, "기록 저장"), (105, 320, 105, 240, "기동")])

USECASE = svg_boxes(900, 380, [
    (30, 150, 110, 70, "사용자\n(본인)", "#e4f6f5"),
    (300, 10, 220, 40, "로그인 / 첫 계정 설정", "#fff3d6"),
    (300, 62, 220, 40, "리뷰 호출(Codex·Gemini)", "#dcecff"),
    (300, 114, 220, 40, "AI 모델 변경", "#dcecff"),
    (300, 166, 220, 40, "사용량·한도 확인", "#dcecff"),
    (300, 218, 220, 40, "디자인 변경", "#dcecff"),
    (300, 270, 220, 40, "이상 신호 확인·처리(관제실)", "#e8ffe9"),
    (300, 322, 220, 40, "기록 확인", "#dcecff"),
    (640, 62, 220, 40, "Codex CLI", "#eef0f3"),
    (640, 114, 220, 40, "Gemini API", "#eef0f3"),
    (640, 166, 220, 40, "Claude 사용량 파일", "#eef0f3"),
], [(140, 185, 300, 30, ""), (140, 185, 300, 82, ""), (140, 185, 300, 134, ""), (140, 185, 300, 186, ""), (140, 185, 300, 238, ""), (140, 185, 300, 290, ""), (140, 185, 300, 342, ""),
    (520, 82, 640, 82, ""), (520, 82, 640, 134, ""), (520, 186, 640, 186, "")])

LAYOUT = svg_boxes(900, 300, [
    (20, 20, 220, 260, "왼쪽 패널\n지금 상태 · 타이머\n미션 카드 · 새 미션 입력\n리뷰어 답변 · 진행 기록", "#e4f6f5"),
    (260, 20, 380, 260, "가운데\n단계 카드(계획·구현·테스트·검수·판단)\n디자인별 시각화(태양계/심해/관제실)\n상태 글자 · 단계 줄", "#dcecff"),
    (660, 20, 220, 260, "오른쪽 패널\nAI별 작업량(이번 미션/오늘/전체)\nClaude 한도 · Codex/Gemini 한도\n최근 호출 · CLI 연결", "#fff3d6"),
], [])


def build_pdfs():
    OUT.mkdir(exist_ok=True)
    pdf("01_프로젝트명_소개.pdf", f"<h1>{E(TITLE)}</h1><div class='sub'>{PERIOD}</div>"
        "<div class='box'><b>한 줄 소개</b> — Claude Code(구현·판단), Codex(코드·보안 리뷰), Gemini(설계 리뷰)가 함께 일하는 모습을 한 화면에서 호출·관찰·관리하는 로컬 관제 화면</div>"
        + table(["항목", "내용"], [("프로젝트명", TITLE), ("유형", "개인 프로젝트(1인)"), ("기간", PERIOD), ("실행 환경", "Windows PC 1대, 브라우저(앱 창)"),
                              ("기술", "Python 3(표준 라이브러리만) · HTML/CSS/JavaScript · Canvas 2D"), ("특징", "로그인, 개인 기록 분리, 3가지 디자인, 실제 한도·사용량 표시")])
        + img("04_control_room.png", "관제실 디자인(데모 데이터)"))
    pdf("02_주제선정배경_기획의도.pdf", "<h1>주제 선정 배경 · 기획 의도</h1><div class='sub'>왜 만들었나</div>"
        "<h2>배경</h2><ul><li>여러 AI(Claude·Codex·Gemini)를 역할을 나눠 쓰면 좋은 점이 많지만, 각각 터미널·창이 따로라 <b>누가 무엇을 하는지, 한도가 얼마나 남았는지</b>가 흩어져 보인다.</li>"
        "<li>한도가 다 되면 호출이 실패하는데, 원인과 풀리는 시각을 매번 찾아야 한다.</li></ul>"
        "<h2>의도</h2><ul><li>한 화면에서 호출·결과·모델·토큰·한도를 보고, 이상(실패·한도·연결 끊김)을 신호로 알려 주는 <b>관제 화면</b>을 만든다.</li>"
        "<li>개인 도구이므로 <b>로그인</b>과 <b>개인 기록 분리</b>를 처음부터 넣어, 깃에 올려도 개인정보가 섞이지 않게 한다.</li>"
        "<li>화면은 단순한 표가 아니라 보는 재미가 있게(태양계·심해·관제실) 만든다.</li></ul>"
        "<h2>참고</h2><div class='box'>화면 구성(왼쪽 미션·가운데 시각화·오른쪽 작업량)은 유튜브 '디렉터스AI'의 'AI DEV DIRECTOR' 영상의 화면 구성을 참고했다. 영상의 소스 코드는 열어 보거나 사용하지 않았고, 이 프로젝트의 코드는 모두 직접 작성했다.</div>")
    pdf("03_유사_서비스_분석·차별화.pdf", "<h1>유사 서비스 분석 · 차별화</h1><div class='sub'>범위: 종류별 비교(개별 제품의 세부 기능은 조사하지 않음)</div>"
        + table(["종류", "하는 일", "한계(이 프로젝트 관점)", "이 프로젝트의 차별점"], [
            ("터미널 기반 AI 코딩 도구", "각 AI를 터미널에서 실행", "AI별로 창이 따로, 한도·상태가 흩어짐", "세 AI를 한 화면에서 호출·비교, 한도·사용량 통합 표시"),
            ("범용 서버/서비스 모니터링 대시보드", "서버 지표 시각화", "AI 호출·한도 개념이 없음", "AI 호출 결과·한도 소진 시각·모델을 직접 다룸"),
            ("LLM 사용량 관측 도구", "토큰·비용 집계", "보통 클라우드 서비스, 계정 연동 필요", "내 PC 안에서만 동작, 개인 기록은 data 폴더에 분리"),
            ("개인 노트/작업 기록", "수동 기록", "자동 수집이 아님", "호출 기록·이벤트를 자동 저장")])
        + "<div class='box'>※ 위 표는 제품군 수준의 비교이며, 특정 제품의 기능을 단정하지 않는다.</div>")
    pdf("04_주요_기능_서비스_컨셉.pdf", "<h1>주요 기능 · 서비스 컨셉</h1><div class='sub'>컨셉: '세 AI를 지휘하는 관제실'</div>"
        + table(["ID", "구분", "기능", "설명"], [(a, b, c, d) for a, b, c, d, _ in FR])
        + img("02_solar.png", "태양계 — 세 AI가 행성이 되어 태양 둘레를 돈다") + img("03_ocean.png", "심해 — 입자로 그린 해양 생물이 헤엄친다") + img("05_connect.png", "AI 연동 창 — 연결하지 않으면 호출되지 않는다(연결 안 된 모습)"))
    pdf("05_개발환경.pdf", "<h1>개발 환경</h1>" + table(["구분", "내용"], [
        ("OS", "Windows 10"), ("언어", "Python 3.14(표준 라이브러리만), JavaScript(바닐라), HTML/CSS"), ("그리기", "Canvas 2D(외부 라이브러리 없음)"),
        ("글꼴", "Pretendard(OFL), JetBrains Mono(OFL) — CDN으로 불러옴"), ("연동", "Codex CLI(읽기 전용 샌드박스), Gemini REST API, Claude Code 사용량 파일(읽기 전용)"),
        ("시험", "자동 시험 19개(로그인), Chrome 수동 확인"), ("산출물 도구", "헤드리스 Chrome(PDF·스크린샷), openpyxl(엑셀), python-pptx(PPT)"),
        ("버전 관리", "Git(날짜별로 나누어 업로드 예정)")]))
    pdf("06_활용방안_기대효과.pdf", "<h1>활용 방안 · 기대 효과</h1><h2>활용</h2><ul><li>여러 AI에게 같은 질문을 동시에 던져 의견을 비교</li><li>AI별 한도·초기화 시각을 확인해 작업 시간 계획</li>"
        "<li>호출 실패·한도 소진을 놓치지 않고 처리 기록으로 남김</li><li>포트폴리오: 보안(로그인)·개인정보 분리·시각화를 갖춘 개인 도구</li></ul>"
        "<h2>기대 효과</h2><ul><li>한도 때문에 막혔을 때 원인·풀리는 시각을 바로 확인</li><li>AI별 역할 분담을 눈에 보이게 하여 작업 흐름 파악이 쉬워짐</li></ul>")
    pdf("10_유스케이스_다이어그램.pdf", "<h1>유스케이스 다이어그램</h1>" + USECASE)
    pdf("11_와이어프레임(요약).pdf", "<h1>화면 설계(요약)</h1><div class='sub'>3단 구성</div>" + LAYOUT
        + "<h2>화면 목록</h2>" + table(["화면", "설명"], [("로그인", "아이디·비밀번호, 잠금 안내"), ("처음 설정", "계정 만들기(첫 실행에만)"), ("관제 화면", "3단 대시보드 + 디자인 3종"), ("목표물 패널(관제실)", "신호 상세·명령 버튼")]))
    pdf("11_와이어프레임(전체).pdf", "<h1>화면 설계(전체) — 실제 화면(데모 데이터)</h1>" + img("01_login.png", "로그인") + img("02_solar.png", "태양계") + img("03_ocean.png", "심해") + img("04_control_room.png", "관제실") + img("05_connect.png", "AI 연동 창(연결 안 됨)"))
    pdf("12_시스템·서비스_구성도.pdf", "<h1>시스템 · 서비스 구성도</h1>" + ARCH
        + "<ul><li>브라우저와 서버는 이 PC 안에서만 통신(127.0.0.1)</li><li>Codex는 읽기 전용 샌드박스로 호출, Gemini 키는 서버가 환경 변수에서 읽어 헤더로만 전송</li><li>개인 기록은 data/ 에만 저장</li></ul>")
    pdf("14_데이터_구조(저장_파일).pdf", "<h1>데이터 구조</h1><div class='sub'>관계형 DB 대신 파일(JSON Lines)에 저장</div>" + table(["파일", "필드", "설명"], DATA)
        + "<div class='box'>관계: runs.jsonl의 한 줄(호출)이 who 아래에 AI별 결과를 가진다. events.jsonl은 관제실 조작 기록이며 호출과 직접 연결되지 않는다.</div>")
    pdf("18_주요_기능_구현·핵심_코드.pdf", "<h1>주요 기능 구현 · 핵심 코드</h1>"
        "<h2>1. 병렬 호출(server.py)</h2><div class='box'>리뷰어마다 스레드를 만들어 동시에 호출하고, 모두 끝나면 한 줄로 runs.jsonl에 저장한다. Codex는 subprocess(읽기 전용 샌드박스), Gemini는 REST 직접 호출(토큰 수 확보).</div>"
        "<h2>2. 로그인(auth.py)</h2><div class='box'>PBKDF2-SHA256 24만 회 + 무작위 솔트, hmac.compare_digest로 비교, 아이디가 틀려도 같은 시간 동안 계산, 5회 실패 시 60초 잠금, 세션 토큰은 서버 메모리에만.</div>"
        "<h2>3. 한도 시각 표시</h2><div class='box'>Codex 응답 문구의 시각을 정규식으로 읽고, Gemini 429는 RetryInfo·'retry in Ns'·Retry-After 헤더에서 대기 시간을 읽어 풀리는 시각을 계산한다.</div>"
        "<h2>4. 관제실 모듈(index.html)</h2><div class='box'>Events / Targets / Commands / Panel / HUD 로 분리. 새 명령은 Commands에 항목 하나를 추가하면 패널에 버튼이 자동으로 생긴다.</div>"
        "<h2>5. AI 연동(로그인) — 내 토큰이 남에게 쓰이지 않게</h2><div class='box'>Codex·Gemini는 앱의 연동 창에서 직접 연결해야만 호출된다. Gemini 키는 저장 전에 Google에 확인하고 윈도우 계정으로 암호화(DPAPI)해 저장하며, 화면·응답·로그에는 나오지 않는다. Codex는 앱 전용 로그인 폴더(CODEX_HOME)를 쓰고, 이 PC의 기존 로그인·환경 변수는 사용자가 켠 경우에만 쓴다. 연결이 없으면 외부 서비스를 부르지 않고 바로 멈춘다.</div>"
        "<h2>6. 개인정보 분리</h2><div class='box'>호출 내용·이벤트·계정은 data/ 로 옮기고, 깃 업로드 전 tools/check_privacy.py 가 개인 경로·이메일·키·기록 파일을 검사한다.</div>")
    pdf("22_성과·목표_달성도.pdf", "<h1>성과 · 목표 달성도</h1>" + table(["목표", "결과"], [
        ("세 AI를 한 화면에서 호출·확인", "달성(Codex 성공 응답은 한도 때문에 미확인)"), ("사용량·한도 표시", "달성(Claude 일일·주간, Codex·Gemini 한도 시각)"),
        ("디자인 3종", "달성"), ("관제실 신호 처리", "달성(실제 이상 신호 포함)"), ("로그인·개인정보 분리", f"달성(자동 시험 {TOTAL_TESTS}개 통과)"),
        ("앱처럼 실행", "달성"), ("산출물·공개 준비", "달성")])
        + f"<h2>자동 시험 결과</h2><div class='box'>로그인 {len(AUTH_TESTS)}개 + AI 연동 {len(CONNECT_TESTS)}개 + 개인정보 점검 도구 {len(PRIVACY_TESTS)}개 = {TOTAL_TESTS}개 시험 모두 통과 (tests/test_auth.py, test_connect.py, test_privacy.py)</div>")
    pdf("23_아쉬운_점·개선_계획.pdf", "<h1>아쉬운 점 · 개선 계획</h1>" + table(["아쉬운 점", "개선 계획"], [
        ("Codex 성공 응답을 확인하지 못함(계정 한도)", "한도 해제 후 호출·토큰 표시 확인"), ("실제 Gemini 429 응답 형식을 못 봄", "실제 발생 시 형식에 맞춰 보완"),
        ("화면(캔버스) 자동 시험 없음", "핵심 계산(한도 시각 파싱 등)부터 단위 시험 추가"), ("검증기(VERIFIER) 단계는 이름만 있음", "허용 명령을 정한 뒤 테스트 실행 기능 추가"),
        ("Windows에서만 시험", "다른 OS 실행 확인"), ("모바일·좁은 화면 미확인", "반응형 점검")]))
    pdf("26_보안·개인정보_점검.pdf", "<h1>보안 · 개인정보 점검</h1>" + table(["ID", "구분", "내용"], NFR)
        + "<h2>AI 토큰(연동) 보호</h2><ul><li>연결하지 않으면 호출 자체가 되지 않음(외부 호출 없음)</li><li>키는 암호화 저장, 응답·화면에 없음</li><li>이 PC의 기존 로그인·환경 변수는 기본 꺼짐</li></ul><h2>깃 업로드 전 점검</h2><ul><li>data/, 바로가기(.lnk), 실행 기록은 .gitignore 로 제외</li><li>tools/check_privacy.py 로 개인 경로·이메일·키·기록 파일 검사</li><li>스크린샷은 데모 모드(가짜 데이터)로만 촬영</li><li>업로드용 깨끗한 사본(release/)은 개발 중 기록 없이 새로 만든다</li></ul>")
    pdf("27_프로젝트_수행일지.pdf", "<h1>프로젝트 수행 일지</h1><div class='sub'>실제 작업한 날짜만 기록(개인 대화·데이터 내용은 적지 않음)</div>" + table(["날짜", "내용"], [
        ("2026-11-09", "기획, 서버(Codex·Gemini 병렬 호출·기록), 3단 대시보드, AI별 사용량·토큰, 모델 선택, 디자인 시안(입자 우주·심해·관제실)"),
        ("2026-11-10", "디자인 3종 정리(태양계·심해·관제실), 관제실 신호 탐지·목표물 명령·자동 처리, Claude 일일·주간 한도·Codex/Gemini 한도 시각, 로그인·개인정보 분리·앱 실행, 자동 시험 19개, 산출물·PPT")]))


def build_xlsx():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    def save(name, sheets):
        wb = Workbook()
        wb.remove(wb.active)
        for title, headers, rows, widths in sheets:
            ws = wb.create_sheet(title)
            ws.append(headers)
            for r in rows:
                ws.append(list(r))
            for c in ws[1]:
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor="0F1B2D")
            for i, w in enumerate(widths, 1):
                ws.column_dimensions[get_column_letter(i)].width = w
            for row in ws.iter_rows(min_row=2):
                for c in row:
                    c.alignment = Alignment(wrap_text=True, vertical="top")
            ws.freeze_panes = "A2"
        wb.save(OUT / name)
        print("XLSX", name)

    save("07_WBS.xlsx", [("WBS", ["단계", "작업", "시작", "종료", "상태"], WBS, [12, 62, 14, 14, 10])])
    save("08_요구사항_명세서.xlsx", [("기능 요구사항", ["ID", "구분", "요구사항", "설명", "검증"], FR, [9, 10, 22, 70, 36]), ("비기능 요구사항", ["ID", "구분", "요구사항"], NFR, [9, 10, 90])])
    save("09_기능_명세서_목록.xlsx", [("기능 목록", ["ID", "구분", "기능명", "처리 내용", "상태/검증"], FR, [9, 10, 22, 70, 36])])
    save("14_데이터_저장파일_명세서.xlsx", [("파일 명세", ["파일", "필드", "설명"], DATA, [22, 80, 40])])
    save("15_API_명세서.xlsx", [("API", ["메서드", "경로", "로그인", "설명"], API, [8, 22, 8, 90])])
    save("19_테스트·검증_결과.xlsx", [("자동 시험(로그인)", ["번호", "시험 항목", "결과"], [(i + 1, t, "통과") for i, t in enumerate(AUTH_TESTS)], [7, 70, 10]),
                                     ("자동 시험(AI 연동)", ["번호", "시험 항목", "결과"], [(i + 1, x, "통과") for i, x in enumerate(CONNECT_TESTS)], [7, 70, 10]),
                                     ("자동 시험(개인정보 점검)", ["번호", "시험 항목", "결과"], [(i + 1, t, "통과") for i, t in enumerate(PRIVACY_TESTS)], [7, 70, 10]),
                                     ("수동 확인", ["항목", "결과", "비고"], MANUAL, [56, 18, 44])])


def build_pptx():
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Emu, Inches, Pt

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    BG, FG, ACC, SUB = RGBColor(6, 12, 22), RGBColor(232, 238, 247), RGBColor(52, 224, 176), RGBColor(127, 144, 168)
    blank = prs.slide_layouts[6]

    def slide(title, bullets=None, pic=None, note=None):
        s = prs.slides.add_slide(blank)
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = BG
        bar = s.shapes.add_shape(1, 0, 0, Inches(0.18), prs.slide_height)
        bar.fill.solid(); bar.fill.fore_color.rgb = ACC; bar.line.fill.background()
        tb = s.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12), Inches(0.9))
        p = tb.text_frame.paragraphs[0]; p.text = title; p.font.size = Pt(32); p.font.bold = True; p.font.color.rgb = FG
        left_w = Inches(5.6) if pic else Inches(12)
        if bullets:
            bb = s.shapes.add_textbox(Inches(0.6), Inches(1.5), left_w, Inches(5.2)); tf = bb.text_frame; tf.word_wrap = True
            for i, b in enumerate(bullets):
                para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                para.text = "▸ " + b; para.font.size = Pt(19); para.font.color.rgb = FG; para.space_after = Pt(10)
        if pic and (SHOT / pic).exists():
            s.shapes.add_picture(str(SHOT / pic), Inches(6.5), Inches(1.5), width=Inches(6.4))
        if note:
            nb = s.shapes.add_textbox(Inches(0.6), Inches(6.85), Inches(12), Inches(0.4)); q = nb.text_frame.paragraphs[0]; q.text = note; q.font.size = Pt(11); q.font.color.rgb = SUB
        return s

    s = slide("AI 팀 관제", ["Claude · Codex · Gemini 를 한 화면에서 호출하고 관찰하는 로컬 관제 화면", "개인 프로젝트 · " + PERIOD], note="화면은 모두 가상(데모) 데이터입니다")
    slide("만든 이유", ["AI마다 창이 따로라 누가 무엇을 하는지, 한도가 얼마나 남았는지 흩어져 보임", "한도가 다 되면 원인과 풀리는 시각을 매번 찾아야 함", "→ 한 화면에서 호출·결과·모델·토큰·한도를 보고, 이상을 신호로 알려 주자"])
    slide("주요 기능 ①  호출과 기록", ["Codex·Gemini 병렬 호출(리뷰어는 읽기 전용)", "결과·시간·모델·토큰을 기록으로 저장", "AI(노드/카드)를 눌러 모델 변경 — Codex는 호출 때만, Claude는 설정 파일의 model만"], "02_solar.png")
    slide("주요 기능 ②  사용량과 한도", ["Claude 일일(5시간)·주간(7일) 남은 % + 초기화까지 시간", "Codex 한도 소진 시 풀리는 시각, Gemini 429 재시도 시각", "AI별 호출 수·시간·토큰(이번 미션/오늘/전체)"], "03_ocean.png")
    slide("디자인 ①  태양계", ["세 AI가 행성이 되어 태양 둘레를 돈다", "타원 궤도·기울기·케플러 속도·원근·자전·달", "작업 중이면 행성이 빨라지고 태양에서 에너지가 흐름"], "02_solar.png")
    slide("디자인 ②  심해", ["입자로 그린 해파리·가오리·물고기가 자유롭게 헤엄", "고래·돌고래·해마·상어·거북이·오징어가 지나감", "눈이 편한 낮은 대비"], "03_ocean.png")
    slide("디자인 ③  관제실", ["실제 이상(실패·한도·연결 끊김)과 연습 신호를 레이더로 탐지", "목표물 선택 → 상세 패널 → 명령(추적·식별·보류·재시도·해소·통과)", "자동 처리와 이벤트 기록"], "04_control_room.png")
    slide("AI 연동(로그인)", ["Codex·Gemini는 앱의 '연동' 창에서 직접 연결해야 호출됨", "Gemini 키는 Google 확인 → 윈도우 계정으로 암호화 저장, 화면에는 다시 안 나옴", "Codex는 앱 전용 로그인 폴더 사용, 이 PC의 기존 로그인·환경 변수는 기본 꺼짐", "연결 전에는 외부 호출 없이 '연결 필요'로 멈춤"], "05_connect.png")
    slide("구성", ["브라우저(앱 창) ↔ Python 서버(127.0.0.1)", "Codex CLI · Gemini REST · Claude 사용량 파일(읽기 전용)", "개인 기록은 data/ 폴더에만"], note="외부 라이브러리 없이 Python 표준 라이브러리만 사용")
    slide("보안 · 개인정보", ["로그인해야 화면이 열림(첫 실행에 계정 생성)", "비밀번호는 PBKDF2 해시로만 저장, 5회 실패 시 잠금", "개인 기록(data/)은 깃에 올리지 않음, 업로드 전 자동 점검"], "01_login.png")
    slide("검증", [f"자동 시험 {TOTAL_TESTS}개 모두 통과(로그인 {len(AUTH_TESTS)} + AI 연동 {len(CONNECT_TESTS)} + 개인정보 점검 {len(PRIVACY_TESTS)})", "Chrome에서 호출·모델 변경·한도 표시·관제실 명령을 직접 확인", "미확인: Codex 성공 응답(한도), 모바일, 다른 OS"])
    slide("아쉬운 점 · 앞으로", ["Codex 성공 응답·토큰은 한도 해제 후 확인", "화면 자동 시험 추가", "검증기(VERIFIER) 단계를 실제 동작하게"])
    slide("감사 · 크레딧", ["화면 구성은 유튜브 '디렉터스AI'의 'AI DEV DIRECTOR' 영상을 참고(코드는 직접 작성)", "글꼴: Pretendard, JetBrains Mono (OFL)", "감사합니다"])
    prs.save(OUT / "AI관제_발표자료.pptx")
    print("PPTX saved")


if __name__ == "__main__":
    if not CHROME:
        sys.exit("Chrome을 찾지 못했어요.")
    OUT.mkdir(exist_ok=True)
    build_xlsx()
    build_pptx()
    build_pdfs()
    tmp = OUT / "_tmp.html"
    if tmp.exists():
        tmp.unlink()
