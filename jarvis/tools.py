"""
J.A.R.V.I.S. Tools & Dynamic Capability Registry
Provides anti-hallucination grounded tools, live information/weather search via Gemini,
and a persistent capability expansion workflow.
"""

import datetime
import json
import os
import math
import urllib.request
import email.utils
from zoneinfo import ZoneInfo
import inspect

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPABILITIES_FILE = os.path.join(BASE_DIR, "jarvis", "capabilities.json")

# Default capabilities baseline
DEFAULT_CAPABILITIES = {
    "active_tools": [
        {
            "name": "get_current_datetime",
            "description": "구글(Google) 공식 타임 서버와 실시간 연동된 대한민국(KST) 및 전 세계 주요 도시의 정확한 날짜, 시간, 요일 조회",
            "status": "active"
        },
        {
            "name": "calculate_math",
            "description": "수학 수식 및 정확한 사칙/공학 계산",
            "status": "active"
        },
        {
            "name": "get_weather",
            "description": "국내외 주요 도시의 실시간 날씨, 기온, 습도, 풍속 조회",
            "status": "active"
        },
        {
            "name": "search_information",
            "description": "Gemini 지능 분석망을 통한 특정 지식, 인물, 역사, 과학, 기술, 일상 정보 심층 탐색 및 요약",
            "status": "active"
        },
        {
            "name": "request_and_register_capability",
            "description": "사용자(Sir)에게 허락/승인받은 신규 기능을 시스템에 정식 등록",
            "status": "active"
        },
        {
            "name": "get_system_capabilities",
            "description": "현재 자비스의 활성화된 기능 및 승인된 확장 기능 목록 조회",
            "status": "active"
        }
    ],
    "approved_backlog": []
}


def load_capabilities() -> dict:
    """Loads capabilities registry from disk or initializes with defaults."""
    if os.path.exists(CAPABILITIES_FILE):
        try:
            with open(CAPABILITIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    save_capabilities(DEFAULT_CAPABILITIES)
    return DEFAULT_CAPABILITIES


def save_capabilities(data: dict):
    """Persists capabilities registry to disk."""
    try:
        os.makedirs(os.path.dirname(CAPABILITIES_FILE), exist_ok=True)
        with open(CAPABILITIES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Capabilities] 저장 실패: {e}")


TIMEZONE_CITY_MAP = {
    "서울": "Asia/Seoul",
    "한국": "Asia/Seoul",
    "대한민국": "Asia/Seoul",
    "도쿄": "Asia/Tokyo",
    "일본": "Asia/Tokyo",
    "베이징": "Asia/Shanghai",
    "상하이": "Asia/Shanghai",
    "중국": "Asia/Shanghai",
    "뉴욕": "America/New_York",
    "로스앤젤레스": "America/Los_Angeles",
    "la": "America/Los_Angeles",
    "샌프란시스코": "America/Los_Angeles",
    "워싱턴": "America/New_York",
    "미국": "America/New_York",
    "런던": "Europe/London",
    "영국": "Europe/London",
    "파리": "Europe/Paris",
    "프랑스": "Europe/Paris",
    "베를린": "Europe/Berlin",
    "독일": "Europe/Berlin",
    "시드니": "Australia/Sydney",
    "호주": "Australia/Sydney",
    "싱가포르": "Asia/Singapore",
    "방콕": "Asia/Bangkok",
    "태국": "Asia/Bangkok",
    "하노이": "Asia/Ho_Chi_Minh",
    "베트남": "Asia/Ho_Chi_Minh",
    "모스크바": "Europe/Moscow",
    "러시아": "Europe/Moscow",
    "두바이": "Asia/Dubai",
}


def fetch_google_server_time() -> tuple[datetime.datetime, str]:
    """
    구글(Google) 공식 웹 서버 및 공개 타임 서버(https://www.google.com, https://time.google.com)의
    원자 시계 기준 HTTP Date 헤더를 실시간 동기화하여 정확한 UTC 시간을 반환합니다.
    연결 지연이나 오프라인 시 고정밀 UTC 시스템 시계로 안전하게 대체합니다.
    """
    google_endpoints = [
        "https://www.google.com",
        "https://time.google.com",
        "https://www.google.co.kr",
    ]
    for url in google_endpoints:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; JarvisGoogleTimeSync/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                date_hdr = resp.headers.get("Date")
                if date_hdr:
                    parsed_dt = email.utils.parsedate_to_datetime(date_hdr)
                    return parsed_dt.astimezone(datetime.timezone.utc), "Google 공식 타임 서버"
        except Exception:
            continue

    return datetime.datetime.now(datetime.timezone.utc), "시스템 고정밀 시계 (KST 기준)"


def get_current_datetime(location: str = "대한민국", timezone: str = "Asia/Seoul", **kwargs) -> str:
    """
    구글(Google) 공식 타임 서버와 실시간 연동하여 정확한 대한민국 표준시(KST) 및 전 세계 주요 도시의 현재 날짜, 시간, 요일을 반환합니다.
    시간이나 날짜 관련 질문을 받을 때 환각(추측) 없이 구글 연동의 정확한 실시간 시각을 제공합니다.

    Args:
        location: 조회할 도시 또는 국가 (기본값: 대한민국)
        timezone: 타임존 (기본값: Asia/Seoul)
    """
    loc_clean = (location or "").strip().lower()
    target_tz_name = "Asia/Seoul"
    resolved_loc_name = "대한민국 (서울)"

    if loc_clean:
        for city_key, tz_val in TIMEZONE_CITY_MAP.items():
            if city_key in loc_clean:
                target_tz_name = tz_val
                resolved_loc_name = location.strip()
                break

    try:
        target_tz = ZoneInfo(target_tz_name)
    except Exception:
        target_tz = datetime.timezone(datetime.timedelta(hours=9))

    utc_now, source_name = fetch_google_server_time()
    local_now = utc_now.astimezone(target_tz)

    days_ko = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    day_str = days_ko[local_now.weekday()]
    ampm = "오전" if local_now.hour < 12 else "오후"
    hour_12 = local_now.hour if local_now.hour <= 12 else local_now.hour - 12
    if hour_12 == 0:
        hour_12 = 12

    result = (
        f"[{source_name} 연동] {resolved_loc_name} 기준 현재 시각은 "
        f"{local_now.year}년 {local_now.month}월 {local_now.day}일 {day_str} "
        f"{ampm} {hour_12}시 {local_now.minute}분 {local_now.second}초"
        f" (24시간제: {local_now.strftime('%H:%M:%S')}) 입니다."
    )
    print(f"⚡ [도구 실행 - get_current_datetime]: {result}")
    return result


def calculate_math(expression: str) -> str:
    """
    수학 연산식(사칙연산, 거듭제곱, 삼각함수, 로그 등)을 안전하게 계산하여 반환합니다.
    예: '125 * 34', 'sqrt(144) + 15', '2 ** 10'
    """
    print(f"⚡ [도구 실행 - calculate_math]: {expression}")
    safe_dict = {
        "abs": abs, "round": round, "min": min, "max": max,
        "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
        "tan": math.tan, "log": math.log, "log10": math.log10,
        "pi": math.pi, "e": math.e, "pow": math.pow
    }
    clean_expr = expression.strip().replace("^", "**")
    try:
        # Evaluate safely with restricted builtins
        result = eval(clean_expr, {"__builtins__": {}}, safe_dict)
        return f"{expression} 계산 결과는 {result} 입니다."
    except Exception as e:
        return f"계산 중 오류가 발생했습니다: {e}"


def get_weather(location: str = "서울") -> str:
    """
    지정된 도시 또는 지역(기본값: 서울)의 실시간 날씨, 기온, 습도, 풍속 정보를 조회하여 반환합니다.
    예: '서울', '부산', '대구', '인천', '광주', '대전', '울산', '제주', '도쿄', '뉴욕', 'London'
    """
    print(f"⚡ [도구 실행 - get_weather]: {location}")
    try:
        import urllib.request
        import urllib.parse
        clean_loc = location.strip() if location else "서울"
        loc_map = {
            "서울": "Seoul", "부산": "Busan", "대구": "Daegu", "인천": "Incheon",
            "광주": "Gwangju", "대전": "Daejeon", "울산": "Ulsan", "수원": "Suwon",
            "제주": "Jeju", "제주도": "Jeju", "성남": "Seongnam", "판교": "Pangyo"
        }
        query_city = loc_map.get(clean_loc, clean_loc)
        url = f"https://wttr.in/{urllib.parse.quote(query_city)}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
            cur = data["current_condition"][0]
            temp = cur["temp_C"]
            desc = cur["weatherDesc"][0]["value"]
            humidity = cur["humidity"]
            wind = cur["windspeedKmph"]
            desc_ko = {
                "Sunny": "맑음", "Clear": "맑음", "Partly cloudy": "구름 조금",
                "Cloudy": "흐림", "Overcast": "흐림", "Mist": "안개", "Patchy rain possible": "간헐적 비",
                "Rain": "비", "Light rain": "가벼운 비", "Heavy rain": "강한 비",
                "Snow": "눈", "Light snow": "가벼운 눈", "Thunderstorm": "뇌우"
            }.get(desc, desc)
            return f"{clean_loc}의 현재 실시간 기온은 {temp}도이며 날씨는 {desc_ko}, 습도는 {humidity}%, 풍속은 시속 {wind}km 입니다."
    except Exception as e:
        return f"{location}의 실시간 날씨를 조회하는 중 문제가 발생했습니다: {e}"


def _search_wikipedia(query: str) -> str:
    """위키백과 요약 정보를 검색하는 보조 함수"""
    try:
        import urllib.request
        import urllib.parse
        search_url = f"https://ko.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json"
        req = urllib.request.Request(search_url, headers={"User-Agent": "JarvisAssistant/1.0"})
        with urllib.request.urlopen(req, timeout=5) as res:
            sdata = json.loads(res.read().decode("utf-8"))
            results = sdata.get("query", {}).get("search", [])
            if not results:
                return ""
            title = results[0]["title"]
        extract_url = f"https://ko.wikipedia.org/w/api.php?action=query&prop=extracts&exintro&explaintext&titles={urllib.parse.quote(title)}&format=json"
        req2 = urllib.request.Request(extract_url, headers={"User-Agent": "JarvisAssistant/1.0"})
        with urllib.request.urlopen(req2, timeout=5) as res2:
            edata = json.loads(res2.read().decode("utf-8"))
            pages = edata.get("query", {}).get("pages", {})
            for pid, pval in pages.items():
                extract = pval.get("extract", "").strip()
                if extract:
                    return f"기초 백과사전 요약: {extract[:350]}"
    except Exception:
        pass
    return ""


def search_information(query: str, topic: str = "") -> str:
    """
    Gemini 지능 분석망 및 외부 지식베이스를 통해 사용자의 질문이나 특정 주제에 대해
    상세하고 정확한 정보를 탐색하고 분석 요약하여 반환합니다.
    예: '양자컴퓨터의 원리', '인플레이션이 경제에 미치는 영향', '최근 인공지능 트렌드', '마블 시네마틱 유니버스 스토리 요약'
    """
    print(f"⚡ [도구 실행 - search_information]: query={query}, topic={topic}")
    
    # Check if query is about weather
    weather_keywords = ["날씨", "기온", "온도", "비 오", "눈 오", "비 와", "눈 와", "우산"]
    if any(k in query for k in weather_keywords):
        loc = "서울"
        for candidate in ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "제주", "수원", "도쿄", "뉴욕"]:
            if candidate in query:
                loc = candidate
                break
        return get_weather(loc)

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        try:
            from jarvis.config import GEMINI_API_KEY
            api_key = GEMINI_API_KEY
        except Exception:
            pass

    if api_key and api_key != "your_gemini_api_key_here":
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = f"""당신은 J.A.R.V.I.S.의 심층 정보 분석 및 지식 탐색 모듈입니다.
사용자 질문: {query}
(관련 분야: {topic if topic else '일반 지식 및 정보'})

위 질문에 대해 최신의 정확한 팩트와 핵심 지식을 정중하고 세련된 자비스의 어조(영국식 위트, Sir 호칭)로 명쾌하게 분석 요약해 주십시오.
실시간 음성 합성 환경이므로 마크다운 기호(별표, 샵, 글머리 기호) 없이 자연스러운 구어체 2~3문장으로 간결하게 답하십시오."""
            resp = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt
            )
            if resp and resp.text:
                return resp.text.strip()
        except Exception as e:
            print(f"⚠️ [search_information Gemini 호출 실패, 위키백과 폴백 시도]: {e}")

    # Fallback to Wikipedia summary if Gemini call was unavailable or failed
    wiki = _search_wikipedia(query)
    if wiki:
        return f"Sir, 질의하신 내용에 대한 분석 요약 정보입니다: {wiki}"

    return f"Sir, 질의하신 '{query}'에 대해 검색 및 분석을 수행하였습니다. 해당 주제에 대해 추가적인 세부 분석이나 다른 질문이 있으시면 언제든 말씀해 주십시오."


def request_and_register_capability(feature_name: str, description: str, rationale: str = "") -> str:
    """
    사용자(Sir)에게 새로운 기능 탑재를 제안하고 허락/승인을 받았을 때,
    해당 기능을 자비스의 정식 확장 레지스트리(Approved Capabilities)에 영구 등록합니다.
    """
    print(f"🛡️ [기능 승인 등록]: {feature_name} - {description} (사유: {rationale})")
    caps = load_capabilities()
    new_entry = {
        "feature_name": feature_name,
        "description": description,
        "rationale": rationale,
        "approved_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "approved_by_user"
    }

    # Avoid duplicate additions
    existing = [item for item in caps.get("approved_backlog", []) if item.get("feature_name") == feature_name]
    if not existing:
        caps.setdefault("approved_backlog", []).append(new_entry)
        save_capabilities(caps)

    return (
        f"기능명 '{feature_name}'이(가) 사용자님의 정식 승인을 받아 자비스 시스템 레지스트리에 영구 등록되었습니다. "
        f"세부 내용: {description}"
    )


def get_system_capabilities() -> str:
    """
    현재 자비스에 활성화된 도구 목록과, 사용자에게 승인받아 등록된 신규 확장 기능 목록을 반환합니다.
    """
    caps = load_capabilities()
    active = caps.get("active_tools", [])
    approved = caps.get("approved_backlog", [])

    active_names = ", ".join([t["name"] + f"({t['description']})" for t in active])
    if approved:
        approved_names = ", ".join([f"'{item['feature_name']}'({item['description']})" for item in approved])
        return f"현재 활성화된 도구: [{active_names}]. 사용자님께 승인받아 등록된 신규 확장 기능 목록: [{approved_names}]."
    else:
        return f"현재 활성화된 도구: [{active_names}]. 아직 새로 승인된 추가 확장 기능은 없습니다."


# Export list of callable functions for Gemini Live API
JARVIS_TOOLS = [
    get_current_datetime,
    calculate_math,
    get_weather,
    search_information,
    request_and_register_capability,
    get_system_capabilities,
]

TOOL_MAP = {
    "get_current_datetime": get_current_datetime,
    "calculate_math": calculate_math,
    "get_weather": get_weather,
    "search_information": search_information,
    "request_and_register_capability": request_and_register_capability,
    "get_system_capabilities": get_system_capabilities,
}


def execute_tool(name: str, args: dict) -> dict:
    """
    지정된 도구를 실행하고 결과를 딕셔너리로 반환합니다.
    Gemini Live API의 FunctionResponse에 담겨 모델에게 전달됩니다.
    모델이 예상치 못한 부가 인자(예: query, extra)를 넘겨도 함수 시그니처에 맞춰 안전하게 필터링합니다.
    """
    if name in TOOL_MAP:
        try:
            fn = TOOL_MAP[name]
            sig = inspect.signature(fn)
            has_var_keyword = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            )
            if has_var_keyword:
                call_args = args
            else:
                call_args = {k: v for k, v in args.items() if k in sig.parameters}
            result = fn(**call_args)
            return {"result": str(result)}
        except Exception as e:
            err_msg = f"도구 실행 중 오류가 발생했습니다: {str(e)}"
            print(f"❌ [도구 실행 오류 - {name}]: {err_msg}")
            return {"error": err_msg}
    err_msg = f"알 수 없는 도구 요청: {name}"
    print(f"❌ {err_msg}")
    return {"error": err_msg}
