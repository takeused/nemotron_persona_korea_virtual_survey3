# 1·2차 통합 리포트: 동일 542명의 Q5~Q30 응답을 UUID로 병합 → 단일 HTML
import argparse, json, os, collections
from survey_schema import QUESTION_BY_ID, DISASTER_CATEGORY, RND_ITEMS
from sample_personas import PROVINCE_LABEL, AGE_LABEL
from pop_table import compute_weights
from parse_aggregate import (
    wpct, wmean, borda, esc,
    scale_table, opt_table, rank_table, demo_table, crosstab_mean,
    EDU_LABEL, SEX_LABEL,
)
from parse_aggregate_phase2 import (
    matrix_table, branch_table, cond_single_table, open_samples,
)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


def _best(path):
    """uuid별 성공응답 우선 채택."""
    best = {}
    for l in open(path, encoding="utf-8"):
        r = json.loads(l)
        u = r["uuid"]
        if u not in best or (best[u]["answers"] is None and r["answers"] is not None):
            best[u] = r
    return best


def load_merged(p1, p2, personas):
    pmap = {json.loads(l)["persona"]["uuid"]: json.loads(l)
            for l in open(personas, encoding="utf-8")}
    b1, b2 = _best(p1), _best(p2)
    recs = []
    for u, p in pmap.items():
        r1, r2 = b1.get(u), b2.get(u)
        if not r1 or r1["answers"] is None or not r2 or r2["answers"] is None:
            continue
        ans = dict(r1["answers"]); ans.update(r2["answers"])  # Q5~Q13 + Q14~Q30
        recs.append({"uuid": u, "demographics": r1["demographics"], "answers": ans,
                     "stratum": p["stratum"], "occupation": p["persona"]["occupation"],
                     "persona": p["persona"]})
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p1", default=os.path.join(OUT_DIR, "responses_phase1.jsonl"))
    ap.add_argument("--p2", default=os.path.join(OUT_DIR, "responses_phase2.jsonl"))
    ap.add_argument("--personas", default=os.path.join(OUT_DIR, "personas_phase2.jsonl"))
    ap.add_argument("--report", default=os.path.join(OUT_DIR, "report_all.html"))
    ap.add_argument("--engagement-weighted", action="store_true",
                    help="잠재 관여도 보정 가중치 적용(기본은 기존 가중치)")
    args = ap.parse_args()

    recs = load_merged(args.p1, args.p2, args.personas)
    n = len(recs)
    if args.engagement_weighted:
        from engagement import engagement_score
        from pop_table import compute_engagement_weights
        for r in recs:
            r["engagement_score"] = engagement_score(r["persona"], r["demographics"])
        weights = compute_engagement_weights(recs)
    else:
        weights = compute_weights(recs)
    print(f"통합 로드: {n}명 (Q5~Q30 병합 완료)")

    A = lambda qid: (lambda r: r["answers"][qid])
    Q = QUESTION_BY_ID

    # ── 인구통계 ──
    age_order = [AGE_LABEL[i] for i in sorted(AGE_LABEL)]
    demo = (demo_table("성별", recs, weights, lambda r: SEX_LABEL[r["demographics"]["Q1"]], order=list(SEX_LABEL.values()))
            + demo_table("연령대", recs, weights, lambda r: r["stratum"]["age_band"], order=age_order)
            + demo_table("학력", recs, weights, lambda r: EDU_LABEL[r["demographics"]["Q3"]], order=list(EDU_LABEL.values()))
            + demo_table("지역", recs, weights, lambda r: PROVINCE_LABEL[r["demographics"]["Q4"]])
            + demo_table("직업 (상위 10)", recs, weights, lambda r: r["occupation"],
                         order=[c for c, _ in collections.Counter(r["occupation"] for r in recs).most_common(10)]))

    # ── 1차: II. 재난 인식 ──
    q5 = scale_table("Q5. 재난안전 평소 관심도", wpct(recs, weights, A("Q5"), range(1, 6)),
                     wmean(recs, weights, A("Q5")), wmean(recs, [1]*n, A("Q5")), Q["Q5"]["scale"])
    q6 = scale_table("Q6. 재난안전 문제 심각성", wpct(recs, weights, A("Q6"), range(1, 6)),
                     wmean(recs, weights, A("Q6")), wmean(recs, [1]*n, A("Q6")), Q["Q6"]["scale"])
    q7 = opt_table("Q7. 2024년 가장 심각했던 재난", wpct(recs, weights, A("Q7"), range(1, 13)), Q["Q7"]["options"])
    q13 = opt_table("Q13. 위험성 인식에 가장 큰 영향", wpct(recs, weights, A("Q13"), range(1, 6)), Q["Q13"]["options"])
    q12sc, q12first = borda(recs, weights, "Q12", 2)
    q12opt = Q["Q12"]["options"]
    q12rows = "".join(f"<tr><td>{esc(q12opt[c])}</td><td class=n>{q12sc[c]:.0f}</td>"
                      f"<td class=n>{q12first.get(c,0):.1f}%</td></tr>"
                      for c in sorted(q12sc, key=lambda c: -q12sc[c]))
    q12 = (f"<h3>Q12. 재난 위험성 판단 기준</h3><table><tr><th>기준</th><th>가중 Borda</th>"
           f"<th>1순위 가중%</th></tr>{q12rows}</table>")
    ranks1 = ""
    for qid, k, title in [("Q8", 3, "Q8. 가장 위험한 자연재난"), ("Q9", 3, "Q9. 가장 위험한 사회재난"),
                          ("Q10", 3, "Q10. 가장 위험한 안전사고"), ("Q11", 3, "Q11. 전체 중 가장 위험한 재난")]:
        sc, fp = borda(recs, weights, qid, k)
        ranks1 += rank_table(title, sc, fp)

    # ── 2차: III. 과학기술 인식 ──
    q14 = scale_table("Q14. 재난안전 과학기술(R&D) 인지도", wpct(recs, weights, A("Q14"), range(1, 6)),
                      wmean(recs, weights, A("Q14")), wmean(recs, [1]*n, A("Q14")), Q["Q14"]["scale"])
    q16 = scale_table("Q16. 현 기술수준의 재난문제 해결 가능성", wpct(recs, weights, A("Q16"), range(1, 6)),
                      wmean(recs, weights, A("Q16")), wmean(recs, [1]*n, A("Q16")), Q["Q16"]["scale"])
    q20 = scale_table("Q20. 재난안전 기술/제품/서비스 실생활 활용도", wpct(recs, weights, A("Q20"), range(1, 6)),
                      wmean(recs, weights, A("Q20")), wmean(recs, [1]*n, A("Q20")), Q["Q20"]["scale"])
    q21scale = dict(Q["Q21"]["scale"]); q21scale[6] = "잘 모르겠다"
    q21 = scale_table("Q21. 재난안전 기술 보급 시 사용 의향", wpct(recs, weights, A("Q21"), range(1, 7)),
                      wmean(recs, weights, lambda r: r["answers"]["Q21"] if r["answers"]["Q21"] != 6 else None),
                      wmean(recs, [1]*n, lambda r: r["answers"]["Q21"] if r["answers"]["Q21"] != 6 else None), q21scale)
    q15sc, q15first = borda(recs, weights, "Q15", 2)
    q15opt = Q["Q15"]["options"]
    q15rows = "".join(f"<tr><td>{esc(q15opt[c])}</td><td class=n>{q15sc[c]:.0f}</td>"
                      f"<td class=n>{q15first.get(c,0):.1f}%</td></tr>"
                      for c in sorted(q15sc, key=lambda c: -q15sc[c]))
    q15 = (f"<h3>Q15. 재난안전 기술 정보 접근 경로</h3><table>"
           f"<tr><th>경로</th><th>가중 Borda</th><th>1순위 가중%</th></tr>{q15rows}</table>")
    mat = (matrix_table("Q17. R&D 중요성 (측면별)", recs, weights, "Q17", RND_ITEMS, Q["Q17"]["scale"])
           + matrix_table("Q18. R&D 효과성·기여도 (측면별)", recs, weights, "Q18", RND_ITEMS, Q["Q18"]["scale"])
           + matrix_table("Q19. R&D 투자확대 필요성 (측면별)", recs, weights, "Q19", RND_ITEMS, Q["Q19"]["scale"]))
    q22 = opt_table("Q22. 재난안전 기술 효과성 향상의 핵심 요소", wpct(recs, weights, A("Q22"), range(1, 6)), Q["Q22"]["options"])
    q27 = opt_table("Q27. 과학기술이 가장 크게 기여하는 재난관리 단계", wpct(recs, weights, A("Q27"), range(1, 6)), Q["Q27"]["options"])
    ranks2 = ""
    for qid, k, title in [("Q23", 3, "Q23. 과학기술 기여 — 자연재난"), ("Q24", 3, "Q24. 과학기술 기여 — 사회재난"),
                          ("Q25", 3, "Q25. 과학기술 기여 — 안전사고"), ("Q26", 3, "Q26. 과학기술 기여 — 전체 재난")]:
        sc, fp = borda(recs, weights, qid, k)
        ranks2 += rank_table(title, sc, fp)

    # ── 2차: IV. 지역 환경 ──
    q28 = scale_table("Q28. 거주지역의 재난 안전도", wpct(recs, weights, A("Q28"), range(1, 6)),
                      wmean(recs, weights, A("Q28")), wmean(recs, [1]*n, A("Q28")), Q["Q28"]["scale"])
    q29 = branch_table("Q29. 거주지역이 타 지역보다 안전한가", recs, weights, "Q29", Q["Q29"]["options"])
    q29_1 = cond_single_table("Q29-1. (안전) 가장 안전하다고 느끼는 재난분류", recs, weights, "Q29_1", "Q29", 1, DISASTER_CATEGORY)
    q29_2 = cond_single_table("Q29-2. (불안) 가장 위험하다고 느끼는 재난분류", recs, weights, "Q29_2", "Q29", 2, DISASTER_CATEGORY)
    q30 = open_samples("Q30. 우리 사회의 잠재적 위험요인 (자유응답)", recs, "Q30")

    # ── 교차분석(1·2차 혼합) ──
    cross = (crosstab_mean("Q6 심각성 — 연령대", recs, weights, A("Q6"), lambda r: r["stratum"]["age_group"], AGE_LABEL)
             + crosstab_mean("Q14 기술인지 — 연령대", recs, weights, A("Q14"), lambda r: r["stratum"]["age_group"], AGE_LABEL)
             + crosstab_mean("Q16 해결가능성 — 학력", recs, weights, A("Q16"), lambda r: r["demographics"]["Q3"], EDU_LABEL)
             + crosstab_mean("Q28 지역안전도 — 지역", recs, weights, A("Q28"), lambda r: r["stratum"]["province_code"], PROVINCE_LABEL))

    # ── 한계 박스 ──
    q6max = max(v[0] for v in wpct(recs, weights, A("Q6"), range(1, 6)).values())
    q17_imp = wmean(recs, weights, lambda r: sum(r["answers"]["Q17"]) / 3)
    q16m = wmean(recs, weights, A("Q16"))
    caveat = (f"<b>⚠ 해석 시 유의 — 합성 응답의 분산 한계</b><br>"
              f"본 결과는 LLM 합성 페르소나(zai-glm-4.7)의 1인칭 응답으로, <b>실제 인간 표본보다 응답 분산이 작은</b> 경향이 있습니다. "
              f"예: Q6 심각성은 단일 보기에 <b>{q6max:.0f}%</b> 집중, R&D 중요성(Q17)은 <b>{q17_imp:.2f}/5</b>로 쏠리는 반면 "
              f"현 기술 해결가능성(Q16)은 <b>{q16m:.2f}/5</b>로 신중합니다. "
              f"→ <b>전반적 경향·순위</b>는 참고 가능하나, <b>하위집단 간 미세 차이는 과대해석하지 않도록</b> 주의가 필요합니다.")

    style = ("body{font-family:'Malgun Gothic',sans-serif;max-width:1000px;margin:24px auto;color:#222;padding:0 16px}"
             "table{border-collapse:collapse;margin:8px 0 20px;width:100%}"
             "th,td{border:1px solid #ddd;padding:5px 9px;font-size:14px}th{background:#f3f4f6}"
             ".n{text-align:right;font-variant-numeric:tabular-nums}h2{border-bottom:2px solid #444;padding-top:12px}"
             "h1{border-bottom:3px solid #1a5}.mean{color:#1a5;margin:2px 0 6px}small{color:#888;font-weight:normal}"
             ".note{background:#fff8e1;padding:10px 14px;border-left:4px solid #fb0;font-size:13px}"
             ".warn{background:#fdecea;padding:10px 14px;border-left:4px solid #e53935;font-size:13px;margin:12px 0}"
             ".phase{background:#e8f0fe;padding:4px 12px;border-left:4px solid #1a73e8;font-weight:bold;margin:18px 0 4px}"
             "ul.open{font-size:13px;line-height:1.6;background:#f8f9fa;padding:10px 14px 10px 30px;border-radius:4px}")
    weight_note = ("사후층화 가중치 + 잠재 관여도 보정(옵트인) 적용" if args.engagement_weighted
                   else "사후층화 가중치(표 7.2 모집단) 적용")
    body = f"""<!doctype html><meta charset=utf-8><title>재난안전 인식조사 — 합성 페르소나 통합(Q1~Q30)</title>
<style>{style}</style>
<h1>재난안전 기술 대국민 인식조사 — 합성 페르소나 통합 결과 (Q1~Q30)</h1>
<div class=note>Nemotron-Personas-Korea 페르소나가 zai-glm-4.7로 1인칭 응답. 표본 {n}명(층화추출, 표 7.3 재현).
1차(Q5~Q13)·2차(Q14~Q30)를 동일 응답자로 병합. {weight_note}.
가중%=모집단 추정치, 비가중%=원표본.</div>
<div class=warn>{caveat}</div>
<h2>0. 표본 구성 (인구통계 Q1~Q4)</h2>{demo}
<div class=phase>━ 1차: 재난 인식 (II) ━</div>
<h2>II-1. 관심도·심각성</h2>{q5}{q6}
<h2>II-2. 2024 재난 인식·판단</h2>{q7}{q12}{q13}
<h2>II-3. 가장 위험한 재난유형 (가중 Borda)</h2>{ranks1}
<div class=phase>━ 2차: 과학기술 인식 (III) · 지역환경 (IV) ━</div>
<h2>III-1. 과학기술 인지·해결 가능성</h2>{q14}{q15}{q16}{q20}{q21}
<h2>III-2. R&D 중요성·효과성·투자필요성 (측면별)</h2>{mat}
<h2>III-3. 효과성 핵심요소·기여 단계</h2>{q22}{q27}
<h2>III-4. 과학기술 기여 재난유형 (가중 Borda)</h2>{ranks2}
<h2>IV. 지역별 재난안전 환경</h2>{q28}{q29}{q29_1}{q29_2}{q30}
<h2>교차분석 (1·2차 종합)</h2>{cross}
"""
    with open(args.report, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"통합 리포트 저장: {args.report}")


if __name__ == "__main__":
    main()
