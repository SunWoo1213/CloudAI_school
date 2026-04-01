import sys
import os
import json
import re
import ollama
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from rich.console import Console
from rich.prompt import Prompt

console = Console()

# 1. 파일 조작 도구(함수) 정의
def read_file(filepath: str) -> str:
    """Reads the contents of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(filepath: str, content: str) -> str:
    """Writes content to a new file, or overwrites an existing file."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return "File written successfully."
    except Exception as e:
        return f"Error writing file: {e}"

def edit_file(filepath: str, search_text: str, replace_text: str) -> str:
    """Edits an existing file by replacing a specific string."""
    try:
        if not search_text:
            return "Error: search_text cannot be empty."
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if search_text not in content:
            return "Error: search_text not found in file."
        content = content.replace(search_text, replace_text)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return "File edited successfully."
    except Exception as e:
        return f"Error editing file: {e}"

def append_file(filepath: str, content: str) -> str:
    """Appends content to the end of an existing file."""
    try:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(content)
        return "File appended successfully."
    except Exception as e:
        return f"Error appending file: {e}"

def search_web(query: str) -> str:
    """Searches the web using DuckDuckGo and returns top snippets."""
    try:
        results = DDGS().text(query, max_results=5)
        if not results:
            return "No results found."
        formatted = "\n".join([f"Title: {r['title']}\nSnippet: {r['body']}\nURL: {r['href']}\n" for r in results])
        return formatted
    except Exception as e:
        return f"Error searching web: {e}"

def fetch_webpage(url: str) -> str:
    """Fetches text content from a URL."""
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)
        return text[:5000] # Return max 5000 chars to avoid overwhelming context
    except Exception as e:
        return f"Error fetching webpage: {e}"

AVAILABLE_TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "append_file": append_file,
    "search_web": search_web,
    "fetch_webpage": fetch_webpage
}

# 2. Ollama에 전달할 도구 명세 (JSON Schema 포맷)
ollama_tools = [
     {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The absolute or relative path to the file"}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Writes content to a file. Overwrites if it exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The path to the file"},
                    "content": {"type": "string", "description": "The text content to write"}
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edits an existing file by replacing search_text with replace_text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The path to the file"},
                    "search_text": {"type": "string", "description": "The exact text string to find and replace in the file (must not be empty)"},
                    "replace_text": {"type": "string", "description": "The new text string to replace it with"}
                },
                "required": ["filepath", "search_text", "replace_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": "Appends content to the end of an existing file.",
            "parameters": {
ㄱ                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The path to the file"},
                    "content": {"type": "string", "description": "The text content to append"}
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Searches the web for a query and returns top results with URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_webpage",
            "description": "Fetches and returns the text content of a webpage given its URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL of the webpage to fetch"}
                },
                "required": ["url"]
            }
        }
    }
]

def parse_manual_tool_calls(content: str) -> list:
    """Extract manually formatted JSON tools from text."""
    tool_calls = []
    
    # 1. 전체가 순수 JSON 문자열인 경우 시도
    try:
        data = json.loads(content.strip())
        if isinstance(data, dict) and "name" in data and "arguments" in data:
            return [{"function": {"name": data["name"], "arguments": data["arguments"]}}]
    except:
        pass
        
    # 2. 마크다운 코드 블록 안의 JSON 찾기
    json_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
    for block in json_blocks:
        try:
            data = json.loads(block)
            if "name" in data and "arguments" in data:
                tool_calls.append({
                    "function": {
                        "name": data["name"],
                        "arguments": data["arguments"]
                    }
                })
        except:
            pass
            
    # 3. fallback: 가장 바깥쪽 중괄호 블록 추출
    if not tool_calls:
        match = re.search(r'(\{.*\})', content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict) and "name" in data and "arguments" in data:
                    tool_calls.append({
                        "function": {
                            "name": data["name"],
                            "arguments": data["arguments"]
                        }
                    })
            except:
                pass
                
    return tool_calls

def main():
    console.print("[bold green]Qwen Agent Terminal에 오신 것을 환영합니다![/bold green]")
    console.print("이 에이전트는 로컬 파일을 읽고, 쓰고, 수정할 수 있습니다.")
    console.print("종료하려면 'exit' 또는 'quit' 입력하세요.\n")

    # 시스템 프롬프트 부여
    system_prompt = (
        "You are an autonomous AI coding agent. "
        "You have the ability to read, write, append, and edit files on the user's system to accomplish tasks. "
        "You also have the ability to search the internet (search_web) and fetch text from webpages (fetch_webpage). "
        "When the user asks you to interact with files or the internet, YOU MUST use the provided tools (read_file, write_file, edit_file, append_file, search_web, fetch_webpage). "
        "Do not just show code; perform the action using your tools. "
        "If you encounter an error, inform the user."
    )

    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
            
            if user_input.lower() in ["exit", "quit"]:
                console.print("[bold yellow]채팅을 종료합니다. 안녕히 가세요![/bold yellow]")
                break
                
            if not user_input.strip():
                continue
                
            messages.append({"role": "user", "content": user_input})
            
            # 모델 호출 루프 (도구를 호출하면 결과를 주고 다시 응답을 받음)
            while True:
                # 도구 호출(Tool Calling)의 안정성을 위해 stream=False 및 반복 제한 옵션 사용
                response = ollama.chat(
                    model='qwen2.5-coder:7b',
                    messages=messages,
                    tools=ollama_tools,
                    stream=False,
                    options={"temperature": 0.1, "repeat_penalty": 1.1}
                )
                
                message = response.get('message', {})
                content = message.get('content', '')
                tool_calls_data = message.get('tool_calls', [])
                
                if content:
                    console.print(f"[bold magenta]Qwen:[/bold magenta]\n{content}")
                
                messages.append(message)
                
                # 기본 tool_calls가 비어있고 내용에 작성한 JSON 도구가 있는지 확인 (수동 파싱)
                is_native = bool(tool_calls_data)
                if not is_native and content:
                    tool_calls_data = parse_manual_tool_calls(content)

                # 도구 호출이 없으면 이번 턴(사용자 입력 시퀀스) 종료
                if not tool_calls_data:
                    break
                    
                # 도구 호출이 배열로 들어왔을 경우 실행
                for tc in tool_calls_data:
                    func_name = tc.get('function', {}).get('name')
                    func_args = tc.get('function', {}).get('arguments', {})
                    
                    console.print(f"\n[dim cyan]🛠️  Executing tool: {func_name}({func_args})[/dim cyan]")
                    
                    if func_name in AVAILABLE_TOOLS:
                        try:
                            result = AVAILABLE_TOOLS[func_name](**func_args)
                        except Exception as e:
                            result = f"Error executing tool: {e}"
                    else:
                        result = f"Tool {func_name} not found."
                        
                    console.print(f"[dim green]Tool result: {result}[/dim green]\n")
                    
                    # 결과를 다시 messages에 추가하여 모델에게 알려줌
                    # 네이티브 도구 호출이 아니었다면 tool role 대신 user role로 결과를 주입하여 모델의 파싱 오류/환각 방지
                    if is_native:
                        messages.append({
                            "role": "tool",
                            "content": result,
                            "name": func_name
                        })
                    else:
                        messages.append({
                            "role": "user",
                            "content": f"[System: Tool '{func_name}' was executed. Result: {result}]"
                        })
                
                # 도구 실행 후 (마지막 루프 끝에서) while True 안에서 다시 ollama.chat 수행

        except KeyboardInterrupt:
            console.print("\n[bold yellow]채팅을 종료합니다. 안녕히 가세요![/bold yellow]")
            break
        except Exception as e:
            console.print(f"\n[bold red]오류 발생: {e}[/bold red]")

if __name__ == "__main__":
    main()
