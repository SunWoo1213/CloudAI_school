"""13주차 과제 - 대화형 CS 처리 에이전트.

12주차의 customer_service.py 구조를 그대로 재사용하되, 미리 정의된 DEMO_TURNS
대신 사용자가 터미널에서 직접 입력하는 REPL 형태로 동작한다.

설계 근거와 사양은 같은 폴더의 CS_AGENT_PLAN.md 참조.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable


MODEL_NAME = "gpt-4.1-mini"
ENV_FILE_PATHS = [
    Path(__file__).with_name(".env"),
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent.parent / "12주차" / ".env",
    Path(__file__).resolve().parent.parent / "11주차" / ".env",
]

EXIT_COMMANDS = {"/exit", "/quit", ":q"}


# ────────────────────────────────────────────────────────────────
# Memory / AgentRegistry / ActionContext (12주차와 동일)
# ────────────────────────────────────────────────────────────────

class Memory:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def add(self, **fields: Any) -> None:
        self.items.append(fields)

    def copy(self) -> "Memory":
        new_memory = Memory()
        new_memory.items = [dict(item) for item in self.items]
        return new_memory

    def to_openai_messages(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.items]

    def to_plain_conversation(self) -> list[dict[str, str]]:
        plain: list[dict[str, str]] = []
        for item in self.items:
            role = item.get("role")
            content = item.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                plain.append({"role": role, "content": content})
        return plain


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Callable[..., Memory]] = {}

    def register(self, name: str, run_fn: Callable[..., Memory]) -> None:
        self._agents[name] = run_fn

    def get_agent(self, name: str) -> Callable[..., Memory] | None:
        return self._agents.get(name)


class ActionContext:
    def __init__(self, **props: Any) -> None:
        self._props = props

    def get(self, key: str, default: Any = None) -> Any:
        return self._props.get(key, default)

    def get_agent_registry(self) -> AgentRegistry | None:
        return self._props.get("agent_registry")

    def get_memory(self) -> Memory | None:
        return self._props.get("memory")


# ────────────────────────────────────────────────────────────────
# 환경설정 / OpenAI 클라이언트
# ────────────────────────────────────────────────────────────────

def load_env_files() -> None:
    for env_path in ENV_FILE_PATHS:
        if not env_path.exists():
            continue
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "openai 패키지가 설치되어 있지 않습니다. `uv add openai` 또는 `pip install openai`"
        ) from exc
    return OpenAI(api_key=api_key)


# ────────────────────────────────────────────────────────────────
# call_agent 도구 (12주차와 동일: 호출자 메모리를 복사해서 sub-agent 에 전달)
# ────────────────────────────────────────────────────────────────

def call_agent(
    action_context: ActionContext,
    agent_name: str,
    task: str,
) -> dict[str, Any]:
    agent_registry = action_context.get_agent_registry()
    if agent_registry is None:
        return {"success": False, "error": "컨텍스트에 에이전트 레지스트리가 없습니다."}

    agent_run = agent_registry.get_agent(agent_name)
    if agent_run is None:
        return {
            "success": False,
            "error": f"에이전트 '{agent_name}'을 레지스트리에서 찾을 수 없습니다.",
        }

    caller_memory = action_context.get_memory()
    invoked_memory = caller_memory.copy() if caller_memory is not None else Memory()
    inherited_context_size = len(invoked_memory.items)

    try:
        result_memory = agent_run(
            user_input=task,
            memory=invoked_memory,
            action_context_props={"caller": "customer_service"},
        )
    except Exception as exc:
        return {"success": False, "error": f"{type(exc).__name__}: {exc}"}

    if not result_memory.items:
        return {"success": False, "error": "에이전트 실행 결과 메모리가 비어있습니다."}

    last_item = result_memory.items[-1]
    return {
        "success": True,
        "agent": agent_name,
        "result": last_item.get("content", "결과 내용 없음"),
        "inherited_context_messages": inherited_context_size,
    }


# ────────────────────────────────────────────────────────────────
# 기술 지원 에이전트 (sub-agent)
# ────────────────────────────────────────────────────────────────

TECH_SUPPORT_SYSTEM_PROMPT = (
    "당신은 기술 지원 전문 에이전트입니다. "
    "지금까지의 고객 대화 맥락을 모두 참고하여 정확한 기술적 답변을 제공하세요. "
    "고객 본인의 환경/제품/주문/이전 발화에서 드러난 사실을 반드시 인용·반영하세요. "
    "예: 고객이 언급한 주문번호, 사용 중인 SDK 버전, 발생한 오류 코드 등을 답변에 포함하세요. "
    "전문적이고 친절한 어조로 한국어로 답변합니다."
)


def run_tech_support_agent(
    user_input: str,
    memory: Memory,
    action_context_props: dict[str, Any] | None = None,
) -> Memory:
    client = _openai_client()

    prior_conversation = memory.to_plain_conversation()

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": TECH_SUPPORT_SYSTEM_PROMPT}
    ]
    if prior_conversation:
        context_dump = "\n".join(
            f"- {turn['role']}: {turn['content']}" for turn in prior_conversation
        )
        messages.append(
            {
                "role": "system",
                "content": (
                    "다음은 고객이 고객 서비스 에이전트와 나눈 이전 대화 기록입니다. "
                    "기술 지원 답변 시 반드시 이 맥락을 참고하세요.\n\n"
                    f"{context_dump}"
                ),
            }
        )
    messages.append(
        {
            "role": "user",
            "content": (
                "기술 지원팀에 이관된 요청입니다. 위 대화 맥락을 모두 고려하여 답변하세요.\n\n"
                f"요청 내용: {user_input}"
            ),
        }
    )

    response = client.chat.completions.create(model=MODEL_NAME, messages=messages)
    answer = response.choices[0].message.content or ""

    memory.add(role="user", content=f"[tech_support 작업 요청] {user_input}")
    memory.add(role="assistant", content=answer)
    return memory


# ────────────────────────────────────────────────────────────────
# 고객 서비스 에이전트 (orchestrator)
# ────────────────────────────────────────────────────────────────

CUSTOMER_SERVICE_SYSTEM_PROMPT = (
    "당신은 회사의 1차 고객 서비스 에이전트입니다. 한국어로 응대하세요.\n"
    "고객 문의가 들어오면 다음 기준으로 처리하세요:\n"
    " - 일반 문의(주문 상태, 배송, 환불/교환 정책, 회사 정보, 단순 안내 등)\n"
    "   → 직접 친절하게 답변한다. 도구를 사용하지 않는다.\n"
    " - 기술적 문의(설치 오류, 인증 실패, API 오류 코드, SDK 사용법, 네트워크 장애, 버그 등)\n"
    "   → 반드시 call_agent 도구를 호출한다. agent_name='tech_support' 로 지정하고,\n"
    "     task 인자에는 (a) 고객이 처한 상황 요약, (b) 정확한 질문 을 명시한다.\n"
    "도구 호출 결과를 받으면 그 내용을 자연스러운 어투로 고객에게 전달하라."
)


CUSTOMER_SERVICE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "call_agent",
            "description": (
                "다른 전문 에이전트에게 작업을 위임한다. "
                "기술적 문의는 agent_name='tech_support' 로 호출한다. "
                "이 도구는 호출자의 전체 대화 맥락을 함께 전달한다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "호출할 에이전트 이름. 예: 'tech_support'",
                    },
                    "task": {
                        "type": "string",
                        "description": "에이전트에게 수행시킬 작업 요약 + 질문.",
                    },
                },
                "required": ["agent_name", "task"],
            },
        },
    }
]


def run_customer_service_agent(
    user_input: str,
    memory: Memory,
    agent_registry: AgentRegistry,
    max_steps: int = 4,
) -> Memory:
    client = _openai_client()
    memory.add(role="user", content=user_input)

    for _ in range(max_steps):
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": CUSTOMER_SERVICE_SYSTEM_PROMPT}
        ]
        messages.extend(memory.to_openai_messages())

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=CUSTOMER_SERVICE_TOOLS,
        )
        choice = response.choices[0].message
        tool_calls = choice.tool_calls or []

        if not tool_calls:
            memory.add(role="assistant", content=choice.content or "")
            return memory

        memory.add(
            role="assistant",
            content=choice.content or "",
            tool_calls=[
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ],
        )

        for tc in tool_calls:
            if tc.function.name != "call_agent":
                memory.add(
                    role="tool",
                    tool_call_id=tc.id,
                    content=json.dumps(
                        {"success": False, "error": f"알 수 없는 도구: {tc.function.name}"},
                        ensure_ascii=False,
                    ),
                )
                continue

            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            ctx = ActionContext(agent_registry=agent_registry, memory=memory)
            tool_result = call_agent(
                action_context=ctx,
                agent_name=args.get("agent_name", ""),
                task=args.get("task", ""),
            )
            memory.add(
                role="tool",
                tool_call_id=tc.id,
                content=json.dumps(tool_result, ensure_ascii=False),
            )

    memory.add(role="assistant", content="(최대 단계 수 초과: 응답을 생성하지 못했습니다.)")
    return memory


# ────────────────────────────────────────────────────────────────
# REPL (13주차 핵심)
# ────────────────────────────────────────────────────────────────

WELCOME_BANNER = (
    "==================================================================\n"
    "  대화형 CS 처리 에이전트 (13주차)\n"
    "  - 일반 문의는 고객 서비스 에이전트가 직접 답변합니다.\n"
    "  - 기술 문의는 자동으로 tech_support 에이전트로 위임됩니다.\n"
    "  - 종료하려면 /exit, /quit, :q 중 하나를 입력하세요.\n"
    "=================================================================="
)


def _extract_final_reply(new_items: list[dict[str, Any]]) -> str:
    """이번 턴에 추가된 아이템들 중 최종 assistant 응답을 골라낸다."""
    for item in reversed(new_items):
        if (
            item.get("role") == "assistant"
            and not item.get("tool_calls")
            and isinstance(item.get("content"), str)
            and item["content"].strip()
        ):
            return item["content"]
    return ""


def _was_delegated(new_items: list[dict[str, Any]]) -> bool:
    """이번 턴에 call_agent 가 호출되어 tech_support 로 위임되었는지."""
    for item in new_items:
        if item.get("role") != "tool":
            continue
        try:
            payload = json.loads(item.get("content") or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if payload.get("success") and payload.get("agent") == "tech_support":
            return True
    return False


def main() -> None:
    load_env_files()

    if not os.getenv("OPENAI_API_KEY"):
        print(
            "[설정 오류] OPENAI_API_KEY 가 설정되어 있지 않습니다.\n"
            "  13주차/.env 또는 상위 폴더 .env 에 OPENAI_API_KEY=... 를 추가하세요."
        )
        sys.exit(1)

    registry = AgentRegistry()
    registry.register("tech_support", run_tech_support_agent)

    memory = Memory()
    turn_count = 0

    print(WELCOME_BANNER)

    while True:
        try:
            user_input = input("\n고객(나) > ").strip()
        except (KeyboardInterrupt, EOFError):
            print()  # 줄바꿈
            break

        if not user_input:
            continue
        if user_input.lower() in EXIT_COMMANDS:
            break

        turn_count += 1
        before_len = len(memory.items)

        try:
            memory = run_customer_service_agent(
                user_input=user_input,
                memory=memory,
                agent_registry=registry,
            )
        except Exception as exc:
            print(f"[오류] {type(exc).__name__}: {exc}")
            continue

        new_items = memory.items[before_len:]

        if _was_delegated(new_items):
            print("[위임됨 → tech_support]")

        final_reply = _extract_final_reply(new_items)
        if not final_reply:
            final_reply = "(응답을 생성하지 못했습니다.)"
        print(f"상담원 > {final_reply}")

    print(f"\n세션을 종료합니다. (총 {turn_count}턴)")


if __name__ == "__main__":
    main()
