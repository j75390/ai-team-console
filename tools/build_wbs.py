"""WBS 엑셀(07_WBS.xlsx) 만들기 — 번호 체계 + 담당 + 일정 + 진행률 + 날짜별 간트 막대.

    python tools/build_wbs.py [프로젝트 폴더]   (기본: 이 파일의 상위 폴더)

AI 팀 관제와 StudySeat 둘 다 같은 형식이라 PROJECT 값만 다르다.
"""
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
DAYS = ["11/09", "11/10"]

# (ID, 대분류, 작업, 담당, 시작 칸(0~), 끝 칸(0~), 진행률, 산출물)  — 대분류만 있는 줄은 작업이 None
AI = [
    ("1", "기획", None, "", 0, 0, 100, ""),
    ("1.1", "", "목표·범위 정리, 참고 영상 화면 구성 분석", "Claude", 0, 0, 100, "README"),
    ("1.2", "", "설계 검토(역할 분담, 읽기 전용 호출 원칙)", "Gemini", 0, 0, 100, ""),
    ("2", "서버", None, "", 0, 1, 100, ""),
    ("2.1", "", "Python 서버, Codex·Gemini 병렬 호출", "Claude", 0, 0, 100, "server.py"),
    ("2.2", "", "호출 기록 저장, 한도 시각 읽기, Claude 사용량 읽기", "Claude", 0, 1, 100, "server.py"),
    ("2.3", "", "코드·보안 검토 반영", "Codex", 1, 1, 100, ""),
    ("3", "화면", None, "", 0, 1, 100, ""),
    ("3.1", "", "3단 대시보드, AI별 사용량·토큰, 모델 선택", "Claude", 0, 1, 100, "index.html"),
    ("3.2", "", "디자인 3종(태양계·심해·관제실)", "Claude", 0, 1, 100, "index.html"),
    ("3.3", "", "관제실 신호 레이더, 목표물 선택·명령, 이벤트 기록", "Claude", 1, 1, 100, "index.html"),
    ("4", "보안", None, "", 1, 1, 100, ""),
    ("4.1", "", "로그인(첫 설정, 세션, 연속 실패 잠금)", "Claude", 1, 1, 100, "auth.py, pages.py"),
    ("4.2", "", "AI 연동(키 암호화 저장, Codex 앱 전용 로그인)", "Claude", 1, 1, 100, "connect.py"),
    ("4.3", "", "개인정보 점검 도구와 시험", "Claude, Codex", 1, 1, 100, "tools/check_privacy.py"),
    ("5", "시험·산출물", None, "", 1, 1, 100, ""),
    ("5.1", "", "자동 시험 60개(로그인 19, 연동 26, 점검 15)", "Claude", 1, 1, 100, "tests/"),
    ("5.2", "", "문서·엑셀·PPT·스크린샷 정리", "Claude", 1, 1, 100, "deliverables/"),
    ("6", "공개", None, "", 1, 1, 100, ""),
    ("6.1", "", "깨끗한 사본 만들기, GitHub 업로드", "Claude", 1, 1, 100, "tools/make_release.py"),
    ("6.2", "", "README 정리", "Claude", 1, 1, 100, "README.md"),
    ("7", "후속", None, "", None, None, 0, ""),
    ("7.1", "", "Codex 성공 응답 확인(한도 해제 후), 검증기 단계 실제 동작", "미정", None, None, 0, ""),
]
SS = [
    ("1", "기획", None, "", 0, 0, 100, ""),
    ("1.1", "", "참고 서비스 분석, 범위 정리", "Claude", 0, 0, 100, "README"),
    ("1.2", "", "요구사항·ERD·API 초안", "Claude", 0, 0, 100, "docs/"),
    ("1.3", "", "설계 리뷰 반영", "Gemini", 0, 0, 100, ""),
    ("2", "기본 예약", None, "", 0, 0, 100, ""),
    ("2.1", "", "좌석 예약, 동시 예약 방지(슬롯 유니크 제약)", "Claude", 0, 0, 100, "ReservationService"),
    ("2.2", "", "포인트 원장, 취소·환불", "Claude", 0, 0, 100, "PointService"),
    ("2.3", "", "체크인·퇴실, 노쇼·자동 종료, 후기·문의", "Claude", 0, 0, 100, "service/"),
    ("2.4", "", "혼잡도 통계, 관리자 화면", "Claude", 0, 0, 100, "StatsService"),
    ("3", "서비스 확장", None, "", 0, 0, 100, ""),
    ("3.1", "", "지점·구역 가격·도면 좌표·예약 코드", "Claude", 0, 0, 100, "domain/"),
    ("3.2", "", "연장, 키오스크, 포인트 충전", "Claude", 0, 0, 100, "service/"),
    ("3.3", "", "지도·지점 상세 화면", "Claude", 0, 0, 100, "templates/"),
    ("4", "전국 지점", None, "", 0, 0, 100, ""),
    ("4.1", "", "행정구역 256개 시·군·구 기준 지점 약 720곳", "Claude", 0, 0, 100, "NationwideSeeder"),
    ("4.2", "", "지도 JSON API, 대용량 시드(JDBC 배치)", "Claude", 0, 0, 100, "web/"),
    ("5", "도면", None, "", 0, 0, 100, ""),
    ("5.1", "", "도면 엔진(FloorPlanLayout)", "Claude", 0, 0, 100, "FloorPlanLayout"),
    ("5.2", "", "성별 전용·고정석·퇴실예정석, 재배치(V5·V6)", "Claude", 0, 0, 100, "db/migration/"),
    ("6", "디자인", None, "", 0, 0, 100, ""),
    ("6.1", "", "홈 화면 분리, Pretendard·Lucide 적용, 로고", "Claude", 0, 0, 100, "static/"),
    ("7", "시험", None, "", 0, 0, 100, ""),
    ("7.1", "", "자동 시험 40개(동시성 포함)", "Claude", 0, 0, 100, "src/test/"),
    ("7.2", "", "코드 리뷰 반영", "Codex", 0, 0, 100, ""),
    ("8", "산출물·공개", None, "", 1, 1, 100, ""),
    ("8.1", "", "문서·엑셀·PPT·스크린샷 정리", "Claude", 1, 1, 100, "deliverables/"),
    ("8.2", "", "GitHub 업로드, README 정리", "Claude", 1, 1, 100, "README.md"),
    ("9", "후속", None, "", None, None, 0, ""),
    ("9.1", "", "MySQL 8 실서버 검증, Docker Compose, GitHub Actions, 웹 계층 시험", "미정", None, None, 0, ""),
]


def build(rows, out):
    wb = Workbook()
    ws = wb.active
    ws.title = "WBS"
    head = ["ID", "대분류", "작업", "담당", "시작", "종료", "진행률", "산출물"] + DAYS
    ws.append(head)
    thin = Side(style="thin", color="CFD6DD")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for r in rows:
        i, big, task, who, s, e, pct, art = r
        ws.append([i, big, task or "", who, DAYS[s] if s is not None else "미정", DAYS[e] if e is not None else "미정", f"{pct}%", art] + [""] * len(DAYS))
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="0F766E")
    for n, r in enumerate(rows, 2):
        is_big = r[2] is None
        for c in ws[n]:
            c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center" if c.column in (1, 4, 5, 6, 7) or c.column > 8 else "left")
            if is_big:
                c.fill = PatternFill("solid", fgColor="E6F2F0")
                c.font = Font(bold=True)
        if r[4] is not None:
            for d in range(r[4], r[5] + 1):
                cell = ws.cell(row=n, column=9 + d)
                cell.fill = PatternFill("solid", fgColor="0F766E" if is_big else "5EB5AB")
    for row in ws.iter_rows():
        for c in row:
            c.border = border
    for i, w in enumerate([6, 14, 52, 14, 9, 9, 8, 24] + [8] * len(DAYS), 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    wb.save(out)
    print("저장", out)


if __name__ == "__main__":
    name = ROOT.name
    build(SS if "studyseat" in name.lower() else AI, ROOT / "deliverables" / "07_WBS.xlsx")
