# 페르소나 1명 → 1인칭 몰입 시스템 프롬프트 + 설문 응답(JSON) 지시 메시지 생성
import json, random, hashlib
from survey_schema import (
    QUESTIONS, LLM_QUESTIONS, get_llm_questions, DISASTER_TYPES, DISASTER_CATEGORY,
    NATURAL, SOCIAL, SAFETY, RND_ITEMS,
)
from sample_personas import PROVINCE_LABEL


def _persona_block(p, demo):
    """페르소나 속성·텍스트를 사람이 읽는 1인칭 배경으로 정리."""
    lines = [
        f"- 이름: {p['persona'].split(' 씨')[0] if ' 씨' in p['persona'] else '익명'}",
        f"- 성별/나이: {p['sex']}, 만 {p['age']}세",
        f"- 혼인상태: {p['marital_status']} / 가구유형: {p['family_type']} / 주거: {p['housing_type']}",
        f"- 최종학력: {p['education_level']}" + (f" (전공: {p['bachelors_field']})" if p.get('bachelors_field') else ""),
        f"- 직업: {p['occupation']}",
        f"- 거주지: {p['province']} {p['district']}",
        "",
        f"[요약] {p['persona']}",
        f"[직업적 면모] {p['professional_persona']}",
        f"[문화적 배경·가치관] {p['cultural_background']}",
        f"[취미·관심사] {p['hobbies_and_interests']}",
        f"[보유 역량] {p['skills_and_expertise']}",
        f"[커리어 목표] {p['career_goals_and_ambitions']}",
    ]
    return "\n".join(lines)


# 2024년 실제 재난 사실 — LLM의 '기억 부재'를 보강(실제조사 대비 Q7 등 최신사건 응답 교정).
# ★중립 톤 유지: 어느 사건이 더 심각한지는 암시하지 않음(파일럿에서 '충격 강조'가 특정 보기 100% 과집중 유발).
EVENT_BRIEF_2024 = """[참고: 2024년 국내에서 발생한 주요 재난·사고 (사실 정보)]
· 2024.12.29 제주항공 여객기 참사 (무안공항, 179명 사망)
· 2024.06.24 화성 아리셀 배터리공장 화재 (23명 사망)
· 2024.07.01 시청역 역주행 교통사고 (보행자 9명 사망)
· 2024.08.01 인천 청라 아파트 지하주차장 전기차 화재
· 2024.06.12 부안 지진 (규모 4.8)
· 2024년 9월 120년 만의 9월 폭염
· 그 밖에 태풍 종다리, 평창 LPG 충전소 폭발, 울릉공항 토사붕괴, 시흥 교량 붕괴 등
※ 위는 사실 나열일 뿐입니다. 어느 사건을 더 심각하게 느끼는지는 당신의 관심·경험·가치관에 따라 사람마다 다릅니다."""

# 시도별 체감 위험요인 — 거주지 맥락 주입으로 지역 인식 차이 반영
REGION_RISK = {
    "서울": "도심 인파밀집·노후 인프라·도시침수", "부산": "해안 해양재난·태풍·인파",
    "인천": "해안·공항/항만 사고·산업단지", "대구": "내륙 폭염·도심 화재",
    "광주": "도심 생활안전", "대전": "내륙·연구단지", "울산": "대규모 산업단지·화학사고",
    "세종": "신도시 인프라", "경기": "도시·산업 혼재·인구밀집", "강원": "산사태·대설·산불·해안",
    "충북": "내륙 호우·산지", "충남": "서해안·산업단지", "전북": "농어업·서해안",
    "전남": "다도해 해양재난·태풍·농어업", "경북": "산불·지진(포항·경주)·내륙",
    "경남": "남해안 태풍·산업단지", "제주": "태풍·해양·관광안전",
}


def region_risk(province):
    for k, v in REGION_RISK.items():
        if k in (province or ""):
            return k, v
    return (province or "거주지"), "일반 생활안전"


# ── B: 잠재 성향 시드 + C: 경험 백스토리 (파일럿 v2 검증 — 전형쏠림·과대긍정 완화) ─────────
# 인간 응답 이질성 모사: 페르소나별 무작위(uuid 시드)로 태도·경험을 부여. 분포는 현실 근사.
TRUST = [("정부·전문가를 잘 신뢰하지 않는 편", 0.30), ("정부·전문가를 보통 수준으로 신뢰", 0.50),
         ("정부·전문가를 비교적 신뢰하는 편", 0.20)]
SENS = [("위험에 다소 둔감하고 무관심한 편", 0.30), ("위험에 보통 수준으로 반응", 0.40),
        ("위험에 예민하고 걱정이 많은 편", 0.30)]
STYLE = [("질문에 비판적이고 까다롭게 답하는 편", 0.30), ("무난하게 중간값으로 답하는 편", 0.40),
         ("대체로 동의·긍정적으로 답하는 편", 0.30)]
# ② Q29 낙관편향 대응: 거주지 애착·정주성(실제 72.5%가 자기지역을 더 안전하다 인식 → 애착 우세 분포)
HOME = [("지금 사는 동네에 애착이 크고, 이 지역이 다른 곳보다 안전하다고 느끼는 편이다", 0.55),
        ("거주지에 특별한 애착은 없고 안전성도 보통이라고 느낀다", 0.30),
        ("거주지에 불만이 있고, 다른 곳보다 위험하다고 느끼는 편이다", 0.15)]


def persona_rng(uuid, salt=""):
    h = int(hashlib.md5((uuid + salt).encode()).hexdigest(), 16) % (2**32)
    return random.Random(h)


def _pick(rng, dist):
    r = rng.random(); c = 0.0
    for label, p in dist:
        c += p
        if r <= c:
            return label
    return dist[-1][0]


def _backstory(rng, prov, risk):
    """C: 45%는 재난 경험 있음, 55%는 뉴스로만(현실 반영)."""
    if rng.random() < 0.55:
        return "당신은 재난을 직접 크게 겪은 적은 없고, 대부분 뉴스로만 접합니다."
    return rng.choice([
        f"당신은 몇 년 전 거주지({prov})에서 {risk.split('·')[0]} 관련 피해를 직접 겪은 적이 있습니다.",
        "당신은 가족·친지 중에 재난·사고로 피해를 본 사람이 있어 그 일을 또렷이 기억합니다.",
        "당신은 직장이나 생업 현장에서 안전사고 위험을 가까이에서 느낀 경험이 있습니다.",
        "당신은 과거 교통사고나 화재를 직접 목격하거나 겪어 그 충격이 남아 있습니다.",
    ])


def latent_block(persona, prov, risk):
    rng = persona_rng(persona.get("uuid", ""))
    bits = [_pick(rng, TRUST), _pick(rng, SENS), _pick(rng, STYLE), _pick(rng, HOME),
            _backstory(rng, prov, risk)]
    return "당신의 숨은 성향·경험(응답에 자연스럽게 반영하되, 드러내 말하지는 마십시오):\n- " + "\n- ".join(bits)


# ── A: 확률추출 대상 유형 + 샘플링 (파일럿 v2 검증 — 분산소멸 해결) ──────────────────────
ELICIT_TYPES = {"scale5", "scale5_dk", "single", "branch"}


def elicit_options(q):
    """확률추출 대상 문항의 유효 보기 코드 리스트."""
    t = q["type"]
    if t == "scale5":
        return [1, 2, 3, 4, 5]
    if t == "scale5_dk":
        return [1, 2, 3, 4, 5, 6]
    if t == "branch":
        return [1, 2]
    if t == "single":
        return list(q["options"])
    return []


def sample_dist(raw, opts, rng):
    """모델이 준 {보기:확률}을 정규화 후 1개 샘플. 이미 정수면 그대로 통과."""
    if isinstance(raw, int) and not isinstance(raw, bool) and raw in opts:
        return raw
    if not isinstance(raw, dict):
        return None
    d = {}
    for k, v in raw.items():
        try:
            ik, fv = int(k), float(v)
        except (ValueError, TypeError):
            continue
        if ik in opts and fv > 0:
            d[ik] = fv
    if not d:
        return None
    tot = sum(d.values())
    r = rng.random(); c = 0.0
    for k in d:
        c += d[k] / tot
        if r <= c:
            return k
    return list(d)[-1]


SYSTEM_TEMPLATE = """당신은 아래에 묘사된 실제 한국인 한 사람입니다. 이 사람의 정체성, 가치관, 생활환경, 교육수준, 사는 지역에 완전히 몰입하십시오.

== 당신의 정체성 ==
{persona}

== 당신의 거주지 체감 위험 ==
당신이 사는 {prov} 지역에서 사람들이 특히 체감하는 위험: {risk}

{events}

== 당신의 성향·경험 ==
{latent}

== 응답 지침 ==
- 위 인물 '본인'으로서 1인칭으로 솔직하게 응답합니다. '모범답안'이나 전문가가 선호할 답을 고르려 애쓰지 마십시오.
- 당신은 평범한 한 개인입니다. 학력·직업·연령·지역에서 비롯되는 당신만의 관점·관심·무관심·오해·소수의견까지 그대로 반영하십시오. 모두가 똑같이 답할 필요는 없습니다.
- 척도 문항에서 습관적으로 중간(보통)이나 최고점(매우)에 몰지 말고, 당신의 실제 생각의 강도에 맞는 값을 고르십시오.
- 거주지(시도)에 따라 체감하는 위험(예: 해안지역의 해양재난, 도시의 인파사고)이 달라질 수 있음을 반영하십시오.
- 반드시 지정된 JSON 형식 하나만 출력하고, 그 외 설명·머리말은 붙이지 마십시오."""


def render_disaster_master(with_category=True):
    def grp(title, ids):
        return f"  [{title}] " + ", ".join(f"{i}.{DISASTER_TYPES[i]}" for i in ids)
    lines = [
        "■ 재난유형 코드표 (Q8~Q11, Q23~Q26 공용)",
        "· 자연재난(1~26)",
        grp("풍수해", [1, 2, 3, 4, 5, 6]), grp("기상재난", [7, 8, 9, 10, 11, 12]),
        grp("지질재난", [13, 14, 15, 16, 17]), grp("해양재난", [18, 19, 20, 21, 22, 23, 24]),
        grp("기타", [25, 26]),
        "· 사회재난(27~55)",
        grp("감염병", [27, 28]), grp("교통사고", [29, 30, 31, 32]), grp("화재·폭발", [33, 34, 35, 36]),
        grp("화학물질", [37, 38]), grp("미세먼지", [39, 40, 41, 42]), grp("환경오염", [43, 44, 45]),
        grp("시설물", [46, 47, 48, 49]), grp("정보·전산", [50, 51]), grp("통신", [52, 53]), grp("기타", [54, 55]),
        "· 안전사고(56~70)",
        grp("생활·레저", [56, 57, 58, 59, 60, 61]), grp("산업재난", [62, 63, 64, 65, 66]),
        grp("치안·기타", [67, 68, 69, 70]),
    ]
    if with_category:
        lines += ["",
                  "■ 재난 대분류/중분류 코드표 (Q29-1, Q29-2 공용)",
                  ", ".join(f"{k}.{v}" for k, v in DISASTER_CATEGORY.items())]
    return "\n".join(lines)


def _opts(d):
    return " / ".join(f"{k}={v}" for k, v in d.items())


def render_question(q):
    """문항 1개를 사람이 읽는 텍스트로."""
    t = q["type"]
    head = f"{q['id']}. {q['text']}"
    if t in ("scale5", "scale5_dk"):
        return head + f"\n   (척도: {_opts(q['scale'])}" + (", 6=잘 모르겠다)" if t == "scale5_dk" else ")")
    if t == "single":
        return head + f"\n   (보기: {_opts(q['options'])})"
    if t == "branch":
        return head + f"\n   (1=예 → Q29_1 응답, 2=아니오 → Q29_2 응답)"
    if t == "rank":
        if "options" in q:
            return head + f"\n   (보기: {_opts(q['options'])}) → {q['k']}개를 순위대로 리스트"
        rng = {tuple(NATURAL): "1~26", tuple(SOCIAL): "27~55", tuple(SAFETY): "56~70",
               tuple(range(1, 71)): "1~70"}.get(tuple(q["candidates"]), "")
        return head + f"\n   (코드표 {rng} 중 {q['k']}개를 위험 순위대로 리스트)"
    if t == "matrix5":
        return head + f"\n   (항목 3개=[{', '.join(RND_ITEMS)}] 각각 척도 {_opts(q['scale'])} → 길이3 리스트)"
    if t == "open":
        return head + "\n   (2~3문장 자유서술)"
    return head


def render_survey(questions):
    qids = {q["id"] for q in questions}
    need_master = any(q["type"] == "rank" and "candidates" in q for q in questions)
    need_category = bool(qids & {"Q29_1", "Q29_2"})
    parts = []
    if need_master:
        parts += [render_disaster_master(with_category=need_category), ""]
    parts.append("■ 설문 문항")
    cur = None
    for q in questions:
        if q["section"] != cur:
            cur = q["section"]
            parts.append(f"\n[{cur}]")
        parts.append(render_question(q))
    return "\n".join(parts)


def _spec_line(q, elicit=False):
    """문항 1개의 출력 JSON 형식 한 줄. elicit=True면 확률추출 대상 유형은 분포로 요청."""
    qid, t = q["id"], q["type"]
    if elicit and t in ELICIT_TYPES:
        codes = "/".join(str(c) for c in elicit_options(q))
        return f'  "{qid}": {{보기 {codes} 각각의 확률(0~1, 합 1 근사)}}'
    if t == "scale5":
        return f'  "{qid}": 1~5 정수'
    if t == "scale5_dk":
        return f'  "{qid}": 1~5 또는 6(잘모름)'
    if t == "single":
        return f'  "{qid}": 1~{max(q["options"])} 중 하나'
    if t == "branch":
        return f'  "{qid}": 1 또는 2'
    if t == "rank":
        if "options" in q:
            rng = f'1~{max(q["options"])}'
        else:
            rng = {tuple(NATURAL): "1~26", tuple(SOCIAL): "27~55", tuple(SAFETY): "56~70",
                   tuple(range(1, 71)): "1~70"}.get(tuple(q["candidates"]), "")
        return f'  "{qid}": [{rng} 중 {q["k"]}개, 순위대로, 중복없이]'
    if t == "matrix5":
        return f'  "{qid}": [1~5, 1~5, 1~5]  (항목순: {", ".join(q["items"])})'
    if t == "open":
        return f'  "{qid}": "자유서술 문자열"'
    return f'  "{qid}": ...'


def render_output_spec(questions, elicit=False):
    lines = [_spec_line(q, elicit) for q in questions]
    extra = ("\n★확률추출 문항은 억지로 한 보기에 1.0을 몰지 말고, 당신의 망설임·이중성을 분포로 드러내십시오(예: 0.6/0.25/0.15)."
             if elicit else "")
    return ("== 출력 형식 (JSON 객체 하나, 아래 키를 모두 포함) ==\n{\n"
            + ",\n".join(lines)
            + "\n}\n순위형은 중복 없는 코드로 가장 위험/중요한 순서대로 나열하십시오." + extra
            + " JSON 외의 텍스트는 절대 출력하지 마십시오.")


def build_user_static(questions, elicit=False):
    return render_survey(questions) + "\n\n" + render_output_spec(questions, elicit)


def build_messages(persona, demographics, questions=None, elicit=False):
    if questions is None:
        questions = LLM_QUESTIONS
    prov, risk = region_risk(persona.get("province", ""))
    sys = SYSTEM_TEMPLATE.format(persona=_persona_block(persona, demographics),
                                 prov=prov, risk=risk, events=EVENT_BRIEF_2024,
                                 latent=latent_block(persona, prov, risk))
    user = "아래 설문에 위 인물 본인으로서 응답해 JSON으로만 답하십시오.\n\n" + build_user_static(questions, elicit)
    return [
        {"role": "system", "content": sys},
        {"role": "user", "content": user},
    ]


if __name__ == "__main__":
    # 미리보기: 첫 페르소나 × PHASE1 문항으로 프롬프트 출력
    import os
    from survey_schema import PHASE1_QIDS
    path = os.path.join(os.path.dirname(__file__), "..", "output", "pilot_personas.jsonl")
    rec = json.loads(open(path, encoding="utf-8").readline())
    qs = get_llm_questions(PHASE1_QIDS)
    msgs = build_messages(rec["persona"], rec["demographics"], qs)
    print("=== SYSTEM ===\n" + msgs[0]["content"][:800] + "\n...(생략)")
    print("\n=== USER ===\n" + msgs[1]["content"])
    print(f"\n[USER 전체 길이 {len(msgs[1]['content'])}자, 문항수 {len(qs)}]")
