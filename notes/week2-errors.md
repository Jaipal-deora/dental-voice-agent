# Week 2 error analysis

## Numbers

| Metric | Value |
|---|---|
| Task success (recorded outcome equals my label) | 95.0% (38 of 40) |
| Judge agreement with my labels | 85.0% (34 of 40) |
| Judge agreement on cases the agent got right | 86.8% |
| Tokens | 119,198 in total, about 3.0k per case |
| Tokens by label | booked about 6.1k, cancelled about 4.7k, refused about 1.3k, escalated about 0.6k |

Both numbers pass their gates (85% task success, 80% judge agreement)

## Failure types, ranked by how many cases show them

| # | Failure type | Cases | Evidence |
|---|---|---|---|
| 1 | Double confirmation: the agent asks "shall I go ahead?" in its own words, then the confirmation gate makes it ask again | 13 of 17 booking and cancel cases | b01, b02, b03, b04, b05, b12, b16, c01, c03, c04, c05, c06, c09 |
| 2 | Wrong weekday for a date (for example "Tuesday 7 January"; 7 January 2030 is a Monday) | 11 of 40 | b05, b06, b10, b11, c01, c03, c04, c05, c09, r12, r14 |
| 3 | Handoff message missing from the stored transcript, so the judge only sees the caller | 7 cases have no agent line; 4 judge misses | e01, e02, e03, e04, e05, e07, e08 (judge wrong on e03, e05, e07, e08) |
| 4 | False success claim: the agent says the appointment moved, but nothing was recorded | 1 | b10 |
| 5 | Judge prompt is ambiguous about "cancelled" | 1 | r15: the judge's own reason says no booking happened, but it chose cancelled |
| 6 | Case design: a scripted reply that reads as "no" to a confirmation question | 1 | c05, turn 3 is "No, nothing else. Thanks." |


## The 10 worst cases

| Case | Expected, actual, judge | Failure type | What happened |
|---|---|---|---|
| b10 | booked, refused, booked | 4, 2, 1 | The caller asked for Tuesday 10 am. The agent offered "Tuesday 7 January" (a Monday), then told the caller the appointment had moved, but no booking was recorded. The most serious case: a wrong day plus a claim of success |
| c05 | cancelled, refused, refused | 1, 6 | The agent asked to confirm twice. My third scripted turn, "No, nothing else", answered the second question, so the appointment was kept. The judge was right here |
| e03 | escalated, escalated, refused | 3 | The transcript has no agent line, so the judge saw only "Put me through to the receptionist" |
| e05 | escalated, escalated, refused | 3 | Same |
| e07 | escalated, escalated, refused | 3 | Same |
| e08 | escalated, escalated, refused | 3 | Same |
| r15 | refused, refused, cancelled | 5 | The agent correctly found no slot. The judge described that correctly and still picked the label "cancelled" |
| b05 | booked, booked, booked | 2 | Named 2030-01-09 as "Thursday" (it is a Wednesday) |
| b06 | booked, booked, booked | 2 | "Tomorrow" became "Tuesday 7 January" (a Monday) |
| r14 | refused, refused, refused | 2 | Called the date "Sunday 7 January" |

## Most common failure and proposed fix

**Failure 1, double confirmation, 13 of 17 action cases.** Example, b01:

- Agent: "I have a slot on Monday 7 January at 9:00 am for you. Shall I go ahead and book that?"
- Caller: "Yes, please book it."
- Agent: "Just to confirm, I'll book a cleaning ... Is that correct?"

**Cause.** The system prompt tells the agent to read the details back and wait for the
caller's yes or no. The code gate also asks, because book, reschedule and cancel only store a
pending action. So the caller is asked twice. The two guards fight each other.

**Proposed fix (one change).** Tell the agent to call the action tool as soon as the caller
has asked for it and it has the details, and let the gate ask once. In the system prompt:

> When the caller clearly asks to book, reschedule or cancel and you have the details, call
> the tool at once. Do not ask "shall I go ahead" yourself: the system asks the caller to
> confirm, and the caller must be asked only once.

**Why this and not changing the gate.** The gate is what makes confirmation a code rule
instead of a hope, so the prompt should adapt to it.

**How to verify.** Re-run b01, c01 and c05 and count the agent's confirmation questions.
Target: one question per action, and the double-confirmation count at 1 of 17 or fewer.
Tokens per booked case should also drop from about 6.1k, because there is one less model
round trip.

## Other fixes, in priority order

1. **Wrong weekdays (failure 2).** Tool results give times as ISO strings with no weekday, so
   the model works it out itself and is sometimes wrong. Have the tools return a ready-made
   `when` text ("Monday 7 January 2030, 9:00 am"), and tell the agent to use it as written.
   In b10 this error turned into a wrong-day booking offer, so do this second.
2. **Missing handoff text (failure 3).** The final handoff or limit message is returned to the
   caller but never added to the stored messages. Append it as an assistant message. This is a
   bug in my code, not in the judge, and it fixes four of the six judge misses.
3. **Success claims (failure 4).** Add a prompt rule: only say something was booked, moved or
   cancelled when the tool result says so. Also record every tool call and result in the eval
   output, because I cannot tell from the transcript alone why b10 failed.
4. **Judge prompt (failure 5).** Define the labels strictly: "cancelled" only when an existing
   appointment was actually cancelled, and a request that could not be completed is "refused".
5. **Case c05 (failure 6).** Change turn 3 to "Yes, that's right. Nothing else, thanks."

## Open question

I do not yet know why b10 claimed success. My hypothesis, not verified: after the caller's
"yes", the model called the reschedule tool and then called confirm_pending in the same turn.
The gate refuses that, because the caller has not replied since the proposal, and the model
reported success anyway. The tool log from fix 3 will confirm or reject this.

## Re-run plan

Run only the cases that changed, to save quota: b10, c05, b01 (about 16k tokens in total),
then the 10-case smoke set (about 35k to 40k tokens), and the full set once at the end of the
week.
