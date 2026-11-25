import os

from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import silero, upliftai

from dental_agent.config import settings
from dental_agent.messages import msg

load_dotenv()


async def entrypoint(ctx: JobContext) -> None:
    os.environ.setdefault("UPLIFTAI_API_KEY", settings.uplift_api_key)
    await ctx.connect()
    session: AgentSession = AgentSession(
        vad=silero.VAD.load(),
        tts=upliftai.TTS(voice_id=settings.uplift_voice, output_format="MP3_22050_32"),
    )
    await session.start(room=ctx.room, agent=Agent(instructions=""))
    await session.say(msg("greeting"))


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
