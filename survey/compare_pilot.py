# 두 모델 파일럿 응답을 페르소나별로 나란히 비교 출력 (코드→라벨 변환)
import json, sys
from survey_schema import DISASTER_TYPES, QUESTION_BY_ID

SCALE5 = {1: "①", 2: "②", 3: "③", 4: "④", 5: "⑤"}


def load(path):
    return {json.loads(l)["uuid"]: json.loads(l) for l in open(path, encoding="utf-8")}


def dz(codes):  # 재난코드 리스트 → 이름
    return " > ".join(f"{c}.{DISASTER_TYPES.get(c, c)}" for c in codes)


def fmt(ans):
    if ans is None:
        return "  (실패)"
    q7 = QUESTION_BY_ID["Q7"]["options"].get(ans["Q7"], ans["Q7"])
    q12 = QUESTION_BY_ID["Q12"]["options"]
    q13 = QUESTION_BY_ID["Q13"]["options"].get(ans["Q13"], ans["Q13"])
    return "\n".join([
        f"    Q5관심={SCALE5.get(ans['Q5'])} Q6심각={SCALE5.get(ans['Q6'])}",
        f"    Q7가장심각재난(2024): {ans['Q7']}.{q7}",
        f"    Q8자연: {dz(ans['Q8'])}",
        f"    Q9사회: {dz(ans['Q9'])}",
        f"    Q10안전: {dz(ans['Q10'])}",
        f"    Q11전체: {dz(ans['Q11'])}",
        f"    Q12판단기준: {' > '.join(q12.get(c, str(c)) for c in ans['Q12'])}",
        f"    Q13영향: {ans['Q13']}.{q13}",
    ])


def main():
    a = load("output/pilot_glm.jsonl")
    b = load("output/pilot_gptoss.jsonl")
    persona = {json.loads(l)["persona"]["uuid"]: json.loads(l)
               for l in open("output/personas_sample.jsonl", encoding="utf-8")}
    for i, uuid in enumerate(a, 1):
        p = persona[uuid]["persona"]
        d = persona[uuid]["demographics"]
        st = persona[uuid]["stratum"]
        print(f"\n{'='*90}\n[{i}] {p['sex']} {p['age']}세 / {p['education_level']} / {p['province']} {p['district']} / {p['occupation']}")
        print(f"    {p['persona'][:95]}")
        print(f"  --- zai-glm-4.7 ---\n{fmt(a[uuid]['answers'])}")
        print(f"  --- gpt-oss-120b ---\n{fmt(b[uuid]['answers'])}")


if __name__ == "__main__":
    main()
