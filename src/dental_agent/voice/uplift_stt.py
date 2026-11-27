from typing import Any

import aiohttp
from livekit import rtc
from livekit.agents import stt
from livekit.agents.language import LanguageCode
from livekit.agents.types import NOT_GIVEN

from dental_agent.config import settings
from dental_agent.reliability import call_with_retries


class UpliftSTT(stt.STT):
    """Uplift Scribe is an HTTP, per-segment API; LiveKit wraps it with VAD for streaming use."""

    def __init__(self) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(streaming=False, interim_results=False)
        )
        self._http: aiohttp.ClientSession | None = (
            None  # reused: no TLS handshake per turn
        )

    async def _recognize_impl(
        self, buffer: Any, *, language: Any = NOT_GIVEN, conn_options: Any
    ) -> stt.SpeechEvent:
        wav = rtc.combine_audio_frames(buffer).to_wav_bytes()
        if self._http is None:
            self._http = aiohttp.ClientSession()
        http = self._http

        async def post() -> str:
            form = aiohttp.FormData()
            form.add_field("file", wav, filename="turn.wav", content_type="audio/wav")
            form.add_field("model", settings.uplift_stt_model)
            form.add_field("language", "ur")
            headers = {"Authorization": f"Bearer {settings.uplift_api_key}"}
            async with http.post(
                settings.uplift_stt_url, data=form, headers=headers
            ) as r:
                r.raise_for_status()
                data = await r.json()
            return str(data.get("text") or data.get("transcript") or "")

        text = await call_with_retries(
            post,
            timeout=settings.uplift_stt_timeout_s,
            attempts=2,
            retry_on=(TimeoutError, aiohttp.ClientError),
        )
        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(language=LanguageCode("ur"), text=text)],
        )
