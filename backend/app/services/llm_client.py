import json
import re
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings


class OllamaClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def health(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{self.settings.ollama_base_url}/api/tags")
                response.raise_for_status()
            return "ok"
        except Exception:
            return "unreachable"

    async def generate_json(self, system_prompt: str, payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
        prompt = f"{system_prompt.strip()}\n\nINPUT JSON:\n{json.dumps(payload, ensure_ascii=False)}"
        body = {
            "model": self.settings.local_llm_model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1},
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{self.settings.ollama_base_url}/api/generate", json=body)
            response.raise_for_status()
        return extract_json_object(response.json().get("response", ""))


def load_prompt(name: str) -> str:
    return (Path(__file__).resolve().parents[1] / "prompts" / name).read_text(encoding="utf-8")


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.I | re.S).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        candidate = first_json_object(text)
        if candidate is None:
            raise
        return json.loads(candidate)


def first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(text[start:], start=start):
        if escape:
            escape = False
            continue
        if char == "\\" and in_string:
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None
