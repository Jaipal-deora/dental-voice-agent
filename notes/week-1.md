# Week 1 note

## 1. What did I build?
A FastAPI service for a made-up dental clinic: list slots, book, reschedule,
cancel and opening hours, backed by SQLite through async SQLAlchemy with the
schema created by an Alembic migration and seeded with fake data. Booking is
idempotent (unique key plus a partial unique index per booked slot). A `/parse`
endpoint turns a caller's sentence into a validated `BookingIntent` using
Groq's `openai/gpt-oss-20b`, with an explicit timeout, retries with jitter and
schema validation. Ruff, mypy, pytest with an 80% coverage gate, pre-commit,
CI and a multi-stage Dockerfile are in place. 

## 2. What broke?
- Didn't know about hatchling and environment was having difficult time following src. 
- A conflict test returned 201 instead of 409. The first request posted to
  `/appointment` instead of `/appointments`, so nothing was booked. Setup
  requests in tests now assert their own status codes.
- Coverage showed 72% even though the service tests passed. Coverage was not
  tracing code that runs inside SQLAlchemy's async greenlets, and `seed.py` was
  counted. Fixed with `concurrency = ["greenlet", "thread"]` and omitting the seed script.
- The first real call to the model returned `intent: unknown, confidence: 0`.
  The prompt did not say what counts as a booking request. The mocked tests
  could never catch that.
- `gemini-2.5-flash` was not supported so switched to `gemini-3.8-flash`. It was taking time even when I increased time to 120 second. Switched to Groq api and model: `openai/gpt-oss-20b`. It is a reasoning model and spent its
  whole output budget thinking about what weekday the date falls on. Fixed with
  a larger output limit, `reasoning_effort="low"`, and an 8-day calendar in the
  prompt so the model looks dates up.
- `TypeError: Object of type set is not JSON serializable`: a `{...}` in the
  request that was a set instead of a dict. 


## 3. What would I change?
- Choose the model and provider before writing `llm.py`, and test it against
  the real API on ten sample sentences on day one, not at the end.
- Add a test that runs the real migration, so a bad migration cannot hide
  behind tests that build tables from the models.

## 4. What did I skip?
- Redis caching (studied the concepts only, as planned).
- Authentication and time-zone handling (assumptions recorded in DESIGN.md).
- A concurrent double-booking test; the in-memory test database shares one
  connection, so it would not prove anything. The database constraint is the
  real protection.
- Pagination for the slots list.

## 5. What do I not yet understand?
- How different things defined in pyproject.toml file works like hatchling, pytest asyncio auto, and greenlets.
- 