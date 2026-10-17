"""Speech-to-text with AssemblyAI (STT_PROVIDER=assemblyai).

How to connect to AssemblyAI's streaming service and read its replies.
Everything else, such as reconnecting, the audio queue and saving turns, is
shared with the other services (see stt_stream.py).

- The connection goes to AssemblyAI's nearest region, in the US or the EU
  (ASSEMBLYAI_URL). Its EU data zone accepted the connection but sent no
  text in our tests.
- While a person speaks, the newest words are shown as soon as they are
  heard, before AssemblyAI is sure of them (see AssemblyTurnBuilder).
- AssemblyAI sends each finished turn with punctuation and capitals
  ("format_turns"), and the job's keywords help it recognise technical
  words ("keyterms_prompt").
- No keep-alive message is needed: the connection stays open while a
  person is muted.
- AssemblyAI refuses audio sent much faster than it is spoken, so audio
  queued during a network drop is sent at up to one and a half times real
  time until it has caught up.
- Problems arrive as close codes, for example 1008 for a wrong key or no
  credit left; they are logged by their number only.
"""

import json
from urllib.parse import urlencode

from app.core.config import get_settings
from app.workers.stt_stream import SAMPLE_RATE, StreamingSink
from app.workers.turns import AssemblyTurnBuilder, AudioClock


def listen_url(keyterms: list[str]) -> str:
    """The address of a live connection: 16 kHz 16-bit audio, the chosen
    model, formatted turns and the job's keywords."""
    settings = get_settings()
    params = [
        ("speech_model", settings.assemblyai_model),
        ("encoding", "pcm_s16le"),
        ("sample_rate", str(SAMPLE_RATE)),
        ("format_turns", "true"),
    ]
    if keyterms:
        params.append(("keyterms_prompt", json.dumps(keyterms)))
    return f"{settings.assemblyai_url}?{urlencode(params)}"


class AssemblyAISink(StreamingSink):
    """Transcribes one person's audio in one interview with AssemblyAI."""

    PROVIDER = "assemblyai"
    CLOSE = {"type": "Terminate"}
    CATCH_UP_SPEED = 1.5

    def connection_url(self) -> str:
        return listen_url(self.keyterms)

    def headers(self) -> dict[str, str]:
        # The key goes as it is, without "Bearer" or "Token" in front.
        return {"Authorization": get_settings().assemblyai_api_key}

    def new_builder(self, clock: AudioClock) -> AssemblyTurnBuilder:
        return AssemblyTurnBuilder(self.speaker, clock)

    def is_error(self, message: dict) -> bool:
        return "error" in message
