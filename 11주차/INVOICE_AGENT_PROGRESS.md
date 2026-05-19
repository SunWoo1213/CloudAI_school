# 인보이스 에이전트 진행 사항

## 1. 현재 상태

`invoice_agent.py`의 기본 인보이스 처리 흐름은 구현 및 검증이 완료되었다.

현재 구현된 범위는 OpenAI API 기반 JSON 프롬프트 헬퍼, `.env` 로딩, 인보이스 데이터 정규화, `extract_invoice_data` 도구, `store_invoice` 도구, 구매 규칙 파일 초안, 구매 규칙 로더, 기본 도구 등록 구조, `run_invoice_agent` 실행 흐름, `main` 직접 실행 진입점이다.

실제 `OPENAI_API_KEY`가 설정된 환경에서 OpenAI API를 호출했고, 예시 인보이스의 신규 저장과 업데이트가 실제 `11주차/invoices.json`에 반영되는 것을 확인했다.

새 기획서 기준으로는 다음 확장이 필요하다.

1. 지출 분류 전문가 도구 `classify_expense` 추가
2. 구매 규정 준수 전문가 도구 `check_compliance` 추가
3. OpenAI JSON 호출 헬퍼 범용화
4. `check_compliance`에서 구매 규칙 문서를 실제 판단 근거로 사용하도록 연결
5. 4단계 실행 흐름 적용
6. 저장 데이터에 `expense_classification`, `compliance` 포함
7. 규칙 파일 변경 전후 동작 변화 검증

## 2. 완료된 작업

- `11주차/INVOICE_AGENT_PLAN.md` 작성 및 확장 계획으로 갱신
- `11주차/INVOICE_AGENT_FEATURES.md` 작성 및 신규 요구사항 반영
- 인보이스 에이전트 기본 목표 정리
- 필수 기본 도구 구조 정리
  - `extract_invoice_data`
  - `store_invoice`
- 고정 인보이스 스키마 정의
- 기본 에이전트 실행 흐름 정의
  - 인보이스 텍스트 수신
  - `extract_invoice_data` 호출
  - `store_invoice` 호출
  - 처리 결과 확인
- OpenAI API 사용 방식으로 계획 수정
- `OPENAI_API_KEY` 환경 변수 사용 계획 반영
- `prompt_llm_for_json`을 OpenAI API 기반 헬퍼로 설계
- `11주차/invoice_agent.py` 구현
- `MODEL_NAME` 상수 정의
- `INVOICE_SCHEMA` 고정 스키마 정의
- `prompt_llm_for_json` 함수 구현
- 인보이스 데이터 정규화 함수 구현
  - `_as_text`
  - `_as_number`
  - `_normalize_items`
  - `normalize_invoice_data`
- `extract_invoice_data` 도구 구현
- `store_invoice` 도구 구현
- `TOOLS`, `AVAILABLE_TOOLS`에 `extract_invoice_data`, `store_invoice` 등록
- 도구 등록 정보에 입력 스키마 추가
- `run_invoice_agent` 기본 실행 흐름 구현
- `main` 직접 실행 진입점 구현
- `if __name__ == "__main__"` guard 구현
- `.env` 로딩 기능 구현
- `invoice_agent.py` 문법 검증 완료
- `prompt_llm_for_json` fake OpenAI 응답 기반 검증 완료
- `extract_invoice_data` fake LLM 응답 기반 검증 완료
- `store_invoice` 임시 저장소 기반 검증 완료
- `run_invoice_agent` 임시 저장소 기반 검증 완료
- `main` 입력/출력 동작 검증 완료
- `OPENAI_API_KEY` 누락 상태의 직접 실행 실패 경로 검증 완료
- 실제 OpenAI API 호출 기반 end-to-end 신규 저장 검증 완료
- 실제 OpenAI API 호출 기반 end-to-end 업데이트 검증 완료
- 실제 `11주차/invoices.json` 생성 및 저장 내용 검증 완료
- `11주차/purchasing_rules.txt` 초안 작성 완료
- `PURCHASING_RULES_PATH` 상수 추가 완료
- `load_purchasing_rules()` 함수 구현 완료
- `load_purchasing_rules()` 정상 규칙 파일 로드 확인 완료

## 3. 새 기획서 반영 완료 사항

- 기존 플랜을 전문가 도구 2개 추가 계획으로 갱신했다.
- `classify_expense`의 책임, 입력, 출력, 분류 후보, 정규화 방식을 문서화했다.
- `check_compliance`의 책임, 입력, 출력, 상태 후보, 정규화 방식을 문서화했다.
- `purchasing_rules.txt`를 Document-as-Implementation으로 사용하는 방식을 문서화했다.
- 확장 후 에이전트 실행 순서를 다음과 같이 정의했다.

```text
raw invoice text
  -> extract_invoice_data(raw_text)
  -> classify_expense(invoice_data)
  -> check_compliance(invoice_data, expense_classification, purchasing_rules.txt)
  -> store_invoice(enriched_invoice_data)
  -> final result summary
```

- 규칙 파일 변경 전후 동작 변화 검증 시나리오를 추가했다.
- Feature List에 신규 지출 분류, 구매 규칙 로딩, 구매 규정 준수 검토, 확장 검증 요구사항을 반영했다.

## 4. 아직 진행되지 않은 작업

- OpenAI JSON 호출 헬퍼 범용화
- `EXPENSE_CLASSIFICATION_SCHEMA` 추가
- `classify_expense` 구현
- `COMPLIANCE_SCHEMA` 추가
- `check_compliance` 구현
- `TOOLS`에 `classify_expense`, `check_compliance` 등록
- `AVAILABLE_TOOLS`에 `classify_expense`, `check_compliance` 매핑
- `run_invoice_agent` 실행 순서 확장
- `store_invoice`에 저장할 enriched invoice 구조 정리
- `main` 콘솔 요약에 compliance status 출력
- 신규 도구 단위 검증
- 확장된 end-to-end 검증
- `purchasing_rules.txt` 변경 전후 결과 비교 검증

## 5. 2026-05-13 추가 검증 결과

- 문법 검증
  - 명령어: `uv run python -m py_compile 11주차/invoice_agent.py`
  - 결과: 성공
  - 참고: sandbox 환경에서는 `uv` 캐시 접근 권한 문제로 실패했으며, 권한 승인 후 성공했다.
- 도구 등록 검증
  - `TOOLS`: `extract_invoice_data`, `store_invoice`
  - `AVAILABLE_TOOLS`: `extract_invoice_data`, `store_invoice`
  - `classify_expense`: 미구현
  - `check_compliance`: 미구현
  - 판단: 네 도구 등록 요구사항은 아직 미충족이다.
- 구매 규칙 로더 검증
  - `purchasing_rules.txt`: 존재함
  - `load_purchasing_rules()`: 존재함
  - 정상 규칙 파일 로드 결과: `ok: True`
  - 판단: 규칙 파일과 로더는 구현되었지만, 준수 검토 도구가 없어 실제 판단 흐름에는 아직 연결되지 않았다.
- 실행 흐름 검증
  - 현재 `run_invoice_agent` 흐름: `extract_invoice_data -> store_invoice`
  - 목표 흐름: `extract_invoice_data -> classify_expense -> check_compliance -> store_invoice`
  - fake LLM 기반 실행 결과에 `expense_classification`, `compliance` 필드는 포함되지 않았다.
- 저장 확장성 검증
  - `store_invoice`에 `expense_classification`, `compliance`가 포함된 입력을 전달했다.
  - 저장된 JSON에는 기본 인보이스 필드만 남았다.
  - 원인: `store_invoice`가 `normalize_invoice_data()` 결과만 저장하기 때문이다.
  - 판단: enriched invoice 저장 요구사항은 아직 미충족이다.

## 6. 기존 검증 진행 사항

- 문법 검증
  - 명령어: `uv run python -m py_compile '11주차/invoice_agent.py'`
  - 결과: 성공
  - 참고: 최초 sandbox 실행에서는 `uv` 캐시 권한 문제로 실패했으나, 권한 승인 후 동일 명령이 성공했다.
- `prompt_llm_for_json` 검증
  - 방식: fake OpenAI 모듈 주입
  - 정상 JSON 응답: 성공
  - 잘못된 JSON 응답: `OpenAI response was not valid JSON.`
  - 빈 응답: `OpenAI returned an empty response.`
  - 객체가 아닌 JSON 응답: `OpenAI response JSON must be an object.`
- `extract_invoice_data` 검증
  - 방식: `prompt_llm_for_json` fake 함수 교체
  - 정상 입력: 성공
  - 빈 입력 실패 메시지: `Invoice text is empty.`
  - API 키 누락 실패 메시지: `OPENAI_API_KEY is not set.`
- `store_invoice` 검증
  - 신규 저장 결과: `ok: True`, `updated: False`
  - 업데이트 결과: `ok: True`, `updated: True`
  - 빈 번호 실패 메시지: `invoice_number is required.`
  - 깨진 JSON 저장소 실패 메시지: `Invoice store is not valid JSON.`
  - JSON 객체가 아닌 저장소 실패 메시지: `Invoice store must be a JSON object.`
  - 읽기/쓰기 실패 처리 확인
- `run_invoice_agent` 검증
  - 성공 흐름: `ok: True`, `stage: complete`
  - 추출 실패 흐름: `stage: extract_invoice_data`
  - 저장 실패 흐름: `stage: store_invoice`
- `main` 직접 실행 검증
  - 빈 입력 시 예시 인보이스 사용 확인
  - 사용자 입력 전달 확인
  - 성공 출력 확인
  - 실패 시 종료 코드 `1` 확인
- 실제 OpenAI API end-to-end 검증
  - 신규 저장 결과: `Invoice INV-001 was stored.`
  - 업데이트 결과: `Invoice INV-001 was updated.`
  - `11주차/invoices.json` 저장 확인

## 7. 다음 작업 예정

구현 순서는 다음과 같이 진행한다.

1. OpenAI JSON 호출 헬퍼 범용화
2. `EXPENSE_CLASSIFICATION_SCHEMA` 추가
3. `classify_expense` 구현
4. `COMPLIANCE_SCHEMA` 추가
5. `check_compliance` 구현
6. `TOOLS`, `AVAILABLE_TOOLS` 업데이트
7. `run_invoice_agent`를 4단계 도구 흐름으로 확장
8. 저장 데이터에 `expense_classification`, `compliance` 포함
9. `main` 콘솔 요약에 compliance status 출력
10. fake LLM 기반 단위 검증
11. 실제 OpenAI API 기반 end-to-end 검증
12. `purchasing_rules.txt` 변경 전후 결과 비교
13. 검증 결과를 Feature List와 Progress 문서에 추가 기록

## 9. 2026-05-19 확장 구현 결과

- OpenAI JSON 호출 헬퍼를 `prompt_openai_for_json(system_message, user_message)`로 범용화했다.
- 기존 `prompt_llm_for_json(raw_invoice_text)`는 인보이스 추출 전용 래퍼로 유지했다.
- `EXPENSE_CLASSIFICATION_SCHEMA`와 `COMPLIANCE_SCHEMA`를 추가했다.
- `classify_expense(invoice_data)` 도구를 구현했다.
- `check_compliance(invoice_data, expense_classification)` 도구를 구현했다.
- `check_compliance`는 실행 시점마다 `purchasing_rules.txt`를 읽어 판단 프롬프트에 전달한다.
- `store_invoice`가 `expense_classification`, `compliance` 확장 필드를 보존해 저장하도록 변경했다.
- `TOOLS`와 `AVAILABLE_TOOLS`에 네 도구를 모두 등록했다.
- `run_invoice_agent` 흐름을 다음 순서로 확장했다.

```text
extract_invoice_data
  -> classify_expense
  -> check_compliance
  -> store_invoice
```

- 중간 단계 실패 시 이후 단계가 실행되지 않도록 실패 분기를 추가했다.
- 최종 요약에 compliance status가 표시되도록 변경했다.

### 검증 결과

- 문법 검증
  - 명령어: `uv run python -m py_compile '11주차/invoice_agent.py'`
  - 결과: 성공
  - 참고: sandbox 환경의 `uv` 캐시 접근 권한 문제로 최초 실행은 실패했고, 권한 승인 후 성공했다.
- fake LLM 기반 4단계 흐름 검증
  - 인보이스 추출, 지출 분류, 구매 규정 검토, 저장 흐름이 `ok: True`로 완료되는 것을 확인했다.
  - 저장 JSON에 `expense_classification.category = professional_services`가 포함되는 것을 확인했다.
  - 저장 JSON에 `compliance.status = needs_approval`이 포함되는 것을 확인했다.
  - `TOOLS` 순서가 `extract_invoice_data`, `classify_expense`, `check_compliance`, `store_invoice`인지 확인했다.
  - `AVAILABLE_TOOLS`가 네 도구 전체와 일치하는지 확인했다.

### 실제 OpenAI API 검증 결과

- 검증 방식: `.env`의 `OPENAI_API_KEY`를 `load_env_files()`로 로드한 뒤 `run_invoice_agent(EXAMPLE_INVOICE_TEXT)` 직접 실행
- 결과: 성공
- 실행 결과: `ok: True`, `stage: complete`
- 요약: `Invoice INV-001 was updated. Compliance status: needs_review.`
- 인보이스 번호: `INV-001`
- 지출 분류: `professional_services`
- 구매 규정 상태: `needs_review`
- 저장 확인: `invoices.json`에 `expense_classification`, `compliance` 필드가 포함됨

### 규칙 파일 변경 전후 검증 결과

- 검증 방식: Python 코드는 수정하지 않고 `purchasing_rules.txt` 내용만 임시 변경한 뒤 같은 `EXAMPLE_INVOICE_TEXT`로 실제 OpenAI API 실행
- 원래 규칙 실행 결과: `needs_approval`
  - 근거: `120,000 KRW` 금액 구간에 manager approval 필요
- 완화 규칙 실행 결과: `approved`
  - 변경 내용: `200,000 KRW` 미만 승인, `200,000 KRW` 미만 professional services 계약 참조 불필요
- 원래 규칙으로 복구 후 실행 결과: `needs_review`
  - 근거: professional services에 written contract reference 필요
- 판단: 규칙 파일 내용 변경만으로 동일 인보이스의 준수 판단이 바뀌는 것을 확인했다.

### 남은 검증

- 없음

## 10. 주의 사항

- 각 도구는 단일 책임만 가진다.
- `extract_invoice_data`는 파싱과 스키마 정규화만 담당한다.
- `classify_expense`는 지출 유형 분류만 담당한다.
- `check_compliance`는 구매 규정 준수 판단만 담당한다.
- `store_invoice`는 저장만 담당한다.
- OpenAI API 키는 코드에 직접 작성하지 않고 환경 변수 `OPENAI_API_KEY`로만 사용한다.
- 구매 규칙은 Python 코드에 하드코딩하지 않는다.
- `purchasing_rules.txt`를 수정하면 Python 코드 수정 없이 결과가 바뀌어야 한다.
- 실제 OpenAI API 호출 검증은 API 키가 설정된 환경에서만 수행한다.
- 실제 OpenAI API 호출 검증은 외부 API 상태와 과금 가능성에 의존한다.
