# 깃 업로드 계획 (날짜별로 조금씩)

> 이 계획은 **실제 날짜에 실제로 커밋하는 것**을 전제로 합니다. 커밋 날짜를 과거로 꾸미지 않습니다(`--date` 사용 금지).
> 개인정보는 올라가지 않도록 아래 "처음 한 번" 단계를 꼭 먼저 하세요.

## 처음 한 번 (개인정보 보호)

1. **깨끗한 사본 만들기** — 개발하면서 쌓인 기록(`data/`, 로그, 바로가기)이 없는 새 폴더를 만듭니다.
   ```
   python -I tools/make_release.py
   cd release/ai-team-console
   ```
   이 폴더에서 새로 `git init` 하므로 '만들면서 쌓인 기록'이 올라가지 않습니다.
2. **내 낱말 목록 만들기** — 실명·GitHub 아이디·학원/회사 이름처럼 올라가면 안 되는 낱말을 적습니다(깃에 올라가지 않는 파일).
   ```
   copy tools\private_terms.example.txt tools\private_terms.txt   (그리고 낱말을 적기)
   ```
3. **커밋 이름·이메일을 가리기** — GitHub 설정 → Emails → *Keep my email addresses private* 를 켜고, 거기 나오는 `숫자+아이디@users.noreply.github.com` 주소를 씁니다.
   ```
   git init
   git config user.name  "<표시할 이름 또는 GitHub 아이디>"
   git config user.email "<숫자+아이디>@users.noreply.github.com"
   ```
4. **저장소는 처음에 비공개(Private)로** 만들고, 점검이 끝난 뒤 공개로 바꿔도 됩니다.

## 날짜별 업로드 (파일 묶음 단위)

| 날짜(예정) | 올릴 파일 | 커밋 메시지 예 |
|---|---|---|
| 11/10 (화) | `.gitignore`, `README.md`, `auth.py`, `pages.py`, `connect.py`, `tests/test_auth.py`, `tests/test_connect.py`, `tools/check_privacy.py`, `tools/private_terms.example.txt` | `로그인·개인정보 점검 도구` |
| 11/11 (수) | `server.py`, `launch.pyw`, `assets/icon.ico` | `서버: 리뷰 병렬 호출·기록·한도 표시, 앱처럼 실행` |
| 11/12 (목) | `index.html` | `화면: 3단 대시보드, 디자인 3종(태양계·심해·관제실), 관제실 신호 처리` |
| 11/13 (금) | `tools/demo_data.py`, `tools/shoot.py`, `tools/make_release.py`, `deliverables/screenshots/` | `데모 모드와 스크린샷 도구` |
| 11/14 (토) | `deliverables/*.pdf`, `*.xlsx`, `*.pptx`, `tools/build_deliverables.py`, `docs/GIT_UPLOAD_PLAN.md`, README 최종 | `산출물(문서·엑셀·PPT)과 README 정리` |

날짜는 편한 대로 바꿔도 됩니다. 중요한 건 **그날 실제로 커밋하고 푸시**하는 것입니다.

## 커밋·푸시 전 점검 (매번)

```
python -I tools/check_privacy.py . --tracked      # 올라갈 파일에 개인정보가 없는지
python -I tests/test_auth.py                      # 로그인 시험 19개 (선택)
python -I tests/test_connect.py                   # AI 연동 시험 24개 (선택)
git status                                        # data/, *.lnk, private_terms.txt 가 목록에 없는지
git push
```

- `check_privacy` 가 "문제 N건"을 보고하면 **푸시하지 마세요.** 파일을 고치거나 `.gitignore` 에 넣은 뒤 다시 점검합니다.
- 실수로 올렸다면: 비밀번호·키는 즉시 바꾸고, 저장소를 지우고 새로 만드는 것이 가장 안전합니다(히스토리에 남기 때문).

## 올라가지 않는 것 (`.gitignore`)

`data/`(계정·호출 기록·이벤트·모델 선택), `*.lnk`(내 PC 바로가기), `tools/private_terms.txt`, `.env`·키 파일, `*.7z`/`*.zip`, `__pycache__/`

## 참고

- API 키는 파일에 쓰지 않고 환경 변수(`GEMINI_API_KEY`)에서 읽습니다. 코드 안에 키가 없습니다.
- 스크린샷·산출물은 **데모 모드(가짜 데이터)** 로만 만들었습니다.
- 화면 코드(`index.html`)는 한 파일에 모듈(Events/Targets/Commands/Panel/HUD)로 나뉘어 있습니다. 더 잘게 올리고 싶다면 이후에 파일을 나누는 정리 작업을 따로 하세요.
