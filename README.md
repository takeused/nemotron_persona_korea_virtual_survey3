# Nemotron 페르소나 × 재난안전 인식 설문 (가상 설문)

[Nemotron-Personas-Korea](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea)의 한국인 합성 페르소나가 「재난안전 기술 대국민 인식조사」(국립재난안전연구원·한국행정연구원·한국갤럽)에 **1인칭으로 응답**하게 하여, 합성 설문 데이터를 생성·집계하는 프로젝트(실리콘 샘플링).

## 개요
- **표본**: 2,000명, 층화추출(시도 17 × 성별 2 × 연령대 5 = 170셀). 참조 보고서의 표 7.3 표본할당을 재현(만 19~69세).
- **응답 생성**: Cerebras API의 `zai-glm-4.7`로 각 페르소나를 연기시켜 응답.
- **1차 범위**: Q1~Q13 (일반현황 + 재난 인식). Q1~Q4는 페르소나 인구통계 직접 매핑, Q5~Q13은 LLM 응답.
- **집계**: 표 7.2 모집단 기반 사후층화 가중치 적용. 가중·비가중 결과 병기.

## 구성
```
survey/
  survey_schema.py     설문 30문항 + 재난유형 1~70 구조화
  sample_personas.py   층화추출 + Q1~Q4 매핑
  build_prompt.py      1인칭 몰입 프롬프트 생성
  validate.py          응답 JSON 스키마 검증
  run_survey.py        Cerebras 호출(페이싱·재시도·체크포인트)
  pop_table.py         모집단(표7.2) + 사후가중치
  parse_aggregate.py   파싱 → CSV + 가중 집계 + HTML 리포트
PROGRESS.md            진행 인수인계
checklist.md / context-notes.md  계획·결정 기록
```
원본 데이터셋(`data/`)과 실제 키(`set_api_key.ps1`)는 저장소에서 제외됨.

## 사용법 (Windows / PowerShell)
```powershell
# 1) 데이터셋 다운로드 (HuggingFace, ~1.9GB)
py -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='nvidia/Nemotron-Personas-Korea', repo_type='dataset', allow_patterns=['data/*.parquet'], local_dir='data')"

# 2) API 키 설정
Copy-Item set_api_key.example.ps1 set_api_key.ps1   # 편집해 키 입력
. .\set_api_key.ps1

# 3) 표본 추출 (2000명)
py survey/sample_personas.py -n 2000 --seed 42 -o output/personas_sample.jsonl

# 4) 설문 응답 생성 (체크포인트 resume 지원)
py survey/run_survey.py --model zai-glm-4.7 --personas output/personas_sample.jsonl `
   --out output/responses_phase1.jsonl --phase phase1 --workers 8 --min-interval 4.0

# 5) 집계·리포트
py survey/parse_aggregate.py   # → output/responses_phase1.csv, report_phase1.html
```

## 참고
- 처리 속도는 Cerebras 계정의 분당 토큰(TPM) 한도에 좌우됨. GLM-4.7은 추론모델이라 호출당 토큰이 많음. 권장 설정 `--workers 8 --min-interval 4.0`(429 실패 0).
- 데이터셋 라이선스: CC BY 4.0 (NVIDIA).
