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


def prompt_llm_for_json(raw_invoice_text: str) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The openai package is not installed. Run: uv add openai") from exc

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
    normalized_invoice = normalize_invoice_data(invoice_data)
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
            "store": None,
            "summary": f"Invoice extraction failed: {extract_result['error']}",
        }

    invoice_data = extract_result["data"]
    store_result = AVAILABLE_TOOLS["store_invoice"](invoice_data)
    if not store_result["ok"]:
        return {
            "ok": False,
            "stage": "store_invoice",
            "error": store_result["error"],
            "invoice": invoice_data,
            "store": store_result,
            "summary": f"Invoice storage failed: {store_result['error']}",
        }

    action = "updated" if store_result["updated"] else "stored"
    invoice_number = store_result["invoice_number"]
    return {
        "ok": True,
        "stage": "complete",
        "error": "",
        "invoice": invoice_data,
        "store": store_result,
        "summary": f"Invoice {invoice_number} was {action}.",
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
