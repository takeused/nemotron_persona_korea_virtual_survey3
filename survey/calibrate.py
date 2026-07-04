# 계획 #4: 문항별 선택적 준지도 보정 (train/test 분할, JS divergence 측정)
# 목적: 일괄 프롬프트/온도 교정 대신, 실제조사 완전분포를 앵커로 한 "로그오즈 시프트" 보정을
#       일부 문항(train)에서 학습해 다른 문항(test, 앵커 미사용)에 일반화되는지 검증.
#       순환논리 차단: test 문항의 실제분포는 평가에만 쓰고 보정계수 학습에는 쓰지 않는다.
import json, math, os, collections, random

OUT = os.path.join(os.path.dirname(__file__), "..", "output")

# ── 실제조사 완전분포(1~5) — survey_ref/대국민조사리포트.pdf 표 7.6/7.7/7.24/7.25/7.16/7.36/7.53에서 추출 ──
# {문항: {1..5: 가중%}}. 전체(n=1,023) 기준.
REAL_DIST = {
    "Q5":  {1: 0.6, 2: 3.0, 3: 15.6, 4: 48.3, 5: 32.5},   # 관심도
    "Q6":  {1: 0.4, 2: 2.4, 3: 17.4, 4: 56.3, 5: 23.5},   # 심각성
    "Q14": {1: 8.7, 2: 30.9, 3: 39.6, 4: 16.9, 5: 3.9},   # R&D 인지도(가중, 표7.24)
    "Q16": {1: 0.8, 2: 9.8, 3: 10.5, 4: 45.3, 5: 2.0, 6: 31.6},  # 해결가능(단, 표7.25 4=해결가능45.3% 근사; 실측표는 5구간뿐이라 6=미사용)
    "Q20": {1: 1.2, 2: 13.7, 3: 14.9, 4: 49.6, 5: 4.5, 6: 16.1}, # 실생활 활용도(단 표7.35 원자료 근사)
    "Q21": {1: 0.1, 2: 1.1, 3: 1.2, 4: 8.0, 5: 48.5, 6: 39.2},   # 사용의향(6=매우그렇다39.2, 표7.36 근사배치)
    "Q28": {1: 1.2, 2: 9.7, 3: 10.9, 4: 44.0, 5: 39.7, 6: 5.3},  # 거주지 안전(표7.53 근사)
}
# ※ 위 수치 중 Q16/Q20/Q21/Q28은 PDF 원문 5구간 라벨 순서가 척도별로 상이해 재정렬 오차 가능 — 보정계수 산출용 근사치로만 사용.
# 신뢰도 높은 앵커(정확 대조 완료, 5점 척도 표준형): Q5, Q6, Q14.

# scale5 문항(1~5)만 사용해 방법론을 검증(가장 깔끔한 앵커)
CLEAN_SCALE_Q = ["Q5", "Q6", "Q14"]


def _best(path):
    best = {}
    for l in open(path, encoding="utf-8"):
        r = json.loads(l); u = r["uuid"]
        if u not in best or (best[u]["answers"] is None and r["answers"] is not None):
            best[u] = r
    return best


def load_synth_dist(paths, qid):
    """여러 test60 파일에서 qid 응답을 모아 1~5 비가중 분포(%) 산출."""
    cnt = collections.Counter()
    for p in paths:
        fp = os.path.join(OUT, p)
        if not os.path.exists(fp):
            continue
        for u, r in _best(fp).items():
            if r["answers"] and qid in r["answers"]:
                v = r["answers"][qid]
                if isinstance(v, int) and 1 <= v <= 5:
                    cnt[v] += 1
    tot = sum(cnt.values())
    if tot == 0:
        return None, 0
    return {k: 100 * cnt.get(k, 0) / tot for k in range(1, 6)}, tot


def js_divergence(p, q, keys=range(1, 6)):
    """Jensen-Shannon divergence (bits). p,q: {key: pct(0~100)}."""
    def norm(d):
        tot = sum(d.get(k, 0) for k in keys) or 1
        return {k: d.get(k, 0) / tot for k in keys}
    P, Q = norm(p), norm(q)
    M = {k: (P[k] + Q[k]) / 2 for k in keys}

    def kl(a, b):
        s = 0.0
        for k in keys:
            if a[k] > 0 and b[k] > 0:
                s += a[k] * math.log2(a[k] / b[k])
        return s
    return 0.5 * kl(P, M) + 0.5 * kl(Q, M)


def fit_logodds_shift(real, synth, keys=range(1, 6)):
    """1차원 순서형 로그오즈 시프트 계수 c를 그리드서치로 적합.
    보정: logit'(k) = logit(synth,k) + c*(k-3)  (동일 c를 모든 학습문항에 공유 → 일반화 가능한 단일 파라미터)."""
    def apply_shift(dist, c):
        raw = {}
        tot_s = sum(dist.get(k, 1e-6) for k in keys)
        for k in keys:
            p = max(dist.get(k, 1e-6) / tot_s, 1e-6)
            logit = math.log(p / (1 - p)) if p < 1 else 10
            raw[k] = logit + c * (k - 3)
        # softmax 재정규화
        m = max(raw.values())
        ex = {k: math.exp(raw[k] - m) for k in keys}
        s = sum(ex.values())
        return {k: 100 * ex[k] / s for k in keys}

    best_c, best_js = 0.0, js_divergence(real, synth, keys)
    for c in [x / 100 for x in range(-100, 101, 2)]:
        cand = apply_shift(synth, c)
        d = js_divergence(real, cand, keys)
        if d < best_js:
            best_js, best_c = d, c
    return best_c, apply_shift(synth, best_c), best_js


def main():
    paths = ["responses_test60_p1_v2.jsonl", "responses_test60_p1_v3.jsonl",
             "responses_test60_p1_v4.jsonl", "responses_test60_p1_v5.jsonl",
             "responses_test60_p2_v2.jsonl", "responses_test60_p2_v3.jsonl",
             "responses_test60_p2_v4.jsonl", "responses_test60_p2_v5.jsonl"]

    print("=" * 70)
    print("계획 #4: 문항별 선택적 준지도 보정 — Leave-One-Out 교차검증")
    print("=" * 70)
    synth_dists = {}
    for q in CLEAN_SCALE_Q:
        d, n = load_synth_dist(paths, q)
        synth_dists[q] = (d, n)
        print(f"\n{q}: 가상표본 n={n}, 분포={({k: round(v,1) for k,v in d.items()} if d else None)}")

    print("\n" + "-" * 70)
    print("Leave-One-Out: 각 문항을 test로 남기고 나머지로 c를 학습 → test에 적용(순환논리 차단)")
    print("-" * 70)

    results = []
    for test_q in CLEAN_SCALE_Q:
        train_qs = [q for q in CLEAN_SCALE_Q if q != test_q]
        # train 문항들에서 각각 최적 c를 구해 평균(공유 파라미터로 일반화)
        cs = []
        for tq in train_qs:
            sd, n = synth_dists[tq]
            if not sd or n == 0:
                continue
            c, _, _ = fit_logodds_shift(REAL_DIST[tq], sd)
            cs.append(c)
        if not cs:
            continue
        shared_c = sum(cs) / len(cs)

        # test 문항에 학습된 c(test 데이터 미사용)를 적용해 보정 전/후 JS 비교
        sd, n = synth_dists[test_q]
        if not sd or n == 0:
            continue
        js_before = js_divergence(REAL_DIST[test_q], sd)

        def apply_shift(dist, c, keys=range(1, 6)):
            raw = {}
            tot_s = sum(dist.get(k, 1e-6) for k in keys)
            for k in keys:
                p = max(dist.get(k, 1e-6) / tot_s, 1e-6)
                logit = math.log(p / (1 - p)) if p < 1 else 10
                raw[k] = logit + c * (k - 3)
            m = max(raw.values())
            ex = {k: math.exp(raw[k] - m) for k in keys}
            s = sum(ex.values())
            return {k: 100 * ex[k] / s for k in keys}

        calibrated = apply_shift(sd, shared_c)
        js_after = js_divergence(REAL_DIST[test_q], calibrated)

        print(f"\n[TEST={test_q}] (학습에 미사용) train_c 평균={shared_c:+.2f} (from {train_qs})")
        print(f"  실제:   {({k: round(v,1) for k,v in REAL_DIST[test_q].items()})}")
        print(f"  가상(전): {({k: round(v,1) for k,v in sd.items()})}  JS={js_before:.4f}")
        print(f"  보정(후): {({k: round(v,1) for k,v in calibrated.items()})}  JS={js_after:.4f}")
        improved = js_after < js_before
        print(f"  → {'✅개선' if improved else '❌악화'} (ΔJS={js_before-js_after:+.4f})")
        results.append((test_q, js_before, js_after, improved))

    print("\n" + "=" * 70)
    print("종합 (Leave-One-Out 일반화 성능)")
    print("=" * 70)
    n_improved = sum(1 for _, _, _, imp in results if imp)
    for q, b, a, imp in results:
        print(f"  {q}: JS {b:.4f} → {a:.4f}  {'✅' if imp else '❌'}")
    print(f"\n개선된 held-out 문항: {n_improved}/{len(results)}")
    if n_improved == len(results):
        print("→ 공유 로그오즈 시프트 계수가 held-out 문항에도 일반화됨. 순환논리 없이 보정 유효성 확인.")
    else:
        print("→ 일부만 일반화됨. 문항별 개별 특성이 강해 단일계수 공유는 제한적 — 더 세밀한 앵커/모델 필요.")


if __name__ == "__main__":
    main()
