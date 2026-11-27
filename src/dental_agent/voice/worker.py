import json
import logging
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import groq as lk_groq
from livekit.plugins import silero, upliftai

from dental_agent.config import settings
from dental_agent.messages import msg
from dental_agent.tracing import setup_tracing
from dental_agent.voice.brain import Brain
from dental_agent.voice.uplift_stt import UpliftSTT

load_dotenv()
TURNS = Path("logs/turns.jsonl")
log = logging.getLogger("clinic")


def build_stt() -> Any:
    if settings.stt_provider == "groq":
        return lk_groq.STT(model="whisper-large-v3-turbo", language="ur")
    return UpliftSTT()


def _last_user_text(chat_ctx: Any) -> str:
    for item in reversed(chat_ctx.items):
        if getattr(item, "role", "") == "user":
            return str(item.text_content or "")
    return ""


class ClinicAgent(Agent):
    def __init__(self, brain: Brain) -> None:
        super().__init__(instructions="")
        self.brain = brain

    async def on_user_turn_completed(self, turn_ctx: Any, new_message: Any) -> None:
        log.warning(
            "USER TURN COMPLETED: %r",
            new_message.text_content,
        )

    async def llm_node(
        self, chat_ctx: Any, tools: Any, model_settings: Any
    ) -> AsyncIterator[str]:
        log.warning("========== LLM NODE ENTERED ==========")
        text = _last_user_text(chat_ctx)
        log.warning("llm_node called with %r", text)
        reply = await self.brain.reply(text)
        log.warning("llm_node reply %r", reply)
        yield reply
        # yield await self.brain.reply(_last_user_text(chat_ctx))


async def entrypoint(ctx: JobContext) -> None:
    os.environ.setdefault("UPLIFTAI_API_KEY", settings.uplift_api_key)
    setup_tracing()
    await ctx.connect()
    session: AgentSession = AgentSession(
        vad=silero.VAD.load(),
        stt=build_stt(),
        llm=lk_groq.LLM(
            model=settings.fallback_model
        ),  # never called: llm_node is overridden
        tts=upliftai.TTS(voice_id=settings.uplift_voice, output_format="MP3_22050_32"),
        turn_detection="vad",
        min_endpointing_delay=settings.endpointing_delay_s,
        allow_interruptions=True,
        # transcription_timeout=10.0,
    )

    @session.on("conversation_item_added")
    def _log_turn(ev: Any) -> None:
        item = ev.item
        TURNS.parent.mkdir(exist_ok=True)
        rec = {
            "t": time.time(),
            "role": item.role,
            "text": item.text_content,
            "interrupted": bool(getattr(item, "interrupted", False)),
            "metrics": dict(getattr(item, "metrics", None) or {}),
        }
        with TURNS.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    @session.on("user_state_changed")
    def on_user_state(ev):
        log.warning("USER STATE CHANGED: %s", ev)

    @session.on("agent_state_changed")
    def on_agent_state(ev):
        log.warning("AGENT STATE CHANGED: %s", ev)

    @session.on("conversation_item_added")
    def on_item(ev):
        log.warning(
            "CONVERSATION ITEM: role=%s text=%r",
            ev.item.role,
            ev.item.text_content,
        )

    # # 1. Listen for transcribed user speech
    # @session.on("user_input_transcribed")
    # def on_user_input_transcribed(event):
    #     print("\n========== TRANSCRIPTION ==========")
    #     print("Text:", event.transcript)
    #     print("Language:", event.language)
    #     print("Final:", event.is_final)
    #     print("===================================\n")

    # # 2. Detect user speaking/listening states
    # @session.on("user_state_changed")
    # def on_user_state_changed(event):
    #     print(
    #         f"\n[USER STATE] {event.new_state}\n"
    #     )

    # # 3. Detect agent speaking/listening states
    # @session.on("agent_state_changed")
    # def on_agent_state_changed(event):
    #     print(
    #         f"\n[AGENT STATE] {event.new_state}\n"
    #     )

    # # 4. Detect when speech is heard but no transcript arrives
    # @session.on("user_transcription_timeout")
    # def on_transcription_timeout(event):
    #     print("\n========== STT TIMEOUT ==========")
    #     print("Speech duration:", event.speech_duration)
    #     print("Groq did not return a final transcript in time.")
    #     print("=================================\n")

    await session.start(room=ctx.room, agent=ClinicAgent(Brain()))
    await session.say(msg("greeting"))


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
