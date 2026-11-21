import asyncio
import random
import re
from collections.abc import Awaitable, Callable

# T = TypeVar("T")
BASEOFF_BASE = 0.3


async def call_with_retries[T](
    fn: Callable[[], Awaitable[T]],
    *,
    timeout: float,
    attempts: int = 3,
    retry_on: tuple[type[BaseException], ...] = (TimeoutError,),
) -> T:
    for i in range(attempts):
        try:
            return await asyncio.wait_for(fn(), timeout)
        except retry_on:
            if i == attempts - 1:
                raise
            await asyncio.sleep(random.uniform(0, min(2.0, BASEOFF_BASE * 2**i)))
    raise RuntimeError("unreachable")


def clean_json(raw: str) -> str:
    raw = re.sub(
        r"<think>.*?</think>", "", raw, flags=re.DOTALL
    )  # some models show reasoning
    return (
        raw.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
