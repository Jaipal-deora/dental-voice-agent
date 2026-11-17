# Dental Voice Agent

A small FastAPI service for an invented dental clinic. It lists slots, books, reschedules and cancels appointments, returns opening hours, and turns a caller's sentence into a validated booking request using an LLM.
All data is fake. Nothing here comes from a real company or client.

## Run it (one command)
```bash
cp .env.example .env # add your llm key here and the rest has defaults 
make run # installs deps, migrates, seeds and starts app on :8000
```
Then open: http://127.0.0.1:8000/docs#

With Docker instead:
```bash 
docker build -t dental_agent .
docker run --rm --env-file .env -p 8000:8000 dental_agent
```



