"""데모 데이터 만들기 — 스크린샷·시연용 가짜 기록과 데모 계정을 지정한 폴더에 만든다.

실제 data 폴더는 건드리지 않는다. 사용법:
    python -I tools/demo_data.py <빈 폴더>
    set AI_CONSOLE_DATA=<그 폴더> & set AI_CONSOLE_DEMO=1 & set AI_CONSOLE_PORT=8797 & python -I server.py
데모 계정은 아래 값(실제 계정과 무관한 시연용)이다.
"""
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from auth import Auth  # noqa: E402

DEMO_USER, DEMO_PASS = "demo", "demo-only-1234"

if len(sys.argv) < 2:
    sys.exit("사용법: python -I tools/demo_data.py <빈 폴더>")
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
Auth(out).setup(DEMO_USER, DEMO_PASS, DEMO_PASS)

now = datetime.now()
def ts(minutes_ago):
    return (now - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%d %H:%M:%S")

RUNS = [
    (95, "로그인 기능의 보안 위험을 점검해줘", {
        "codex":  {"status": "done", "output": "비밀번호는 PBKDF2로 해시되어 있어 양호합니다. 세션 만료와 잠금 정책도 확인했습니다.", "sec": 6.2, "tokens": 2210, "model": "gpt-6.1-sol"},
        "gemini": {"status": "done", "output": "설계 측면에서 첫 실행 때 계정을 직접 만드는 방식은 좋습니다. 로그아웃 시 쿠키 삭제도 포함하세요.", "sec": 3.1, "tokens": 640, "model": "gemini-3.5-flash"}}),
    (70, "대시보드 레이아웃 3단 구성이 읽기 편한지 의견 부탁", {
        "gemini": {"status": "done", "output": "좌측 입력, 중앙 시각화, 우측 지표의 3단 구성은 시선 흐름이 자연스럽습니다.", "sec": 2.8, "tokens": 512, "model": "gemini-3.5-flash"}}),
    (45, "호출 기록 저장 구조를 검토해줘", {
        "codex":  {"status": "failed", "reason": "limit", "output": "사용 한도를 다 썼습니다. " + (now + timedelta(hours=5)).strftime("%b %d, %Y %I:%M %p").replace(" 0", " ") + " 이후 다시 시도할 수 있어요.", "sec": 4.1, "model": "gpt-6.1-sol"},
        "gemini": {"status": "done", "output": "JSONL 한 줄에 한 번의 요청을 기록하는 방식은 단순하고 추가에 안전합니다.", "sec": 2.4, "tokens": 388, "model": "gemini-3.5-flash"}}),
    (20, "모델 변경 창의 문구를 더 쉽게 다듬어줘", {
        "gemini": {"status": "done", "output": "'다음 호출부터 적용돼요'처럼 시점을 분명히 쓰는 문구가 좋습니다.", "sec": 2.2, "tokens": 301, "model": "gemini-3.5-flash"}}),
    (6, "한도 초과 표시가 눈에 잘 띄는지 확인", {
        "gemini": {"status": "failed", "reason": "limit", "output": "요청 한도를 초과했습니다. 약 45초 뒤 다시 시도할 수 있어요.", "sec": 0.4, "model": "gemini-3.5-flash",
                   "reset_at": (datetime.now().astimezone() + timedelta(seconds=40)).isoformat()}}),
]
with (out / "runs.jsonl").open("w", encoding="utf-8") as f:
    for i, (ago, prompt, who) in enumerate(RUNS):
        f.write(json.dumps({"id": f"demo{i:04d}", "prompt": prompt, "started": ts(ago), "who": who}, ensure_ascii=False) + "\n")

EVENTS = [("DETECT", "T-01 SIM LATENCY SPIKE"), ("AUTO", "T-01 자동 추적 고정"), ("AUTO", "T-01 자동 식별: NETWORK"), ("RESOLVED", "T-01 LATENCY SPIKE"),
          ("DETECT", "T-02 SIM HEARTBEAT"), ("PASS", "T-02 통과 승인(정상 신호)"), ("PASSED", "T-02 HEARTBEAT 통과 완료")]
with (out / "events.jsonl").open("w", encoding="utf-8") as f:
    for i, (tag, text) in enumerate(EVENTS):
        f.write(json.dumps({"ts": ts(30 - i), "tag": tag, "text": text, "target": text.split()[0], "sim": True}, ensure_ascii=False) + "\n")
print("데모 데이터 생성:", out)
