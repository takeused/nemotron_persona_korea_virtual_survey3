# v2 통합 파이프라인 검증: responses_validate_v2(Q5~Q30, 개선판) 가중집계 vs 실제 vs 기존
import json, os, collections, math
from survey_schema import QUESTION_BY_ID, DISASTER_TYPES, DISASTER_CATEGORY
from pop_table import compute_weights

OUT = os.path.join(os.path.dirname(__file__), "..", "output")
Q7L = {7: "제주항공", 6: "아리셀", 2: "9월고온", 10: "평창LPG", 9: "울릉공항", 8: "청라전기차"}
Q12L = {1: "인명피해", 2: "재산피해", 3: "피해범위", 4: "정서적", 5: "지속성", 6: "회복가능"}
Q22L = {1: "연구개발", 2: "접근성보급", 3: "분야협력", 4: "법제도", 5: "기타"}
Q27L = {1: "예측예방", 2: "대비", 3: "대응", 4: "복구", 5: "기타"}

REAL = {  # PDF 제7장 1순위/평균
    "Q6m": 4.0, "Q7": ("제주항공", 38.2), "Q9": ("감염병", 41.6), "Q11": ("감염병", 13.4),
    "Q12": ("인명피해", 62.9), "Q13": ("뉴스미디어", 64.8), "Q16m": 3.4, "Q22": ("접근성보급", 43.6),
    "Q27": ("예측예방", 55.6), "Q28m": 3.4, "Q29yes": 72.5, "Q29_1": ("풍수해", 23.6), "Q29_2": ("기상재난", 12.3),
}
ORIG = {  # 기존 가상(통합 report_all)
    "Q6m": 4.02, "Q7": ("전기차화재", 51.9), "Q9": ("화재", 73.4), "Q11": ("화재", 58.5),
    "Q12": ("인명피해", 100.0), "Q13": ("뉴스미디어", 96.8), "Q16m": 3.03, "Q22": ("접근성보급", 86.9),
    "Q27": ("예측예방", 99.4), "Q28m": 3.49, "Q29yes": 48.8, "Q29_1": ("해양재난", 61.2), "Q29_2": ("화재폭발", 34.2),
}


def load(path, personas):
    pmap = {json.loads(l)["persona"]["uuid"]: json.loads(l) for l in open(personas, encoding="utf-8")}
    best = {}
    for l in open(path, encoding="utf-8"):
        r = json.loads(l); u = r["uuid"]
        if u not in best or (best[u]["answers"] is None and r["answers"] is not None):
            best[u] = r
    recs = []
    for u, r in best.items():
        if r["answers"] is None:
            continue
        p = pmap[u]
        recs.append({"uuid": u, "demographics": r["demographics"], "answers": r["answers"],
                     "stratum": p["stratum"], "occupation": p["persona"]["occupation"]})
    return recs


def mean(recs, w, qid):
    num = den = 0
    for r, wt in zip(recs, w):
        v = r["answers"].get(qid)
        if v is not None and v != 6:
            num += wt*v; den += wt
    return round(num/den, 2) if den else None


def rank1(recs, w, qid, lab=None):
    d = collections.defaultdict(float)
    for r, wt in zip(recs, w):
        v = r["answers"].get(qid)
        if isinstance(v, list):
            d[v[0]] += wt
    tot = sum(d.values())
    return [( (lab.get(k, k) if lab else DISASTER_TYPES.get(k, k)), round(100*v/tot, 1)) for k, v in sorted(d.items(), key=lambda x:-x[1])[:4]]


def single(recs, w, qid, lab):
    d = collections.defaultdict(float)
    for r, wt in zip(recs, w):
        v = r["answers"].get(qid)
        if v is not None:
            d[v] += wt
    tot = sum(d.values())
    return [(lab.get(k, k), round(100*v/tot, 1)) for k, v in sorted(d.items(), key=lambda x:-x[1])[:4]]


def cond(recs, w, qid, dep, val, lab):
    d = collections.defaultdict(float)
    for r, wt in zip(recs, w):
        if r["answers"].get(dep) == val and r["answers"].get(qid):
            d[r["answers"][qid]] += wt
    tot = sum(d.values())
    if not tot:
        return []
    return [(lab.get(k, k), round(100*v/tot, 1)) for k, v in sorted(d.items(), key=lambda x:-x[1])[:4]]


def ent(pairs):
    ps = [v/100 for _, v in pairs if v > 0]
    return round(-sum(p*math.log2(p) for p in ps), 2)


def row(name, real, orig, v2):
    print(f"  {name:18} 실제 {real:<16} | 기존 {orig:<16} | v2개선 {v2}")


def main():
    recs = load(os.path.join(OUT, "responses_validate_v2.jsonl"), os.path.join(OUT, "personas_phase2.jsonl"))
    w = compute_weights(recs)
    print(f"검증표본 n={len(recs)} (개선 파이프라인 --elicit, 사후가중)\n")

    row("Q6 심각 평균", REAL["Q6m"], ORIG["Q6m"], mean(recs, w, "Q6"))
    print(f"  Q7 2024재난 1위: 실제 제주항공38.2 | 기존 전기차51.9 | v2 {single(recs,w,'Q7',Q7L)}")
    print(f"  Q9 사회재난 1위: 실제 감염병41.6 | 기존 화재73.4 | v2 {rank1(recs,w,'Q9')}")
    print(f"  Q11 전체 1위:   실제 감염병13.4 | 기존 화재58.5 | v2 {rank1(recs,w,'Q11')}")
    q12 = rank1(recs, w, "Q12", Q12L)
    print(f"  Q12 판단기준1위: 실제 인명62.9 | 기존 인명100 | v2 {q12} 엔트로피={ent(q12)}")
    print(f"  Q13 영향 1위:   실제 뉴스64.8 | 기존 뉴스96.8 | v2 {single(recs,w,'Q13',{1:'개인경험',2:'뉴스미디어',3:'정부발표',4:'논문',5:'기타'})}")
    row("Q16 해결 평균", REAL["Q16m"], ORIG["Q16m"], mean(recs, w, "Q16"))
    q22 = single(recs, w, "Q22", Q22L)
    print(f"  Q22 효과성요소: 실제 접근성43.6 | 기존 접근성86.9 | v2 {q22} 엔트로피={ent(q22)}")
    q27 = single(recs, w, "Q27", Q27L)
    print(f"  Q27 기여단계:   실제 예방55.6 | 기존 예방99.4 | v2 {q27} 엔트로피={ent(q27)}")
    row("Q28 안전 평균", REAL["Q28m"], ORIG["Q28m"], mean(recs, w, "Q28"))
    # Q29 — ★애착 프라이어 타겟
    d = collections.defaultdict(float)
    for r, wt in zip(recs, w):
        if r["answers"].get("Q29") in (1, 2):
            d[r["answers"]["Q29"]] += wt
    yes = round(100*d[1]/(d[1]+d[2]), 1) if (d[1]+d[2]) else 0
    print(f"  ★Q29 자기지역안전 예%: 실제 72.5 | 기존 48.8 | v2 {yes}  (애착 프라이어 타겟)")
    print(f"  Q29-1 안전유형: 실제 풍수해23.6 | 기존 해양61.2 | v2 {cond(recs,w,'Q29_1','Q29',1,DISASTER_CATEGORY)}")
    print(f"  Q29-2 위험유형: 실제 기상12.3 | 기존 화재폭발34.2 | v2 {cond(recs,w,'Q29_2','Q29',2,DISASTER_CATEGORY)}")


if __name__ == "__main__":
    main()
