# MyAgent 프로젝트 시작 가이드

이것은 README입니다.

## 프로젝트 설정 및 실행 방법 (`uv` 패키지 매니저 사용)

1. **가상환경 동기화 (의존성 설치)**
   프로젝트 설정(`pyproject.toml` 또는 `uv.lock`)을 기반으로 가상환경을 구축하고 패키지를 설치합니다.

   ```bash
   uv sync
   ```

2. **새로운 패키지 추가**
   의존성으로 사용할 새로운 라이브러리를 설치할 때 사용합니다. (예: `fastapi`)

   ```bash
   uv add fastapi
   ```

3. **애플리케이션(스크립트) 실행**
   가상환경을 수동으로 활성화할 필요 없이, `uv run` 명령어로 코드를 바로 실행할 수 있습니다.

   ```bash
   uv run hello.py
   # 혹은 메인 스크립트 실행 시:
   # uv run main.py
   ```

4. **에디터(VS Code 등)에서 가상환경 버전 선택하기**
   작업 중인 에디터가 프로젝트의 의존성을 올바르게 인식하고 자동완성 및 린트(Linting) 기능을 제공하도록 하려면 방금 생성한 가상환경 공간(`.venv`)을 파이썬 인터프리터로 선택해야 합니다.
   - **Command Palette 열기**: `Ctrl + Shift + P` (Mac: `Cmd + Shift + P`)
   - **인터프리터 선택**: `Python: Select Interpreter` 입력 후 선택
   - **가상환경 지정**: 목록에서 현재 프로젝트 내의 `./.venv/Scripts/python.exe` (Mac/Linux는 `./.venv/bin/python`) 경로를 찾아 선택합니다. 목록에 없을 경우 `Enter interpreter path...`를 클릭하여 폴더 내의 해당 경로를 직접 찾아 지정해 줍니다.
