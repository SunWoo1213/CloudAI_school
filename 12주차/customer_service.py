"""12주차 과제 - 에이전트 간 통신 패턴 선택과 구현.

# 시나리오 분석
고객 서비스 에이전트가 고객 문의를 받는다.
- 일반 문의 → 자체 처리
- 기술적 문의 → 기술 지원 에이전트에게 넘긴다
- 기술 에이전트는 고객과의 대화 전체 맥락이 필요하다

# Step 1. 어느 통신 패턴을 써야 하나?
후보:
  (1) Pipeline (순차 처리)
      A → B → C 고정 흐름. 모든 입력이 항상 같은 경로를 탄다.
      → 부적합. 일반/기술 분기는 "조건부"라서 항상 위임하지 않는다.

  (2) Handoff (제어 이양)
      호출 에이전트가 완전히 빠지고 다른 에이전트가 대화를 인계받는다.
      → 부적합. 고객 입장에선 같은 창구에서 응대받아야 하므로
        고객 서비스 에이전트가 응답을 돌려받아 전달해야 한다.

  (3) Orchestrator-Worker, "Agent as Tool" (도구로서의 에이전트)
      메인(고객 서비스) 에이전트가 LLM tool-calling 으로
      필요할 때만 sub-agent(기술 지원)를 호출한다.
      → 적합. 조건부 위임 + 결과 회수 + 단일 응대 창구 유지.

선택: (3) Orchestrator-Worker + call_agent 도구.
참조 코드(call_agent.py)는 호출 시 새 빈 메모리를 만들어 sub-agent에
전달한다. 그런데 우리 시나리오는 "기술 에이전트가 고객과의 대화 전체
맥락이 필요하다"라고 명시했으므로, 참조 코드를 그대로 쓰면 안 된다.
→ 변형: 호출자의 메모리를 복사해서 sub-agent 의 시작 메모리로 넘긴다.

# Step 2. call_agent 도구 구현 (아래 call_agent 함수)
# Step 3. 두 에이전트 연결 + 테스트 (아래 main 함수)
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
    Path(__file__).resolve().parent.parent / "11주차" / ".env",
]


# ────────────────────────────────────────────────────────────────
# Memory / AgentRegistry / ActionContext
#  - 참조 코드의 ActionContext.get_agent_registry / Memory 추상을 따른다.
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
        """tool 호출 메타데이터를 제거하고 사용자/응답 텍스트만 남긴다."""
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
# Step 2. call_agent 도구
#  - 참조 코드(call_agent.py)를 바탕으로 작성.
#  - 변경점: invoked_memory 를 빈 메모리가 아니라 "호출자 메모리의 복사본"
#    으로 시작한다. 시나리오가 "전체 대화 맥락"을 요구하기 때문.
# ────────────────────────────────────────────────────────────────

def call_agent(
    action_context: ActionContext,
    agent_name: str,
    task: str,
) -> dict[str, Any]:
    """다른 에이전트를 호출하여 특정 작업을 수행하게 한다.

    호출 시 호출자의 대화 메모리를 복사해서 sub-agent 의 초기 메모리로
    넘긴다. 이렇게 해야 sub-agent 가 고객과의 전체 맥락을 알 수 있다.
    """
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
            # 무한 재귀 방지: agent_registry 는 다시 전달하지 않는다.
            action_context_props={
                "caller": "customer_service",
            },
        )
    except Exception as exc:  # sub-agent 실행 오류는 도구 결과로 회수
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
    """기술 지원 에이전트. 호출자(고객 서비스)에게서 복사된 메모리를 받는다."""
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
    """고객 발화 1건을 처리한다. 필요 시 call_agent 도구로 위임한다."""
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

            # call_agent 가 메모리를 복사해 sub-agent 에 넘길 수 있도록 컨텍스트 구성
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
# Step 3. 두 에이전트 연결 + 테스트
# ────────────────────────────────────────────────────────────────

DEMO_TURNS = [
    # 1) 일반 문의: 자체 처리되어야 함
    "안녕하세요. 저는 어제 주문번호 ORD-9988 로 결제했는데, 배송이 보통 며칠 걸리나요?",
    # 2) 일반 문의: 자체 처리되어야 함
    "감사합니다. 그리고 그 주문은 저희 회사 개발팀이 쓸 PaymentSDK 2.3.0 인데요, 받자마자 설치는 끝냈습니다.",
    # 3) 기술 문의: tech_support 로 위임되어야 하고, 답변에 ORD-9988 또는
    #    PaymentSDK 2.3.0 같은 이전 맥락이 인용되어야 함.
    "그런데 그 SDK 로 결제 API 를 호출하면 계속 401 Unauthorized 가 떨어집니다. 어떻게 해결하나요?",
]


def _print_separator(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def verify_tech_used_context(tech_answer: str, expected_keywords: list[str]) -> dict[str, Any]:
    hits = [kw for kw in expected_keywords if kw.lower() in tech_answer.lower()]
    return {
        "used_context": bool(hits),
        "matched_keywords": hits,
        "expected_keywords": expected_keywords,
    }


def main() -> None:
    load_env_files()

    registry = AgentRegistry()
    registry.register("tech_support", run_tech_support_agent)

    memory = Memory()

    delegated = False
    for i, user_text in enumerate(DEMO_TURNS, start=1):
        _print_separator(f"[Turn {i}] 고객 → 고객 서비스 에이전트")
        print(f"고객: {user_text}")

        before_len = len(memory.items)
        memory = run_customer_service_agent(
            user_input=user_text,
            memory=memory,
            agent_registry=registry,
        )
        new_items = memory.items[before_len:]

        used_call_agent = any(item.get("role") == "tool" for item in new_items)
        if used_call_agent:
            delegated = True
            print("\n[관찰] 이번 턴에 call_agent 가 호출되어 tech_support 로 위임되었습니다.")
            for item in new_items:
                if item.get("role") == "tool":
                    try:
                        payload = json.loads(item["content"])
                    except (json.JSONDecodeError, TypeError):
                        payload = {"raw": item.get("content")}
                    inherited = payload.get("inherited_context_messages")
                    print(
                        f"        → tech_support 에 전달된 사전 대화 메시지 수: {inherited}"
                    )

        final_reply = next(
            (
                item["content"]
                for item in reversed(new_items)
                if item.get("role") == "assistant"
                and not item.get("tool_calls")
                and isinstance(item.get("content"), str)
                and item["content"].strip()
            ),
            "",
        )
        print(f"\n고객 서비스 에이전트: {final_reply}")

    _print_separator("검증: 기술 에이전트가 고객 대화 맥락을 활용했는가")

    # 검증은 "기술 에이전트의 직접 출력"으로만 한다. 고객 서비스가 paraphrase
    # 하면서 키워드를 흘렸을 가능성을 배제하기 위해서다.
    # 기술 에이전트의 응답은 tool 메시지의 JSON payload(result 필드)에 있다.
    tech_answers: list[str] = []
    for item in memory.items:
        if item.get("role") != "tool":
            continue
        try:
            payload = json.loads(item.get("content") or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if payload.get("success") and payload.get("agent") == "tech_support":
            tech_answers.append(str(payload.get("result", "")))

    last_tech_answer = tech_answers[-1] if tech_answers else ""

    verdict = verify_tech_used_context(
        last_tech_answer, expected_keywords=["ORD-9988", "PaymentSDK", "2.3.0", "401"]
    )
    print(json.dumps(
        {
            "delegated_to_tech_support": delegated,
            "tech_support_invocations": len(tech_answers),
            "context_check": verdict,
            "tech_agent_raw_answer": last_tech_answer,
        },
        ensure_ascii=False,
        indent=2,
    ))

    if not delegated:
        print("\n[경고] 기술 문의에도 불구하고 call_agent 가 호출되지 않았습니다.")
        sys.exit(1)
    if not verdict["used_context"]:
        print("\n[경고] 기술 에이전트 답변에서 이전 대화 맥락 키워드를 찾지 못했습니다.")
        sys.exit(2)


if __name__ == "__main__":
    main()
