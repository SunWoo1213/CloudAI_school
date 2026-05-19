# 인보이스 에이전트 Feature List

## 1. OpenAI API 기반 JSON 프롬프트 기능

- `OPENAI_API_KEY` 환경 변수를 읽어 OpenAI API를 사용할 수 있어야 한다.
- `.env` 파일에서 `OPENAI_API_KEY`를 로드할 수 있어야 한다.
- OpenAI 클라이언트를 초기화하는 구조가 있어야 한다.
- 사용할 모델명을 상수로 관리해야 한다.
- LLM 응답은 JSON 객체로 파싱되어야 한다.
- LLM 응답이 JSON 형식이 아닐 경우 명확한 오류를 반환하거나 예외 처리해야 한다.
- API 키가 없을 경우 사용자에게 원인을 알 수 있는 오류 메시지를 제공해야 한다.
- 인보이스 추출, 지출 분류, 구매 규정 검토가 공통 JSON 호출 헬퍼를 재사용할 수 있어야 한다.

## 2. 인보이스 데이터 추출 기능

- `extract_invoice_data` 도구를 구현해야 한다.
- 입력값은 원시 인보이스 텍스트여야 한다.
- 내부에서 OpenAI API 기반 JSON 프롬프트 헬퍼를 호출해야 한다.
- 인보이스 번호, 날짜, 발행처, 통화, 총액, 품목 목록을 추출해야 한다.
- 추출 결과는 고정 스키마를 따라야 한다.
- 누락된 문자열 값은 빈 문자열로 보정해야 한다.
- 누락된 숫자 값은 `0`으로 보정해야 한다.
- 누락된 품목 목록은 빈 배열로 보정해야 한다.
- 이 도구는 파싱과 스키마 정규화만 담당해야 한다.

## 3. 지출 분류 전문가 기능

- `classify_expense` 도구를 구현해야 한다.
- 이 도구는 지출 분류 전문가 페르소나를 가져야 한다.
- 입력값은 구조화된 인보이스 데이터여야 한다.
- 공급사, 총액, 품목명, 품목 설명을 근거로 지출 카테고리를 분류해야 한다.
- 출력에는 `category`, `confidence`, `reason`이 포함되어야 한다.
- 카테고리 후보는 `office_supplies`, `software`, `hardware`, `professional_services`, `travel`, `training`, `other`를 기본으로 한다.
- 카테고리 판단이 어려우면 `other`를 반환해야 한다.
- confidence가 누락되거나 잘못되면 `0`으로 보정해야 한다.
- 이 도구는 구매 규정 준수 여부를 판단하지 않아야 한다.

## 4. 구매 규칙 Document-as-Implementation 기능

- `purchasing_rules.txt` 파일을 작성해야 한다.
- 구매 규칙은 Python 코드에 하드코딩하지 않아야 한다.
- `check_compliance` 실행 시 최신 `purchasing_rules.txt` 내용을 읽어야 한다.
- 규칙 파일은 UTF-8 텍스트로 읽어야 한다.
- 규칙 파일이 없으면 명확한 오류를 반환해야 한다.
- 규칙 파일이 비어 있으면 명확한 오류를 반환해야 한다.
- 규칙 파일의 금액 기준, 승인 조건, 반려 조건을 바꾸면 Python 코드 수정 없이 결과가 달라져야 한다.

## 5. 구매 규정 준수 전문가 기능

- `check_compliance` 도구를 구현해야 한다.
- 이 도구는 구매 규정 준수 검토 전문가 페르소나를 가져야 한다.
- 입력값은 인보이스 데이터와 지출 분류 결과여야 한다.
- 도구 내부에서 `purchasing_rules.txt`를 읽어 판단 근거로 사용해야 한다.
- 출력에는 `status`, `violations`, `required_actions`, `reason`이 포함되어야 한다.
- `status` 후보는 `approved`, `needs_approval`, `rejected`, `needs_review`를 기본으로 한다.
- 명확한 위반이 없으면 `approved`를 반환해야 한다.
- 추가 승인이 필요하면 `needs_approval`을 반환해야 한다.
- 명확한 반려 조건에 해당하면 `rejected`를 반환해야 한다.
- 정보가 부족하거나 판단이 어려우면 `needs_review`를 반환해야 한다.
- 이 도구는 인보이스 추출, 지출 분류, 저장을 수행하지 않아야 한다.

## 6. 인보이스 저장 기능

- `store_invoice` 도구를 구현해야 한다.
- 입력값은 구조화된 인보이스 데이터여야 한다.
- `invoice_number`를 저장 키로 사용해야 한다.
- 저장 파일은 `11주차/invoices.json`을 사용해야 한다.
- 저장 파일이 없으면 새로 생성해야 한다.
- 기존 인보이스 번호가 있으면 데이터를 덮어써야 한다.
- 새 인보이스 번호이면 새 항목으로 추가해야 한다.
- 저장 결과에 신규 저장인지 업데이트인지 표시해야 한다.
- `invoice_number`가 비어 있으면 저장하지 않고 오류를 반환해야 한다.
- 확장 후에는 인보이스 데이터에 `expense_classification`, `compliance` 결과를 포함해 저장할 수 있어야 한다.
- 이 도구는 저장만 담당해야 한다.

## 7. 도구 등록 기능

- `extract_invoice_data`, `classify_expense`, `check_compliance`, `store_invoice`를 도구 목록에 등록해야 한다.
- 도구 이름, 설명, 입력 스키마를 명시해야 한다.
- 실제 실행 함수 매핑을 별도 테이블로 관리해야 한다.
- 등록 구조는 이후 다른 도구를 추가할 수 있도록 읽기 쉬워야 한다.
- 고정 실행 흐름에서도 도구 메타데이터와 실행 함수 매핑이 일치해야 한다.

## 8. 에이전트 실행 흐름 기능

- 에이전트는 인보이스 텍스트를 입력받아야 한다.
- 실행 순서는 고정되어야 한다.
- 첫 번째 단계에서 `extract_invoice_data`를 호출해야 한다.
- 두 번째 단계에서 `classify_expense`를 호출해야 한다.
- 세 번째 단계에서 `check_compliance`를 호출해야 한다.
- 네 번째 단계에서 `store_invoice`를 호출해야 한다.
- 마지막 단계에서 처리 결과를 요약해야 한다.
- LLM에게 다음 도구 선택을 맡기지 않아야 한다.
- 각 단계의 성공 또는 실패 상태를 확인할 수 있어야 한다.
- 중간 단계 실패 시 이후 단계는 실행하지 않아야 한다.

## 9. 사용자 실행 기능

- `invoice_agent.py`를 직접 실행할 수 있어야 한다.
- 사용자가 인보이스 텍스트를 입력할 수 있어야 한다.
- 입력이 비어 있으면 예시 인보이스 텍스트로 실행할 수 있어야 한다.
- 실행 결과는 콘솔에 보기 좋게 출력되어야 한다.
- 실행 요약에는 저장 결과와 구매 규정 준수 상태가 포함되어야 한다.

## 10. 오류 처리 기능

- OpenAI API 키가 없을 때 오류를 제공해야 한다.
- OpenAI API 호출 실패 시 오류를 제공해야 한다.
- JSON 파싱 실패 시 오류를 제공해야 한다.
- 인보이스 번호가 없는 데이터는 저장하지 않아야 한다.
- 저장 파일 읽기 또는 쓰기 실패 시 오류를 제공해야 한다.
- `purchasing_rules.txt` 파일이 없을 때 오류를 제공해야 한다.
- `purchasing_rules.txt` 파일이 비어 있을 때 오류를 제공해야 한다.
- 지출 분류 실패 시 준수 검토와 저장을 건너뛰어야 한다.
- 준수 검토 실패 시 저장을 건너뛰어야 한다.

## 11. 검증 기능

- `uv run python -m py_compile 11주차/invoice_agent.py`로 문법 검사를 통과해야 한다.
- 도구 등록 목록에 네 도구가 모두 포함되어야 한다.
- 예시 인보이스 텍스트로 실행했을 때 구조화 데이터가 생성되어야 한다.
- 지출 분류 결과가 생성되어야 한다.
- `purchasing_rules.txt` 기반 준수 판단 결과가 생성되어야 한다.
- 실행 후 `invoices.json`에 인보이스 번호 기준으로 데이터가 저장되어야 한다.
- 같은 인보이스 번호를 다시 저장하면 업데이트 결과가 표시되어야 한다.
- API 키가 없는 환경에서도 명확한 실패 메시지를 확인할 수 있어야 한다.
- 규칙 파일을 변경한 뒤 같은 인보이스로 재실행하면 준수 판단 결과가 달라지는지 확인해야 한다.

## 12. 기존 구현 검증 기록

검증일: 2026-05-13

### 문법 검증

- 검증 명령어: `uv run python -m py_compile '11주차/invoice_agent.py'`
- 결과: 성공
- 성공 메시지: 별도 출력 없이 종료 코드 `0`으로 완료됨.
- 참고: 최초 sandbox 환경에서는 `uv` 캐시 접근 권한 문제로 실패했다.
- 실패 메시지: `Failed to initialize cache at C:\Users\swsj1\AppData\Local\uv\cache`, `액세스가 거부되었습니다. (os error 5)`
- 판단: 코드 문법 오류가 아니라 실행 환경 권한 문제였으며, 권한 승인 후 동일 명령이 성공했다.

### 기존 도구 검증

- `prompt_llm_for_json`의 정상 JSON, 잘못된 JSON, 빈 응답, 객체가 아닌 JSON 응답 처리를 검증했다.
- `extract_invoice_data`의 정상 입력, 빈 입력, API 키 누락 실패 경로를 검증했다.
- `store_invoice`의 신규 저장, 업데이트, 빈 `invoice_number`, 깨진 저장소 JSON, 저장소 구조 오류, 읽기/쓰기 실패 처리를 검증했다.
- `run_invoice_agent`의 추출, 저장, 실패 분기 흐름을 검증했다.
- `main`의 사용자 입력, 빈 입력 예시 사용, 콘솔 출력, 실패 시 종료 코드 처리를 검증했다.
- 실제 OpenAI API end-to-end 실행으로 `INV-001` 신규 저장과 업데이트를 확인했다.

### 현재 한계

- 아직 `classify_expense`는 구현되지 않았다.
- 아직 `check_compliance`는 구현되지 않았다.
- `purchasing_rules.txt`는 작성되어 있다.
- `PURCHASING_RULES_PATH` 상수와 `load_purchasing_rules()` 함수는 구현되어 있다.
- `load_purchasing_rules()`는 현재 규칙 파일을 UTF-8로 읽고, 파일 없음/빈 파일 오류를 반환하는 구조를 가진다.
- 다만 `check_compliance`가 아직 없기 때문에 규칙 파일은 실제 준수 판단 흐름에 연결되어 있지 않다.
- 현재 `run_invoice_agent`는 추출 후 저장만 수행한다.
- 현재 저장 데이터에는 지출 분류 및 구매 규정 준수 결과가 포함되지 않는다.
- 현재 `store_invoice`는 `normalize_invoice_data()` 결과만 저장하므로, 입력에 `expense_classification` 또는 `compliance` 필드가 있어도 저장 시 제거된다.
- 현재 `TOOLS`와 `AVAILABLE_TOOLS`에는 `extract_invoice_data`, `store_invoice` 두 도구만 등록되어 있다.
- 따라서 네 도구 등록 요구사항과 4단계 실행 흐름 요구사항은 아직 충족되지 않았다.

### 2026-05-13 추가 검증 기록

- 검증 명령어: `uv run python -m py_compile 11주차/invoice_agent.py`
- 결과: 성공
- 참고: sandbox 환경에서는 `uv` 캐시 접근 권한 문제로 실패했으며, 권한 승인 후 성공했다.
- 런타임 도구 등록 확인 결과: `TOOLS = ['extract_invoice_data', 'store_invoice']`
- 런타임 실행 함수 매핑 확인 결과: `AVAILABLE_TOOLS = ['extract_invoice_data', 'store_invoice']`
- `classify_expense` 함수 존재 여부: 없음
- `check_compliance` 함수 존재 여부: 없음
- `load_purchasing_rules` 함수 존재 여부: 있음
- `load_purchasing_rules()` 정상 규칙 파일 로드 결과: `ok: True`
- fake LLM 기반 `run_invoice_agent` 흐름 확인 결과, 최종 결과에는 `expense_classification`과 `compliance`가 포함되지 않았다.
- 임시 저장소 기반 검증 결과, `store_invoice`에 확장 필드를 포함한 입력을 전달해도 저장된 JSON에는 기본 인보이스 필드만 남았다.

## 13. 확장 구현 후 추가 검증 예정

- `classify_expense` fake LLM 응답 기반 검증
- `check_compliance` fake LLM 응답 기반 검증
- `load_purchasing_rules` 정상/파일 없음/빈 파일 검증
- 네 도구 등록 상태 검증
- 확장된 `run_invoice_agent` 성공 흐름 검증
- 지출 분류 실패 흐름 검증
- 구매 규정 검토 실패 흐름 검증
- 실제 OpenAI API 기반 end-to-end 검증
- `purchasing_rules.txt` 변경 전후 결과 비교 검증

## 14. 2026-05-19 확장 구현 검증 기록

### 구현 완료

- `prompt_openai_for_json(system_message, user_message)` 공통 JSON 호출 헬퍼를 추가했다.
- `prompt_llm_for_json(raw_invoice_text)`는 기존 인보이스 추출 전용 래퍼로 유지했다.
- `classify_expense`를 구현하고 `EXPENSE_CLASSIFICATION_SCHEMA`를 추가했다.
- `check_compliance`를 구현하고 `COMPLIANCE_SCHEMA`를 추가했다.
- `check_compliance`는 `purchasing_rules.txt`를 실행 시점에 읽어 LLM 판단 근거로 전달한다.
- `store_invoice`는 확장된 인보이스 데이터의 `expense_classification`, `compliance` 필드를 저장한다.
- `TOOLS`와 `AVAILABLE_TOOLS`에 `extract_invoice_data`, `classify_expense`, `check_compliance`, `store_invoice` 네 도구를 모두 등록했다.
- `run_invoice_agent`를 `extract_invoice_data -> classify_expense -> check_compliance -> store_invoice` 순서로 확장했다.
- 실패 단계별로 이후 도구 실행을 중단하고 `stage`, `error`, `summary`를 반환하도록 정리했다.

### 검증 완료

- 검증 명령어: `uv run python -m py_compile '11주차/invoice_agent.py'`
- 결과: 성공
- fake LLM 응답으로 4단계 실행 흐름이 완료되는지 확인했다.
- fake LLM 응답으로 분류 결과가 `professional_services`로 저장되는지 확인했다.
- fake LLM 응답으로 준수 결과가 `needs_approval`로 저장되는지 확인했다.
- 도구 등록 목록과 실행 함수 매핑이 네 도구를 모두 포함하는지 확인했다.
- 실제 OpenAI API 기반 end-to-end 실행 결과 `ok: True`, `stage: complete`를 확인했다.
- 실제 OpenAI API 실행 결과 `INV-001`이 업데이트되었고, 지출 분류는 `professional_services`, 구매 규정 상태는 `needs_review`로 반환되었다.
- 실제 저장소 `invoices.json`에 `expense_classification`, `compliance` 필드가 포함되는 것을 확인했다.
- Python 코드는 수정하지 않고 `purchasing_rules.txt`만 완화한 뒤 같은 인보이스를 실행했을 때 구매 규정 상태가 `approved`로 바뀌는 것을 확인했다.
- 원래 `purchasing_rules.txt`로 복구한 뒤 같은 인보이스를 다시 실행했을 때 구매 규정 상태가 `needs_review`로 돌아오는 것을 확인했다.

### 미완료 검증

- 없음
