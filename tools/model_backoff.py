import asyncio
import collections
import json
import statistics
import time

from openai import APIError

from dental_agent.backends import GroqBackend
from dental_agent.llm import build_system
from dental_agent.reliability import clean_json

MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
CASES = [
    ("Can I come in Thursday afternoon for a clean?", "book"),
    ("I'd like to move my appointment to next week", "reschedule"),
    ("Please cancel my booking", "cancel"),
    ("What time do you open on Saturday?", "hours"),
    ("Is the pharmacy next door open?", "unknown"),
    ("Do you have anything tomorrow morning?", "book"),
    ("کیا میں جمعرات کی دوپہر صفائی کے لیے آ سکتا ہوں؟", "book"),
    ("مجھے اپنی اپائنٹمنٹ منسوخ کرنی ہے", "cancel"),
    ("کلینک کب کھلتا ہے؟", "hours"),
    ("آج موسم کیسا ہے؟", "unknown"),
]


async def trial(model: str, text: str, want: str) -> tuple[bool, bool, float, str]:
    t0 = time.monotonic()
    try:
        r = await GroqBackend(model).complete(
            build_system(), [{"role": "user", "content": text}], []
        )
        data = json.loads(clean_json(r.text))
        return True, data.get("intent") == want, time.monotonic() - t0, ""
    except (APIError, TimeoutError, ValueError, AttributeError) as e:
        return False, False, time.monotonic() - t0, type(e).__name__


async def main() -> None:
    for m in MODELS:
        rs = [await trial(m, t, w) for t, w in CASES]
        errors = collections.Counter(r[3] for r in rs if r[3])
        print(
            f"{m}: valid_json={sum(r[0] for r in rs)}/{len(rs)} "
            f"right_intent={sum(r[1] for r in rs)}/{len(rs)} "
            f"median_s={statistics.median(r[2] for r in rs):.2f} errors={dict(errors)}"
        )


asyncio.run(main())
