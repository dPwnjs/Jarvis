# 🦾 J.A.R.V.I.S. (Just A Rather Very Intelligent System)

영화 **아이언맨(Iron Man)**의 인공지능 개인 비서 '자비스'를 모티브로 한 **초저지연 실시간 양방향 음성 대화기**입니다.  
최신 **Gemini 2.0 Multimodal Live API (WebSockets)**를 활용하여 텍스트 변환 지연 없이, 오디오를 오디오로 직접 주고받는 초고속 음성 대화를 구현합니다.

---

## ⚡ 핵심 기능

1. **초저지연 실시간 양방향 음성 & 텍스트 동시 지원 (Dual Modality)**
   - **🎙️ 음성 대화**: 마이크(16kHz PCM)를 항상 켜두고 자연스럽게 말로 대화
   - **⌨️ 텍스트 타이핑**: 터미널에 직접 질문을 타이핑하고 Enter를 치면 음성과 텍스트로 즉각 답변
2. **말끊김 방지 (No Interruption / Continuous Speech)**
   - 발화 도중 외부 소음이나 스피커 소리로 인해 자비스의 말이 도중에 끊기지 않고 끝까지 안정적으로 답변을 완수합니다.
3. **자비스 시그니처 페르소나 탑재**
   - 영국식 위트와 차분하고 지적인 어조 (`Puck` 보이스)
   - 음성 인터페이스에 맞춘 간결하고 명확한 대화 스타일 (1~2문장 구어체)

---

## 🛠️ 시스템 요구 사항 (Mac Apple Silicon)

- **OS**: macOS (Apple Silicon M1 / M2 / M3 / M4 권장)
- **Python**: Python 3.10 이상 권장 (3.11 추천)
- **오디오 라이브러리**: `portaudio` (Homebrew로 설치)

---

## 🚀 빠른 시작 가이드 (Quick Start)

### 1. 포트오디오(PortAudio) 및 Python 설치
터미널에서 아래 명령어로 오디오 드라이버와 Python 3.11을 설치합니다:
```bash
brew install portaudio python@3.11
```

### 2. 가상환경 생성 및 라이브러리 설치
프로젝트 루트 디렉터리(`~/Desktop/Jarvis`)에서 가상환경을 생성하고 패키지를 설치합니다:
```bash
# Python 3.11 가상환경 생성
/opt/homebrew/opt/python@3.11/bin/python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# 의존성 패키지 설치
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Gemini API 키 설정
1. [Google AI Studio](https://aistudio.google.com/apikey)에서 무료 API 키를 발급받습니다.
2. `.env` 파일을 열고 발급받은 키를 입력합니다:
```ini
GEMINI_API_KEY=AIzaSyYourActualAPIKeyHere...
JARVIS_VOICE=Puck
GEMINI_MODEL=gemini-2.0-flash-exp
```

> **TIP - 목소리 옵션**:
> - `Puck`: 영국식 억양이 살짝 느껴지는 지적이고 위트 있는 목소리 (자비스 추천)
> - `Charon`: 깊은 중저음의 묵직하고 차분한 목소리
> - `Kore`: 차분하고 부드러운 목소리

### 4. 자비스 실행하기

#### 방법 A: 🌐 웹 인터페이스 실행 (강력 추천!)
아이언맨 토니 스타크의 랩실처럼 화려한 **아크 리액터 HUD 웹 화면**에서 대화할 수 있습니다:
```bash
./run_web.sh
```
* 명령어를 실행하면 웹 서버가 시작되고 기본 브라우저(`http://localhost:8000`)가 자동으로 열립니다.
* 화면 가운데의 **아크 리액터(Arc Reactor)**를 클릭하면 자비스가 온라인으로 연결되며, 음성 오디오 비주얼라이저와 실시간 대화 콘솔이 활성화됩니다.
* 마이크로 직접 말하거나, 하단 입력창에 타이핑하여 실시간으로 음성 답변을 주고받을 수 있습니다.

---

#### 방법 B: 💻 터미널 CLI 실행
기존 터미널 창에서 경량으로 실행하고자 할 때 사용합니다:
```bash
./run.sh
```

실행 후 화면에 `🟢 [대기 중 (말씀하시거나 타이핑하세요)]`가 뜨면 아래 두 가지 방식 중 편한 방식으로 대화하세요:
- **음성 대화**: 마이크를 향해 *"자비스, 시스템 상태 보고해줘"* 또는 *"오늘 날씨 어때?"* 라고 말합니다.
- **키보드 타이핑**: 터미널에 곧바로 텍스트를 입력하고 Enter를 누르면 자비스가 답변을 읽어주고 화면에 출력합니다.
- **종료**: `exit`, `quit`, `q`, `종료` 입력 또는 `Ctrl + C` 키를 누르면 안전하게 종료됩니다.

---

## 📂 프로젝트 구조

```
Jarvis/
├── web/
│   └── index.html         # 아이언맨 아크 리액터 HUD 웹 인터페이스 (HTML5/Canvas/Web Audio)
├── web_jarvis.py          # 웹 서버 및 브라우저-Gemini Live WebSocket 브릿지
├── run_web.sh             # 웹 인터페이스 원클릭 실행 스크립트
├── live_jarvis.py         # 터미널용 실시간 오디오 WebSocket 클라이언트
├── run.sh                 # 터미널용 실행 스크립트
├── main.py                # 진입점
├── requirements.txt       # 의존성 패키지 목록
├── .env                   # API 키 보관 파일
└── jarvis/
    ├── config.py          # 모델, 오디오 규격, 시스템 프롬프트
    └── audio_manager.py   # 로컬 오디오 캡처 & 재생 관리
```
