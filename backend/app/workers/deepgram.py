"""Speech-to-text with Deepgram (STT_PROVIDER=deepgram).

How to connect to Deepgram and read its replies. Everything else, such as
reconnecting, the audio queue and saving turns, is shared with the other
services (see stt_stream.py).

- Deepgram is asked not to keep the audio for improving its models.
- Deepgram closes a connection that receives nothing for about ten
  seconds, for example while a person is muted, so a keep-alive message
  is sent while there is no audio.
"""

from urllib.parse import urlencode

from app.core.config import get_settings
from app.workers.stt_stream import SAMPLE_RATE, StreamingSink
from app.workers.turns import AudioClock, TurnBuilder


def listen_url(keyterms: list[str]) -> str:
    """The address of a live connection: English, interim results, and a
    pause of 300 ms ending a piece of speech."""
    settings = get_settings()
    params = [
        ("model", settings.deepgram_model),
        ("language", "en"),
        ("encoding", "linear16"),
        ("sample_rate", str(SAMPLE_RATE)),
        ("channels", "1"),
        ("interim_results", "true"),
        ("smart_format", "true"),
        ("endpointing", "300"),
        ("utterance_end_ms", "1000"),
        ("mip_opt_out", "true"),
    ]
    params += [("keyterm", term) for term in keyterms]
    return f"{settings.deepgram_url}?{urlencode(params)}"


class DeepgramSink(StreamingSink):
    """Transcribes one person's audio in one interview with Deepgram."""

    PROVIDER = "deepgram"
    KEEP_ALIVE = {"type": "KeepAlive"}
    CLOSE = {"type": "CloseStream"}

    def connection_url(self) -> str:
        return listen_url(self.keyterms)

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Token {get_settings().deepgram_api_key}"}

    def new_builder(self, clock: AudioClock) -> TurnBuilder:
        return TurnBuilder(self.speaker, clock)

    def is_error(self, message: dict) -> bool:
        return message.get("type") == "Error"
