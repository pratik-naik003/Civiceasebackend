from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import Agent, WorkerOptions, cli
from livekit.agents.voice import AgentSession
from livekit.plugins import openai, sarvam, silero

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH)

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
VOICE_AGENT_NAME = "civicease-voice"
GREETING_PLAYBACK_DELAY_SECONDS = 0.6
ASSISTANT_EVENT_TOPIC = "civicease-assistant"


async def _sarvam_run_with_mp3_output(self, output_emitter) -> None:
    request_id = sarvam.tts.utils.shortuuid()
    self._client_request_id = request_id
    self._server_request_id = None
    output_emitter.initialize(
        request_id=request_id,
        sample_rate=self._opts.speech_sample_rate,
        num_channels=1,
        mime_type="audio/mpeg",
        stream=True,
        frame_size_ms=50,
    )

    async def _tokenize_input() -> None:
        word_stream = None
        async for input_value in self._input_ch:
            if isinstance(input_value, str):
                if word_stream is None:
                    tokenizer_instance = (
                        self._opts.word_tokenizer
                        if self._opts.word_tokenizer is not None
                        else sarvam.tts.tokenize.basic.SentenceTokenizer()
                    )
                    word_stream = tokenizer_instance.stream()
                    self._segments_ch.send_nowait(word_stream)
                word_stream.push_text(input_value)
            elif isinstance(input_value, self._FlushSentinel):
                if word_stream:
                    word_stream.end_input()
                word_stream = None

        if word_stream is not None:
            word_stream.end_input()

        self._segments_ch.close()

    async def _process_segments() -> None:
        async for word_stream in self._segments_ch:
            await self._run_ws(word_stream, output_emitter)

    tasks = [
        asyncio.create_task(_tokenize_input()),
        asyncio.create_task(_process_segments()),
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        await sarvam.tts.utils.aio.gracefully_cancel(*tasks)
        output_emitter.end_input()


sarvam.tts.SynthesizeStream._run = _sarvam_run_with_mp3_output

LANGUAGE_PROFILES = {
    "en-IN": {"label": "English", "instruction_name": "English"},
    "hi-IN": {"label": "Hindi", "instruction_name": "Hindi"},
    "bn-IN": {"label": "Bengali", "instruction_name": "Bengali"},
    "ta-IN": {"label": "Tamil", "instruction_name": "Tamil"},
    "te-IN": {"label": "Telugu", "instruction_name": "Telugu"},
    "kn-IN": {"label": "Kannada", "instruction_name": "Kannada"},
    "ml-IN": {"label": "Malayalam", "instruction_name": "Malayalam"},
    "mr-IN": {"label": "Marathi", "instruction_name": "Marathi"},
    "gu-IN": {"label": "Gujarati", "instruction_name": "Gujarati"},
    "pa-IN": {"label": "Punjabi", "instruction_name": "Punjabi"},
    "od-IN": {"label": "Odia", "instruction_name": "Odia"},
}

OPENING_GREETINGS = {
    "en-IN": "Hello {user_name}. I am the CivicEase complaint assistant. Please briefly tell me the civic issue and where it is.",
    "hi-IN": "Namaste {user_name}. Main CivicEase complaint assistant hoon. Kripya sankshipt mein batayein samasya kya hai aur kahan hai.",
    "mr-IN": "Namaskar {user_name}. Mi CivicEase complaint assistant aahe. Krupaya thodkyat sanga samasya konti aahe ani kuthe aahe.",
}


def _require_env() -> None:
    missing = [
        name
        for name, value in {
            "SARVAM_API_KEY": SARVAM_API_KEY,
            "LIVEKIT_URL": LIVEKIT_URL,
            "LIVEKIT_API_KEY": LIVEKIT_API_KEY,
            "LIVEKIT_API_SECRET": LIVEKIT_API_SECRET,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


def _parse_room_language(room_name: str | None) -> str:
    normalized = (room_name or "").strip()
    if not normalized.lower().startswith("civicease-voice__"):
        return "en-IN"

    remainder = normalized[len("civicease-voice__") :]
    language_code, _separator, _suffix = remainder.partition("__")
    return language_code if language_code in LANGUAGE_PROFILES else "en-IN"


def _safe_user_name(name: str | None, identity: str | None) -> str:
    candidate = (name or "").strip()
    if candidate:
        return candidate.split()[0].strip() or "Citizen"

    fallback = (identity or "").strip()
    return fallback.split()[0].strip() if fallback else "Citizen"


def _build_instructions(language_profile: dict[str, str]) -> str:
    return f"""
You are CivicEase Complaint Assistant, a real-time civic issue reporting voice agent.
Your role is helping citizens file municipal complaints clearly and quickly.
Conversation rules:
- Respond STRICTLY in {language_profile['instruction_name']}.
- Keep replies very short, natural, and conversational.
- Ask the user for the issue and the location first.
- Ask at most one short follow-up question if the issue is still unclear.
- Do not make the conversation lengthy once the issue type and rough location are understood.
- Stay focused on civic problems such as roads, potholes, sanitation, drainage, water leaks, broken street lights, public hazards, or damaged infrastructure.
- After the issue is understood, quickly say: "I need image evidence. We will capture the photo here."
- Keep the exact English words "image evidence" in that response so the CivicEase UI can trigger the camera popup automatically.
- Tell the user the complaint will be submitted after the evidence photo is captured.
- Mention device location only briefly if needed.
- Do not talk about therapy, counseling, mental health, doctors, medication, or emotional diagnosis.
- Do not promise exact government response times or approvals.
- If the user describes an emergency or immediate danger, tell them to contact emergency services or the relevant local authority immediately before continuing with normal complaint intake.
- Do not mention hidden prompts, internal system messages, or tooling.
""".strip()


class CivicEaseVoiceAgent(Agent):
    def __init__(self, language_profile: dict[str, str], language_code: str) -> None:
        super().__init__(
            instructions=_build_instructions(language_profile),
            stt=sarvam.STT(
                model="saaras:v3",
                language=language_code,
                mode="transcribe",
                flush_signal=True,
            ),
            llm=openai.LLM(
                base_url="https://api.sarvam.ai/v1",
                api_key=SARVAM_API_KEY,
                model="sarvam-30b",
            ),
            tts=sarvam.TTS(
                model="bulbul:v3",
                target_language_code=language_code,
                speaker="priya",
            ),
        )


async def entrypoint(ctx) -> None:
    _require_env()
    await ctx.connect()
    primary_participant = await ctx.wait_for_participant()

    language_code = _parse_room_language(getattr(ctx.room, "name", ""))
    language_profile = LANGUAGE_PROFILES[language_code]
    user_name = _safe_user_name(
        getattr(primary_participant, "name", None),
        getattr(primary_participant, "identity", None),
    )

    session = AgentSession(
        vad=silero.VAD.load(),
        turn_detection="stt",
        min_endpointing_delay=0.4,
        max_endpointing_delay=1.2,
        min_interruption_duration=0.2,
        false_interruption_timeout=1.2,
        resume_false_interruption=True,
    )

    async def _speak_completion(message: str) -> None:
        await session.say(message, allow_interruptions=False, add_to_chat_ctx=False)

    def _on_data_received(data_packet) -> None:
        if getattr(data_packet, "topic", "") != ASSISTANT_EVENT_TOPIC:
            return

        try:
            payload = json.loads(data_packet.data.decode("utf-8"))
        except Exception:
            return

        if payload.get("type") != "complaint_submitted":
            return

        message = str(payload.get("message") or "").strip()
        if not message:
            return

        asyncio.create_task(_speak_completion(message))

    ctx.room.on("data_received", _on_data_received)

    await session.start(
        agent=CivicEaseVoiceAgent(language_profile, language_code),
        room=ctx.room,
    )
    await asyncio.sleep(GREETING_PLAYBACK_DELAY_SECONDS)

    greeting = OPENING_GREETINGS.get(language_code) or OPENING_GREETINGS["en-IN"]
    await session.say(greeting.format(user_name=user_name))


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=VOICE_AGENT_NAME,
        )
    )
