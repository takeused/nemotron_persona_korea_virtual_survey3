# 진행상황 인수인계 (PROGRESS)

마지막 업데이트: 2026-06-04 (야간 자율 진행 중)

## 한 줄 요약
Nemotron-Personas-Korea 페르소나 2000명이 「재난안전 기술 대국민 인식조사」 Q1~Q13에 zai-glm-4.7로 1인칭 응답 → 가중 집계·리포트. **1차(Q1~Q13) 본 실행 단계.**

## 디렉터리
```
data/data/*.parquet            원본 100만 건 (다운로드 완료)
survey_ref/대국민_설문지.pdf       설문 30문항
survey_ref/대국민_표본추출.pdf      표본설계(층화·가중) — 표7.2 모집단, 표7.3 할당
survey/
  survey_schema.py    30문항+재난유형1~70 구조화, PHASE1_QIDS=Q5~Q13
  sample_personas.py  층화추출(표7.3×2)+Q1~Q4매핑  → output/personas_sample.jsonl
  build_prompt.py     1인칭 프롬프트(문항 부분집합 동적)
  validate.py         응답 JSON 검증
  run_survey.py       Cerebras 호출(페이싱·재시도·체크포인트)
  pop_table.py        표7.2 모집단 + 사후가중치 (합 36,864,414 검증완료)
  parse_aggregate.py  파싱→CSV+가중집계+HTML 리포트
  compare_pilot.py    두 모델 파일럿 비교 뷰
output/
  personas_sample.jsonl   2000명 표본(층 정보 포함) ✅
  pilot_glm.jsonl / pilot_gptoss.jsonl  파일럿 8명×2모델 ✅
  responses_phase1.jsonl  ★본 실행 응답(진행/체크포인트)
set_api_key.ps1        CEREBRAS_API_KEY 설정(세션+User). 키 들어있음 — 외부공유 금지
```

## 확정 사항
- 표본: **2000명**, 층화추출(시도17×성별2×연령대5=170셀, 표7.3×2). 만19~69세. seed=42. 34개 셀 분포 일치 검증.
- 범위: **1차 Q1~Q13만**. Q1~Q4 직접매핑 + Q5~Q13 LLM 9문항. Q14~Q30은 2차.
- 모델: **zai-glm-4.7** (Cerebras). gpt-oss-120b보다 페르소나 반영도 우세(파일럿). 둘 다 추론모델.
- Cerebras 제약: **RPM/TPM 한도 낮음**. 동시성↑ = 429 역효과. → 전역 페이싱(--min-interval 4.0s≈15RPM)+재시도6.

## 실행 명령 (항상 키 점-소싱 + UTF-8 먼저)
```powershell
chcp 65001 > $null; $env:PYTHONUTF8="1"
. "D:\01 WORK\260603 Nemoton korean persona\set_api_key.ps1" | Out-Null
cd "D:\01 WORK\260603 Nemoton korean persona"

# 본 실행(체크포인트 resume — 끊겨도 다시 실행하면 이어감)
py survey/run_survey.py --model zai-glm-4.7 --personas output/personas_sample.jsonl `
   --out output/responses_phase1.jsonl --phase phase1 --workers 8 --min-interval 4.0

# 집계·리포트
py survey/parse_aggregate.py
# → output/responses_phase1.csv, output/report_phase1.html
```
주의: `python`은 WindowsApps 스텁이라 작동X → **`py`** 사용. 콘솔 한글 깨지면 위 chcp/PYTHONUTF8 필요.

## 현재 상태 / 다음 할 일
- [일시중지] 2026-06-04, 사용자 요청으로 본 실행 중단. **178/2000명 완료.** 남은 1822명(파일 내 미복구 실패 22건 포함 — resume 시 자동 재시도).
- [모델 확정] **zai-glm-4.7** (사용자: 느려도 GLM으로. gpt-oss 안 씀).
- [★속도 결론 — 다시 탐색 말 것] 병목은 **TPM(분당 토큰) 한도**. GLM은 호출당 ~2000~3000 추론토큰 → TPM 포화.
  - 동시성 올려도 처리율 동일하고 실패만 늘어남(workers16/2.5s 테스트: 56성공+24실패, workers8/4.0s: 74성공 0실패, 같은 시간).
  - GLM thinking 끄기 미지원(chat_template_kwargs 미지원). → **최적 설정 = workers 8 + --min-interval 4.0 (0 실패)**, 처리율 ~0.067건/초.
  - 남은 1822명 ≈ **약 7.5시간**. 단축하려면 gpt-oss(저품질) 또는 Cerebras 티어 상향뿐.
- [다음, 이어서 시작] 동일 출력파일로 재실행하면 resume으로 이어감(백그라운드 권장):
  ```
  py survey/run_survey.py --model zai-glm-4.7 --personas output/personas_sample.jsonl `
     --out output/responses_phase1.jsonl --phase phase1 --workers 8 --min-interval 4.0
  ```
- [그다음] 전량 완료 후 `py survey/parse_aggregate.py` → output/responses_phase1.csv + report_phase1.html.
  (parse_aggregate는 지금 178명으로도 동작 — 중간 점검 가능.)
- [2차] 만족 시 Q14~Q30: run_survey `--phase all` + parse_aggregate에 Q14~Q30 집계 추가 필요.

## 알아둘 점
- 추론모델: reasoning는 message.reasoning(별도), 최종답 message.content. max_tokens 4000.
- resume 시 이전 실패 uuid가 파일에 중복으로 남음 → parse_aggregate.load가 uuid별 성공우선 중복제거.
- 가중치: 표본이 제곱근배분이라 모집단 추정엔 사후가중 필수(parse_aggregate 자동). 리포트에 가중%/비가중% 병기.
- 학력은 층화변수 아님 → Nemotron 자연분포(실제 인구에 근접, 참조설문 온라인패널보다 저학력).
```
```
