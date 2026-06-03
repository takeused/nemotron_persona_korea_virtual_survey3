# 체크리스트 — Nemotron 페르소나 × 재난안전 인식 설문

대상: nvidia/Nemotron-Personas-Korea (100만 건) 페르소나가 「재난안전 기술 대국민 인식 조사」(30문항)에 1인칭으로 응답.
응답 생성: Cerebras API (OpenAI 호환). 모델 후보: `zai-glm-4.6`, `gpt-oss-120b`.

## 0. 준비 (완료)
- [x] 데이터셋 전체 다운로드 (`data/data/*.parquet`, 9개, ~1.9GB, 100만 건)
- [x] 스키마 확인 (26컬럼, 한국어 UTF-8)
- [x] 설문지 PDF 분석 (`survey_ref/대국민_설문지.pdf`, 30문항)
- [x] 인구통계 값 분포 확인 (성별/학력/지역/연령)

## 범위 (1차)
- **Q1~Q13만 진행.** Q1~Q4 매핑 + Q5~Q13 LLM. Q14~Q30은 2차.
- 표본 2000명, 층화추출(표 7.3 재현).

## 1. 설문 정의 구조화
- [x] `survey/survey_schema.py` — 30문항 구조화 + 단계(PHASE1) 구분
- [x] 재난유형 마스터(1~70) 및 선택지 인코딩

## 2. 페르소나 샘플링 + 인구통계 매핑
- [x] `survey/sample_personas.py` — 층화추출(표 7.3 ×2) → `output/personas_sample.jsonl` (2000명)
- [x] Q1~Q4 직접 매핑 + 층 정보 기록
- [x] 분포 검증 (34개 지역×성별 셀 전부 일치)

## 3. 프롬프트 구성
- [x] `survey/build_prompt.py` — 1인칭 프롬프트 + 문항 부분집합(Phase1) 동적 출력형식

## 4. 파일럿 (모델 비교)
- [x] `survey/run_survey.py` — Cerebras 호출 (재시도·JSON검증·체크포인트, 추론모델 대응)
- [x] CEREBRAS_API_KEY 설정 (set_api_key.ps1, 세션+User)
- [x] 8명 × 2모델 비교 → **zai-glm-4.7 확정** (페르소나 반영도 우세)
  - 실제 모델 ID: `zai-glm-4.7`(4.6 아님), `gpt-oss-120b`. 둘 다 추론모델(thinking).

## 5. 본 실행 (2000명, Q1~Q13)
- [ ] 동시성 튜닝(50명 배치) → 본 실행
- [ ] 확정 모델 zai-glm-4.7로 전체 실행 (병렬, 체크포인트)
- [ ] 원자료 저장 `output/responses_phase1.jsonl`

## 6. 파싱 · 집계 · 리포트
- [ ] `survey/parse_aggregate.py` — JSON 응답 파싱·검증 → tidy CSV `output/responses.csv`
- [ ] 인구통계 교차분석 (지역/연령/성별/학력별)
- [ ] 결과 리포트 `output/report.html`

## 검증 기준
- [ ] 응답 파싱 성공률 ≥ 95% (실패분 재시도)
- [ ] 모든 문항 응답이 정의된 선택지 범위 내
- [ ] Q1~Q4가 원본 페르소나 인구통계와 일치
