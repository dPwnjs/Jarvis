#!/usr/bin/env python3
"""
J.A.R.V.I.S. (Just A Rather Very Intelligent System)
Real-time Multimodal Voice & Text Assistant powered by Gemini Multimodal Live API.
Features Always-On Microphone, Keyboard Typing Support, and Interruption-Free Audio (No Barge-in).
"""

import asyncio
import math
import os
import struct
import subprocess
import sys
import threading
import time
import traceback

from dotenv import load_dotenv

load_dotenv()

from jarvis.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    JARVIS_VOICE,
    JARVIS_SYSTEM_INSTRUCTION,
    INPUT_SAMPLE_RATE,
)
from jarvis.audio_manager import AudioManager

BANNER = r"""
   ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
   ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
   ██║███████║██████╔╝██║   ██║██║███████╗
██╗██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚████║██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
   [ Just A Rather Very Intelligent System ]
   >>> 🎤 음성 발화 & ⌨️ 텍스트 입력 동시 지원 <<<
   >>> 끊김 없는 상시 수신 (No Interruption) <<<
"""

_last_chime_time = 0.0


def play_activation_chime():
    """Plays a sleek Mac system chime when '자비스' wake word is detected."""
    global _last_chime_time
    now = time.time()
    if now - _last_chime_time < 2.5:
        return
    _last_chime_time = now

    chime_path = "/System/Library/Sounds/Tink.aiff"
    if os.path.exists(chime_path):
        try:
            subprocess.Popen(
                ["afplay", chime_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


def compute_rms(data: bytes) -> int:
    """Calculates RMS audio level for microphone input activity check."""
    if not data:
        return 0
    count = len(data) // 2
    if count == 0:
        return 0
    shorts = struct.unpack(f"{count}h", data)
    sum_squares = sum(s * s for s in shorts)
    return int(math.sqrt(sum_squares / count))


async def send_mic_audio(session, audio_manager: AudioManager, types, shutdown_event: asyncio.Event):
    """
    100% Always-On Microphone Stream:
    Continuously reads raw 16kHz PCM audio from microphone and streams it to Gemini.
    """
    loop = asyncio.get_running_loop()
    zero_rms_count = 0
    warned_mic_perm = False

    while not shutdown_event.is_set():
        chunk = await loop.run_in_executor(None, audio_manager.read_mic_chunk)
        if not chunk:
            await asyncio.sleep(0.005)
            continue

        # Check audio signal (detect if mic is returning pure zeros / no permission)
        rms = compute_rms(chunk)
        if rms == 0:
            zero_rms_count += 1
            if zero_rms_count > 60 and not warned_mic_perm:
                warned_mic_perm = True
                print("\n⚠️  [마이크 주의] 마이크 신호가 들어오지 않습니다 (RMS 0).")
                print("   Mac 시스템 설정 > 개인정보 보호 및 보안 > 마이크에서 터미널 권한을 확인하세요.")
        else:
            zero_rms_count = 0

        try:
            blob = types.Blob(
                data=chunk,
                mime_type=f"audio/pcm;rate={INPUT_SAMPLE_RATE}",
            )
            await session.send_realtime_input(media=blob)
        except asyncio.CancelledError:
            break
        except Exception as e:
            if not shutdown_event.is_set():
                print(f"\n[오디오 전송 중단]: {e}")
                shutdown_event.set()
            break


async def receive_audio_response(session, audio_manager: AudioManager, shutdown_event: asyncio.Event):
    """
    Receives real-time response chunks (Audio PCM & Text Transcription)
    from Gemini Live API. Multi-turn conversation is maintained continuously
    using an outer loop across all turns until shutdown.
    """
    is_speaking = False

    try:
        while not shutdown_event.is_set():
            async for response in session.receive():
                if shutdown_event.is_set():
                    break

                server_content = response.server_content
                if server_content is None:
                    continue

                # 1. Live Input Transcription (What user said via microphone)
                if server_content.input_transcription and server_content.input_transcription.text:
                    user_text = server_content.input_transcription.text.strip()
                    if user_text:
                        lower_text = user_text.lower()
                        if any(w in lower_text for w in ["자비스", "jarvis", "자비"]):
                            play_activation_chime()
                            print("\n⚡ [자비스 호출 감지]")
                        print(f"\n👤 [음성]: {user_text}")

                # 2. Live Output Transcription (What Jarvis is saying)
                if server_content.output_transcription and server_content.output_transcription.text:
                    if not is_speaking:
                        is_speaking = True
                        print("\n🔊 [자비스]: ", end="", flush=True)
                    print(server_content.output_transcription.text, end="", flush=True)

                # 3. Handle Model Audio Response Parts
                model_turn = server_content.model_turn
                if model_turn:
                    for part in model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            audio_manager.play_chunk(part.inline_data.data)

                # 4. Handle Turn Completion
                if server_content.turn_complete:
                    is_speaking = False
                    print("\n🟢 [대기 중 (말씀하시거나 타이핑하세요)] ", end="", flush=True)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        if not shutdown_event.is_set():
            print(f"\n[응답 수신 오류]: {e}")
            shutdown_event.set()
    finally:
        if not shutdown_event.is_set():
            shutdown_event.set()


def start_stdin_reader(input_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> threading.Thread:
    """Runs a daemon thread to read terminal input without blocking the asyncio loop."""
    def _reader():
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    loop.call_soon_threadsafe(input_queue.put_nowait, None)
                    break
                loop.call_soon_threadsafe(input_queue.put_nowait, line)
            except Exception:
                break

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()
    return thread


async def terminal_input_loop(session, types, input_queue: asyncio.Queue, shutdown_event: asyncio.Event):
    """
    Reads keyboard input typed into the terminal and sends it to Gemini Live session.
    Allows concurrent text chatting alongside the active microphone stream.
    """
    while not shutdown_event.is_set():
        try:
            line = await input_queue.get()
            if line is None:
                # EOF reached (e.g. Ctrl+D)
                print("\n👋 [입력 종료 감지] 시스템을 종료합니다, Sir...")
                shutdown_event.set()
                break

            text = line.strip()
            if not text:
                continue

            # Graceful exit commands
            if text.lower() in ["exit", "quit", "q", "종료"]:
                print("\n👋 [종료 요청] 시스템을 안전하게 종료합니다, Sir...")
                shutdown_event.set()
                break

            print(f"\n⌨️ [타이핑 입력]: {text}")

            # Send turn-based text content to Gemini Live API
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=text)],
                ),
                turn_complete=True,
            )
        except asyncio.CancelledError:
            break
        except Exception as e:
            if not shutdown_event.is_set():
                print(f"\n[키보드 입력 전송 오류]: {e}")
            break


async def run_jarvis():
    """Main loop for Gemini Multimodal Live API Voice & Text Session."""
    api_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)
    if not api_key or api_key == "your_gemini_api_key_here":
        print("\n❌ [오류] GEMINI_API_KEY가 설정되지 않았습니다.")
        print("  .env 파일에 유효한 GEMINI_API_KEY를 입력해 주세요.\n")
        return

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("\n❌ [오류] 'google-genai' 패키지가 설치되어 있지 않습니다.")
        print("  source venv/bin/activate 후 실행해 주세요.\n")
        return

    print(BANNER)
    print(f"🚀 모델: {GEMINI_MODEL}")
    print(f"🎙️ 목소리: {JARVIS_VOICE}")
    print("🎙️ 마이크: 상시 활성화 (Always-On Open Mic)")
    print("⌨️ 키보드: 터미널 타이핑 대화 상시 지원 (음성/텍스트 동시 대화)")
    print("🚫 말끊기 방지: 활성화 (말이 도중에 끊기지 않고 끝까지 발화)")
    print("--------------------------------------------------")
    print("초기화 중... 잠시만 기다려 주십시오, Sir.")

    # Initialize Audio Streamer
    audio_manager = AudioManager()
    try:
        audio_manager.start()
    except Exception as e:
        print(f"\n❌ [오디오 장치 오류] 마이크/스피커를 열 수 없습니다: {e}")
        print("  Mac 설정에서 터미널(Terminal)에 '마이크 접근 권한'이 허용되어 있는지 확인하세요.")
        return

    # Initialize Google GenAI Client with v1alpha
    client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})

    # Configure Live Voice Session:
    # activity_handling=NO_INTERRUPTION prevents speech cutoff
    live_config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=JARVIS_VOICE
                )
            )
        ),
        realtime_input_config=types.RealtimeInputConfig(
            activity_handling=types.ActivityHandling.NO_INTERRUPTION
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        system_instruction=types.Content(
            parts=[types.Part.from_text(text=JARVIS_SYSTEM_INSTRUCTION)]
        ),
    )

    print("🔌 Gemini Multimodal Live 서버에 연결 중...")

    # Start terminal keyboard listener queue and daemon thread
    loop = asyncio.get_running_loop()
    input_queue: asyncio.Queue = asyncio.Queue()
    start_stdin_reader(input_queue, loop)

    shutdown_event = asyncio.Event()

    try:
        async with client.aio.live.connect(
            model=GEMINI_MODEL, config=live_config
        ) as session:
            print("✨ [연결 성공] 자비스 시스템이 활성화되었습니다.")
            print("💡 대화 방법 안내:")
            print("   1) 🎙️ 음성: 마이크에 대고 언제든 말씀하세요 ('자비스' 호출 또는 일반 대화).")
            print("   2) ⌨️ 타이핑: 터미널에 메시지를 입력하고 Enter를 누르면 답변을 음성과 텍스트로 드립니다.")
            print("   3) 🚫 말끊김 없음: 발화 도중 끊기지 않고 항상 끝까지 안정적으로 답변합니다.")
            print("   4) 🚪 종료: 'exit', 'quit', 'q', '종료' 입력 또는 Ctrl+C.")
            print("--------------------------------------------------")
            print("🟢 [대기 중 (말씀하시거나 타이핑하세요)] ", end="", flush=True)

            # Run microphone streaming, speaker playback, and terminal typing input concurrently
            send_task = asyncio.create_task(
                send_mic_audio(session, audio_manager, types, shutdown_event)
            )
            receive_task = asyncio.create_task(
                receive_audio_response(session, audio_manager, shutdown_event)
            )
            input_task = asyncio.create_task(
                terminal_input_loop(session, types, input_queue, shutdown_event)
            )

            # Wait until shutdown is signaled
            await shutdown_event.wait()

            # Cleanly cancel running tasks
            for task in [send_task, receive_task, input_task]:
                task.cancel()
            await asyncio.gather(send_task, receive_task, input_task, return_exceptions=True)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"\n❌ [연결 실패]: {e}")
        traceback.print_exc()
    finally:
        audio_manager.close()
        print("\n\n🔒 [시스템 오프라인] 자비스가 대기 모드로 전환되었습니다. 좋은 하루 되십시오, Sir.")


def main():
    try:
        asyncio.run(run_jarvis())
    except KeyboardInterrupt:
        print("\n\n[사용자 중단 요청] 시스템을 안전하게 종료합니다.")


if __name__ == "__main__":
    main()
