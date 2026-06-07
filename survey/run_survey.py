# Cerebras API(OpenAI 호환)로 페르소나별 설문 응답을 병렬 수집. 체크포인트·재시도·JSON검증 포함
import argparse, json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed

# 사내/프록시 TLS 가로채기(self-signed CA) 환경 대응: OS 인증서 저장소 사용
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

from build_prompt import build_messages
from validate import validate_response
from survey_schema import get_llm_questions, PHASE1_QIDS, PHASE2_QIDS

CEREBRAS_BASE = "https://api.cerebras.ai/v1"
_write_lock = threading.Lock()


class RateLimiter:
    """전역 호출 간격 제한 — 재시도 포함 모든 요청을 min_interval초 간격으로 페이싱(RPM/TPM 한도 회피)."""
    def __init__(self, min_interval=0.0):
        self.min_interval = min_interval
        self.lock = threading.Lock()
        self.next_t = 0.0

    def wait(self):
        if self.min_interval <= 0:
            return
        with self.lock:
            now = time.time()
            t = max(now, self.next_t)
            self.next_t = t + self.min_interval
            delay = t - now
        if delay > 0:
            time.sleep(delay)


_limiter = RateLimiter(0.0)  # main에서 설정


def get_client():
    from openai import OpenAI
    key = os.environ.get("CEREBRAS_API_KEY")
    if not key:
        sys.exit("환경변수 CEREBRAS_API_KEY 가 설정되어 있지 않습니다.")
    return OpenAI(api_key=key, base_url=CEREBRAS_BASE)


def _extract_json(text):
    """모델 출력에서 JSON 객체 추출 (코드펜스/잡텍스트 제거)."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b != -1:
        s = s[a:b + 1]
    return json.loads(s)


def answer_one(client, model, rec, questions, max_retry=6, max_tokens=4000, reasoning_effort=None):
    """페르소나 1명에 대해 응답 수집. (uuid, demographics, answers, meta) 반환.
    GLM-4.7·gpt-oss는 추론모델 → reasoning은 별도 필드, content엔 최종 JSON. 토큰 넉넉히 필요."""
    msgs = build_messages(rec["persona"], rec["demographics"], questions)
    last_err = None
    for attempt in range(1, max_retry + 1):
        try:
            kwargs = dict(model=model, messages=msgs, temperature=0.7, max_tokens=max_tokens)
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort
            _limiter.wait()
            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
            if not content:  # 추론 토큰 초과로 최종응답 미생성
                raise RuntimeError("빈 content (추론 토큰 초과 추정)")
            ans = _extract_json(content)
            ok, errs = validate_response(ans, questions)
            if ok:
                return {"uuid": rec["persona"]["uuid"], "demographics": rec["demographics"],
                        "answers": ans, "model": model, "attempts": attempt}
            last_err = "; ".join(errs[:6])
            # 검증 실패 → 오류를 알려주고 재요청
            msgs = msgs + [{"role": "assistant", "content": content},
                           {"role": "user", "content": f"다음 항목이 잘못되었습니다: {last_err}. 모든 문항을 규칙에 맞게 다시 JSON으로만 답하십시오."}]
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            # 재시도는 다음 루프의 _limiter.wait()가 min_interval만큼 간격을 강제하므로
            # 별도 백오프는 거의 불필요(중복 누적 방지). 비-429 일시오류에만 짧은 지터 추가.
            is_429 = ("429" in str(e) or "too_many" in str(e) or "queue" in str(e))
            time.sleep(0.0 if is_429 else min(3.0, 1.0 * attempt))
    return {"uuid": rec["persona"]["uuid"], "demographics": rec["demographics"],
            "answers": None, "model": model, "error": last_err}


def load_done(path):
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if r.get("answers") is not None:
                        done.add(r["uuid"])
                except Exception:
                    pass
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="예: zai-glm-4.6, gpt-oss-120b")
    ap.add_argument("--personas", default="../output/personas_sample.jsonl")
    ap.add_argument("--out", required=True, help="응답 저장 jsonl (이어쓰기/체크포인트)")
    ap.add_argument("--limit", type=int, default=0, help="처리 개수 제한(0=전체)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--phase", default="phase1", choices=["phase1", "phase2", "all"], help="응답 대상 문항 범위")
    ap.add_argument("--max-tokens", type=int, default=4000, help="추론모델은 넉넉히 필요")
    ap.add_argument("--reasoning-effort", default=None, help="gpt-oss 전용: low/medium/high (GLM 미지원)")
    ap.add_argument("--min-interval", type=float, default=4.0,
                    help="전역 호출 간격(초). 4.0≈15RPM. Cerebras RPM/TPM 한도 회피용")
    ap.add_argument("--max-retry", type=int, default=6)
    args = ap.parse_args()

    global _limiter
    _limiter = RateLimiter(args.min_interval)
    print(f"호출 페이싱: {args.min_interval}s 간격(≈{60/args.min_interval:.0f} RPM 상한), max_retry={args.max_retry}")

    _phase_map = {"phase1": PHASE1_QIDS, "phase2": PHASE2_QIDS, "all": None}
    questions = get_llm_questions(_phase_map[args.phase])
    print(f"문항 범위: {args.phase} ({len(questions)}문항: {[q['id'] for q in questions]})")

    recs = [json.loads(l) for l in open(args.personas, encoding="utf-8")]
    if args.limit:
        recs = recs[:args.limit]
    done = load_done(args.out)
    todo = [r for r in recs if r["persona"]["uuid"] not in done]
    print(f"대상 {len(recs)}명 / 완료 {len(done)} / 처리예정 {len(todo)} (model={args.model}, workers={args.workers})")
    if not todo:
        print("이미 모두 완료됨."); return

    client = get_client()
    t0 = time.time()
    n_ok = n_fail = 0
    with open(args.out, "a", encoding="utf-8") as fout, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(answer_one, client, args.model, r, questions,
                          max_retry=args.max_retry, max_tokens=args.max_tokens,
                          reasoning_effort=args.reasoning_effort): r for r in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            res = fut.result()
            with _write_lock:
                fout.write(json.dumps(res, ensure_ascii=False) + "\n")
                fout.flush()
            if res["answers"] is not None:
                n_ok += 1
            else:
                n_fail += 1
            if i % 25 == 0 or i == len(todo):
                rate = i / (time.time() - t0)
                print(f"  {i}/{len(todo)}  성공 {n_ok} 실패 {n_fail}  ({rate:.1f}건/초)")
    print(f"완료: 성공 {n_ok}, 실패 {n_fail}, 소요 {time.time()-t0:.0f}s → {args.out}")


if __name__ == "__main__":
    main()
