# LLM이 반환한 설문 응답 JSON을 스키마에 맞게 검증·정규화 (run/parse 공용)
from survey_schema import LLM_QUESTIONS, QUESTION_BY_ID, NATURAL, SOCIAL, SAFETY


def _is_int_in(v, lo, hi):
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def _check_rank(v, candidates, k):
    if not isinstance(v, list) or len(v) != k:
        return False
    cand = set(candidates)
    return all(_is_int_in(x, min(candidates), max(candidates)) and x in cand for x in v) and len(set(v)) == k


def validate_response(ans, questions=None):
    """ans: dict, questions: 검증할 문항 리스트(None이면 전체).
    반환: (ok: bool, errors: list[str]). 누락/범위이탈 문항을 수집."""
    errors = []
    for q in (questions if questions is not None else LLM_QUESTIONS):
        qid = q["id"]
        t = q["type"]
        # 분기 종속 문항: 조건 불충족 시 None 허용
        if "depends_on" in q:
            dep_id, dep_val = q["depends_on"]
            if ans.get(dep_id) != dep_val:
                continue  # 해당 분기 아님 → 검사 생략
        if qid not in ans or ans[qid] is None:
            errors.append(f"{qid} 누락")
            continue
        v = ans[qid]
        if t == "scale5":
            if not _is_int_in(v, 1, 5):
                errors.append(f"{qid} 척도범위(1~5) 위반: {v}")
        elif t == "scale5_dk":
            if not _is_int_in(v, 1, 6):
                errors.append(f"{qid} 척도범위(1~6) 위반: {v}")
        elif t == "single":
            if not _is_int_in(v, 1, max(q["options"])):
                errors.append(f"{qid} 보기범위 위반: {v}")
        elif t == "branch":
            if v not in (1, 2):
                errors.append(f"{qid} 분기값(1/2) 위반: {v}")
        elif t == "rank":
            cands = q.get("candidates") or list(q["options"])
            if not _check_rank(v, cands, q["k"]):
                errors.append(f"{qid} 순위형(서로 다른 {q['k']}개, 범위) 위반: {v}")
        elif t == "matrix5":
            if not (isinstance(v, list) and len(v) == len(q["items"]) and all(_is_int_in(x, 1, 5) for x in v)):
                errors.append(f"{qid} 매트릭스(길이{len(q['items'])}, 1~5) 위반: {v}")
        elif t == "open":
            if not (isinstance(v, str) and v.strip()):
                errors.append(f"{qid} 주관식 비어있음")
    return (len(errors) == 0, errors)
