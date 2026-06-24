# v2 파일럿(A+B+C) vs 실제 vs 기존가상 vs v1파일럿 비교 + D(학력 재가중) 적용
import json, os, collections, math

OUT = os.path.join(os.path.dirname(__file__), "..", "output")
Q7L = {1:"태풍종다리",2:"9월고온",3:"부안지진",4:"시청역",5:"시흥교량",6:"아리셀",7:"제주항공",8:"청라전기차",9:"울릉공항",10:"평창LPG",11:"기타",12:"모름"}
Q12L = {1:"인명피해",2:"재산피해",3:"피해범위",4:"정서적",5:"지속성",6:"회복가능"}
Q22L = {1:"연구개발",2:"접근성보급",3:"분야협력",4:"법제도",5:"기타"}
Q27L = {1:"예측예방",2:"대비",3:"대응",4:"복구",5:"기타"}

# 실제 패널 학력분포(가중후): 고졸11.3 / 대졸71.9 / 대학원16.8
REAL_EDU = {1: 0.113, 2: 0.719, 3: 0.168}


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if json.loads(l).get("answers")]


def edu_weights(recs):
    """D: 페르소나 학력분포를 실제 패널에 맞춤(사후층화). w = target / observed."""
    obs = collections.Counter(r["demographics"]["Q3"] for r in recs)
    n = len(recs)
    return [REAL_EDU.get(r["demographics"]["Q3"], 0) / (obs[r["demographics"]["Q3"]]/n) for r in recs]


def dist(recs, qid, weights=None, lab=None, rank1=False):
    weights = weights or [1]*len(recs)
    d = collections.defaultdict(float)
    for r, w in zip(recs, weights):
        v = r["answers"].get(qid)
        if v is None:
            continue
        if rank1 and isinstance(v, list):
            v = v[0]
        d[v] += w
    tot = sum(d.values())
    out = {(lab[k] if lab else k): round(100*v/tot, 1) for k, v in sorted(d.items(), key=lambda x:-x[1])}
    return out


def mean(recs, qid, weights=None):
    weights = weights or [1]*len(recs)
    num = den = 0
    for r, w in zip(recs, weights):
        v = r["answers"].get(qid)
        if v is not None and v != 6:
            num += w*v; den += w
    return round(num/den, 2) if den else None


def ent(d):
    ps = [v/100 for v in d.values() if v > 0]
    return round(-sum(p*math.log2(p) for p in ps), 2)


def top(d, k=4):
    return list(d.items())[:k]


def main():
    v2 = load(os.path.join(OUT, "pilot_improved2.jsonl"))
    w = edu_weights(v2)
    print(f"v2 파일럿 n={len(v2)}  (A:확률추출+B:성향+C:백스토리, D:학력재가중 병기)\n")

    print("=== Q7 제주항공% (최신사건) ===  실제 38.2 / 기존 5.7 / v1 100")
    d0 = dist(v2, "Q7", lab=Q7L); dW = dist(v2, "Q7", w, Q7L)
    print(f"  v2: {top(d0)}  제주항공={d0.get('제주항공',0)}")
    print(f"  v2+D(학력보정): 제주항공={dW.get('제주항공',0)}")

    print("\n=== Q12 인명피해% 1순위 (분산소멸) ===  실제 62.9 / 기존 100 / v1 100")
    d0 = dist(v2, "Q12", lab=Q12L)
    print(f"  v2: {top(d0)}  | 엔트로피={ent(d0)}  (실제는 분산 큼)")

    print("\n=== Q27 예측예방% (분산소멸) ===  실제 55.6 / 기존 99.4 / v1 100")
    d0 = dist(v2, "Q27", lab=Q27L)
    print(f"  v2: {top(d0)}  | 엔트로피={ent(d0)}")

    print("\n=== Q22 효과성요소 (긍정/전형쏠림) ===  실제 접근성43.6 / 기존 86.9 / v1 법제도60")
    d0 = dist(v2, "Q22", lab=Q22L)
    print(f"  v2: {top(d0)}  | 엔트로피={ent(d0)}")

    print("\n=== Q9 사회재난1순위 (대조군: A미적용, B+C만) ===  실제 감염병41.6 / 기존 화재73.4")
    from survey_schema import DISASTER_TYPES
    d0 = dist(v2, "Q9", lab=DISASTER_TYPES)
    print(f"  v2: {top(d0)}")

    print("\n=== Q6 심각성 / Q16 해결가능 평균 ===")
    print(f"  Q6  실제4.0 기존4.02 v1(temp1.0)4.57 → v2 {mean(v2,'Q6')} / +D {mean(v2,'Q6',w)}")
    print(f"  Q16 실제3.4 기존3.03 v1 3.03 → v2 {mean(v2,'Q16')} / +D {mean(v2,'Q16',w)}")

    print("\n=== Q29 자기지역안전 예% (낙관편향) ===  실제 72.5 / 기존 48.8 / v1 46.7")
    d0 = dist(v2, "Q29"); dW = dist(v2, "Q29", w)
    print(f"  v2: 예={d0.get(1,0)} / +D 예={dW.get(1,0)}")


if __name__ == "__main__":
    main()
