# 개선 파일럿 v2: A(확률추출+샘플링) + B(잠재성향 시드) + C(개인 경험 백스토리) 결합
# 대조: Q9는 일반선택 유지(A 미적용) → B+C 단독효과 분리. D(학력보정)는 비교스크립트에서 적용.
import argparse, json, os, sys, time, threading, random, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import truststore; truststore.inject_into_ssl()
except Exception:
    pass

from survey_schema import QUESTION_BY_ID
from build_prompt import _persona_block, region_risk, EVENT_BRIEF_2024

CEREBRAS_BASE = "https://api.cerebras.ai/v1"
_lock = threading.Lock()

# A 확률추출 대상 문항(보기 집합 작거나 중간) — 분포를 받아 샘플
ELICIT = {
    "Q6":  ("scale", {i: QUESTION_BY_ID["Q6"]["scale"][i] for i in range(1, 6)}),
    "Q7":  ("single", QUESTION_BY_ID["Q7"]["options"]),
    "Q12": ("rank1", QUESTION_BY_ID["Q12"]["options"]),     # 1순위 분포만 추출
    "Q16": ("scale", {i: QUESTION_BY_ID["Q16"]["scale"][i] for i in range(1, 6)}),
    "Q22": ("single", QUESTION_BY_ID["Q22"]["options"]),
    "Q27": ("single", QUESTION_BY_ID["Q27"]["options"]),
    "Q29": ("branch", QUESTION_BY_ID["Q29"]["options"]),
}
NORMAL = ["Q9"]  # 대조군: 일반 1순위 선택(사회재난 27~55 중)

# B 잠재성향 분포(인간 응답스타일·태도 이질성 모사)
TRUST = [("정부·전문가를 잘 신뢰하지 않는 편", 0.30), ("정부·전문가를 보통 수준으로 신뢰", 0.50), ("정부·전문가를 비교적 신뢰하는 편", 0.20)]
SENS = [("위험에 다소 둔감하고 무관심한 편", 0.30), ("위험에 보통 수준으로 반응", 0.40), ("위험에 예민하고 걱정이 많은 편", 0.30)]
STYLE = [("질문에 비판적이고 까다롭게 답하는 편", 0.30), ("무난하게 중간값으로 답하는 편", 0.40), ("대체로 동의·긍정적으로 답하는 편", 0.30)]


def _pick(rng, dist):
    r = rng.random(); c = 0
    for label, p in dist:
        c += p
        if r <= c:
            return label
    return dist[-1][0]


def persona_rng(uuid):
    h = int(hashlib.md5(uuid.encode()).hexdigest(), 16) % (2**32)
    return random.Random(h)


def backstory(rng, persona):
    """C: 페르소나별 짧은 재난 경험담(45%는 경험 있음, 55%는 없음 — 현실 반영)."""
    prov, risk = region_risk(persona.get("province", ""))
    if rng.random() < 0.55:
        return "당신은 재난을 직접 크게 겪은 적은 없고, 대부분 뉴스로만 접합니다."
    templates = [
        f"당신은 몇 년 전 거주지({prov})에서 {risk.split('·')[0]} 관련 피해를 직접 겪은 적이 있습니다.",
        "당신은 가족·친지 중에 재난·사고로 피해를 본 사람이 있어 그 일을 또렷이 기억합니다.",
        "당신은 직장이나 생업 현장에서 안전사고 위험을 가까이에서 느낀 경험이 있습니다.",
        "당신은 과거 교통사고나 화재를 직접 목격하거나 겪어 그 충격이 남아 있습니다.",
    ]
    return rng.choice(templates)


def latent_block(persona):
    rng = persona_rng(persona["uuid"])
    bits = [_pick(rng, TRUST), _pick(rng, SENS), _pick(rng, STYLE), backstory(rng, persona)]
    return "당신의 숨은 성향·경험(응답에 자연스럽게 반영하되 드러내 말하지는 마십시오):\n- " + "\n- ".join(bits)


def build_user(persona, demographics):
    prov, risk = region_risk(persona.get("province", ""))
    head = (f"당신은 아래 한국인 본인입니다. 완전히 몰입해 1인칭으로 솔직하게 답하십시오.\n\n"
            f"== 정체성 ==\n{_persona_block(persona, demographics)}\n\n"
            f"== 거주지 체감 위험 ==\n{prov}: {risk}\n\n{EVENT_BRIEF_2024}\n\n{latent_block(persona)}\n")
    # A: 확률 추출 지시
    spec = ["== 응답 형식 (JSON 하나) ==",
            "아래 각 문항에 대해, '당신이라는 개인'이 각 보기를 고를 주관적 확률(0~1, 합 1 근사)을 추정해 분포로 출력하십시오.",
            "★억지로 한 보기에 1.0을 몰지 마십시오. 당신의 망설임·이중성을 분포로 드러내십시오(예: 0.6/0.25/0.15).",
            "단, Q9는 분포가 아니라 사회재난 코드 1개(27~55)를 정수로 고르십시오.",
            "{"]
    for qid, (typ, opts) in ELICIT.items():
        q = QUESTION_BY_ID[qid]
        olist = " / ".join(f"{k}={v}" for k, v in opts.items())
        spec.append(f'  "{qid}": {{보기 {olist} 의 확률 분포}},   // {q["text"][:40]}')
    spec.append('  "Q9": 27~55 사회재난 코드 1개 (가장 위험한 사회재난 1순위)')
    spec.append("}")
    spec.append("JSON 외 텍스트 금지.")
    return head + "\n" + "\n".join(spec)


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
    # 줄끝 // 주석 제거
    import re
    s = re.sub(r"//[^\n]*", "", s)
    return json.loads(s)


def sample_from(dist_raw, opts, rng):
    """모델이 준 {보기:확률}을 정규화 후 1개 샘플."""
    d = {}
    for k, v in dist_raw.items():
        try:
            ik = int(k); fv = float(v)
        except (ValueError, TypeError):
            continue
        if ik in opts and fv > 0:
            d[ik] = fv
    if not d:
        return None
    tot = sum(d.values())
    keys = list(d.keys()); ps = [d[k]/tot for k in keys]
    r = rng.random(); c = 0
    for k, p in zip(keys, ps):
        c += p
        if r <= c:
            return k
    return keys[-1]


_next_t = [0.0]; _pace_lock = threading.Lock()


def pace(interval):
    with _pace_lock:
        now = time.time(); t = max(now, _next_t[0]); _next_t[0] = t + interval; d = t - now
    if d > 0:
        time.sleep(d)


def answer_one(client, rec, interval, max_retry=5):
    persona, demo = rec["persona"], rec["demographics"]
    user = build_user(persona, demo)
    rng = persona_rng(persona["uuid"] + "_sample")
    last = None
    for attempt in range(1, max_retry + 1):
        try:
            pace(interval)
            resp = client.chat.completions.create(
                model="zai-glm-4.7",
                messages=[{"role": "system", "content": "당신은 설문에 응답하는 평범한 한국인 개인입니다."},
                          {"role": "user", "content": user}],
                temperature=0.85, top_p=0.95, max_tokens=4000)
            content = resp.choices[0].message.content
            if not content:
                raise RuntimeError("빈 content")
            raw = _extract_json(content)
            ans = {}
            for qid, (typ, opts) in ELICIT.items():
                if qid not in raw or not isinstance(raw[qid], dict):
                    raise RuntimeError(f"{qid} 분포 누락")
                s = sample_from(raw[qid], opts, rng)
                if s is None:
                    raise RuntimeError(f"{qid} 샘플 실패")
                ans[qid] = s
            q9 = raw.get("Q9")
            ans["Q9"] = int(q9) if isinstance(q9, (int, str)) and str(q9).isdigit() and 27 <= int(q9) <= 55 else None
            return {"uuid": persona["uuid"], "demographics": demo, "answers": ans,
                    "dist": {q: raw[q] for q in ELICIT}, "attempts": attempt}
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            is_429 = "429" in str(e) or "too_many" in str(e) or "quota" in str(e)
            time.sleep(0.0 if is_429 else min(3.0, attempt))
    return {"uuid": persona["uuid"], "demographics": demo, "answers": None, "error": last}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--personas", default="../output/personas_phase2.jsonl")
    ap.add_argument("--out", default="../output/pilot_improved2.jsonl")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--interval", type=float, default=20.0)
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    recs = [json.loads(l) for l in open(args.personas, encoding="utf-8")][:args.n]
    done = set()
    if os.path.exists(args.out):
        for l in open(args.out, encoding="utf-8"):
            r = json.loads(l)
            if r.get("answers") is not None:
                done.add(r["uuid"])
    todo = [r for r in recs if r["persona"]["uuid"] not in done]
    print(f"v2 파일럿(A+B+C): 대상 {len(recs)} / 완료 {len(done)} / 예정 {len(todo)}")
    if not todo:
        print("이미 완료"); return

    client = get_client()
    ok = fail = 0
    with open(args.out, "a", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(answer_one, client, r, args.interval): r for r in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            res = fut.result()
            with _lock:
                f.write(json.dumps(res, ensure_ascii=False) + "\n"); f.flush()
            ok += res["answers"] is not None; fail += res["answers"] is None
            if i % 5 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} 성공 {ok} 실패 {fail}")
    print(f"완료: 성공 {ok} 실패 {fail} → {args.out}")


if __name__ == "__main__":
    main()
