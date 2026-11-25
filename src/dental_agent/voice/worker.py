import os
from typing import Any

from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import groq as lk_groq
from livekit.plugins import silero, upliftai

from dental_agent.config import settings
from dental_agent.messages import msg
from dental_agent.voice.uplift_stt import UpliftSTT

load_dotenv()

def build_stt() -> Any:
    if settings.stt_provider == "groq":
        print("groq provider")
        return lk_groq.STT(model="whisper-large-v3-turbo", language="ur")
    print("uplift provided")
    return UpliftSTT()

async def entrypoint(ctx: JobContext) -> None:
    os.environ.setdefault("UPLIFTAI_API_KEY", settings.uplift_api_key)
    await ctx.connect()
    session: AgentSession = AgentSession(
        vad=silero.VAD.load(),
        stt=build_stt(),
        tts=upliftai.TTS(voice_id=settings.uplift_voice, output_format="MP3_22050_32"),
        transcription_timeout=10.0,
    )

    # 1. Listen for transcribed user speech
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event):
        print("\n========== TRANSCRIPTION ==========")
        print("Text:", event.transcript)
        print("Language:", event.language)
        print("Final:", event.is_final)
        print("===================================\n")

    # 2. Detect user speaking/listening states
    @session.on("user_state_changed")
    def on_user_state_changed(event):
        print(
            f"\n[USER STATE] {event.new_state}\n"
        )

    # 3. Detect agent speaking/listening states
    @session.on("agent_state_changed")
    def on_agent_state_changed(event):
        print(
            f"\n[AGENT STATE] {event.new_state}\n"
        )

    # 4. Detect when speech is heard but no transcript arrives
    @session.on("user_transcription_timeout")
    def on_transcription_timeout(event):
        print("\n========== STT TIMEOUT ==========")
        print("Speech duration:", event.speech_duration)
        print("Groq did not return a final transcript in time.")
        print("=================================\n")

    await session.start(room=ctx.room, agent=Agent(instructions=""))
    await session.say(msg("greeting"))


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
