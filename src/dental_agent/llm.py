import asyncio
import random
from datetime import date, timedelta

from openai import (
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from pydantic import ValidationError

from dental_agent.config import settings
from dental_agent.schemas import BookingIntent

BACKOFF_BASE = 0.3


SYSTEM = """You extract requests from callers of a dental clinic.
Reply with one JSON object and nothing else: no markdown, no explanation.

Keys:
- intent: "book", "reschedule", "cancel", "hours" or "unknown"
- day: the date the caller means as an ISO date (YYYY-MM-DD), or null
- daypart: "morning", "afternoon", "evening" or null
- service: short lowercase string such as "clean", "check-up", "filling", or null
- confidence: number from 0 to 1

Calendar. Use it to resolve days. Do not calculate dates yourself:
__CALENDAR__

Rules:
- Wanting to come in, make or ask for an appointment is "book".
- Moving an existing appointment is "reschedule". Calling one off is "cancel".
- Asking when the clinic is open is "hours".
- Use "unknown" only when the sentence has nothing to do with the clinic.
  Never give confidence 0 to a clinic-related sentence.
- A weekday name means its next occurrence in the calendar. If the caller names
  today's weekday, use today's date unless they say "next".
- "today" and "tomorrow" come straight from the calendar.
- If a time is given, set daypart: before 12:00 morning, 12:00 to 16:59 afternoon,
  17:00 or later evening.
- If the caller did not say something, use null. Never guess.

Examples:
Caller: Can I come in for a clean on December 1st in the morning?
{"intent": "book", "day": "2026-12-01", "daypart": "morning", "service": "clean", "confidence": 0.95}
Caller: What time do you close on Saturdays?
{"intent": "hours", "day": null, "daypart": null, "service": null, "confidence": 0.9}
Caller: I need to cancel my appointment.
{"intent": "cancel", "day": null, "daypart": null, "service": null, "confidence": 0.9}
Caller: What's the weather like?
{"intent": "unknown", "day": null, "daypart": null, "service": null, "confidence": 0.9}"""


def build_system(today: date | None = None) -> str:
    today = today or date.today()
    days = [today + timedelta(days=i) for i in range(8)]
    calendar = "\n".join(
        d.strftime("%A %Y-%m-%d") + (" (today)" if i == 0 else "")
        for i, d in enumerate(days)
    )
    return SYSTEM.replace("__CALENDAR__", calendar)


_client = AsyncOpenAI(
    api_key=settings.llm_api_key or "unset",
    base_url="https://api.groq.com/openai/v1",
    timeout=settings.llm_timeout_s,  # already specieid in seconds
    max_retries=0,
)


class LLMUnavailable(Exception):
    pass


async def _call_model(text: str) -> str:

    messages: list[
        ChatCompletionUserMessageParam | ChatCompletionSystemMessageParam
    ] = [
        {
            "role": "system",
            "content": build_system(),  # .format(today=date.today().isoformat())
        },
        {"role": "user", "content": text},
    ]

    # Print complete prompt
    # import json
    # print("\n========== GROQ PROMPT ==========")
    # print(json.dumps(messages, indent=2, ensure_ascii=False))
    # print("========== END PROMPT ==========\n")

    response = await _client.chat.completions.create(
        model=settings.llm_model,
        max_completion_tokens=1500,
        reasoning_effort="low",
        temperature=0,
        messages=messages,
        response_format={"type": "json_object"},
    )

    # print("\n========== COMPLETE GROQ RESPONSE ==========")
    # print(response.model_dump_json(indent=2))
    # print("============================================")

    message = response.choices[0].message

    print("Content:", repr(message.content))
    print("Tool calls:", message.tool_calls)
    print("Finish reason:", response.choices[0].finish_reason)
    return response.choices[0].message.content or ""


def _clean(raw: str) -> str:
    return (
        raw.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )


async def parse_intent(text: str) -> BookingIntent:
    last: Exception | None = None
    for attempt in range(settings.llm_max_attempts):
        try:
            raw = await asyncio.wait_for(_call_model(text), settings.llm_timeout_s)
            return BookingIntent.model_validate_json(_clean(raw))
        except (
            TimeoutError,
            APIError,
            APITimeoutError,
            RateLimitError,
            ValidationError,
        ) as e:
            last = e
            await asyncio.sleep(random.uniform(0, min(2.0, BACKOFF_BASE * 2**attempt)))
    raise LLMUnavailable from last
