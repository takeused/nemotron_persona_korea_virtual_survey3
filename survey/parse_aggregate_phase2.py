# Phase2 응답(Q14~Q30) 파싱 → tidy CSV + 사후가중 집계 + HTML 리포트 생성
# 공용 헬퍼는 parse_aggregate에서 재사용, matrix5/branch/open 전용 빌더만 신설
import argparse, json, os, collections
from survey_schema import QUESTION_BY_ID, DISASTER_TYPES, DISASTER_CATEGORY, RND_ITEMS
from sample_personas import PROVINCE_LABEL, AGE_LABEL
from pop_table import compute_weights
from parse_aggregate import (
    load, wpct, wmean, borda, esc,
    scale_table, opt_table, rank_table, demo_table, crosstab_mean,
    EDU_LABEL, SEX_LABEL,
)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


def matrix_table(title, recs, weights, qid, items, scale):
    """matrix5: 항목별 (가중평균, 비가중평균) + 1~5 가중% 분포."""
    n = len(recs)
    head = ("<tr><th>항목</th><th>가중평균</th><th>비가중평균</th>"
            + "".join(f"<th>{esc(scale[s])}<br>(가중%)</th>" for s in range(1, 6)) + "</tr>")
    rows = ""
    for idx, item in enumerate(items):
        gv = lambda r, i=idx: r["answers"][qid][i]
        mw = wmean(recs, weights, gv)
        mu = wmean(recs, [1] * n, gv)
        dist = wpct(recs, weights, gv, range(1, 6))
        cells = "".join(f"<td class=n>{dist[s][0]:.1f}%</td>" for s in range(1, 6))
        rows += (f"<tr><td>{esc(item)}</td><td class=n><b>{mw:.2f}</b></td>"
                 f"<td class=n>{mu:.2f}</td>{cells}</tr>")
    return f"<h3>{esc(title)}</h3><table>{head}{rows}</table>"


def branch_table(title, recs, weights, qid, options):
    """branch(1/2): 예/아니오 가중·비가중 분포."""
    dist = wpct(recs, weights, lambda r: r["answers"][qid], [1, 2])
    rows = "".join(
        f"<tr><td>{esc(options[o])}</td><td class=n>{dist[o][0]:.1f}%</td>"
        f"<td class=n>{dist[o][1]:.1f}%</td></tr>" for o in (1, 2))
    return f"<h3>{esc(title)}</h3><table><tr><th>응답</th><th>가중%</th><th>비가중%</th></tr>{rows}</table>"


def cond_single_table(title, recs, weights, qid, dep_id, dep_val, options):
    """분기 종속 단답(Q29_1/Q29_2): 해당 분기 응답자만 모아 가중% 분포."""
    sub = [(r, w) for r, w in zip(recs, weights)
           if r["answers"].get(dep_id) == dep_val and r["answers"].get(qid) is not None]
    if not sub:
        return f"<h3>{esc(title)}</h3><p class=mean>해당 분기 응답 없음</p>"
    sr = [r for r, _ in sub]
    sw = [w for _, w in sub]
    dist = wpct(sr, sw, lambda r: r["answers"][qid], list(options))
    rows = "".join(
        f"<tr><td>{o}.{esc(options[o])}</td><td class=n>{dist[o][0]:.1f}%</td>"
        f"<td class=n>{dist[o][1]:.1f}%</td></tr>"
        for o in sorted(dist, key=lambda o: -dist[o][0]) if dist[o][1] > 0)
    return (f"<h3>{esc(title)} <small>(n={len(sr)})</small></h3>"
            f"<table><tr><th>분류</th><th>가중%</th><th>비가중%</th></tr>{rows}</table>")


def open_samples(title, recs, qid, k=20):
    """open(Q30): 대표 자유응답 표본 + 키워드 빈도 상위."""
    import re
    texts = [r["answers"][qid].strip() for r in recs if isinstance(r["answers"].get(qid), str)]
    # 키워드 빈도(2글자 이상 한글 명사 근사 — 공백/조사 단순 토큰화)
    cnt = collections.Counter()
    for t in texts:
        for tok in re.findall(r"[가-힣]{2,}", t):
            cnt[tok] += 1
    stop = {"있다", "있는", "있습니다", "생각", "생각합니다", "생각해", "생각이", "위험", "재난", "사회", "우리", "대한",
            "때문", "위한", "수도", "있어", "있을", "있고", "있으며", "같은", "같습니다", "같다", "통해", "경우",
            "발생", "관리", "문제", "요인", "인한", "인해", "또한", "그리고", "하지만", "요즘", "너무", "특히",
            "매우", "더욱", "점점", "많은", "많이", "다양한", "여러", "이런", "그런", "저런", "정도", "관련",
            "현재", "최근", "앞으로", "계속", "점차", "대비", "필요", "필요하다", "필요한", "중요", "중요하다",
            "안전", "예방", "대응", "가장", "가능성", "어려운", "심각", "심각한", "수많은", "지금", "이러한"}
    kw = [(w, c) for w, c in cnt.most_common(80) if w not in stop][:20]
    kwrow = " · ".join(f"{w}({c})" for w, c in kw)
    import random
    random.seed(42)
    sample = random.sample(texts, min(k, len(texts)))
    items = "".join(f"<li>{esc(t)}</li>" for t in sample)
    return (f"<h3>{esc(title)} <small>(응답 {len(texts)}건)</small></h3>"
            f"<p class=mean>빈출 키워드: {esc(kwrow)}</p>"
            f"<ul class=open>{items}</ul>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--responses", default=os.path.join(OUT_DIR, "responses_phase2.jsonl"))
    ap.add_argument("--personas", default=os.path.join(OUT_DIR, "personas_phase2.jsonl"))
    ap.add_argument("--csv", default=os.path.join(OUT_DIR, "responses_phase2.csv"))
    ap.add_argument("--report", default=os.path.join(OUT_DIR, "report_phase2.html"))
    args = ap.parse_args()

    recs, n_total, n_fail = load(args.responses, args.personas)
    n = len(recs)
    weights = compute_weights(recs)
    print(f"로드: 총 {n_total}건, 성공 {n}, 실패 {n_fail} (성공률 {100*n/n_total:.1f}%)")

    # ── tidy CSV ──
    import csv as csvmod
    phase2_qids = ["Q14", "Q15", "Q16", "Q17", "Q18", "Q19", "Q20", "Q21", "Q22",
                   "Q23", "Q24", "Q25", "Q26", "Q27", "Q28", "Q29", "Q29_1", "Q29_2", "Q30"]
    with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csvmod.writer(f)
        w.writerow(["uuid", "weight", "sex", "age", "edu", "region", "age_band", "occupation"] + phase2_qids)
        for r, wt in zip(recs, weights):
            d, a, s = r["demographics"], r["answers"], r["stratum"]
            def cell(qid):
                v = a.get(qid)
                if v is None:
                    return ""
                return ">".join(map(str, v)) if isinstance(v, list) else v
            w.writerow([r["uuid"], f"{wt:.4f}", SEX_LABEL[d["Q1"]], d["Q2"], EDU_LABEL[d["Q3"]],
                        PROVINCE_LABEL[d["Q4"]], s["age_band"], r["occupation"]]
                       + [cell(q) for q in phase2_qids])
    print(f"CSV 저장: {args.csv}")

    A = lambda qid: (lambda r: r["answers"][qid])
    Q = QUESTION_BY_ID

    # III-1. 과학기술 인식·해결 가능성
    q14 = scale_table("Q14. 재난안전 과학기술(R&D) 인지도", wpct(recs, weights, A("Q14"), range(1, 6)),
                      wmean(recs, weights, A("Q14")), wmean(recs, [1]*n, A("Q14")), Q["Q14"]["scale"])
    q16 = scale_table("Q16. 현 기술수준의 재난문제 해결 가능성", wpct(recs, weights, A("Q16"), range(1, 6)),
                      wmean(recs, weights, A("Q16")), wmean(recs, [1]*n, A("Q16")), Q["Q16"]["scale"])
    q20 = scale_table("Q20. 재난안전 기술/제품/서비스 실생활 활용도", wpct(recs, weights, A("Q20"), range(1, 6)),
                      wmean(recs, weights, A("Q20")), wmean(recs, [1]*n, A("Q20")), Q["Q20"]["scale"])
    # Q21: scale5_dk (6=잘모름)
    q21scale = dict(Q["Q21"]["scale"]); q21scale[6] = "잘 모르겠다"
    q21 = scale_table("Q21. 재난안전 기술 보급 시 사용 의향", wpct(recs, weights, A("Q21"), range(1, 7)),
                      wmean(recs, weights, lambda r: r["answers"]["Q21"] if r["answers"]["Q21"] != 6 else None),
                      wmean(recs, [1]*n, lambda r: r["answers"]["Q21"] if r["answers"]["Q21"] != 6 else None), q21scale)

    # Q15: 정보 접근 경로 (rank k=2)
    q15sc, q15first = borda(recs, weights, "Q15", 2)
    q15opt = Q["Q15"]["options"]
    q15rows = "".join(f"<tr><td>{esc(q15opt[c])}</td><td class=n>{q15sc[c]:.0f}</td>"
                      f"<td class=n>{q15first.get(c,0):.1f}%</td></tr>"
                      for c in sorted(q15sc, key=lambda c: -q15sc[c]))
    q15 = (f"<h3>Q15. 재난안전 기술/제품/서비스 정보 접근 경로</h3><table>"
           f"<tr><th>경로</th><th>가중 Borda</th><th>1순위 가중%</th></tr>{q15rows}</table>")

    # III-2. R&D 중요성·효과성·투자필요성 (matrix5 ×3, 항목 = RND_ITEMS)
    mat = (matrix_table("Q17. R&D 중요성 (측면별)", recs, weights, "Q17", RND_ITEMS, Q["Q17"]["scale"])
           + matrix_table("Q18. R&D 효과성·기여도 (측면별)", recs, weights, "Q18", RND_ITEMS, Q["Q18"]["scale"])
           + matrix_table("Q19. R&D 투자확대 필요성 (측면별)", recs, weights, "Q19", RND_ITEMS, Q["Q19"]["scale"]))

    # III-3. 효과성 요소·기여 단계 (single)
    q22 = opt_table("Q22. 재난안전 기술 효과성 향상의 핵심 요소", wpct(recs, weights, A("Q22"), range(1, 6)),
                    Q["Q22"]["options"])
    q27 = opt_table("Q27. 과학기술이 가장 크게 기여하는 재난관리 단계",
                    wpct(recs, weights, A("Q27"), range(1, 6)), Q["Q27"]["options"])

    # III-4. 과학기술 기여 재난유형 (rank Q23~Q26)
    ranks = ""
    for qid, k, title in [("Q23", 3, "Q23. 과학기술 기여 — 자연재난"),
                          ("Q24", 3, "Q24. 과학기술 기여 — 사회재난"),
                          ("Q25", 3, "Q25. 과학기술 기여 — 안전사고"),
                          ("Q26", 3, "Q26. 과학기술 기여 — 전체 재난")]:
        sc, fp = borda(recs, weights, qid, k)
        ranks += rank_table(title, sc, fp)

    # IV. 지역별 재난안전 환경
    q28 = scale_table("Q28. 거주지역의 재난 안전도", wpct(recs, weights, A("Q28"), range(1, 6)),
                      wmean(recs, weights, A("Q28")), wmean(recs, [1]*n, A("Q28")), Q["Q28"]["scale"])
    q29 = branch_table("Q29. 거주지역이 타 지역보다 안전한가", recs, weights, "Q29", Q["Q29"]["options"])
    q29_1 = cond_single_table("Q29-1. (안전) 가장 안전하다고 느끼는 재난분류", recs, weights,
                              "Q29_1", "Q29", 1, DISASTER_CATEGORY)
    q29_2 = cond_single_table("Q29-2. (불안) 가장 위험하다고 느끼는 재난분류", recs, weights,
                              "Q29_2", "Q29", 2, DISASTER_CATEGORY)
    q30 = open_samples("Q30. 우리 사회의 잠재적 위험요인 (자유응답)", recs, "Q30")

    # 교차분석
    cross = (crosstab_mean("Q14 기술인지 — 연령대", recs, weights, A("Q14"), lambda r: r["stratum"]["age_group"], AGE_LABEL)
             + crosstab_mean("Q16 해결가능성 — 학력", recs, weights, A("Q16"), lambda r: r["demographics"]["Q3"], EDU_LABEL)
             + crosstab_mean("Q28 지역안전도 — 지역", recs, weights, A("Q28"), lambda r: r["stratum"]["province_code"], PROVINCE_LABEL))

    # 인구통계(표본 구성)
    age_order = [AGE_LABEL[i] for i in sorted(AGE_LABEL)]
    demo = (demo_table("성별", recs, weights, lambda r: SEX_LABEL[r["demographics"]["Q1"]], order=list(SEX_LABEL.values()))
            + demo_table("연령대", recs, weights, lambda r: r["stratum"]["age_band"], order=age_order)
            + demo_table("학력", recs, weights, lambda r: EDU_LABEL[r["demographics"]["Q3"]], order=list(EDU_LABEL.values()))
            + demo_table("지역", recs, weights, lambda r: PROVINCE_LABEL[r["demographics"]["Q4"]]))

    # 한계 박스 — 데이터 기반
    q17_imp = wmean(recs, weights, lambda r: sum(r["answers"]["Q17"]) / 3)
    q19_need = wmean(recs, weights, lambda r: sum(r["answers"]["Q19"]) / 3)
    q16m = wmean(recs, weights, A("Q16"))
    q21dk = wpct(recs, weights, A("Q21"), range(1, 7))[6][0]
    caveat = (f"<b>⚠ 해석 시 유의 — 합성 응답의 분산 한계</b><br>"
              f"본 결과는 LLM 합성 페르소나(zai-glm-4.7)의 1인칭 응답으로, <b>실제 인간 표본보다 응답 분산이 작은</b> 경향이 있습니다. "
              f"R&D 중요성·필요성 문항(Q17·Q19)은 가중평균이 각각 <b>{q17_imp:.2f}·{q19_need:.2f}/5</b>로 매우 높게 쏠리는 반면, "
              f"현 기술수준의 해결 가능성(Q16)은 <b>{q16m:.2f}/5</b>로 상대적으로 신중합니다. "
              f"Q21 사용의향의 '잘 모르겠다'는 <b>{q21dk:.1f}%</b>에 그칩니다. "
              f"→ <b>전반적 경향·순위</b>는 참고 가능하나, <b>하위집단 간 미세 차이는 과대해석하지 않도록</b> 주의가 필요합니다.")

    style = ("body{font-family:'Malgun Gothic',sans-serif;max-width:1000px;margin:24px auto;color:#222;padding:0 16px}"
             "table{border-collapse:collapse;margin:8px 0 20px;width:100%}"
             "th,td{border:1px solid #ddd;padding:5px 9px;font-size:14px}th{background:#f3f4f6}"
             ".n{text-align:right;font-variant-numeric:tabular-nums}h2{border-bottom:2px solid #444;padding-top:12px}"
             ".mean{color:#1a5;margin:2px 0 6px}small{color:#888;font-weight:normal}"
             ".note{background:#fff8e1;padding:10px 14px;border-left:4px solid #fb0;font-size:13px}"
             ".warn{background:#fdecea;padding:10px 14px;border-left:4px solid #e53935;font-size:13px;margin:12px 0}"
             "ul.open{font-size:13px;line-height:1.6;background:#f8f9fa;padding:10px 14px 10px 30px;border-radius:4px}")
    body = f"""<!doctype html><meta charset=utf-8><title>재난안전 인식조사 — 합성 페르소나 2차(Q14~Q30)</title>
<style>{style}</style>
<h1>재난안전 기술 대국민 인식조사 — 합성 페르소나 결과 (2차: Q14~Q30)</h1>
<div class=note>Nemotron-Personas-Korea 페르소나가 zai-glm-4.7로 1인칭 응답. 표본 {n}명(1차와 동일 응답자, 층화추출).
사후층화 가중치(표 7.2 모집단) 적용. 성공률 {100*n/n_total:.1f}% (실패 {n_fail}).
가중%=모집단 추정치, 비가중%=원표본.</div>
<div class=warn>{caveat}</div>
<h2>0. 표본 구성</h2>{demo}
<h2>III-1. 재난안전 과학기술 인지·해결 가능성</h2>{q14}{q15}{q16}{q20}{q21}
<h2>III-2. R&D 중요성·효과성·투자필요성 (3개 측면별)</h2>{mat}
<h2>III-3. 효과성 핵심요소 · 기여 단계</h2>{q22}{q27}
<h2>III-4. 과학기술 기여 재난유형 (가중 Borda: 1순위3·2순위2·3순위1점)</h2>{ranks}
<h2>IV. 지역별 재난안전 환경</h2>{q28}{q29}{q29_1}{q29_2}{q30}
<h2>교차분석</h2>{cross}
"""
    with open(args.report, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"리포트 저장: {args.report}")


if __name__ == "__main__":
    main()
