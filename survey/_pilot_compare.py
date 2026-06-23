# 파일럿(개선) vs 기존 가상 vs 실제 — 대표 발산 문항 3-way 비교
import json, os, collections
from survey_schema import QUESTION_BY_ID, DISASTER_TYPES
from pop_table import compute_weights
from parse_aggregate_all import load_merged

OUT = os.path.join(os.path.dirname(__file__), "..", "output")

# 실제 조사값(PDF 제7장) — 1순위/평균 기준
REAL = {
    "Q6_mean": 4.0, "Q6_severe": 79.7,
    "Q7_top": ("제주항공 참사", 38.2), "Q7_dist": {7: 38.2, 2: 13.8, 10: 11.3, 9: 11.0, 8: 2.8},
    "Q9_top": ("감염병", 41.6),
    "Q12_top": ("인명피해", 62.9),
    "Q16_mean": 3.4, "Q16_solv": 47.4,
    "Q22_top": ("기술접근성·보급", 43.6),
    "Q27_top": ("예측·예방", 55.6),
    "Q29_yes": 72.5,
}

# 기존 가상값(앞서 계산)
ORIG = {
    "Q6_mean": 4.02, "Q6_severe": 99.6,
    "Q7_top": ("전기차화재", 51.9), "Q7_제주항공": 5.7,
    "Q9_top": ("화재", 73.4),
    "Q12_top": ("인명피해", 100.0),
    "Q16_mean": 3.03, "Q16_solv": 3.1,
    "Q22_top": ("기술접근성·보급", 86.9),
    "Q27_top": ("예측·예방", 99.4),
    "Q29_yes": 48.8,
}

# Q7 옵션 라벨(약식)
Q7L = {1: "태풍종다리", 2: "9월고온", 3: "부안지진", 4: "시청역", 5: "시흥교량",
       6: "아리셀화재", 7: "제주항공", 8: "청라전기차", 9: "울릉공항", 10: "평창LPG", 11: "기타", 12: "모름"}
Q12L = {1: "인명피해", 2: "재산피해", 3: "피해범위", 4: "정서적파장", 5: "지속성", 6: "회복가능"}
Q22L = {1: "연구개발", 2: "접근성보급", 3: "분야협력", 4: "법제도", 5: "기타"}
Q27L = {1: "예측예방", 2: "대비", 3: "대응", 4: "복구", 5: "기타"}


def load_pilot(path):
    recs = []
    for l in open(path, encoding="utf-8"):
        r = json.loads(l)
        if r.get("answers"):
            recs.append(r)
    return recs


def pct_single(recs, qid, lab=None):
    c = collections.Counter(r["answers"][qid] for r in recs if qid in r["answers"])
    tot = sum(c.values())
    out = {(lab[k] if lab else k): round(100*v/tot, 1) for k, v in c.most_common()}
    return out, tot


def pct_rank1(recs, qid, lab=None):
    c = collections.Counter(r["answers"][qid][0] for r in recs if qid in r["answers"])
    tot = sum(c.values())
    out = {(lab[k] if lab else DISASTER_TYPES.get(k, k)): round(100*v/tot, 1) for k, v in c.most_common()}
    return out, tot


def mean(recs, qid):
    vs = [r["answers"][qid] for r in recs if qid in r["answers"] and r["answers"][qid] != 6]
    return round(sum(vs)/len(vs), 2)


def entropy(dist):
    import math
    ps = [v/100 for v in dist.values() if v > 0]
    return round(-sum(p*math.log2(p) for p in ps), 2)


def main():
    pilot = load_pilot(os.path.join(OUT, "pilot_improved.jsonl"))
    print(f"파일럿 n={len(pilot)} (비가중 — 소표본 검증용)\n")

    print("=== Q7 2024 재난 (1위) — 최신사건 기억 ===")
    d, _ = pct_single(pilot, "Q7", Q7L)
    print(f"  실제 : 제주항공 38.2%")
    print(f"  기존 : 전기차화재 51.9% (제주항공 5.7%)")
    print(f"  파일럿: {list(d.items())[:4]}  | 제주항공={d.get('제주항공',0)}%")

    print("\n=== Q12 위험판단기준 (1위) — 분산 소멸 ===")
    d, _ = pct_rank1(pilot, "Q12", Q12L)
    print(f"  실제 : 인명피해 62.9% (엔트로피 높음)")
    print(f"  기존 : 인명피해 100% (엔트로피 0)")
    print(f"  파일럿: {list(d.items())[:4]}  | 엔트로피={entropy(d)}")

    print("\n=== Q27 기여단계 (1위) — 분산 소멸 ===")
    d, _ = pct_single(pilot, "Q27", Q27L)
    print(f"  실제 : 예측예방 55.6%")
    print(f"  기존 : 예측예방 99.4%")
    print(f"  파일럿: {list(d.items())[:4]}  | 엔트로피={entropy(d)}")

    print("\n=== Q9 사회재난 (1위) — 전형 쏠림 ===")
    d, _ = pct_rank1(pilot, "Q9")
    print(f"  실제 : 감염병 41.6%")
    print(f"  기존 : 화재 73.4%")
    print(f"  파일럿: {list(d.items())[:4]}")

    print("\n=== Q22 효과성요소 (1위) — 긍정/전형 쏠림 ===")
    d, _ = pct_single(pilot, "Q22", Q22L)
    print(f"  실제 : 접근성보급 43.6%")
    print(f"  기존 : 접근성보급 86.9%")
    print(f"  파일럿: {list(d.items())[:4]}  | 엔트로피={entropy(d)}")

    print("\n=== Q6 심각성 평균 / Q16 해결가능 평균 ===")
    print(f"  Q6  실제 4.0 / 기존 4.02 / 파일럿 {mean(pilot,'Q6')}  (심각4+5: 실제79.7 기존99.6)")
    print(f"  Q16 실제 3.4 / 기존 3.03 / 파일럿 {mean(pilot,'Q16')}")

    print("\n=== Q29 자기지역 안전(예%) — 낙관편향 ===")
    d, _ = pct_single(pilot, "Q29")
    yes = d.get(1, 0)
    print(f"  실제 72.5% / 기존 48.8% / 파일럿 {yes}%")


if __name__ == "__main__":
    main()
