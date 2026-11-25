# Week 2 note


## 1. What did I build?
A conversational agent for the dental clinic that holds a multi-turn text conversation and
uses eight tools (search slots, hours, find appointments, book, reschedule, cancel, confirm,
hand off to a person). The loop, tool dispatch and conversation state are hand-written
against the Groq API through the openai library, with no agent framework. Booking,
rescheduling and cancelling never run directly: they store a pending action, and only
confirm_pending runs it, after a new caller turn. Hard limits: 8 tool calls and 30,000
tokens per conversation, both covered by tests. Every outbound call has an explicit timeout,
at most 3 attempts and jittered backoff. If the primary model fails, a cheaper model takes
over, then a scripted reply that hands the caller to a person (a test kills the primary and
proves the call survives). Every model and tool call is a span in Phoenix. The golden set
has 51 labelled conversations (16 booked, 9 cancelled, 9 escalated, 17 refused). A judge
model scores transcripts. The harness prints task success and judge agreement, and CI can
run a 10-case smoke subset on demand.

Latest full run (40 of 51 cases): task success 95.0%, judge agreement 85.0%, 119,198 tokens.

## 2. What broke?
- Free-tier rate limits. I first suspected concurrency, but the calls were sequential: each
  turn makes several model calls and each one re-sends the prompt, the tool schemas and the
  history. I added pacing to the eval harness only, so production fails over quickly.
- The agent spoke internal ids and slot numbers. Fixed with a prompt rule, and the evals
  count leaks (currently 0).
- The eval run showed that the agent asks for confirmation twice in 13 of 17 booking and
  cancel cases, because the prompt and the code gate both ask.
- It also showed wrong weekdays (11 of 40 cases): the tools returned ISO timestamps, so the
  model worked the weekday out itself. In b10 this led to a wrong-day offer and a false
  claim that the appointment had moved.
- The handoff message was never stored, so the judge could not see it: four wrong judge
  verdicts that were my bug, not the judge's.
- One of my own cases (c05) was ambiguous: "No, nothing else" read as a "no" to the
  confirmation. A good reminder that the golden set has bugs too.

## 3. What would I change?
- Write the prompt and the confirmation gate together, so they do not both ask.
- Return human-readable dates from tools from the start, not raw timestamps.
- Log every tool call and result in the eval output from day one for better eval trace.

## 4. What did I skip?
- Running the full 51 cases with the judge in CI: free-tier limits make it unaffordable, so
  CI runs a balanced 10-case subset on demand and the full run happens locally.
- 11 of the 51 cases have not been run yet.
- Used Phoenix over langfuse.
- Conversation state in a database (it lives in memory, so a restart loses it).
- Phone number normalisation: lookups need the exact stored format.
- Parallel tool calls in one reply.

## 5. What do I not yet understand?
- Why b10 claimed success when nothing was recorded. My hypothesis is that the model called
  confirm_pending in the same turn as the proposal and ignored the error, but I have not
  confirmed it.
