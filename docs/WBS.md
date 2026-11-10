# WBS (작업 분해표)

개인 프로젝트 "AI 팀 관제"의 작업 구성과 올리는 순서입니다. 날짜는 **실제로 올리는 날**만 적고, 아직 안 한 것은 "예정"으로 둡니다.

| 단계 | 작업 | 산출물 | 올리는 날 | 상태 |
|---|---|---|---|---|
| 1. 기반 | 로그인(계정 만들기·세션·잠금) | `auth.py`, `pages.py`, `tests/test_auth.py` | 11/10 | 올림 |
| 1. 기반 | AI 연동(Gemini 키 암호화 저장, Codex 앱 전용 로그인, 설치·로그인 안내) | `connect.py`, `tests/test_connect.py` | 11/10 | 올림 |
| 1. 기반 | 개인정보 점검 도구와 시험 | `tools/check_privacy.py`, `tests/test_privacy.py` | 11/10 | 올림 |
| 1. 기반 | README·업로드 계획·WBS | `README.md`, `docs/` | 11/10 | 올림 |
| 2. 서버 | 리뷰어 병렬 호출, 기록, 한도 표시, Claude 사용량 읽기, 앱처럼 실행 | `server.py`, `launch.pyw` | 예정 | 대기 |
| 3. 화면 | 3단 대시보드, 디자인 3종(태양계·심해·관제실), 관제실 신호 처리 | `index.html` | 예정 | 대기 |
| 4. 시연 | 데모 모드, 스크린샷 도구, 공개용 복사 도구 | `tools/demo_data.py`, `tools/shoot.py`, `tools/make_release.py`, `deliverables/screenshots/` | 예정 | 대기 |
| 5. 문서 | 산출물(PDF·엑셀·PPT)과 README 정리 | `deliverables/`, `tools/build_deliverables.py` | 예정 | 대기 |

## 올리기 전 매번 하는 점검
1. `python -I tools/check_privacy.py . --tracked` 로 올라갈 파일에 개인정보가 없는지 확인
2. `python -I tests/test_auth.py`, `tests/test_connect.py`, `tests/test_privacy.py` 통과 확인
3. `git status` 에 `data/` 와 `private_terms.txt` 가 없는지 확인

## 하지 않는 것
- 커밋 날짜를 과거로 꾸미지 않습니다.
- 내 계정·키·호출 기록(`data/`)은 올리지 않습니다.
