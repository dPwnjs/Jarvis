"""
J.A.R.V.I.S. Tools & Dynamic Capability Registry
Provides anti-hallucination grounded tools and a persistent capability expansion workflow.
"""

import datetime
import json
import os
import math

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPABILITIES_FILE = os.path.join(BASE_DIR, "jarvis", "capabilities.json")

# Default capabilities baseline
DEFAULT_CAPABILITIES = {
    "active_tools": [
        {
            "name": "get_current_datetime",
            "description": "실시간 대한민국(KST) 날짜, 시간, 요일 조회",
            "status": "active"
        },
        {
            "name": "calculate_math",
            "description": "수학 수식 및 정확한 사칙/공학 계산",
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


def get_current_datetime() -> str:
    """
    현재의 정확한 대한민국 표준시(KST) 날짜, 시간, 요일을 반환합니다.
    사용자가 시간이나 날짜를 물어볼 때 환각(추측) 없이 정확한 현재 시각을 제공합니다.
    """
    now = datetime.datetime.now()
    days_ko = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    day_str = days_ko[now.weekday()]
    res = now.strftime(f"%Y년 %m월 %d일 {day_str} %H시 %M분 %S초")
    print(f"⚡ [도구 실행 - get_current_datetime]: {res}")
    return res


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
    request_and_register_capability,
    get_system_capabilities,
]

TOOL_MAP = {
    "get_current_datetime": get_current_datetime,
    "calculate_math": calculate_math,
    "request_and_register_capability": request_and_register_capability,
    "get_system_capabilities": get_system_capabilities,
}


def execute_tool(name: str, args: dict) -> dict:
    """
    지정된 도구를 실행하고 결과를 딕셔너리로 반환합니다.
    Gemini Live API의 FunctionResponse에 담겨 모델에게 전달됩니다.
    """
    if name in TOOL_MAP:
        try:
            fn = TOOL_MAP[name]
            result = fn(**args)
            return {"result": str(result)}
        except Exception as e:
            err_msg = f"도구 실행 중 오류가 발생했습니다: {str(e)}"
            print(f"❌ [도구 실행 오류 - {name}]: {err_msg}")
            return {"error": err_msg}
    err_msg = f"알 수 없는 도구 요청: {name}"
    print(f"❌ {err_msg}")
    return {"error": err_msg}

