#!/usr/bin/env python3
"""
J.A.R.V.I.S. Web Interface Server
Serves the Iron Man Arc Reactor Web UI via HTTP (Port 8000)
and provides a real-time WebSocket bridge (Port 8001) to Google Gemini 2.5 Live API.
"""

import asyncio
import atexit
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time

from dotenv import load_dotenv

load_dotenv()

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from jarvis.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    JARVIS_VOICE,
    JARVIS_SYSTEM_INSTRUCTION,
    INPUT_SAMPLE_RATE,
)
from jarvis.tools import JARVIS_TOOLS, execute_tool


HTTP_PORT = int(os.getenv("PORT", "8000"))
WS_PORT = int(os.getenv("WS_PORT", "8001"))
if WS_PORT == HTTP_PORT:
    WS_PORT = HTTP_PORT + 1
HOST = os.getenv("HOST", "0.0.0.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
INDEX_PATH = os.path.join(WEB_DIR, "index.html")

TUNNEL_PROCESS = None
TUNNEL_URL = None


def find_cloudflared_bin() -> str | None:
    """Finds the cloudflared binary in local bin/ or system PATH."""
    # Check if disabled or already deployed on a cloud PaaS (Render, Railway, Fly, Heroku, etc.)
    if os.getenv("DISABLE_TUNNEL", "").lower() in ("1", "true", "yes"):
        return None
    if os.getenv("RENDER") or os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("FLY_APP_NAME") or os.getenv("DYNO"):
        return None

    # Only use macOS binary when running locally on macOS
    if sys.platform == "darwin":
        local_bin = os.path.join(BASE_DIR, "bin", "cloudflared")
        if os.path.exists(local_bin) and os.access(local_bin, os.X_OK):
            return local_bin

    system_bin = shutil.which("cloudflared")
    if system_bin:
        return system_bin
    return None


def start_cloudflare_tunnel(port: int = HTTP_PORT) -> str | None:
    """
    Spawns Cloudflare Tunnel to expose HTTP_PORT to the public internet
    with zero configuration, valid HTTPS, and WebSocket support.
    """
    global TUNNEL_PROCESS, TUNNEL_URL
    cf_bin = find_cloudflared_bin()
    if not cf_bin:
        print("💡 [Cloudflare Tunnel]: cloudflared 실행 파일이 없어 로컬 모드로 실행합니다.")
        return None

    print("🌐 [Cloudflare Tunnel]: 외부 인터넷 접속용 보안 터널(HTTPS)을 생성하는 중...")
    try:
        proc = subprocess.Popen(
            [cf_bin, "tunnel", "--url", f"http://127.0.0.1:{port}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        TUNNEL_PROCESS = proc

        def stop_tunnel():
            global TUNNEL_PROCESS
            if TUNNEL_PROCESS and TUNNEL_PROCESS.poll() is None:
                try:
                    TUNNEL_PROCESS.terminate()
                    TUNNEL_PROCESS.wait(timeout=2)
                except Exception:
                    try:
                        TUNNEL_PROCESS.kill()
                    except Exception:
                        pass

        atexit.register(stop_tunnel)

        tunnel_url = None
        start_time = time.time()
        while time.time() - start_time < 12:
            if proc.poll() is not None:
                break
            line = proc.stderr.readline()
            if not line:
                time.sleep(0.1)
                continue
            if "trycloudflare.com" in line:
                match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if match:
                    tunnel_url = match.group(0)
                    break

        if tunnel_url:
            TUNNEL_URL = tunnel_url
            return tunnel_url
        else:
            print("⚠️ [Cloudflare Tunnel]: 터널 주소 탐색 시간 초과. 로컬 모드로 계속합니다.")
            return None

    except Exception as e:
        print(f"⚠️ [Cloudflare Tunnel 실행 오류]: {e}")
        return None


def get_local_ip() -> str:
    """Detects the primary LAN IP address of this machine for mobile access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class JarvisHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """
    Custom HTTP request handler that serves web/ directory,
    supports WebSocket proxying on the same port,
    injects window.JARVIS_WS_PORT and local IP into index.html,
    and sets CORS and cache-control headers.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        # Fast health check route for cloud deployment (Render, AWS, Railway, GCP)
        clean_path = self.path.split("?")[0]
        if clean_path in ["/healthz", "/ping", "/health"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"jarvis-neural-web"}\n')
            return

        # Support WebSocket connections on the HTTP port via reverse proxy
        if self.headers.get("Upgrade", "").lower() == "websocket":
            self.proxy_websocket()
            return
        # Serve index.html with dynamically injected config for root paths
        if clean_path in ["", "/", "/index.html"]:
            if os.path.exists(INDEX_PATH):
                with open(INDEX_PATH, "rb") as f:
                    content = f.read()

                local_ip = get_local_ip()
                tunnel_url_str = TUNNEL_URL if TUNNEL_URL else ""
                port_injection = (
                    f"<head><script>"
                    f"window.JARVIS_WS_PORT = {WS_PORT};"
                    f"window.JARVIS_LOCAL_IP = '{local_ip}';"
                    f"window.JARVIS_HTTP_PORT = {HTTP_PORT};"
                    f"window.JARVIS_TUNNEL_URL = '{tunnel_url_str}';"
                    f"</script>".encode("utf-8")
                )
                if b"<head>" in content:
                    content = content.replace(b"<head>", port_injection, 1)

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
                return

        return super().do_GET()

    def proxy_websocket(self):
        """Proxies WebSocket handshake and bidirectional stream to local WS_PORT."""
        upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            upstream.connect(("127.0.0.1", WS_PORT))
        except Exception as e:
            self.send_error(502, f"WebSocket upstream failure: {e}")
            return

        raw_req = f"{self.command} {self.path} {self.request_version}\r\n"
        for key, val in self.headers.items():
            raw_req += f"{key}: {val}\r\n"
        raw_req += "\r\n"
        upstream.sendall(raw_req.encode("latin1"))

        def pipe(src, dst):
            try:
                while True:
                    data = src.recv(8192)
                    if not data:
                        break
                    dst.sendall(data)
            except Exception:
                pass
            finally:
                try:
                    dst.shutdown(socket.SHUT_WR)
                except Exception:
                    pass

        client_sock = self.connection
        t1 = threading.Thread(target=pipe, args=(client_sock, upstream), daemon=True)
        t2 = threading.Thread(target=pipe, args=(upstream, client_sock), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        upstream.close()
        self.close_connection = True

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format, *args):
        # Suppress standard 200/304 noise, only log non-standard requests/errors
        if args and len(args) > 1 and str(args[1]) not in ["200", "304"]:
            print(f"[HTTP] {self.address_string()} - {format % args}")


def start_http_server(host: str, port: int) -> http.server.ThreadingHTTPServer:
    """Starts the static HTTP file server in a background daemon thread."""
    server = http.server.ThreadingHTTPServer((host, port), JarvisHTTPHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server


async def handle_gemini_to_browser(
    session, websocket, types, disconnect_event: asyncio.Event
):
    """
    Continuously receives responses from Gemini Live API and streams them
    to the browser WebSocket (audio PCM chunks as binary, text/status as JSON).
    Maintains multi-turn conversation continuously across turns until disconnect.
    """
    is_speaking = False

    try:
        while not disconnect_event.is_set():
            turn_items = 0
            async for response in session.receive():
                if disconnect_event.is_set():
                    break

                turn_items += 1

                # Check for Gemini Tool/Function Calls
                if getattr(response, "tool_call", None) and response.tool_call.function_calls:
                    function_responses = []
                    for call in response.tool_call.function_calls:
                        call_name = call.name
                        call_args = dict(call.args) if call.args else {}
                        call_id = call.id
                        print(f"⚡ [Gemini Tool Call]: {call_name} (args: {call_args}, id: {call_id})")

                        # 1. Notify browser UI
                        try:
                            await websocket.send(
                                json.dumps(
                                    {
                                        "type": "tool_call",
                                        "tool_name": call_name,
                                        "args": call_args,
                                    }
                                )
                            )
                        except Exception:
                            pass

                        # 2. Execute tool locally
                        tool_result = execute_tool(call_name, call_args)
                        print(f"⚡ [Tool Result]: {tool_result}")

                        function_responses.append(
                            types.FunctionResponse(
                                name=call_name,
                                response=tool_result,
                                id=call_id,
                            )
                        )

                    # 3. Send tool response back to Gemini session
                    try:
                        await session.send_tool_response(
                            function_responses=function_responses
                        )
                    except Exception as e:
                        print(f"[Tool Response Error]: {e}")

                server_content = response.server_content
                if server_content is None:
                    continue

                # 1. User Speech Transcription
                if (
                    server_content.input_transcription
                    and server_content.input_transcription.text
                ):
                    user_text = server_content.input_transcription.text.strip()
                    if user_text:
                        is_wake_word = any(
                            w in user_text.lower() for w in ["자비스", "jarvis", "자비"]
                        )
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "user_transcription",
                                    "text": user_text,
                                    "wake_word": is_wake_word,
                                }
                            )
                        )

                # 2. Jarvis Speech Transcription
                if (
                    server_content.output_transcription
                    and server_content.output_transcription.text
                ):
                    if not is_speaking:
                        is_speaking = True
                        await websocket.send(
                            json.dumps({"type": "speaking_state", "is_speaking": True})
                        )

                    await websocket.send(
                        json.dumps(
                            {
                                "type": "jarvis_transcription",
                                "text": server_content.output_transcription.text,
                            }
                        )
                    )

                # 3. Model Audio Response Parts (24kHz raw PCM bytes)
                model_turn = server_content.model_turn
                if model_turn:
                    for part in model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            # Send audio chunk as raw binary frame directly to browser
                            await websocket.send(part.inline_data.data)

                # 4. Turn Completion
                if server_content.turn_complete:
                    is_speaking = False
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "turn_complete",
                                "is_speaking": False,
                            }
                        )
                    )

            # Prevent tight-spinning if receive() yielded 0 items before next turn
            if turn_items == 0 and not disconnect_event.is_set():
                await asyncio.sleep(0.05)

    except asyncio.CancelledError:
        pass
    except ConnectionClosed:
        pass
    except Exception as e:
        if not disconnect_event.is_set():
            print(f"[Gemini->Browser 에러]: {e}")
    finally:
        disconnect_event.set()


async def handle_browser_to_gemini(
    websocket, session, types, disconnect_event: asyncio.Event
):
    """
    Listens for messages from the browser WebSocket:
    - Binary message: 16kHz PCM audio chunk from microphone -> send_realtime_input
    - String message: JSON command (e.g. text typing) -> send_client_content
    """
    try:
        async for message in websocket:
            if disconnect_event.is_set():
                break

            # 1. Binary Audio Frame (16kHz PCM from browser mic)
            if isinstance(message, bytes):
                if len(message) > 0:
                    try:
                        blob = types.Blob(
                            data=message,
                            mime_type=f"audio/pcm;rate={INPUT_SAMPLE_RATE}",
                        )
                        await session.send_realtime_input(media=blob)
                    except Exception as e:
                        if not disconnect_event.is_set():
                            print(f"[오디오 전송 경고]: {e}")

            # 2. JSON Message (Text input or control)
            elif isinstance(message, str):
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")

                # Typed user question
                if msg_type == "text_input":
                    text = data.get("text", "").strip()
                    if text:
                        print(f"⌨️ [웹 입력]: {text}")
                        try:
                            await session.send_client_content(
                                turns=types.Content(
                                    role="user",
                                    parts=[types.Part.from_text(text=text)],
                                ),
                                turn_complete=True,
                            )
                        except Exception as e:
                            print(f"[텍스트 전송 오류]: {e}")

                # Ping / Heartbeat
                elif msg_type == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))

    except asyncio.CancelledError:
        pass
    except ConnectionClosed:
        pass
    except Exception as e:
        if not disconnect_event.is_set():
            print(f"[Browser->Gemini 에러]: {e}")
    finally:
        disconnect_event.set()


async def websocket_handler(websocket):
    """
    Handles an incoming browser connection:
    Establishes a dedicated Gemini Live API session for this browser client.
    """
    print(f"\n🌐 [웹 클라이언트 접속]: {websocket.remote_address}")

    api_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)

    # Check if client provided api_key via query parameter (?api_key=...)
    if not api_key or api_key == "your_gemini_api_key_here":
        try:
            from urllib.parse import urlparse, parse_qs
            req_path = getattr(getattr(websocket, "request", None), "path", "")
            query = parse_qs(urlparse(req_path).query)
            if "api_key" in query and query["api_key"][0]:
                api_key = query["api_key"][0].strip()
        except Exception:
            pass

    if not api_key or api_key == "your_gemini_api_key_here":
        await websocket.send(
            json.dumps(
                {
                    "type": "error",
                    "code": "AUTH_KEY_MISSING",
                    "message": "GEMINI_API_KEY가 설정되지 않았습니다. 상단 [🔑 API 키] 버튼을 눌러 등록하시거나 Render 대시보드의 Environment에 등록해 주세요.",
                }
            )
        )
        await websocket.close()
        return

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        await websocket.send(
            json.dumps(
                {
                    "type": "error",
                    "message": "google-genai 패키지가 설치되지 않았습니다.",
                }
            )
        )
        await websocket.close()
        return

    # Notify browser that connection is starting
    await websocket.send(
        json.dumps(
            {
                "type": "status",
                "state": "connecting",
                "message": "Gemini Multimodal Live API에 연결 중...",
            }
        )
    )

    client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})

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
        tools=JARVIS_TOOLS,
        system_instruction=types.Content(
            parts=[types.Part.from_text(text=JARVIS_SYSTEM_INSTRUCTION)]
        ),
    )

    disconnect_event = asyncio.Event()

    try:
        async with client.aio.live.connect(
            model=GEMINI_MODEL, config=live_config
        ) as session:
            print("✨ [Gemini Live 연결 성공] 세션 활성화 완료")
            await websocket.send(
                json.dumps(
                    {
                        "type": "status",
                        "state": "ready",
                        "message": "자비스 시스템이 준비되었습니다.",
                        "model": GEMINI_MODEL,
                        "voice": JARVIS_VOICE,
                    }
                )
            )

            # Run bidirectional streaming tasks
            gemini_task = asyncio.create_task(
                handle_gemini_to_browser(session, websocket, types, disconnect_event)
            )
            browser_task = asyncio.create_task(
                handle_browser_to_gemini(websocket, session, types, disconnect_event)
            )

            await disconnect_event.wait()

            gemini_task.cancel()
            browser_task.cancel()
            await asyncio.gather(gemini_task, browser_task, return_exceptions=True)

    except ConnectionClosed:
        pass
    except Exception as e:
        err_str = str(e)
        print(f"❌ [Gemini Live 세션 오류]: {err_str}")
        user_msg = f"연결 오류: {err_str}"
        err_code = "CONNECTION_ERROR"
        if "exceeded your current quota" in err_str.lower() or "1011" in err_str:
            err_code = "QUOTA_EXCEEDED"
            user_msg = (
                "구글 Gemini Live API 쿼터(무료 사용량)가 초과되었습니다. "
                "Google AI Studio에서 '새 프로젝트(New Project)'로 새 API 키를 무료 발급받아 상단 [🔑 API 키] 버튼에 입력해 주십시오."
            )
        try:
            await websocket.send(
                json.dumps({"type": "error", "code": err_code, "message": user_msg})
            )
        except Exception:
            pass
    finally:
        print(f"🔒 [웹 클라이언트 연결 종료]: {websocket.remote_address}")


async def main():
    local_ip = get_local_ip()

    # 1. Start HTTP Static Server in background thread
    try:
        http_server = start_http_server(HOST, HTTP_PORT)
    except OSError as e:
        print(f"❌ [HTTP 서버 시작 실패]: 포트 {HTTP_PORT}가 이미 사용 중입니다. ({e})")
        sys.exit(1)

    # 2. Establish Cloudflare Tunnel for Anywhere/Cellular/External Access
    tunnel_url = start_cloudflare_tunnel(HTTP_PORT)

    print(
        r"""
   ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
   ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
   ██║███████║██████╔╝██║   ██║██║███████╗
██╗██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚████║██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
   [ Just A Rather Very Intelligent System ]
   >>> J.A.R.V.I.S. Multi-Device Web Server <<<
"""
    )
    print(f"🚀 Gemini 모델: {GEMINI_MODEL}")
    print(f"🎙️ 음성 목소리: {JARVIS_VOICE}")
    print("=" * 64)
    if tunnel_url:
        print("🌐 [외부 인터넷 접속 (LTE / 5G / 카페 / 어디서나)]:")
        print(f"   {tunnel_url}")
        print("   ※ HTTPS 보안 연결 적용 (아이폰/안드로이드 마이크 자동 허용)")
        print("-" * 64)
    print(f"🏠 [로컬 Wi-Fi 접속 (동일 공유기)]:  http://{local_ip}:{HTTP_PORT}")
    print(f"💻 [Mac 로컬 브라우저 접속]:        http://localhost:{HTTP_PORT}")
    print("=" * 64)
    print("💡 스마트폰 브라우저에서 위 주소에 접속하거나 PC 화면 우측 상단의")
    print("   '📱 모바일 연동' 버튼을 눌러 QR 코드를 스캔하시면 됩니다.")
    print("=" * 64)
    print("종료하려면 터미널에서 Ctrl+C 를 누르세요.\n")

    # 3. Start WebSocket Server
    try:
        async with serve(websocket_handler, HOST, WS_PORT):
            await asyncio.get_running_loop().create_future()  # run forever
    except OSError as e:
        print(f"❌ [WebSocket 서버 시작 실패]: 포트 {WS_PORT}가 이미 사용 중입니다. ({e})")
        sys.exit(1)
    finally:
        http_server.shutdown()
        global TUNNEL_PROCESS
        if TUNNEL_PROCESS and TUNNEL_PROCESS.poll() is None:
            try:
                TUNNEL_PROCESS.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[서버 종료] 자비스 웹 서버를 종료합니다.")
