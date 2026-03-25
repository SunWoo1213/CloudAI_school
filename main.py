import sys
import ollama
from rich.console import Console
from rich.prompt import Prompt

console = Console()

def main():
    console.print("[bold green]Qwen Terminal Chat에 오신 것을 환영합니다![/bold green]")
    console.print("종료하려면 'exit' 또는 'quit' 입력하세요.\n")

    messages = []
    
    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
            
            if user_input.lower() in ["exit", "quit"]:
                console.print("[bold yellow]채팅을 종료합니다. 안녕히 가세요![/bold yellow]")
                break
                
            if not user_input.strip():
                continue
                
            messages.append({"role": "user", "content": user_input})
            
            console.print("[bold magenta]Qwen:[/bold magenta] ", end="")
            
            # Start streaming response
            response_text = ""
            stream = ollama.chat(
                model='qwen2.5-coder:7b',
                messages=messages,
                stream=True,
            )
            
            for chunk in stream:
                content = chunk.get('message', {}).get('content', '')
                response_text += content
                # flush=True is important for streaming effect in terminal
                print(content, end="", flush=True)
            
            print() # Add a newline after the response
            messages.append({"role": "assistant", "content": response_text})
            
        except KeyboardInterrupt:
            console.print("\n[bold yellow]채팅을 종료합니다. 안녕히 가세요![/bold yellow]")
            break
        except Exception as e:
            console.print(f"\n[bold red]오류 발생: {e}[/bold red]")

if __name__ == "__main__":
    main()
