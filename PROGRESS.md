# 진행상황 인수인계 (PROGRESS)

마지막 업데이트: 2026-06-26 (★v3 재검증 완료 — 과잉보정 원인=프롬프트 규명, 프롬프트 완화 반영. 다음=v4 재검증)

## ⏭️ 다음 세션 바로 할 일 — v4 재검증 (토큰 리셋 후)
**목적:** 완화된 프롬프트(무관심유도 제거+심각도 보호절, 커밋됨)로 척도평균 과잉보정이 해소되면서 분산회복이 유지되는지 확인.
**전제:** Cerebras 일일토큰 리셋 필요(1M). `set_api_key.ps1` 점-소싱 먼저. 분리수집(phase1→phase2)이 필수(단일 phase all은 토큰폭증으로 실패 확정).
```powershell
. "D:\01 WORK\260605 nemotron virtual survey2\set_api_key.ps1"
cd "D:\01 WORK\260605 nemotron virtual survey2"
# 1) phase1 (가벼움 ~234K)
py survey/run_survey.py --model zai-glm-4.7 --personas output/personas_phase2.jsonl --out output/responses_test60_p1_v4.jsonl --phase phase1 --workers 2 --min-interval 20 --limit 60
# 2) phase2 (~530K) — phase1 끝난 뒤
py survey/run_survey.py --model zai-glm-4.7 --personas output/personas_phase2.jsonl --out output/responses_test60_p2_v4.jsonl --phase phase2 --workers 2 --min-interval 28 --limit 60
# 3) 병합 비교
py survey/_validate_compare.py responses_test60_p1_v4.jsonl responses_test60_p2_v4.jsonl
```
**확인 포인트:** Q6 심각(현 v3 3.55 → 실제 4.0에 접근?), Q28 안전(3.05→3.4?), Q16(2.73→3.4?) 회복 여부 + Q9/Q22 다양성·Q27 분산 유지 여부.
**만약 과잉보정 여전하면:** 근본 해법은 **계획 #4(문항별 선택보정, train/test 분할 JS divergence)** — 일괄 프롬프트 교정의 한계. report_compare.html 10절 참조.
**토큰 소진 주의:** 호출당 약 phase1 4K/phase2 9K. 분당 30K TPM 한도 → interval 20~28s 유지. 빈content/재시도는 max_retry=4·max_tokens=6000·누적echo제거로 이미 완화됨.

### 검증 이력(계수·프롬프트별 척도평균, 실제 Q6=4.0/Q16=3.4/Q28=3.4)
| 버전 | 설정 | Q6 | Q16 | Q28 | Q27예방 | Q29예% |
|---|---|---|---|---|---|---|
| 기존 | 구프롬프트·elicit無 | 4.02 | 3.03 | 3.49 | 99.4 | 48.8 |
| v2(n46) | 계수0.30+무관심프롬프트 | 3.53 | 2.76 | 2.95 | 66.1 | 61.6 |
| v3(n56) | 계수0.15+무관심프롬프트 | 3.55 | 2.73 | 3.05 | 56.5 | 54.0 |
| v4-p1(n48) | 계수0.15+완화프롬프트 | **3.66** | (phase2 미측정) | - | - | - |
→ v2→v3: 계수완화 효과 미미(과잉보정 원인=프롬프트 확인). **v4-p1: 프롬프트 완화가 Q6 3.55→3.66 회복(부분)·Q9 모드 감염병으로 교정·Q12 분산유지 — 진단 확증.** phase2(Q16/Q28/Q29)는 다음 토큰사이클서 측정 필요(v4-p2).

### v4 재개(다음 토큰사이클) — phase2만 마저
```powershell
. "D:\01 WORK\260605 nemotron virtual survey2\set_api_key.ps1"; cd "D:\01 WORK\260605 nemotron virtual survey2"
py survey/run_survey.py --model zai-glm-4.7 --personas output/personas_phase2.jsonl --out output/responses_test60_p2_v4.jsonl --phase phase2 --workers 2 --min-interval 28 --limit 60
py survey/_validate_compare.py responses_test60_p1_v4.jsonl responses_test60_p2_v4.jsonl
```
확인: Q16(v3 2.73→?), Q28(v3 3.05→?), Q29(v3 54→?)가 완화프롬프트로 회복되는지. 회복 부족하면 → 계획#4 문항별 선택보정.

---


## ★실제조사 근접 개선 (2026-06-23 반영) — 다음 실행부터 자동 적용
- **배경:** 실제 대국민조사(1,023명, PDF)와 가상조사(542명) 비교 → `output/report_compare.html`. LLM 응답의 ①분산소멸 ②최신사건 기억부재 ③전형쏠림 ④자기지역 낙관편향 미재현 ⑤긍정편향 ⑥표본학력차 6원인 분석.
- **A/B 파일럿(n=30, `output/pilot_improved.jsonl`) 검증 결과:** 사건브리핑=Q7 즉효(제주항공 5.7→100%, 단 과집중), 비전형성지시=Q9/Q22 분산 부분회복(모드왜곡 부작용), 온도1.0=Q6 긍정편향 악화, Q12/Q27/Q29 완강편향은 프롬프트로 미해결.
- **본 파이프라인 반영(커밋됨):**
  - `build_prompt.py`: SYSTEM_TEMPLATE에 ①거주지 시도별 체감위험(REGION_RISK) ②2024 실제재난 팩트 브리핑(EVENT_BRIEF_2024, 중립톤) ③비전형성·솔직성 지시 추가.
  - `run_survey.py`: `--temperature` 기본 0.85(1.0 아님)·`--top-p` 0.95 신설.
  - ⚠ **기존 responses_phase1/phase2.jsonl은 구(舊) 프롬프트(temp 0.7) 산물** → 개선 효과 보려면 새 출력파일로 재수집 필요.
- **남은 과제:** Q12/Q27 완강합의·Q29 낙관편향은 교차-페르소나 이질성 주입/분포 사전보정 등 표본·보정 레벨 개입 필요.

## ★★개선안 v2 검증 완료 (2026-06-24) — A+B+C+D 결합, 대성공
- **기법:** A=확률추출+샘플링(단일선택 대신 보기별 확률 추정→샘플), B=잠재성향 시드(정부신뢰·위험민감도·응답스타일), C=개인 경험 백스토리, D=학력 재가중(분석단계).
- **구현:** `survey/pilot_improved2.py`(수집), `survey/_pilot2_compare.py`(비교). 결과 `output/pilot_improved2.jsonl`(n=27/30, 실패3=JSON파싱).
- **핵심 성과(실제 / 기존 / v2):** Q12 인명피해 62.9 / 100 / **51.9(엔트로피 0→1.85)** — 분산소멸 해결. Q27 55.6 / 99.4 / **70.4**. Q9(대조 B+C만) 감염병41.6 / 화재73.4 / **감염병48.1** — 전형쏠림 해결. Q7 제주항공 38.2 / 5.7 / **40.7**. Q16 3.4 / 3.03 / **3.41(+D)**. Q6 4.0 / 4.02 / **3.59**(v1 4.57 과대 해소).
- **결론:** A(확률추출)+B+C 결합이 가장 효과적. 기존 ✘(Q12·Q27·Q9)가 ◎/○로 전환. **잔존 실패=Q29 자기지역 낙관편향(51.9 vs 실제72.5)** — 거주지 애착 프라이어 추가 필요.
- **다음:** v2 기법을 본 파이프라인에 정식 통합(현재는 별도 파일럿 스크립트) + 전체표본 재수집으로 확정 검증. 보고서 `output/report_compare.html` 7절에 상세.

## ★★★v2 기법 본 파이프라인 정식 통합 완료 (2026-06-24)
- **build_prompt.py:** SYSTEM_TEMPLATE에 `latent_block`(B 잠재성향: 정부신뢰·위험민감도·응답스타일 + ②거주지 애착(HOME) 프라이어 + C 경험 백스토리) 추가. `ELICIT_TYPES`(scale5/scale5_dk/single/branch)·`elicit_options`·`sample_dist` 신설. `build_messages`/`render_output_spec`/`_spec_line`에 `elicit` 파라미터 — 확률추출 대상은 출력스펙을 {보기:확률}로 요청, rank/matrix/open은 직접 유지.
- **run_survey.py:** `--elicit` 기본 ON(`--no-elicit`로 구식 강제선택). `_sample_elicited`가 분포→정수 샘플(uuid 시드). 검증·집계 다운스트림은 정수만 받으므로 무변경.
- **검증:** 1명 엔드투엔드 스모크 OK — Q5/Q6/Q7/Q13(elicit)→정수 샘플, Q8~Q12(rank)→리스트, Q12=[1,4] 분산 발현, validate 통과.
- ②Q29 낙관편향 대응: HOME 프라이어(애착 우세 0.55)를 latent_block에 포함 → Q29 예% 상향 기대(전체표본 재수집으로 확정 검증 필요).
- ⚠ **기존 responses_*.jsonl은 구식 산물.** 개선판은 새 출력파일로 재수집해야 반영됨(예: `--out output/responses_phase1_v2.jsonl`).
- 파일럿 스크립트(`pilot_improved*.py`)는 기록용으로 유지(본 실행은 run_survey로 충분).

## ★심화 개선 1·2·3 파이프라인 반영 (2026-06-24, report_compare.html 8절)
- **1 순위형 확률추출(Plackett–Luce):** elicit을 rank까지 확장. 모델이 상위 6후보를 [코드,가중치]로 출력→`sample_rank`가 무복원 가중표집. Q8·Q9·Q11·Q23~26 1순위 과집중 해소.
- **2 DK·불성실 주입:** `persona_traits`에 dk_weight(저학력·둔감→Q21 '잘모름' +6~12%)·low_effort(~10%→매트릭스 직선응답). 측정 노이즈 재현.
- **3 응답스타일 분포변환:** `style_transform`(agree↑/critical↓/mid중앙, 계수0.30)을 elicit 척도분포에 사후 적용. `apply_dk`로 scale5_dk DK주입.
- **구조:** build_prompt에 `persona_traits`(키 기반 성향)·`style_transform`·`apply_dk`·`sample_rank` 신설. run_survey `_sample_elicited`가 통합 후처리(샘플 전 변환). 검증·집계 다운스트림 무변경.
- **검증:** 오프라인 단위테스트 전부 통과(방향성·rank유효성·결정론성·validate통과). 라이브 검증은 ★내일 phase2 n=30(토큰 리셋 후)으로 1~6 종합 확정 예정.
- **계획(미구현):** 4 준지도보정+train/test분할(JS divergence), 5 잠재관여도 재가중, 6 페르소나 내 일관성(프로파일 선생성).

## ★통합 파이프라인 검증 (2026-06-25, n=30 부분수집) + 토큰소진 버그수정
- **60명 phase all 시도 중 토큰 1M이 37명에서 소진** → 원인: ①검증실패율↑(elicit 복잡포맷, 첫시도성공 10/30) ②재시도가 대화 누적 echo로 입력 토큰 폭증 ③phase all 28문항.
- **수정(커밋):** run_survey 재시도 시 `base_msgs + 정정1개`만 전송(누적 echo 제거), max_retry 6→4, 빈content 상향 cap 16000→12000.
- **n=30 검증결과(개선 파이프라인, 사후가중) — 실제 vs 기존 vs v2:**
  - Q22 효과성요소: 접근성43.6 / 86.9 / **접근성45.4(1위 일치!)** Q27 예방55.6 / 99.4 / **59.5(근접)** Q6 4.0/4.02/**4.0** Q12 인명62.9/100/**56.2(엔트1.54)**
  - ★Q29 자기지역안전 예%: 72.5 / 48.8 / **64.2** — HOME 애착 프라이어 효과 확인(48.8→64.2).
  - Q11 전체: 화재58.5(기존)→ v2 화재19.7/도로17.6/폭염17.3/감염11.9 — 순위형 PL이 실제처럼 평탄화.
  - 잔존 격차: Q9 사회재난(사이버46 vs 실제 감염병42, 모드 어긋남), Q13 뉴스92(과집중), Q16 3.01(낮음), Q29-1/2 분류 불일치.
- **재진행 계획:** 같은 파일 `responses_test60_v2.jsonl`로 resume(완료 30 스킵, 남은 ~30만 ~600K → 일일예산 내). 토큰 리셋 후 동일명령 재실행.

## ★분리수집 검증 n=46 — 분산회복 성공 / 척도평균 과잉보정 발견 (2026-06-25)
- **분리 전략 검증됨:** phase1·phase2 분리수집으로 첫시도 성공률 급등(phase1 57/60, phase2 24/32 첫시도) → 재시도 폭증·토큰낭비 해소. phase1 60/60(234K), phase2 46성공(막판 토큰소진 8건 429).
- **병합 비교(n=46, `_validate_compare.py p1 p2`):**
  - ✅ 붕괴/분산소멸 해결: Q27 99.4→**66.1**(실제55.6), Q12 100→분산(엔트1.84), Q11 화재58.5→평탄화, **Q29 애착 48.8→61.6**(실제72.5 방향).
  - ❌ **과잉보정:** 이미 잘맞던 척도평균이 실제 아래로 하락 — Q6 4.02→**3.53**(실제4.0), Q16 3.03→**2.76**(실제3.4), Q28 3.49→**2.95**(실제3.4).
- **원인:** 응답스타일 분포변환(critical하향+mid중앙수렴, 계수0.30) + '비위맞추기 금지·무관심' 프롬프트가 **정당한 고심각도 합의까지 깎음**. 고첨도 분포에서 상한(5) 막혀 하향 비대칭.
- **수정(커밋):** style_transform 계수 0.30→0.15·mid 0.22→0.12로 완화. ⚠ 재검증은 다음 토큰사이클.
- **다음 튜닝 후보:** (a)분포변환 추가 완화/문항선택적 적용, (b)anti-people-pleasing 프롬프트 강도 조정, (c)Q12 순위형 PL 과분산 점검, (d)Q9/Q16/Q29-1·2 모드 불일치.
- **데이터:** `output/responses_test60_p1_v2.jsonl`(60), `responses_test60_p2_v2.jsonl`(46).

## ★v3 재검증(계수0.15, n=56) — "계수는 헛다리, 원인은 프롬프트" 발견 (2026-06-26)
- **목적:** style_transform 계수 0.30→0.15 완화가 과잉보정(척도평균 하락)을 고치는지 검증. phase1·phase2 분리수집(v3).
- **결과(실제/기존/v2 0.30/v3 0.15):**
  - Q6 4.0/4.02/3.53/**3.55**, Q16 3.4/3.03/2.76/**2.73**, Q28 3.4/3.49/2.95/**3.05** → **계수 완화해도 척도평균 거의 안 올라옴(과잉보정 미해결).**
  - 분산회복은 견고: Q27 예방 실제55.6 → v2 66.1 → **v3 56.5(거의 정확)**, Q12 엔트로피 1.79 유지, Q11 평탄 유지.
  - Q29 애착: 실제72.5/기존48.8/v2 61.6/**v3 54.0**(표본변동+프롬프트 긴장).
- **★핵심 진단:** 척도평균 과잉하락의 원인은 **사후 style_transform이 아니라 프롬프트 레벨 반긍정 압력**(anti-people-pleasing '무관심·귀찮음' 유도 + 잠재 dull/critical). 모델이 애초에 낮은 분포를 생성 → 변환 튜닝으론 못 고침.
- **수정(커밋):** anti-people-pleasing 프롬프트에서 '무관심·귀찮음·피로' 유도문구 제거, 안티-이상화 취지는 유지 + "걱정·중요 사안은 강도 낮추지 말라" 보호절 추가. style_transform 0.15는 유지(밀수록 안전).
- **다음(v4, 다음 토큰사이클):** 완화 프롬프트로 재검증 — Q6/Q28 척도평균이 실제로 회복되면서 Q9/Q22 다양성이 유지되는지. 근본적으론 계획 #4(문항별 선택보정)가 정공법.
- **데이터:** responses_test60_p1_v3.jsonl(59), p2_v3.jsonl(57).

## 외부 베스트프랙티스 대조 반영 (2026-06-24, report_compare.html 9절)
- **프롬프트 보강(build_prompt.py):** 응답지침에 '비위맞추기·이상적답 금지, 무관심·피로·현실제약 반영, 모르면 모른다고' 추가 — people-pleasing 편향 대응.
- **거버넌스 명시(리포트 9절):** 합성=가설(결론 아님), 확신왜곡 경계, 고위험 의사결정 시 실제≥60%/합성≤40% 혼합, 지속 검증(JS divergence).
- **순서·이월효과(메모리 초기화)는 미적용·한계명시:** 본 설문은 문항 간 의존성(Q11/Q26 '위 9개 중', Q29_1/2 분기종속, 공용 코드표)이 있어 문항 독립화·순서셔플이 설문논리를 깨뜨림. 전문항 단일콜의 '인위적 과일관성'은 알려진 한계로 문서화(완전해결은 계획 #6).
- **실증 그라운딩:** Nemotron(센서스 기반 고밀도 프로필)로 부분 충족, 개인 응답 transcript 미보유 → 계획 #4(실제집계 보정)가 실증경로.

## ✅✅ 1차(Q1~Q13) 완료 — 현재 상태
- **전체 성공 542명 / topup 197·197 완료 (잔여 0, 실패 0).** 170개 층 전부 충족, 성공자 전원 9문항(Q5~Q13) 누락 0. 목표 n≈542 정확히 달성.
- **산출물:** `output/responses_phase1.jsonl`(원본 응답), `output/responses_phase1.csv`(542행), `output/report_phase1.html`(사후가중 집계 + Borda 순위 + 인구통계 교차분석).
- 재집계 명령: `chcp 65001 > $null; $env:PYTHONUTF8="1"; py survey/parse_aggregate.py`
- 참고: 응답파일에 초기(540초 시절) 429 실패행 41개가 남아있으나 **무해**(parse_aggregate가 성공우선 dedup으로 자동 제외, 해당 층은 이미 충족돼 topup 대상 아니었음).

### 핵심 학습(다음 실행/2차에 그대로 적용)
- ★★ **회사망 TLS 차단 해결됨(중요):** `run_survey.py` 시작부에 `truststore.inject_into_ssl()` 추가함(커밋됨). 회사 보안 프록시가 self-signed CA로 HTTPS 가로채 → Python이 `CERTIFICATE_VERIFY_FAILED`로 전부 실패하던 문제. truststore가 OS 인증서저장소(사내 CA 포함) 사용해 통과. **이거 없으면 회사망에서 한 줄도 안 들어옴.** (`py -c "import truststore"`로 설치 확인, 없으면 `py -m pip install truststore`.)
- ★ **페이싱 540→300→240초로 단축 가능했음.** 실측 헤더로 일일토큰 버킷 여유(거의 만충 ~960K) 확인 후 결정. 240초도 att=1 대부분·실패 0으로 안정. 더 당기면 시간당 한도(150요청/시=24초)와 일일토큰 재고갈 위험 — 240초가 무난한 하한. (집/한가한 망이면 더 공격적으로 가능하나 실측 헤더 먼저 확인.)
- ★ **백그라운드 프로세스는 세션 env 상속 안 함** → 키를 명령 환경에 직접 넣거나 점-소싱 먼저.
- ★ **굳이 멈출 땐 run_survey 프로세스만** 종료: `Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? { $_.CommandLine -like '*run_survey*' } | % { Stop-Process -Id $_.ProcessId -Force }` (다른 python(예: http.server 3737)은 건드리지 말 것.)

## ⚡⚡ 2차(Q14~Q30) 재개 — 바로 이 명령 (2026-06-08 중단지점)
```powershell
chcp 65001 > $null; $env:PYTHONUTF8="1"; $env:PYTHONUNBUFFERED="1"
. "D:\01 WORK\260605 nemotron virtual survey2\set_api_key.ps1" | Out-Null
cd "D:\01 WORK\260605 nemotron virtual survey2"
py survey/run_survey.py --model zai-glm-4.7 --personas output/personas_phase2.jsonl `
   --out output/responses_phase2.jsonl --phase phase2 --workers 1 --min-interval 240.0
```
- **현재 상태: phase2 고유 완료 542 / 542 (전량 완료, 실패 0).** 수집 종료.
- ✅ **2차 집계·리포트 구현 완료:** `survey/parse_aggregate_phase2.py` 신설. matrix5(Q17~19)·branch(Q29)·분기종속(Q29_1/2)·open(Q30 키워드+표본) 전용 빌더 추가, 공용 헬퍼는 parse_aggregate에서 import.
  - 실행: `chcp 65001 > $null; $env:PYTHONUTF8="1"; py survey/parse_aggregate_phase2.py`
  - 산출물: `output/responses_phase2.csv`(542행), `output/report_phase2.html`(사후가중 집계 + Borda + 교차분석 + Q30 자유응답).
- ★ **phase2 = Q14~Q30 (19문항, matrix·branch·open 포함).** `--phase phase2` 옵션 신설(코드 커밋됨). 대상은 1차 완료 542명과 동일(`personas_phase2.jsonl`) → Q5~Q30 일관.
- ★ **코드는 새 문항타입 전부 처리 검증됨**(validate/build_prompt). 스모크 테스트 OK.
- ★ **호출당 토큰 ~9K(1차 6.5K보다 무거움)** → 일일토큰 1M/일 천장에 더 빨리 닿음. 542×9K≈4.9M → **완료까지 약 5일**(페이싱 무관, 토큰 충전속도가 한계). 300초로 진행 중, 막판 버킷 바닥나면 429는 resume이 흡수.
- ⚠ **2차 집계는 아직 미구현:** `parse_aggregate.py`는 phase1(Q5~Q13) 전용. Q14~Q30 수집 완료 후 **집계·리포트 로직 추가 필요**(matrix5/branch/open 표 포함).

## ⚡ 회사에서 이어하기 (fresh clone일 때만)
1. clone 후 **`set_api_key.ps1` 직접 생성**: `set_api_key.example.ps1` 복사 → `PUT_KEY_HERE`에 Cerebras 키 입력. (실제 키 파일은 gitignore라 repo에 없음.)
2. `data/`·`DATASET/`(원본 1.9GB)는 **없어도 집계/2차 가능** — 필요한 페르소나는 `output/personas_*.jsonl`에 내장됨. (재표집할 때만 HF에서 재다운로드.)
3. 1차는 완료됨. 재집계만 하려면 `py survey/parse_aggregate.py`. 2차는 위 ➡️ 섹션 명령 실행.

## 진행상황 모니터링 (현재 진척 확인 스니펫)
```powershell
py -c "import json; tu=set(json.loads(l)['persona']['uuid'] for l in open('output/personas_topup_r3.jsonl',encoding='utf-8')); rs=[json.loads(l) for l in open('output/responses_phase1.jsonl',encoding='utf-8')]; bu={}; [bu.__setitem__(r['uuid'],r) for r in rs if r.get('answers') or r['uuid'] not in bu]; s=set(u for u,r in bu.items() if r.get('answers')); print('전체성공',len(s),'| topup',len(tu&s),'/197 | 잔여',len(tu-s))"
```
실시간 쿼터 확인(헤더): `c.chat.completions.with_raw_response.create(...).headers['x-ratelimit-remaining-tokens-day']` (truststore inject 후). 일일토큰 1M이 유일 병목.

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
- [2026-06-05 16:53 중단] **전체 성공 449명, topup 104/197 (잔여 93).** 240초 페이싱·workers1로 안정 진행(att=1 대부분, 실패 0) 중 사용자 요청으로 일시중단, 내일 재개 예정. 위 ⚡⚡ 명령으로 재개.
- [TLS 해결] 회사망 self-signed CA 차단 → truststore 주입으로 해결(run_survey.py 커밋됨). 이게 오늘의 핵심 트러블.
- [실측 쿼터] 일일토큰 버킷이 가정보다 여유 있음(오늘 실패호출들은 TLS단에서 막혀 토큰 0 소비). 13:01에 547K → 16:57에 951K로 회복 관측 = 충전/부분리셋. 300초로도 막판 외엔 429 거의 없음.
- [구버전 메모] 2026-06-04: 540초 시절 429 급증으로 340/345명에서 중단했던 기록(아래). 그 원인의 일부는 사실 TLS였을 가능성 — 회사망 기준으론 truststore가 진짜 해결책.

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
