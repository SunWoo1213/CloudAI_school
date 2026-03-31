# 4주차 - 나무위키 검색/저장 에이전트

로컬 Ollama 모델을 사용해서 나무위키 내용을 검색하고, 결과를 파일로 저장하는 예제입니다.

## 파일 구성
- `namuwiki_file_agent.py`: 메인 에이전트 스크립트
- `zelda_info.txt`: 실행 예시 결과 파일

## 실행 전 준비
1. Ollama 실행
2. 모델 준비
   - `ollama pull qwen2.5-coder:7b`
3. 패키지 설치
   - `pip install ollama requests beautifulsoup4`

## 실행 방법
```bash
uv run python "4주차/namuwiki_file_agent.py"
```

## 예시 입력
`젤다에 대해 나무위키에서 검색한 뒤, 그 결과를 zelda_info.txt 파일에 저장해줘`

