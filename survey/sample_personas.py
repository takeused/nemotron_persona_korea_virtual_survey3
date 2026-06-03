# Nemotron 페르소나를 「표 7.3 표본할당」(시도×성별×연령대 층화)에 따라 추출 + Q1~Q4 매핑
# 참조: survey_ref/대국민_표본추출.pdf (만 19~69세, 17개 시도, 제곱근+비례 배분, 층 내 랜덤)
import argparse, glob, json, os, random

DATA_GLOB = os.path.join(os.path.dirname(__file__), "..", "data", "data", "*.parquet")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

# Q3 학력 7값 → 3구간
EDU_MAP = {
    "무학": 1, "초등학교": 1, "중학교": 1, "고등학교": 1,
    "2~3년제 전문대학": 2, "4년제 대학교": 2,
    "대학원": 3,
}
# Q4 데이터 지역명 → 설문 코드(1~17)
PROVINCE_MAP = {
    "서울": 1, "부산": 2, "대구": 3, "인천": 4, "광주": 5, "대전": 6, "울산": 7, "세종": 8,
    "경기": 9, "강원": 10, "충청북": 11, "충청남": 12, "전북": 13, "전라남": 14,
    "경상북": 15, "경상남": 16, "제주": 17,
}
PROVINCE_LABEL = {1: "서울", 2: "부산", 3: "대구", 4: "인천", 5: "광주", 6: "대전", 7: "울산",
                  8: "세종", 9: "경기", 10: "강원", 11: "충북", 12: "충남", 13: "전북",
                  14: "전남", 15: "경북", 16: "경남", 17: "제주"}

# 연령대 그룹(0~4): 19-29 / 30-39 / 40-49 / 50-59 / 60-69. 그 외는 None(제외)
AGE_BANDS = [(19, 29), (30, 39), (40, 49), (50, 59), (60, 69)]
AGE_LABEL = {0: "19-29", 1: "30-39", 2: "40-49", 3: "50-59", 4: "60-69"}


def age_group(age):
    for i, (lo, hi) in enumerate(AGE_BANDS):
        if lo <= age <= hi:
            return i
    return None


# 표 7.3 표본할당 (합 1,000). (시도코드, 성별코드[1남2여]) → [19-29,30-39,40-49,50-59,60-69]
ALLOC_1000 = {
    (1, 1): [11, 13, 12, 13, 11], (1, 2): [12, 13, 12, 13, 12],   # 서울
    (2, 1): [5, 5, 6, 7, 7],      (2, 2): [5, 5, 6, 7, 8],        # 부산
    (3, 1): [4, 5, 5, 6, 6],      (3, 2): [4, 4, 5, 7, 6],        # 대구
    (4, 1): [5, 6, 7, 7, 6],      (4, 2): [5, 5, 6, 7, 6],        # 인천
    (5, 1): [4, 4, 5, 5, 4],      (5, 2): [4, 3, 5, 5, 4],        # 광주
    (6, 1): [5, 4, 4, 5, 4],      (6, 2): [4, 4, 4, 5, 5],        # 대전
    (7, 1): [4, 4, 4, 5, 5],      (7, 2): [3, 3, 4, 5, 4],        # 울산
    (8, 1): [3, 4, 5, 4, 2],      (8, 2): [2, 4, 5, 3, 2],        # 세종
    (9, 1): [14, 16, 18, 19, 16], (9, 2): [13, 15, 17, 19, 16],   # 경기
    (10, 1): [4, 4, 4, 5, 6],     (10, 2): [3, 3, 4, 5, 6],       # 강원
    (11, 1): [4, 4, 5, 6, 6],     (11, 2): [3, 3, 4, 5, 5],       # 충북
    (12, 1): [4, 5, 6, 6, 6],     (12, 2): [4, 4, 5, 5, 5],       # 충남
    (13, 1): [4, 3, 5, 6, 6],     (13, 2): [3, 3, 4, 6, 6],       # 전북
    (14, 1): [4, 3, 5, 6, 6],     (14, 2): [3, 3, 4, 6, 6],       # 전남
    (15, 1): [4, 4, 5, 7, 7],     (15, 2): [3, 4, 5, 7, 7],       # 경북
    (16, 1): [5, 5, 7, 8, 7],     (16, 2): [4, 4, 6, 7, 7],       # 경남
    (17, 1): [3, 3, 4, 5, 4],     (17, 2): [2, 3, 4, 4, 4],       # 제주
}

# 프롬프트에 넣을 페르소나 속성/텍스트 컬럼
PERSONA_COLS = [
    "uuid", "sex", "age", "marital_status", "military_status", "family_type",
    "housing_type", "education_level", "bachelors_field", "occupation", "district", "province",
    "persona", "professional_persona", "cultural_background",
    "hobbies_and_interests", "skills_and_expertise", "career_goals_and_ambitions",
]


def map_demographics(rec):
    """원본 인구통계 → 설문 Q1~Q4 코드."""
    q1 = 1 if rec["sex"] == "남자" else 2
    q3 = EDU_MAP.get(rec["education_level"])
    q4 = PROVINCE_MAP.get(rec["province"])
    return {"Q1": q1, "Q2": int(rec["age"]), "Q3": q3, "Q4": q4}


def build_allocation(num):
    """표 7.3(합1000)을 목표 num명으로 비례 확대(최대잔여법으로 정수 보정)."""
    factor = num / 1000.0
    raw = {(k, gi): ALLOC_1000[k][gi] * factor for k in ALLOC_1000 for gi in range(5)}
    floored = {c: int(v) for c, v in raw.items()}
    deficit = num - sum(floored.values())
    # 소수부 큰 셀부터 +1
    for c in sorted(raw, key=lambda c: raw[c] - floored[c], reverse=True)[:deficit]:
        floored[c] += 1
    return floored  # {((prov,sex), agegroup): target}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--num", type=int, default=2000, help="추출 인원 수")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("-o", "--out", default=os.path.join(OUT_DIR, "personas_sample.jsonl"))
    args = ap.parse_args()

    import pyarrow.parquet as pq

    files = sorted(glob.glob(DATA_GLOB))
    assert files, f"parquet 파일 없음: {DATA_GLOB}"
    rng = random.Random(args.seed)

    alloc = build_allocation(args.num)
    print(f"목표 {args.num}명 = 표 7.3 ×{args.num/1000:.2f} (170개 셀, seed={args.seed})")

    # ── Pass 1: 층(시도,성별,연령대)별 전역 인덱스 수집 ───────────────────────────
    strata = {}  # ((prov,sex), agegroup) → [global_idx,...]
    offset = 0
    for f in files:
        tbl = pq.read_table(f, columns=["province", "sex", "age"])
        prov = tbl.column("province").to_pylist()
        sex = tbl.column("sex").to_pylist()
        age = tbl.column("age").to_pylist()
        for i in range(len(prov)):
            pc = PROVINCE_MAP.get(prov[i])
            if pc is None:
                continue
            ag = age_group(age[i])
            if ag is None:
                continue
            sc = 1 if sex[i] == "남자" else 2
            strata.setdefault(((pc, sc), ag), []).append(offset + i)
        offset += len(prov)
    total_pool = sum(len(v) for v in strata.values())
    print(f"모집단 풀(19~69세, 17시도): {total_pool:,}명")

    # ── 층별 무작위 추출 ─────────────────────────────────────────────────────────
    picked = []  # global_idx 리스트
    short = []
    for cell, target in alloc.items():
        pool = strata.get(cell, [])
        if len(pool) < target:
            short.append((cell, len(pool), target))
            chosen = list(pool)  # 부족하면 가능한 만큼
        else:
            chosen = rng.sample(pool, target)
        picked.extend(chosen)
    if short:
        print(f"⚠ 풀 부족 셀 {len(short)}개:", short[:8])
    print(f"추출 인원: {len(picked)}명")

    # ── Pass 2: 전역 인덱스 → (파일, 파일내 인덱스) → 페르소나 추출 ───────────────
    counts = [pq.ParquetFile(f).metadata.num_rows for f in files]
    starts, acc = [], 0
    for c in counts:
        starts.append(acc); acc += c
    by_file = {}
    for gi in picked:
        fi = max(i for i, s in enumerate(starts) if s <= gi)
        by_file.setdefault(fi, []).append(gi - starts[fi])

    os.makedirs(OUT_DIR, exist_ok=True)
    n_written = 0
    with open(args.out, "w", encoding="utf-8") as out:
        for fi, local_idxs in by_file.items():
            tbl = pq.read_table(files[fi], columns=PERSONA_COLS)
            cols = {c: tbl.column(c).to_pylist() for c in PERSONA_COLS}
            for li in local_idxs:
                rec = {c: cols[c][li] for c in PERSONA_COLS}
                demo = map_demographics(rec)
                rec["age"] = int(rec["age"])
                stratum = {"province_code": demo["Q4"], "sex_code": demo["Q1"],
                           "age_group": age_group(rec["age"]), "age_band": AGE_LABEL[age_group(rec["age"])]}
                out.write(json.dumps({"persona": rec, "demographics": demo, "stratum": stratum},
                                     ensure_ascii=False) + "\n")
                n_written += 1
    print(f"저장 완료: {args.out}  ({n_written}명)")


if __name__ == "__main__":
    main()
