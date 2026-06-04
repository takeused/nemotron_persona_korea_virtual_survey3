# 진행상황 인수인계 (PROGRESS)

마지막 업데이트: 2026-06-05 (회사에서 이어하기용 커밋)

## ⚡ 회사에서 이어하기 (fresh clone)
1. clone 후 **`set_api_key.ps1` 직접 생성**: `set_api_key.example.ps1` 복사 → `PUT_KEY_HERE`에 Cerebras 키 입력. (실제 키 파일은 gitignore라 repo에 없음.)
2. `data/`(원본 1.9GB)는 **없어도 보충/집계 가능** — 필요한 페르소나는 `output/personas_*.jsonl`에 내장됨. (재표집할 때만 HF에서 재다운로드.)
3. **현재 진행: 348명 성공, R3 보충 잔여 194명.** 저녁/회사에서 보충 재개 명령(아래 ★표본 축소 섹션) 실행 → resume으로 이어감. Free tier는 호출당 ~9분(540s) 페이싱 필수.
4. 보충 197건 다 차면 `py survey/parse_aggregate.py` → 사후가중 집계(n≈542).

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
- [중단·보완전환] 2026-06-04. 재개 실행 중 429 rate-limit 급증(하드실패 uuid 27→136) → 사용자 요청으로 **340/2000명에서 중단**. 400 목표는 다음으로 미룸.
- [실패 보완 중단] 느린 페이스(workers4/interval6.0)로도 429 거의 전부 실패 → 쿼터 소모 판단해 중단. **현재 345명 성공.**

## ★Cerebras rate-limit 확정 (2026-06-04, 공식문서 inference-docs.cerebras.ai/support/rate-limits)
실측 대시보드(Personal, zai-glm-4.7) — **Requests: 분5 / 시간150 / 일2,400.  Tokens: 분30K / 시간1M / 일1M.  Max context 64,000.**
- **이 계정 = Free Trial(분5 RPM)** 확정. 본실행 15RPM·보완 10RPM = 상한 초과 → 429 폭증의 진짜 원인. (이전 "TPM 병목" 메모는 오진.)
- 호출당 토큰 ≈ **6K**(입력 ~2.6~4.3K + 추론/출력 ~3K).
- [★숨은 병목 2개] (1) **시간당 요청 150** — 분당5만 보면 안 됨. 지속 안전 = 150/h = **1건당 24초**. (2) **일 토큰 1M** — 6K/호출 → **하루 ~166건**이 일일 천장(일 요청 2,400은 넉넉, 토큰이 먼저 막음).
- 오늘 167건 성공 ≈ 1M 토큰 = **일일 TPD 소진**. → 추가 호출은 **TPD 리셋된 다음날**.
- [★실측 보정 2026-06-05] 다음날 25s로 재개했더니 **"Tokens per day limit exceeded"(token_quota_exceeded)** 429. 일 토큰 1M은 **하드리셋이 아니라 연속충전 버킷** → 어제 소진분이 천천히 차는 중. 충전속도 ≈ 1M/일 = **6K(1호출)당 약 9분**. 즉 지속가능 속도가 곧 일일천장 166건/일 = **호출당 ~9분**.
- **확정 페이싱(연속충전 대응): `--workers 1 --min-interval 540.0`** (호출당 9분, 충전속도에 자가정렬 → 429 거의 0). 25s 같은 빠른 페이싱은 충전 앞질러 token_quota 429만 양산.

## ★표본 축소 확정: R3 (n≈542, 500 비례)  ← 사용자 결정, 업그레이드 안 함
- 345명은 170층 중 141채움/29빈셀(소형셀). 근사 비례축소 상태.
- 각 층 500-비례목표 대비 부족분만 보충 → **`output/personas_topup_r3.jsonl` (197명)**. 빈 셀 29→0 전부 해소. 최종 n≈542.
- **보충 실행(내일 TPD 리셋 후, 약 2일 소요):**
  ```
  py survey/run_survey.py --model zai-glm-4.7 --personas output/personas_topup_r3.jsonl --out output/responses_phase1.jsonl --phase phase1 --workers 1 --min-interval 540.0
  ```
  resume이라 끊겨도 재실행하면 이어감. 호출당 ~9분 자가페이싱 → 197건 약 30시간(1.5~2일) 무인 진행. 멈추면 같은 명령 재실행.
- [진행중 2026-06-05] 위 540s 백그라운드 가동 시작(348명~). 30분마다 자동 점검·재시작 wakeup.
- 완료 후 `py survey/parse_aggregate.py` → 사후가중 집계(n≈542). 빈 셀 0이라 가중 안정적.
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
