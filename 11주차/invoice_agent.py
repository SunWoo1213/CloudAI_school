from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


MODEL_NAME = "gpt-4.1-mini"
INVOICE_STORE_PATH = Path(__file__).with_name("invoices.json")
PURCHASING_RULES_PATH = Path(__file__).with_name("purchasing_rules.txt")
EXAMPLE_INVOICE_TEXT = """
Invoice Number: INV-001
Date: 2026-05-13
Vendor: ACME Corp
Currency: KRW
Item: Consulting, Quantity: 1, Unit Price: 120000, Total: 120000
Amount Due: 120000
""".strip()
ENV_FILE_PATHS = [
    Path(__file__).with_name(".env"),
    Path(__file__).resolve().parent.parent / ".env",
]

INVOICE_SCHEMA: dict[str, Any] = {
    "invoice_number": "",
    "date": "",
    "vendor": "",
    "currency": "",
    "amount": 0,
    "items": [
        {
            "name": "",
            "quantity": 0,
            "unit_price": 0,
            "total": 0,
        }
    ],
}
EXPENSE_CATEGORIES = {
    "office_supplies",
    "software",
    "hardware",
    "professional_services",
    "travel",
    "training",
    "other",
}
COMPLIANCE_STATUSES = {
    "approved",
    "needs_approval",
    "rejected",
    "needs_review",
}
EXPENSE_CLASSIFICATION_SCHEMA: dict[str, Any] = {
    "category": "professional_services",
    "confidence": 0.9,
    "reason": "The invoice contains consulting services.",
}
COMPLIANCE_SCHEMA: dict[str, Any] = {
    "status": "approved",
    "violations": [],
    "required_actions": [],
    "reason": "The invoice satisfies the purchasing rules.",
}


def prompt_openai_for_json(system_message: str, user_message: str) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The openai package is not installed. Run: uv add openai") from exc

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI returned an empty response.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI response was not valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("OpenAI response JSON must be an object.")

    return parsed


def prompt_llm_for_json(raw_invoice_text: str) -> dict[str, Any]:
    system_message = (
        "You extract invoice data. Return only one valid JSON object. "
        "Do not include markdown, explanations, or code fences."
    )
    user_message = (
        "Extract the invoice below into this exact schema. "
        "Use empty strings, 0, and empty arrays for missing values.\n\n"
        f"Schema:\n{json.dumps(INVOICE_SCHEMA, ensure_ascii=False, indent=2)}\n\n"
        f"Invoice text:\n{raw_invoice_text}"
    )
    return prompt_openai_for_json(system_message, user_message)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_number(value: Any) -> int | float:
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return value
    if isinstance(value, str):
        cleaned = (
            value.strip()
            .replace(",", "")
            .replace("KRW", "")
            .replace("USD", "")
            .replace("$", "")
        )
        try:
            number = float(cleaned)
        except ValueError:
            return 0
        return int(number) if number.is_integer() else number
    return 0


def _normalize_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []

    normalized_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized_items.append(
            {
                "name": _as_text(item.get("name")),
                "quantity": _as_number(item.get("quantity")),
                "unit_price": _as_number(item.get("unit_price")),
                "total": _as_number(item.get("total")),
            }
        )
    return normalized_items


def normalize_invoice_data(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "invoice_number": _as_text(data.get("invoice_number")),
        "date": _as_text(data.get("date")),
        "vendor": _as_text(data.get("vendor")),
        "currency": _as_text(data.get("currency")),
        "amount": _as_number(data.get("amount")),
        "items": _normalize_items(data.get("items")),
    }


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_as_text(item) for item in value if _as_text(item)]


def normalize_expense_classification(data: dict[str, Any]) -> dict[str, Any]:
    category = _as_text(data.get("category"))
    if category not in EXPENSE_CATEGORIES:
        category = "other"

    confidence_value = data.get("confidence")
    if isinstance(confidence_value, bool):
        confidence = 0
    else:
        confidence = _as_number(confidence_value)
    if not isinstance(confidence, int | float):
        confidence = 0
    confidence = max(0, min(1, confidence))

    return {
        "category": category,
        "confidence": confidence,
        "reason": _as_text(data.get("reason")),
    }


def normalize_compliance(data: dict[str, Any]) -> dict[str, Any]:
    status = _as_text(data.get("status"))
    if status not in COMPLIANCE_STATUSES:
        status = "needs_review"

    return {
        "status": status,
        "violations": _as_string_list(data.get("violations")),
        "required_actions": _as_string_list(data.get("required_actions")),
        "reason": _as_text(data.get("reason")),
    }


def normalize_enriched_invoice_data(data: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_invoice_data(data)

    if isinstance(data.get("expense_classification"), dict):
        normalized["expense_classification"] = normalize_expense_classification(
            data["expense_classification"]
        )

    if isinstance(data.get("compliance"), dict):
        normalized["compliance"] = normalize_compliance(data["compliance"])

    return normalized


def extract_invoice_data(raw_text: str) -> dict[str, Any]:
    if not raw_text.strip():
        return {
            "ok": False,
            "error": "Invoice text is empty.",
            "data": normalize_invoice_data({}),
        }

    try:
        llm_data = prompt_llm_for_json(raw_text)
    except RuntimeError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "data": normalize_invoice_data({}),
        }

    return {
        "ok": True,
        "error": "",
        "data": normalize_invoice_data(llm_data),
    }


def classify_expense(invoice_data: dict[str, Any]) -> dict[str, Any]:
    normalized_invoice = normalize_invoice_data(invoice_data)
    system_message = (
        "You are a corporate expense classification expert. "
        "Classify the invoice into exactly one category. "
        "Return only one valid JSON object. Do not include markdown, "
        "explanations, or code fences."
    )
    user_message = (
        "Classify this invoice by vendor, amount, item names, and item details. "
        "Do not evaluate purchasing compliance.\n\n"
        f"Allowed categories:\n{json.dumps(sorted(EXPENSE_CATEGORIES), indent=2)}\n\n"
        f"Output schema:\n"
        f"{json.dumps(EXPENSE_CLASSIFICATION_SCHEMA, ensure_ascii=False, indent=2)}\n\n"
        f"Invoice data:\n"
        f"{json.dumps(normalized_invoice, ensure_ascii=False, indent=2)}"
    )

    try:
        llm_data = prompt_openai_for_json(system_message, user_message)
    except RuntimeError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "data": normalize_expense_classification({}),
        }

    return {
        "ok": True,
        "error": "",
        "data": normalize_expense_classification(llm_data),
    }


def load_purchasing_rules() -> dict[str, Any]:
    if not PURCHASING_RULES_PATH.exists():
        return {
            "ok": False,
            "error": "purchasing_rules.txt was not found.",
            "data": "",
        }

    try:
        rules_text = PURCHASING_RULES_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        return {
            "ok": False,
            "error": f"Could not read purchasing_rules.txt: {exc}",
            "data": "",
        }

    if not rules_text:
        return {
            "ok": False,
            "error": "purchasing_rules.txt is empty.",
            "data": "",
        }

    return {
        "ok": True,
        "error": "",
        "data": rules_text,
    }


def check_compliance(
    invoice_data: dict[str, Any], expense_classification: dict[str, Any]
) -> dict[str, Any]:
    normalized_invoice = normalize_invoice_data(invoice_data)
    normalized_classification = normalize_expense_classification(
        expense_classification
    )
    rules_result = load_purchasing_rules()
    if not rules_result["ok"]:
        return {
            "ok": False,
            "error": rules_result["error"],
            "data": normalize_compliance({}),
        }

    system_message = (
        "You are a company purchasing policy compliance reviewer. "
        "Judge compliance only from the provided purchasing rules document, "
        "invoice data, and expense classification. "
        "Return only one valid JSON object. Do not include markdown, "
        "explanations, or code fences."
    )
    user_message = (
        "Review the invoice against the purchasing rules. "
        "If approval is required, use status needs_approval. "
        "If a rejection rule clearly applies, use status rejected. "
        "If information is missing or the rules are insufficient to decide, "
        "use status needs_review. Otherwise use approved.\n\n"
        f"Output schema:\n{json.dumps(COMPLIANCE_SCHEMA, ensure_ascii=False, indent=2)}\n\n"
        f"Invoice data:\n{json.dumps(normalized_invoice, ensure_ascii=False, indent=2)}\n\n"
        "Expense classification:\n"
        f"{json.dumps(normalized_classification, ensure_ascii=False, indent=2)}\n\n"
        f"Purchasing rules document:\n{rules_result['data']}"
    )

    try:
        llm_data = prompt_openai_for_json(system_message, user_message)
    except RuntimeError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "data": normalize_compliance({}),
        }

    return {
        "ok": True,
        "error": "",
        "data": normalize_compliance(llm_data),
    }


def _load_invoice_store() -> dict[str, Any]:
    if not INVOICE_STORE_PATH.exists():
        return {}

    try:
        with INVOICE_STORE_PATH.open("r", encoding="utf-8") as file:
            store = json.load(file)
    except OSError as exc:
        raise RuntimeError(f"Could not read invoice store: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invoice store is not valid JSON.") from exc

    if not isinstance(store, dict):
        raise RuntimeError("Invoice store must be a JSON object.")

    return store


def _save_invoice_store(store: dict[str, Any]) -> None:
    try:
        with INVOICE_STORE_PATH.open("w", encoding="utf-8") as file:
            json.dump(store, file, ensure_ascii=False, indent=2)
            file.write("\n")
    except OSError as exc:
        raise RuntimeError(f"Could not write invoice store: {exc}") from exc


def store_invoice(invoice_data: dict[str, Any]) -> dict[str, Any]:
    normalized_invoice = normalize_enriched_invoice_data(invoice_data)
    invoice_number = normalized_invoice["invoice_number"]

    if not invoice_number:
        return {
            "ok": False,
            "error": "invoice_number is required.",
            "updated": False,
            "invoice_number": "",
        }

    try:
        store = _load_invoice_store()
        updated = invoice_number in store
        store[invoice_number] = normalized_invoice
        _save_invoice_store(store)
    except RuntimeError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "updated": False,
            "invoice_number": invoice_number,
        }

    return {
        "ok": True,
        "error": "",
        "updated": updated,
        "invoice_number": invoice_number,
    }


def run_invoice_agent(raw_invoice_text: str) -> dict[str, Any]:
    extract_result = AVAILABLE_TOOLS["extract_invoice_data"](raw_invoice_text)
    if not extract_result["ok"]:
        return {
            "ok": False,
            "stage": "extract_invoice_data",
            "error": extract_result["error"],
            "invoice": extract_result["data"],
            "expense_classification": None,
            "compliance": None,
            "store": None,
            "summary": f"Invoice extraction failed: {extract_result['error']}",
        }

    invoice_data = extract_result["data"]
    classification_result = AVAILABLE_TOOLS["classify_expense"](invoice_data)
    if not classification_result["ok"]:
        return {
            "ok": False,
            "stage": "classify_expense",
            "error": classification_result["error"],
            "invoice": invoice_data,
            "expense_classification": classification_result["data"],
            "compliance": None,
            "store": None,
            "summary": (
                "Expense classification failed: "
                f"{classification_result['error']}"
            ),
        }

    expense_classification = classification_result["data"]
    compliance_result = AVAILABLE_TOOLS["check_compliance"](
        invoice_data, expense_classification
    )
    if not compliance_result["ok"]:
        return {
            "ok": False,
            "stage": "check_compliance",
            "error": compliance_result["error"],
            "invoice": invoice_data,
            "expense_classification": expense_classification,
            "compliance": compliance_result["data"],
            "store": None,
            "summary": (
                "Purchasing compliance check failed: "
                f"{compliance_result['error']}"
            ),
        }

    compliance = compliance_result["data"]
    enriched_invoice_data = {
        **invoice_data,
        "expense_classification": expense_classification,
        "compliance": compliance,
    }

    store_result = AVAILABLE_TOOLS["store_invoice"](enriched_invoice_data)
    if not store_result["ok"]:
        return {
            "ok": False,
            "stage": "store_invoice",
            "error": store_result["error"],
            "invoice": enriched_invoice_data,
            "expense_classification": expense_classification,
            "compliance": compliance,
            "store": store_result,
            "summary": f"Invoice storage failed: {store_result['error']}",
        }

    action = "updated" if store_result["updated"] else "stored"
    invoice_number = store_result["invoice_number"]
    compliance_status = compliance["status"]
    return {
        "ok": True,
        "stage": "complete",
        "error": "",
        "invoice": enriched_invoice_data,
        "expense_classification": expense_classification,
        "compliance": compliance,
        "store": store_result,
        "summary": (
            f"Invoice {invoice_number} was {action}. "
            f"Compliance status: {compliance_status}."
        ),
    }


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


TOOLS = [
    {
        "name": "extract_invoice_data",
        "description": "Convert raw invoice text into the fixed invoice JSON schema.",
        "input_schema": {
            "type": "object",
            "properties": {
                "raw_text": {"type": "string"},
            },
            "required": ["raw_text"],
        },
    },
    {
        "name": "classify_expense",
        "description": "Classify normalized invoice data into one expense category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_data": {
                    "type": "object",
                    "properties": {
                        "invoice_number": {"type": "string"},
                        "date": {"type": "string"},
                        "vendor": {"type": "string"},
                        "currency": {"type": "string"},
                        "amount": {"type": "number"},
                        "items": {"type": "array"},
                    },
                    "required": ["invoice_number"],
                }
            },
            "required": ["invoice_data"],
        },
    },
    {
        "name": "check_compliance",
        "description": (
            "Review invoice compliance against purchasing_rules.txt and "
            "the expense classification."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_data": {
                    "type": "object",
                    "properties": {
                        "invoice_number": {"type": "string"},
                        "date": {"type": "string"},
                        "vendor": {"type": "string"},
                        "currency": {"type": "string"},
                        "amount": {"type": "number"},
                        "items": {"type": "array"},
                    },
                    "required": ["invoice_number"],
                },
                "expense_classification": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "confidence": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["category"],
                },
            },
            "required": ["invoice_data", "expense_classification"],
        },
    },
    {
        "name": "store_invoice",
        "description": "Store normalized invoice data by invoice_number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_data": {
                    "type": "object",
                    "properties": {
                        "invoice_number": {"type": "string"},
                        "date": {"type": "string"},
                        "vendor": {"type": "string"},
                        "currency": {"type": "string"},
                        "amount": {"type": "number"},
                        "items": {"type": "array"},
                        "expense_classification": {"type": "object"},
                        "compliance": {"type": "object"},
                    },
                    "required": ["invoice_number"],
                }
            },
            "required": ["invoice_data"],
        },
    }
]

AVAILABLE_TOOLS = {
    "extract_invoice_data": extract_invoice_data,
    "classify_expense": classify_expense,
    "check_compliance": check_compliance,
    "store_invoice": store_invoice,
}


def main() -> None:
    load_env_files()

    print("Enter invoice text. Leave blank to use the example invoice.")
    raw_invoice_text = input("> ").strip()
    if not raw_invoice_text:
        raw_invoice_text = EXAMPLE_INVOICE_TEXT

    result = run_invoice_agent(raw_invoice_text)
    print(result["summary"])
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not result["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
