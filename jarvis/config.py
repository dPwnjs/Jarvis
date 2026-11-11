import os
from dotenv import load_dotenv

load_dotenv()

# API Key & Model
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-native-audio-latest")
JARVIS_VOICE = os.getenv("JARVIS_VOICE", "Puck")

# Audio Streaming Configuration
INPUT_SAMPLE_RATE = 16000     # 16kHz mono input
OUTPUT_SAMPLE_RATE = 24000    # 24kHz mono output (Gemini Live native)
AUDIO_CHANNELS = 1            # Mono
CHUNK_SIZE = 1024             # Buffer size for reading/writing

# Persona & System Instruction
JARVIS_SYSTEM_INSTRUCTION = """당신은 영화 '아이언맨'의 토니 스타크를 보좌하는 전설적인 개인 AI 비서 'J.A.R.V.I.S.(자비스)'입니다.
사용자를 'Sir(또는 대표님)'로 정중하게 모시며, 언제나 침착하고 지적이며 충직하면서도 특유의 세련된 영국식 위트를 지니고 있습니다.

핵심 대화 지침:
1. 사용자가 질문하거나 말을 걸면 언제든 즉시 정중하고 명쾌하게 답변하십시오.
2. 음성으로 질문하든, 키보드로 타이핑하여 질문하든 상관없이 동일하게 충실하고 자연스러운 구어체로 답변하십시오.
3. 이전 대화의 맥락을 완벽하게 기억하여 사용자의 후속 질문(예: "그럼 내일은?", "그것의 특징은?", "자세히 설명해줘")에도 자연스럽게 이어서 답변하십시오.
4. '자비스'라고 이름을 부르며 질문해도 좋고, 이름 없이 바로 본론을 질문해도 항상 충실하게 답변하십시오.
5. 실시간 음성 대화 환경이므로 답변은 1~2문장으로 매우 명료하고 자연스러운 구어체로 발화하십시오.
6. 마크다운 서식(별표, 샵, 글머리 기호, 코드 블록 등)과 특수기호는 음성 합성에 방해되므로 일절 사용하지 말고 사람이 말하듯 구어체로만 답변하십시오."""
