import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from dental_agent.agent import run_turn
from dental_agent.backends import Backend, GroqBackend, build_llm
from dental_agent.config import settings
from dental_agent.conversation import Conversation
from dental_agent.reliability import clean_json
from dental_agent.testing import make_memory_maker
from dental_agent.tracing import setup_tracing

THRESHOLD = 0.85  # task success gate
JUDGE_MIN = 0.80
JUDGE = (
    "You grade a dental clinic phone transcript. Decide the final outcome: booked (an appointment "
    "was booked or moved), cancelled, escalated (handed to a person) or refused (no action "
    "taken). Use only what the transcript shows was confirmed and completed. Reply with JSON: "
    '{"outcome": "...", "reason": "..."}'
)


class Verdict(BaseModel):
    outcome: str
    reason: str


def transcript(conv: Conversation) -> str:
    lines = []
    for m in conv.messages:
        c = m["content"]
        t = (
            c
            if isinstance(c, str)
            else " ".join(b["text"] for b in c if b.get("type") == "text")
        )
        if t:
            lines.append(f"{'Caller' if m['role'] == 'user' else 'Agent'}: {t}")
    return "\n".join(lines)


async def run_case(
    case: dict[str, Any], llm: Backend, use_judge: bool
) -> dict[str, Any]:
    maker = await make_memory_maker(
        days=5, per_day=16, preload=bool(case.get("preload"))
    )
    conv = Conversation()
    async with maker() as s:
        for turn in case["turns"]:
            await run_turn(conv, turn, s, llm, date(2030, 1, 6))
    tr = transcript(conv)
    judged, reason = None, ""
    if use_judge:
        try:
            r = await GroqBackend(settings.judge_model, max_tokens=3000).complete(
                JUDGE, [{"role": "user", "content": tr}], []
            )
            v = Verdict.model_validate_json(clean_json(r.text))
            judged, reason = v.outcome, v.reason
        except (
            TimeoutError,
            ConnectionError,
            ValueError,
            ValidationError,
        ) as e:  # a failed judge call must not hide the agent's result
            reason = f"judge error: {e!r}"
    return {
        "id": case["id"],
        "expected": case["expected"],
        "actual": conv.outcome(),
        "judge": judged,
        "reason": reason,
        "transcript": tr,
        "tokens": conv.tokens_used,
        "infra_error": "degraded"
        in conv.events,  # every model failed: not a quality signal
    }


async def main() -> int:
    smoke = "--smoke" in sys.argv
    use_judge = "--no-judge" not in sys.argv
    limit = (
        int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    )

    lines = Path("evals/golden.jsonl").read_text().splitlines()
    cases = [json.loads(x) for x in lines if x.startswith("{")]
    if smoke:
        cases = [c for c in cases if c.get("smoke")]
    if limit is not None:
        cases = cases[:limit]
    if not cases:
        print("No cases selected. Are the smoke cases tagged in evals/golden.jsonl?")
        return 1

    llm, sem = (
        build_llm(),
        asyncio.Semaphore(1),
    )  # one at a time: kind to free-tier limits

    async def one(c: dict[str, Any]) -> dict[str, Any]:
        async with sem:
            return await run_case(c, llm, use_judge)

    rows = await asyncio.gather(*(one(c) for c in cases))
    infra = [r for r in rows if r["infra_error"]]
    ok = [r for r in rows if not r["infra_error"]]
    success = sum(r["actual"] == r["expected"] for r in ok) / max(len(ok), 1)
    Path("evals/results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    )

    line = (
        f"cases={len(rows)} infra_errors={len(infra)} task_success={success:.0%} "
        f"tokens={sum(r['tokens'] for r in rows)}"
    )
    agree = 1.0
    if use_judge:
        judged = [r for r in ok if r["judge"] is not None]
        agree = sum(r["judge"] == r["expected"] for r in judged) / max(len(judged), 1)
        line += f" judge_agreement={agree:.0%}"
    print(line)
    for r in ok:
        if r["actual"] != r["expected"]:
            print("FAIL", r["id"], r["expected"], "->", r["actual"])

    if len(infra) > len(rows) * 0.2:
        print(
            "INCONCLUSIVE: too many provider errors (rate limit or outage). Rerun later."
        )
        return 2
    needed = limit if limit is not None else (8 if smoke else 40)
    enough = len(rows) >= needed
    passed = success >= THRESHOLD and (not use_judge or agree >= JUDGE_MIN)
    return 0 if enough and passed else 1


if __name__ == "__main__":
    setup_tracing()
    sys.exit(asyncio.run(main()))
