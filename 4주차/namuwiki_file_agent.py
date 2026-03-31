#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ollama(qwen2.5-coder:7b) 기반 "나무위키 검색 + 파일 저장" 에이전트 예제

요구사항 요약
1) Tool 함수 2개 구현
   - file_manager: read / write / append
   - namuwiki_search: 나무위키 본문 스크래핑
2) Ollama Tool(JSON Schema) 정의
3) Multi-step Tool Calling 루프 구현
4) 터미널 로그로 실행 흐름이 잘 보이도록 출력

실행 전 준비
1) Ollama가 실행 중이어야 합니다.
2) 모델이 준비되어 있어야 합니다.
   ollama pull qwen2.5-coder:7b
3) 의존성 설치
   pip install ollama requests beautifulsoup4

실행
python namuwiki_file_agent.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote

import ollama
import requests
from bs4 import BeautifulSoup


# ====== 에이전트 설정값 ======
MODEL_NAME = "qwen2.5-coder:7b"
MAX_AGENT_STEPS = 8
MAX_WIKI_TEXT_LENGTH = 2000
HTTP_TIMEOUT_SECONDS = 12

# 나무위키 접근 시 봇 차단을 완화하기 위해 일반 브라우저처럼 보이는 헤더를 사용합니다.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


# ====== System Prompt ======
# LLM에게 "언제 어떤 툴을 써야 하는지"를 명확히 지시합니다.
SYSTEM_PROMPT = """
당신은 로컬 환경에서 실행되는 도구 사용 AI 에이전트입니다.
사용자의 요청을 해결하기 위해 아래 규칙을 따르세요.

규칙:
1) 나무위키 정보가 필요하면 반드시 namuwiki_search 도구를 먼저 호출하세요.
2) 파일 저장/읽기/추가가 필요하면 file_manager 도구를 사용하세요.
3) 사용자가 "검색 후 저장"을 요청하면:
   (a) namuwiki_search 호출
   (b) 결과를 file_manager(action="write")로 저장
   (c) 최종 완료 보고
4) 도구 실행이 실패하면 원인을 설명하고 대안을 제시하세요.
5) 최종 응답은 간결하고 명확한 한국어로 작성하세요.
""".strip()


# ====== Ollama Tools(JSON Schema) 정의 ======
# 주의: 여기서는 "파이썬 함수"를 직접 넘기지 않고, JSON Schema로 툴을 명시합니다.
# 이후 LLM이 tool_call을 반환하면 우리가 직접 Python 함수를 매핑 실행합니다.
TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "file_manager",
            "description": "로컬 텍스트 파일 읽기/쓰기/추가를 수행합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write", "append"],
                        "description": "파일 작업 종류",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "대상 파일 경로",
                    },
                    "content": {
                        "type": "string",
                        "description": "write/append 시 사용할 텍스트(read 시 빈 문자열)",
                    },
                },
                "required": ["action", "file_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "namuwiki_search",
            "description": (
                "키워드 기반으로 나무위키 문서를 열어 의미 있는 본문 텍스트를 추출합니다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "검색할 나무위키 키워드",
                    }
                },
                "required": ["keyword"],
            },
        },
    },
]


def _json_result(data: Dict[str, Any]) -> str:
    """Tool 결과를 LLM이 처리하기 쉬운 JSON 문자열로 통일합니다."""
    return json.dumps(data, ensure_ascii=False)


def file_manager(action: str, file_path: str, content: str) -> str:
    """
    로컬 파일을 read/write/append 하는 Tool 함수.

    Parameters
    ----------
    action : str
        read | write | append
    file_path : str
        대상 파일 경로
    content : str
        write/append 시 저장할 내용 (read에서는 무시 가능)
    """
    try:
        path = Path(file_path).expanduser()

        if action == "read":
            if not path.exists():
                return _json_result(
                    {
                        "ok": False,
                        "action": action,
                        "file_path": str(path),
                        "error": "파일이 존재하지 않습니다.",
                    }
                )
            text = path.read_text(encoding="utf-8")
            return _json_result(
                {
                    "ok": True,
                    "action": action,
                    "file_path": str(path),
                    "content": text,
                    "content_length": len(text),
                }
            )

        if action == "write":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return _json_result(
                {
                    "ok": True,
                    "action": action,
                    "file_path": str(path),
                    "written_chars": len(content),
                }
            )

        if action == "append":
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as file:
                file.write(content)
            return _json_result(
                {
                    "ok": True,
                    "action": action,
                    "file_path": str(path),
                    "appended_chars": len(content),
                }
            )

        return _json_result(
            {
                "ok": False,
                "action": action,
                "file_path": str(path),
                "error": "action은 read/write/append 중 하나여야 합니다.",
            }
        )
    except Exception as exc:  # 예외를 JSON으로 감싸 반환해 에이전트가 후속 판단 가능하게 만듭니다.
        return _json_result(
            {
                "ok": False,
                "action": action,
                "file_path": file_path,
                "error": f"file_manager 예외 발생: {exc}",
            }
        )


def namuwiki_search(keyword: str) -> str:
    """
    나무위키 문서에서 의미 있는 텍스트를 추출하는 Tool 함수.

    동작:
    1) /w/{keyword} URL 접근
    2) 본문 영역 후보에서 문단/목록/헤더 텍스트 추출
    3) 중복 정리 후 길이 제한(기본 2000자)
    """
    try:
        encoded_keyword = quote(keyword, safe="")
        url = f"https://namu.wiki/w/{encoded_keyword}"

        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=HTTP_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            return _json_result(
                {
                    "ok": False,
                    "keyword": keyword,
                    "source_url": url,
                    "status_code": response.status_code,
                    "error": "나무위키 페이지를 정상적으로 불러오지 못했습니다.",
                }
            )

        soup = BeautifulSoup(response.text, "html.parser")

        # 불필요한 요소 제거 (스크립트/스타일/광고성 영역 가능성 최소화)
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        # 본문 영역 후보를 순차 탐색해 가장 가능성 높은 컨테이너를 선택합니다.
        content_root = (
            soup.select_one("article")
            or soup.select_one("main")
            or soup.select_one("div.wiki-content")
            or soup.select_one("div.wiki-body")
            or soup.body
        )

        if content_root is None:
            return _json_result(
                {
                    "ok": False,
                    "keyword": keyword,
                    "source_url": response.url,
                    "error": "본문 영역을 찾지 못했습니다.",
                }
            )

        # 의미 있는 텍스트 후보를 우선적으로 수집합니다.
        fragments: List[str] = []
        for node in content_root.select("h1, h2, h3, h4, p, li"):
            text = " ".join(node.get_text(" ", strip=True).split())
            # 너무 짧은 조각은 잡음일 확률이 높아 제외
            if len(text) >= 8:
                fragments.append(text)

        # 구조 셀렉터 추출이 비어 있을 때를 대비해 전체 텍스트 백업 추출
        if not fragments:
            backup = content_root.get_text("\n", strip=True)
            for line in backup.splitlines():
                cleaned = " ".join(line.split())
                if len(cleaned) >= 8:
                    fragments.append(cleaned)

        # 순서 보존 중복 제거
        unique_fragments: List[str] = []
        seen = set()
        for item in fragments:
            if item not in seen:
                seen.add(item)
                unique_fragments.append(item)

        final_text = "\n".join(unique_fragments).strip()
        final_text = final_text[:MAX_WIKI_TEXT_LENGTH]

        return _json_result(
            {
                "ok": True,
                "keyword": keyword,
                "source_url": response.url,
                "content": final_text,
                "content_length": len(final_text),
            }
        )
    except requests.RequestException as exc:
        return _json_result(
            {
                "ok": False,
                "keyword": keyword,
                "error": f"HTTP 요청 실패: {exc}",
            }
        )
    except Exception as exc:
        return _json_result(
            {
                "ok": False,
                "keyword": keyword,
                "error": f"namuwiki_search 예외 발생: {exc}",
            }
        )


def _parse_tool_arguments(raw_args: Any) -> Dict[str, Any]:
    """
    Ollama tool arguments는 dict 또는 JSON 문자열로 올 수 있어 안전하게 파싱합니다.
    """
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        stripped = raw_args.strip()
        if not stripped:
            return {}
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def _execute_tool(tool_name: str, args: Dict[str, Any]) -> str:
    """Tool 이름으로 실제 Python 함수를 실행하는 디스패처."""
    if tool_name == "file_manager":
        return file_manager(
            action=str(args.get("action", "")),
            file_path=str(args.get("file_path", "")),
            content=str(args.get("content", "")),
        )
    if tool_name == "namuwiki_search":
        return namuwiki_search(keyword=str(args.get("keyword", "")))

    return _json_result(
        {
            "ok": False,
            "error": f"알 수 없는 tool입니다: {tool_name}",
            "received_args": args,
        }
    )


def _response_to_dict(response: Any) -> Dict[str, Any]:
    """
    ollama.ChatResponse 객체/딕셔너리 양쪽을 모두 지원하기 위한 변환 헬퍼.
    """
    if isinstance(response, dict):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump()
    # 예외적으로 다른 타입이 올 때 최소한의 정보라도 남깁니다.
    return {"message": {"content": str(response)}}


def _normalize_tool_calls_from_object(obj: Any) -> List[Dict[str, Any]]:
    """
    모델이 반환한 다양한 JSON 형태를 표준 tool_calls 형태로 정규화합니다.

    지원 예시:
    - {"name":"namuwiki_search","arguments":{"keyword":"젤다"}}
    - {"function":{"name":"...","arguments":{...}}}
    - {"tool_calls":[...]}
    - [ {name/arguments}, ... ]
    """
    # 형태 1) {"tool_calls":[...]}
    if isinstance(obj, dict) and isinstance(obj.get("tool_calls"), list):
        normalized: List[Dict[str, Any]] = []
        for item in obj["tool_calls"]:
            normalized.extend(_normalize_tool_calls_from_object(item))
        return normalized

    # 형태 2) {"function":{"name":"...","arguments":...}}
    if isinstance(obj, dict) and isinstance(obj.get("function"), dict):
        fn = obj["function"]
        name = fn.get("name")
        if name:
            return [{"function": {"name": str(name), "arguments": fn.get("arguments", {})}}]

    # 형태 3) {"name":"...","arguments":...}
    if isinstance(obj, dict) and obj.get("name"):
        return [
            {
                "function": {
                    "name": str(obj.get("name")),
                    "arguments": obj.get("arguments", {}),
                }
            }
        ]

    # 형태 4) [{"name":"...","arguments":...}, ...]
    if isinstance(obj, list):
        normalized = []
        for item in obj:
            normalized.extend(_normalize_tool_calls_from_object(item))
        return normalized

    return []


def _extract_tool_calls_from_text_content(content: str) -> List[Dict[str, Any]]:
    """
    모델이 `tool_calls` 필드 대신 content에 JSON 문자열을 넣어 보낼 때를 위한 fallback 파서.
    """
    if not content.strip():
        return []

    candidates: List[str] = [content.strip()]

    # ```json ... ``` 코드블록 안 JSON도 파싱 대상에 포함
    for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", content, flags=re.IGNORECASE):
        block = match.group(1).strip()
        if block:
            candidates.append(block)

    # 문장+JSON 혼합 응답 대비: 가장 바깥쪽 객체/배열 추출 시도
    if "{" in content and "}" in content:
        start = content.find("{")
        end = content.rfind("}")
        if end > start:
            candidates.append(content[start : end + 1].strip())
    if "[" in content and "]" in content:
        start = content.find("[")
        end = content.rfind("]")
        if end > start:
            candidates.append(content[start : end + 1].strip())

    # 중복 후보 제거
    dedup_candidates = []
    seen = set()
    for item in candidates:
        if item not in seen:
            seen.add(item)
            dedup_candidates.append(item)

    for candidate in dedup_candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        normalized = _normalize_tool_calls_from_object(parsed)
        if normalized:
            return normalized

    return []


def run_agent(user_input: str) -> str:
    """
    Multi-step Tool Calling의 핵심 루프.

    루프 흐름:
    1) user 메시지를 messages에 추가
    2) ollama.chat 호출 (tools 포함)
    3) tool_calls 존재 시:
       - assistant 메시지 추가
       - 각 tool_call 실행 후 role='tool' 메시지 추가
       - 다시 2)로 반복
    4) tool_calls가 없으면 최종 응답 출력 후 종료
    """
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    for step in range(1, MAX_AGENT_STEPS + 1):
        print(f"\n[STEP {step}] ollama.chat 호출 중...")

        response = ollama.chat(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS,
            options={"temperature": 0.1},
        )
        response_dict = _response_to_dict(response)
        assistant_message = response_dict.get("message", {})
        assistant_content = (assistant_message.get("content") or "").strip()
        tool_calls = assistant_message.get("tool_calls") or []

        # 일부 모델은 tool_calls 필드 대신 JSON 텍스트를 content로 반환합니다.
        # 이 경우 content를 파싱해 "의도된 tool call"을 복구합니다.
        if not tool_calls and assistant_content:
            recovered_calls = _extract_tool_calls_from_text_content(assistant_content)
            if recovered_calls:
                tool_calls = recovered_calls
                assistant_message = dict(assistant_message)
                assistant_message["tool_calls"] = tool_calls
                print("[INFO] content JSON에서 tool call을 복구해 계속 진행합니다.")

        # Tool 호출이 없으면 최종 답변 단계입니다.
        if not tool_calls:
            print("\n[FINAL ANSWER]")
            print(assistant_content if assistant_content else "(빈 응답)")
            return assistant_content

        # assistant의 tool_call 메시지를 대화 이력에 반영
        messages.append(assistant_message)
        print(f"[TOOL CALL] {len(tool_calls)}개 요청됨")

        # 한 번의 assistant 응답에서 여러 tool call이 오면 순차 실행
        for index, tool_call in enumerate(tool_calls, start=1):
            function_block = tool_call.get("function", {})
            tool_name = function_block.get("name", "")
            raw_args = function_block.get("arguments", {})
            parsed_args = _parse_tool_arguments(raw_args)

            print(f"  - #{index} tool: {tool_name}")
            print(f"    args: {parsed_args}")

            result = _execute_tool(tool_name, parsed_args)
            preview = result[:220].replace("\n", " ")
            if len(result) > 220:
                preview += "..."
            print(f"    result preview: {preview}")

            # Tool 결과를 role='tool' 메시지로 추가해야 LLM이 다음 추론에 활용할 수 있습니다.
            tool_message: Dict[str, Any] = {
                "role": "tool",
                "name": tool_name,
                "content": result,
            }
            # 일부 모델/버전 호환을 위해 tool_call_id가 있으면 함께 넣어줍니다.
            if "id" in tool_call:
                tool_message["tool_call_id"] = tool_call["id"]

            messages.append(tool_message)

    timeout_message = (
        f"\n[중단] 최대 단계({MAX_AGENT_STEPS})에 도달해 루프를 종료합니다."
    )
    print(timeout_message)
    return timeout_message


def main() -> None:
    """
    단일 사용자 요청을 받아 에이전트를 실행하는 엔트리포인트.
    입력이 비어 있으면 요구사항의 예시 문장을 기본값으로 사용합니다.
    """
    print("=== 나무위키 검색 및 파일 저장 AI 에이전트 ===")
    print(f"모델: {MODEL_NAME}")
    print("- 예시 요청: 젤다에 대해 나무위키에서 검색한 뒤, 그 결과를 zelda_info.txt 파일에 저장해줘")

    user_input = input("\n사용자 입력 > ").strip()
    if not user_input:
        user_input = "젤다에 대해 나무위키에서 검색한 뒤, 그 결과를 zelda_info.txt 파일에 저장해줘"
        print(f"[INFO] 입력이 없어 기본 요청을 사용합니다: {user_input}")

    try:
        run_agent(user_input)
    except KeyboardInterrupt:
        print("\n[중단] 사용자 인터럽트로 종료했습니다.")
    except Exception as exc:
        print(f"\n[오류] 실행 중 예외 발생: {exc}")


if __name__ == "__main__":
    main()
