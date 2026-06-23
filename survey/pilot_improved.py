# 개선 프롬프트 A/B 파일럿: 온도↑ + 2024 사건 팩트 브리핑 + 비전형성 지시 + 거주지 위험맥락
# 대표 발산 문항(Q6,Q7,Q9,Q12,Q16,Q22,Q27,Q29)만 수집해 실제값·기존가상값과 비교
import argparse, json, os, sys, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import truststore; truststore.inject_into_ssl()
except Exception:
    pass

from survey_schema import get_llm_questions
from build_prompt import _persona_block, build_user_static
from validate import validate_response

PILOT_QIDS = ["Q6", "Q7", "Q9", "Q12", "Q16", "Q22", "Q27", "Q29"]
CEREBRAS_BASE = "https://api.cerebras.ai/v1"
_lock = threading.Lock()

# 2024년 실제 재난 팩트(시점·규모) — 모범답 유도가 아닌, 인간의 '기억'을 보강하기 위한 중립적 사실 제공
EVENT_BRIEF = """[2024년에 당신이 겪은 주요 재난 사건들 — 기억을 떠올려 보십시오]
· 2024.12.29 제주항공 여객기 참사(무안공항 동체착륙, 179명 사망) — 역대 최악의 국내 항공사고
· 2024.06.24 화성 아리셀 리튬배터리 공장 화재(23명 사망)
· 2024.07.01 시청역 역주행 교통사고(보행자 9명 사망)
· 2024.08.01 인천 청라 아파트 지하주차장 전기차 화재(대규모 정전·이재민)
· 2024.06.12 부안 지진(규모 4.8)
· 2024년 9월 120년 만의 9월 폭염(역대 가장 늦은 폭염)
· 그 밖에 태풍 종다리, 평창 LPG 충전소 폭발, 울릉공항 토사붕괴, 시흥 교량 붕괴 등
당신이 그 해에 뉴스로 접하고 느꼈을 법한 충격·체감을 그대로 반영해 답하십시오."""

# 시도별 체감 위험요인(거주지 맥락) — province 문자열 키워드 매칭
REGION_RISK = {
    "서울": "도심 인파밀집·노후 인프라·도시침수", "부산": "해안 해양재난·태풍·해운대 인파",
    "인천": "해안·공항/항만 사고·산업단지", "대구": "내륙 폭염·도심 화재",
    "광주": "도심 생활안전", "대전": "내륙·연구단지", "울산": "대규모 산업단지·화학사고",
    "세종": "신도시 인프라", "경기": "도시·산업 혼재·인구밀집", "강원": "산사태·대설·산불·해안",
    "충북": "내륙 호우·산지", "충남": "서해안·산업단지", "전북": "농어업·서해안",
    "전남": "다도해 해양재난·태풍·농어업", "경북": "산불·지진(포항·경주)·내륙",
    "경남": "남해안 태풍·산업단지", "제주": "태풍·해양·관광안전",
}

SYS_V2 = """당신은 아래에 묘사된 실제 한국인 한 사람입니다. 이 사람의 정체성·가치관·생활환경·교육수준·사는 지역에 완전히 몰입하십시오.

== 당신의 정체성 ==
{persona}

== 당신의 거주지 체감 위험 ==
당신이 사는 {prov} 지역에서 사람들이 특히 체감하는 위험: {risk}

{events}

== 응답 지침 (매우 중요) ==
- 위 인물 '본인'으로서 1인칭으로 솔직하게 답하십시오.
- ★당신은 평범한 개인입니다. '모범답안'이나 '전문가가 선호할 답'을 고르지 마십시오. 당신의 학력·직업·연령·지역에서 비롯되는 편향·무관심·오해·소수의견을 그대로 드러내십시오.
- ★다른 사람과 똑같이 답할 필요가 없습니다. 남들이 잘 고르지 않는 보기라도, 당신 생각이 그렇다면 그것을 고르십시오.
- 척도 문항에서 무조건 중간(보통)이나 극단(매우)에 쏠리지 말고, 당신의 실제 온도에 맞는 값을 고르십시오.
- 거주지·연령·체감에 따라 위험 인식이 달라짐을 반영하십시오.
- 반드시 지정된 JSON 형식 하나만 출력하고 그 외 설명은 붙이지 마십시오."""


def region_of(prov):
    for k, v in REGION_RISK.items():
        if k in prov:
            return k, v
    return prov, "일반 생활안전"


def build_messages_v2(persona, demographics, questions):
    prov, risk = region_of(persona["province"])
    sys = SYS_V2.format(persona=_persona_block({"persona": persona}, demographics) if False else _persona_block_safe(persona, demographics),
                        prov=prov, risk=risk, events=EVENT_BRIEF)
    user = "아래 설문에 위 인물 본인으로서 응답해 JSON으로만 답하십시오.\n\n" + build_user_static(questions)
    return [{"role": "system", "content": sys}, {"role": "user", "content": user}]


def _persona_block_safe(persona, demo):
    # build_prompt._persona_block은 rec 형태를 기대 → persona dict 직접 사용 위해 재구성
    return _persona_block(persona, demo)


def get_client():
    from openai import OpenAI
    key = os.environ.get("CEREBRAS_API_KEY")
    if not key:
        sys.exit("CEREBRAS_API_KEY 미설정")
    return OpenAI(api_key=key, base_url=CEREBRAS_BASE)


def _extract_json(text):
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b != -1:
        s = s[a:b + 1]
    return json.loads(s)


_next_t = [0.0]
_pace_lock = threading.Lock()


def pace(interval):
    with _pace_lock:
        now = time.time()
        t = max(now, _next_t[0])
        _next_t[0] = t + interval
        d = t - now
    if d > 0:
        time.sleep(d)


def answer_one(client, rec, questions, temperature, interval, max_retry=5):
    msgs = build_messages_v2(rec["persona"], rec["demographics"], questions)
    last = None
    for attempt in range(1, max_retry + 1):
        try:
            pace(interval)
            resp = client.chat.completions.create(model="zai-glm-4.7", messages=msgs,
                                                  temperature=temperature, top_p=0.95, max_tokens=4000)
            content = resp.choices[0].message.content
            if not content:
                raise RuntimeError("빈 content")
            ans = _extract_json(content)
            ok, errs = validate_response(ans, questions)
            if ok:
                return {"uuid": rec["persona"]["uuid"], "demographics": rec["demographics"],
                        "answers": ans, "attempts": attempt}
            last = "; ".join(errs[:5])
            msgs = msgs + [{"role": "assistant", "content": content},
                          {"role": "user", "content": f"다음이 잘못됨: {last}. 규칙대로 JSON만 다시."}]
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            is_429 = "429" in str(e) or "too_many" in str(e) or "quota" in str(e)
            time.sleep(0.0 if is_429 else min(3.0, attempt))
    return {"uuid": rec["persona"]["uuid"], "demographics": rec["demographics"], "answers": None, "error": last}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--personas", default="../output/personas_phase2.jsonl")
    ap.add_argument("--out", default="../output/pilot_improved.jsonl")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    questions = get_llm_questions(PILOT_QIDS)
    print(f"파일럿 문항: {[q['id'] for q in questions]}  temp={args.temperature} interval={args.interval}s")

    recs = [json.loads(l) for l in open(args.personas, encoding="utf-8")][:args.n]
    done = set()
    if os.path.exists(args.out):
        for l in open(args.out, encoding="utf-8"):
            r = json.loads(l)
            if r.get("answers") is not None:
                done.add(r["uuid"])
    todo = [r for r in recs if r["persona"]["uuid"] not in done]
    print(f"대상 {len(recs)} / 완료 {len(done)} / 처리예정 {len(todo)}")
    if not todo:
        print("이미 완료"); return

    client = get_client()
    ok = fail = 0
    with open(args.out, "a", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(answer_one, client, r, questions, args.temperature, args.interval): r for r in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            res = fut.result()
            with _lock:
                f.write(json.dumps(res, ensure_ascii=False) + "\n"); f.flush()
            if res["answers"] is not None:
                ok += 1
            else:
                fail += 1
            if i % 5 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} 성공 {ok} 실패 {fail}")
    print(f"완료: 성공 {ok} 실패 {fail} → {args.out}")


if __name__ == "__main__":
    main()
