# 인보이스 에이전트 확장 개발 계획

## 1. 목표

현재 인보이스 에이전트는 원시 인보이스 텍스트를 OpenAI API로 고정 스키마 JSON으로 추출하고, `invoices.json`에 저장하는 흐름까지 구현되어 있다.

이번 확장의 목표는 기존 흐름에 전문가 페르소나 기반 도구 두 개를 추가하고, 구매 규칙을 코드에 하드코딩하지 않고 `purchasing_rules.txt` 문서로부터 읽어 동작하게 만드는 것이다.

추가 목표:

1. `classify_expense` 도구 구현
2. `check_compliance` 도구 구현
3. `purchasing_rules.txt` 작성
4. 에이전트 실행 흐름에 두 도구 연결
5. 규칙 파일 내용을 바꾸면 준수 판단 결과가 바뀌는지 검증

핵심 설계 원칙은 기존과 동일하게 각 도구가 하나의 책임만 가지도록 분리하는 것이다.

## 2. 현재 구현 상태

현재 완료된 기능:

1. `.env` 기반 `OPENAI_API_KEY` 로딩
2. `prompt_llm_for_json` OpenAI API JSON 응답 헬퍼
3. `extract_invoice_data` 인보이스 추출 도구
4. `store_invoice` 인보이스 저장 도구
5. `TOOLS`, `AVAILABLE_TOOLS` 도구 등록 구조
6. `run_invoice_agent` 고정 순서 실행 흐름
7. `main` 직접 실행 진입점
8. 실제 OpenAI API 기반 신규 저장 및 업데이트 검증

현재 실행 흐름:

```text
raw invoice text
  -> extract_invoice_data(raw_text)
  -> store_invoice(invoice_data)
  -> final result summary
```

확장 후 목표 실행 흐름:

```text
raw invoice text
  -> extract_invoice_data(raw_text)
  -> classify_expense(invoice_data)
  -> check_compliance(invoice_data, expense_classification, purchasing_rules.txt)
  -> store_invoice(enriched_invoice_data)
  -> final result summary
```

## 3. 개발 파일 구조

확장 후 파일 구조는 다음과 같이 관리한다.

```text
11주차/
  invoice_agent.py              # 인보이스 에이전트, 도구, 실행 코드
  invoices.json                 # 인보이스 저장소
  purchasing_rules.txt          # 구매 규칙 원문 문서
  INVOICE_AGENT_PLAN.md         # 구현 계획 문서
  INVOICE_AGENT_FEATURES.md     # 기능 요구사항 및 검증 기록
  INVOICE_AGENT_PROGRESS.md     # 진행 상황 기록
  .env                          # 로컬 OpenAI API 키
  .env.example                  # 환경 변수 예시
```

`purchasing_rules.txt`는 Document-as-Implementation 방식으로 사용한다. 즉, 구매 규칙은 Python 코드 안에 조건문으로 하드코딩하지 않고, 실행 시 이 텍스트 파일을 읽어 `check_compliance` 판단 프롬프트의 근거로 전달한다.

## 4. 데이터 구조 확장

기존 인보이스 스키마:

```json
{
  "invoice_number": "INV-001",
  "date": "2026-05-13",
  "vendor": "ACME Corp",
  "currency": "KRW",
  "amount": 120000,
  "items": [
    {
      "name": "Consulting",
      "quantity": 1,
      "unit_price": 120000,
      "total": 120000
    }
  ]
}
```

확장 후 에이전트 결과에는 다음 정보가 추가된다.

```json
{
  "expense_classification": {
    "category": "professional_services",
    "confidence": 0.9,
    "reason": "Consulting service item indicates professional services."
  },
  "compliance": {
    "status": "approved",
    "violations": [],
    "required_actions": [],
    "reason": "The amount is within the approval threshold in purchasing_rules.txt."
  }
}
```

저장 방식은 두 가지 중 하나로 선택한다.

1. 권장: 기존 인보이스 데이터에 `expense_classification`, `compliance` 필드를 추가해 저장한다.
2. 대안: 기존 인보이스 데이터는 그대로 저장하고, 최종 실행 결과에만 분류/준수 결과를 포함한다.

이번 과제에서는 실행 결과 확인과 후속 검증이 쉬운 1번 방식을 우선 적용한다.

## 5. Step 1: `classify_expense` 도구 구현

### 책임

`classify_expense`는 구조화된 인보이스 데이터를 보고 지출 유형을 분류한다. 이 도구는 지출 분류 전문가 페르소나를 가진다.

### 입력

```json
{
  "invoice_data": {
    "invoice_number": "INV-001",
    "vendor": "ACME Corp",
    "amount": 120000,
    "items": []
  }
}
```

### 출력

```json
{
  "ok": true,
  "error": "",
  "data": {
    "category": "professional_services",
    "confidence": 0.9,
    "reason": "The invoice contains consulting services."
  }
}
```

### 분류 후보

초기 후보는 다음 정도로 둔다.

1. `office_supplies`
2. `software`
3. `hardware`
4. `professional_services`
5. `travel`
6. `training`
7. `other`

### 구현 방식

1. `EXPENSE_CLASSIFICATION_SCHEMA` 상수를 추가한다.
2. `prompt_llm_for_json`을 재사용할지, 범용 헬퍼로 확장할지 결정한다.
3. 현재 `prompt_llm_for_json(raw_invoice_text)`는 인보이스 추출 전용이므로 다음 중 하나를 택한다.
   - 권장: `prompt_openai_for_json(system_message, user_message)` 범용 헬퍼를 만들고 기존 추출 함수도 이 헬퍼를 사용하게 정리한다.
   - 간단한 대안: `classify_expense` 내부에서 별도 OpenAI 호출 코드를 작성한다.
4. 시스템 메시지에 “당신은 기업 지출 분류 전문가” 페르소나를 명시한다.
5. 응답은 JSON 객체만 반환하도록 강제한다.
6. 결과를 정규화한다.
   - `category`가 없으면 `other`
   - `confidence`가 없거나 숫자가 아니면 `0`
   - `reason`이 없으면 빈 문자열
7. API 키 누락, API 실패, JSON 파싱 실패는 `ok: false`로 반환한다.

### 단일 책임 기준

`classify_expense`는 구매 규칙 준수 여부를 판단하지 않는다. 오직 지출 카테고리 분류만 수행한다.

## 6. Step 2: `check_compliance` 도구 구현

### 책임

`check_compliance`는 인보이스 데이터, 지출 분류 결과, 구매 규칙 문서를 근거로 구매 규칙 준수 여부를 판단한다. 이 도구는 구매 규정 검토 전문가 페르소나를 가진다.

### 입력

```json
{
  "invoice_data": {},
  "expense_classification": {},
  "rules_text": "구매 규칙 원문"
}
```

실제 도구 함수에서는 `rules_text`를 외부에서 직접 받기보다 `purchasing_rules.txt`를 읽는 구조를 권장한다.

### 출력

```json
{
  "ok": true,
  "error": "",
  "data": {
    "status": "approved",
    "violations": [],
    "required_actions": [],
    "reason": "The invoice satisfies the purchasing rules."
  }
}
```

### 상태 후보

1. `approved`: 규칙 위반 없음
2. `needs_approval`: 추가 승인 필요
3. `rejected`: 명확한 규칙 위반
4. `needs_review`: 정보 부족 또는 판단 불가

### 구현 방식

1. `PURCHASING_RULES_PATH = Path(__file__).with_name("purchasing_rules.txt")` 상수를 추가한다.
2. `load_purchasing_rules()` 함수를 구현한다.
   - 파일이 없으면 명확한 오류 반환
   - 파일이 비어 있으면 명확한 오류 반환
   - UTF-8로 읽는다.
3. `COMPLIANCE_SCHEMA` 상수를 추가한다.
4. 시스템 메시지에 “당신은 회사 구매 규정 준수 검토 전문가” 페르소나를 명시한다.
5. 사용자 메시지에는 다음을 포함한다.
   - 인보이스 JSON
   - 지출 분류 JSON
   - `purchasing_rules.txt` 원문
   - 출력 JSON 스키마
6. LLM은 반드시 규칙 문서에 근거해 판단하도록 지시한다.
7. 결과를 정규화한다.
   - `status`가 후보에 없으면 `needs_review`
   - `violations`가 배열이 아니면 빈 배열
   - `required_actions`가 배열이 아니면 빈 배열
   - `reason`이 없으면 빈 문자열

### 단일 책임 기준

`check_compliance`는 인보이스 추출이나 저장을 하지 않는다. 구매 규칙 준수 판단만 수행한다.

## 7. Step 3: `purchasing_rules.txt` 작성

초기 규칙 파일은 사람이 읽을 수 있는 자연어 문서로 작성한다. 예시는 다음과 같다.

```text
# Purchasing Rules

1. General approval
- Purchases under 100,000 KRW are approved unless another rule requires review.
- Purchases from 100,000 KRW to 500,000 KRW require manager approval.
- Purchases above 500,000 KRW require finance approval.

2. Category rules
- Software purchases require manager approval.
- Hardware purchases above 300,000 KRW require finance approval.
- Professional services require a written contract reference.
- Travel expenses require a trip purpose.

3. Rejection rules
- Missing invoice number must be rejected.
- Missing vendor must require review.
- Any purchase explicitly marked personal must be rejected.
```

### Document-as-Implementation 원칙

1. 규칙 변경은 `purchasing_rules.txt`에서만 한다.
2. Python 코드에는 특정 금액 기준이나 카테고리별 승인 조건을 하드코딩하지 않는다.
3. `check_compliance`는 실행할 때마다 최신 파일 내용을 읽는다.
4. 규칙 파일 수정 후 Python 코드를 바꾸지 않고 재실행해 결과 변화를 확인한다.

## 8. Step 4: 에이전트에 두 도구 추가 후 실행

### 도구 등록

`TOOLS`에 다음 도구를 추가한다.

1. `classify_expense`
2. `check_compliance`

각 도구는 `name`, `description`, `input_schema`를 가진다.

`AVAILABLE_TOOLS`에는 실제 실행 함수를 매핑한다.

```python
AVAILABLE_TOOLS = {
    "extract_invoice_data": extract_invoice_data,
    "classify_expense": classify_expense,
    "check_compliance": check_compliance,
    "store_invoice": store_invoice,
}
```

### 실행 순서

`run_invoice_agent`는 다음 순서를 따른다.

1. `extract_invoice_data`
2. `classify_expense`
3. `check_compliance`
4. `store_invoice`

중간 단계 실패 시 다음 단계로 진행하지 않고 실패 결과를 반환한다.

### 최종 결과 예시

```json
{
  "ok": true,
  "stage": "complete",
  "error": "",
  "invoice": {},
  "expense_classification": {},
  "compliance": {},
  "store": {},
  "summary": "Invoice INV-001 was stored. Compliance status: needs_approval."
}
```

## 9. 심화 검증: 규칙 파일 변경 테스트

규칙 파일 변경이 실제 동작에 반영되는지 다음 순서로 확인한다.

### 테스트 A: 기본 규칙

1. `purchasing_rules.txt`에 “100,000 KRW 이상은 manager approval 필요” 규칙을 둔다.
2. 예시 인보이스 금액 `120000`으로 실행한다.
3. 예상 결과: `status`가 `needs_approval` 또는 그에 준하는 결과가 나온다.

### 테스트 B: 규칙 완화

1. Python 코드는 수정하지 않는다.
2. `purchasing_rules.txt`만 수정해 “200,000 KRW 미만은 approved”로 바꾼다.
3. 같은 인보이스로 다시 실행한다.
4. 예상 결과: `status`가 `approved`로 바뀐다.

### 테스트 C: 규칙 강화

1. Python 코드는 수정하지 않는다.
2. `purchasing_rules.txt`에 “Professional services always require finance approval”을 추가한다.
3. 같은 인보이스로 다시 실행한다.
4. 예상 결과: 지출 분류가 `professional_services`일 때 `needs_approval` 또는 finance approval 요구가 나온다.

이 검증이 성공하면 규칙 문서가 실제 구현처럼 동작한다는 것을 확인할 수 있다.

## 10. 검증 계획

### 문법 검증

```powershell
uv run python -m py_compile 11주차/invoice_agent.py
```

### 도구 등록 검증

확인 항목:

1. `TOOLS`에 네 도구가 모두 등록되어 있는가
2. 각 도구에 `input_schema`가 있는가
3. `AVAILABLE_TOOLS`에 실제 함수가 모두 매핑되어 있는가

예상 도구:

```text
extract_invoice_data
classify_expense
check_compliance
store_invoice
```

### 단위 검증

1. `classify_expense` fake LLM 응답으로 정상 분류 확인
2. `classify_expense` API 키 누락/JSON 오류 처리 확인
3. `load_purchasing_rules` 파일 없음/빈 파일/정상 파일 확인
4. `check_compliance` fake LLM 응답으로 상태 정규화 확인
5. `check_compliance` 규칙 파일 오류 처리 확인

### 흐름 검증

1. 정상 인보이스 입력
2. 추출 실패 시 분류/준수/저장 미실행
3. 분류 실패 시 준수/저장 미실행
4. 규칙 파일 없음으로 준수 검토 실패
5. 준수 검토 성공 후 enriched invoice 저장
6. 같은 인보이스 번호 재실행 시 업데이트 확인

### 실제 OpenAI API 검증

`.env`에 `OPENAI_API_KEY`가 설정된 상태에서 실행한다.

```powershell
uv run python 11주차/invoice_agent.py
```

확인 항목:

1. 인보이스 추출 성공
2. 지출 분류 성공
3. 구매 규칙 준수 판단 성공
4. 저장 성공
5. 콘솔 요약에 compliance status 표시
6. `invoices.json`에 분류/준수 결과 포함

## 11. 작업 순서

권장 구현 순서:

1. `purchasing_rules.txt` 초안 작성
2. `PURCHASING_RULES_PATH`, `load_purchasing_rules` 추가
3. OpenAI JSON 호출 헬퍼를 범용화
4. `classify_expense` 구현
5. `check_compliance` 구현
6. `TOOLS`, `AVAILABLE_TOOLS` 업데이트
7. `run_invoice_agent` 흐름 확장
8. `main` 출력에 분류/준수 결과가 잘 보이도록 정리
9. fake LLM 기반 단위 검증
10. 실제 API 기반 end-to-end 검증
11. `purchasing_rules.txt` 변경 전후 결과 비교
12. 검증 결과를 `INVOICE_AGENT_FEATURES.md`, `INVOICE_AGENT_PROGRESS.md`에 기록

## 12. 주의 사항

- OpenAI API 키는 코드에 직접 작성하지 않는다.
- 구매 규칙은 코드에 하드코딩하지 않는다.
- `purchasing_rules.txt`는 UTF-8 텍스트로 관리한다.
- 규칙 파일이 없거나 비어 있으면 `check_compliance`는 명확히 실패해야 한다.
- LLM 출력은 항상 JSON 객체로 파싱하고 정규화한다.
- 각 도구는 단일 책임을 유지한다.
- 실제 OpenAI API 검증은 외부 API 상태와 비용에 영향을 받을 수 있다.
