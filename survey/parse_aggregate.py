# Phase1 응답(Q1~Q13) 파싱 → tidy CSV + 사후가중 집계 + HTML 리포트 생성
import argparse, json, os, collections, html
from survey_schema import QUESTION_BY_ID, DISASTER_TYPES
from sample_personas import PROVINCE_LABEL, AGE_LABEL
from pop_table import compute_weights

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
EDU_LABEL = {1: "고졸 이하", 2: "대학교 졸업", 3: "대학원 졸업"}
SEX_LABEL = {1: "남성", 2: "여성"}


def load(responses, personas):
    pmap = {}
    for l in open(personas, encoding="utf-8"):
        r = json.loads(l)
        pmap[r["persona"]["uuid"]] = r
    # resume로 같은 uuid가 여러 줄일 수 있음 → uuid별로 성공 응답 우선 채택(중복제거)
    best = {}
    for l in open(responses, encoding="utf-8"):
        r = json.loads(l)
        u = r["uuid"]
        if u not in best or (best[u]["answers"] is None and r["answers"] is not None):
            best[u] = r
    recs = []
    n_fail = 0
    for u, r in best.items():
        if r["answers"] is None:
            n_fail += 1
            continue
        p = pmap[u]
        recs.append({"uuid": u, "demographics": r["demographics"],
                     "answers": r["answers"], "stratum": p["stratum"],
                     "occupation": p["persona"]["occupation"]})
    return recs, len(best), n_fail


def wpct(recs, weights, getval, options):
    """가중 % 분포: options 각 값에 대한 (가중%, 비가중%)."""
    tw = sum(weights)
    wsum = collections.defaultdict(float)
    csum = collections.Counter()
    for r, w in zip(recs, weights):
        v = getval(r)
        wsum[v] += w
        csum[v] += 1
    return {o: (100 * wsum.get(o, 0) / tw, 100 * csum.get(o, 0) / len(recs)) for o in options}


def wmean(recs, weights, getval):
    tw = sum(w for r, w in zip(recs, weights) if getval(r) is not None)
    s = sum(w * getval(r) for r, w in zip(recs, weights) if getval(r) is not None)
    return s / tw if tw else float("nan")


def borda(recs, weights, qid, k):
    """순위형: 1순위 k점 … 가중 합산 → 코드별 점수."""
    score = collections.defaultdict(float)
    first = collections.defaultdict(float)
    tw = sum(weights)
    for r, w in zip(recs, weights):
        lst = r["answers"][qid]
        for rank, code in enumerate(lst):
            score[code] += w * (k - rank)
        first[lst[0]] += w
    return score, {c: 100 * v / tw for c, v in first.items()}


# ── HTML 빌더 ────────────────────────────────────────────────────────────────
def esc(s):
    return html.escape(str(s))


def scale_table(title, dist, mean_w, mean_u, labels):
    rows = "".join(
        f"<tr><td>{esc(labels[o])}</td><td class=n>{dist[o][0]:.1f}%</td><td class=n>{dist[o][1]:.1f}%</td></tr>"
        for o in sorted(dist))
    return (f"<h3>{esc(title)}</h3><p class=mean>가중평균 <b>{mean_w:.2f}</b> / 5 "
            f"(비가중 {mean_u:.2f})</p><table><tr><th>응답</th><th>가중%</th><th>비가중%</th></tr>{rows}</table>")


def opt_table(title, dist, options):
    rows = "".join(
        f"<tr><td>{esc(options[o])}</td><td class=n>{dist[o][0]:.1f}%</td><td class=n>{dist[o][1]:.1f}%</td></tr>"
        for o in sorted(dist, key=lambda o: -dist[o][0]))
    return f"<h3>{esc(title)}</h3><table><tr><th>보기</th><th>가중%</th><th>비가중%</th></tr>{rows}</table>"


def rank_table(title, score, firstpct, topn=10):
    top = sorted(score, key=lambda c: -score[c])[:topn]
    rows = "".join(
        f"<tr><td>{c}.{esc(DISASTER_TYPES.get(c, c))}</td><td class=n>{score[c]:.0f}</td>"
        f"<td class=n>{firstpct.get(c, 0):.1f}%</td></tr>" for c in top)
    return (f"<h3>{esc(title)}</h3><table><tr><th>유형</th><th>가중 Borda점수</th>"
            f"<th>1순위 가중%</th></tr>{rows}</table>")


def crosstab_mean(title, recs, weights, getval, group_key, label_map):
    groups = collections.defaultdict(lambda: ([], []))
    for r, w in zip(recs, weights):
        g = group_key(r)
        groups[g][0].append(r)
        groups[g][1].append(w)
    rows = ""
    for g in sorted(groups):
        gr, gw = groups[g]
        m = wmean(gr, gw, getval)
        rows += f"<tr><td>{esc(label_map.get(g, g))}</td><td class=n>{m:.2f}</td><td class=n>{len(gr)}</td></tr>"
    return f"<h3>{esc(title)}</h3><table><tr><th>구분</th><th>가중평균</th><th>n</th></tr>{rows}</table>"


def demo_table(title, recs, weights, getval, label_map=None, order=None):
    """인구통계 분포: 구분별 (가중%, 비가중%, n). order로 정렬 고정 가능."""
    tw = sum(weights)
    wsum = collections.defaultdict(float)
    csum = collections.Counter()
    for r, w in zip(recs, weights):
        v = getval(r)
        wsum[v] += w
        csum[v] += 1
    keys = order if order else sorted(wsum, key=lambda k: -wsum[k])
    rows = ""
    for k in keys:
        lab = label_map.get(k, k) if label_map else k
        rows += (f"<tr><td>{esc(lab)}</td><td class=n>{100*wsum[k]/tw:.1f}%</td>"
                 f"<td class=n>{100*csum[k]/len(recs):.1f}%</td><td class=n>{csum[k]}</td></tr>")
    return (f"<h3>{esc(title)}</h3><table><tr><th>구분</th><th>가중%</th>"
            f"<th>비가중%</th><th>n</th></tr>{rows}</table>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--responses", default=os.path.join(OUT_DIR, "responses_phase1.jsonl"))
    ap.add_argument("--personas", default=os.path.join(OUT_DIR, "personas_sample.jsonl"))
    ap.add_argument("--csv", default=os.path.join(OUT_DIR, "responses_phase1.csv"))
    ap.add_argument("--report", default=os.path.join(OUT_DIR, "report_phase1.html"))
    args = ap.parse_args()

    recs, n_total, n_fail = load(args.responses, args.personas)
    n = len(recs)
    weights = compute_weights(recs)
    print(f"로드: 총 {n_total}건, 성공 {n}, 실패 {n_fail} (성공률 {100*n/n_total:.1f}%)")

    # ── tidy CSV ──
    import csv as csvmod
    with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csvmod.writer(f)
        cols = (["uuid", "weight", "sex", "age", "edu", "region", "age_band", "occupation"]
                + [f"Q{i}" for i in range(5, 14)])
        w.writerow(cols)
        for r, wt in zip(recs, weights):
            d, a, s = r["demographics"], r["answers"], r["stratum"]
            def cell(qid):
                v = a[qid]
                return ">".join(map(str, v)) if isinstance(v, list) else v
            w.writerow([r["uuid"], f"{wt:.4f}", SEX_LABEL[d["Q1"]], d["Q2"], EDU_LABEL[d["Q3"]],
                        PROVINCE_LABEL[d["Q4"]], s["age_band"], r["occupation"]]
                       + [cell(f"Q{i}") for i in range(5, 14)])
    print(f"CSV 저장: {args.csv}")

    # ── 집계 ──
    A = lambda qid: (lambda r: r["answers"][qid])
    q5 = scale_table("Q5. 재난안전 평소 관심도", wpct(recs, weights, A("Q5"), range(1, 6)),
                     wmean(recs, weights, A("Q5")), wmean(recs, [1]*n, A("Q5")),
                     QUESTION_BY_ID["Q5"]["scale"])
    q6 = scale_table("Q6. 재난안전 문제 심각성", wpct(recs, weights, A("Q6"), range(1, 6)),
                     wmean(recs, weights, A("Q6")), wmean(recs, [1]*n, A("Q6")),
                     QUESTION_BY_ID["Q6"]["scale"])
    q7 = opt_table("Q7. 2024년 가장 심각했던 재난", wpct(recs, weights, A("Q7"), range(1, 13)),
                   QUESTION_BY_ID["Q7"]["options"])
    q13 = opt_table("Q13. 위험성 인식에 가장 큰 영향", wpct(recs, weights, A("Q13"), range(1, 6)),
                    QUESTION_BY_ID["Q13"]["options"])
    q12sc, q12first = borda(recs, weights, "Q12", 2)
    q12opt = QUESTION_BY_ID["Q12"]["options"]
    q12rows = "".join(f"<tr><td>{esc(q12opt[c])}</td><td class=n>{q12sc[c]:.0f}</td>"
                      f"<td class=n>{q12first.get(c,0):.1f}%</td></tr>"
                      for c in sorted(q12sc, key=lambda c: -q12sc[c]))
    q12 = (f"<h3>Q12. 재난 위험성 판단 기준</h3><table><tr><th>기준</th><th>가중 Borda</th>"
           f"<th>1순위 가중%</th></tr>{q12rows}</table>")

    ranks = ""
    for qid, k, title in [("Q8", 3, "Q8. 가장 위험한 자연재난"), ("Q9", 3, "Q9. 가장 위험한 사회재난"),
                          ("Q10", 3, "Q10. 가장 위험한 안전사고"), ("Q11", 3, "Q11. 전체 중 가장 위험한 재난")]:
        sc, fp = borda(recs, weights, qid, k)
        ranks += rank_table(title, sc, fp)

    cross = (crosstab_mean("Q6 심각성 — 성별", recs, weights, A("Q6"), lambda r: r["stratum"]["sex_code"], SEX_LABEL)
             + crosstab_mean("Q6 심각성 — 연령대", recs, weights, A("Q6"), lambda r: r["stratum"]["age_group"], AGE_LABEL)
             + crosstab_mean("Q6 심각성 — 지역", recs, weights, A("Q6"), lambda r: r["stratum"]["province_code"], PROVINCE_LABEL)
             + crosstab_mean("Q5 관심도 — 연령대", recs, weights, A("Q5"), lambda r: r["stratum"]["age_group"], AGE_LABEL))

    # ── 인구통계(Q1~Q4) 표본 구성 분포 ──
    age_order = [AGE_LABEL[i] for i in sorted(AGE_LABEL)]
    demo = (demo_table("Q1. 성별", recs, weights, lambda r: SEX_LABEL[r["demographics"]["Q1"]], order=list(SEX_LABEL.values()))
            + demo_table("Q2. 연령대", recs, weights, lambda r: r["stratum"]["age_band"], order=age_order)
            + demo_table("Q3. 학력", recs, weights, lambda r: EDU_LABEL[r["demographics"]["Q3"]], order=list(EDU_LABEL.values()))
            + demo_table("Q4. 지역", recs, weights, lambda r: PROVINCE_LABEL[r["demographics"]["Q4"]])
            + demo_table("직업 (상위 10)", recs, weights, lambda r: r["occupation"],
                         order=[c for c, _ in collections.Counter(r["occupation"] for r in recs).most_common(10)]))

    # ── 한계 박스용 데이터 기반 지표 ──
    q6dist = wpct(recs, weights, A("Q6"), range(1, 6))
    q6max = max(v[0] for v in q6dist.values())              # Q6 단일 보기 최대 가중%
    q12max = max(q12first.values()) if q12first else 0.0    # Q12 1순위 최대 쏠림%
    reg_means = [wmean([r for r in recs if r["stratum"]["province_code"] == pc],
                       [w for r, w in zip(recs, weights) if r["stratum"]["province_code"] == pc], A("Q6"))
                 for pc in set(r["stratum"]["province_code"] for r in recs)]
    q6range = max(reg_means) - min(reg_means)               # Q6 지역별 가중평균 범위(점)
    caveat = (f"<b>⚠ 해석 시 유의 — 합성 응답의 분산 한계</b><br>"
              f"본 결과는 LLM 합성 페르소나(zai-glm-4.7)의 1인칭 응답으로, <b>실제 인간 표본보다 응답 분산이 작은</b> 경향이 있습니다. "
              f"관측 예: Q6 심각성은 단일 보기에 <b>{q6max:.0f}%</b>가 집중, Q12 위험성 판단기준은 1순위가 <b>{q12max:.0f}%</b> 한 항목에 쏠렸습니다. "
              f"교차분석의 집단 간 가중평균 차이도 매우 작습니다(예: Q6 지역별 범위 <b>{q6range:.2f}점</b>). "
              f"→ <b>평균·순위 등 전반적 경향</b>은 참고 가능하나, <b>하위집단 간 미세한 수치 차이는 통계적으로 과대해석하지 않도록</b> 주의가 필요합니다.")

    style = ("body{font-family:'Malgun Gothic',sans-serif;max-width:1000px;margin:24px auto;color:#222;padding:0 16px}"
             "table{border-collapse:collapse;margin:8px 0 20px;width:100%}"
             "th,td{border:1px solid #ddd;padding:5px 9px;font-size:14px}th{background:#f3f4f6}"
             ".n{text-align:right;font-variant-numeric:tabular-nums}h2{border-bottom:2px solid #444;padding-top:12px}"
             ".mean{color:#1a5;margin:2px 0 6px}.note{background:#fff8e1;padding:10px 14px;border-left:4px solid #fb0;font-size:13px}"
             ".warn{background:#fdecea;padding:10px 14px;border-left:4px solid #e53935;font-size:13px;margin:12px 0}")
    body = f"""<!doctype html><meta charset=utf-8><title>재난안전 인식조사 — 합성 페르소나 1차(Q1~Q13)</title>
<style>{style}</style>
<h1>재난안전 기술 대국민 인식조사 — 합성 페르소나 결과 (1차: Q1~Q13)</h1>
<div class=note>Nemotron-Personas-Korea 페르소나가 zai-glm-4.7로 1인칭 응답. 표본 {n}명(층화추출, 표 7.3 재현).
사후층화 가중치(표 7.2 모집단) 적용. 성공률 {100*n/n_total:.1f}% (실패 {n_fail}).
가중%=모집단 추정치, 비가중%=원표본.</div>
<div class=warn>{caveat}</div>
<h2>II-0. 표본 구성 (인구통계 Q1~Q4)</h2>{demo}
<h2>II-1. 관심도·심각성</h2>{q5}{q6}
<h2>II-2. 2024 재난 인식 · 판단</h2>{q7}{q12}{q13}
<h2>II-3. 가장 위험한 재난유형 (가중 Borda: 1순위3·2순위2·3순위1점)</h2>{ranks}
<h2>II-4. 인구통계 교차분석</h2>{cross}
"""
    with open(args.report, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"리포트 저장: {args.report}")


if __name__ == "__main__":
    main()
