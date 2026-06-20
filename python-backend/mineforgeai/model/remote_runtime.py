from __future__ import annotations

import json
import os
import ssl
import urllib.request
from typing import Optional


class RemoteModelRuntime:
    """Simple remote LLM wrapper. If `OPENAI_API_KEY` (or env `MINEFORGE_OPENAI_API_KEY`) is set,
    it will attempt a real request to OpenAI's chat completion endpoint. Otherwise
    it provides a prompt-based mock response so the CLI still behaves interactively.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("MINEFORGE_OPENAI_API_KEY")
        self.model = model or os.environ.get("MINEFORGE_OPENAI_MODEL") or "gpt-4o-mini"

    def generate_text(self, prompt: str, max_new_tokens: int = 160, temperature: float = 0.8, **_kwargs) -> str:
        if not self.api_key:
            # Mock: try to extract the user's message from the prompt for more varied replies
            user_text = None
            if "\nuser:" in prompt:
                try:
                    user_text = prompt.rsplit("\nuser:", 1)[1].strip()
                except Exception:
                    user_text = None
            if not user_text and "user:" in prompt:
                try:
                    user_text = prompt.rsplit("user:", 1)[1].strip()
                except Exception:
                    user_text = None
            snippet = (user_text or prompt).strip().replace("\n", " ")[:140]
            return f"(remote-mock) I would respond to: {snippet}"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_new_tokens,
            "temperature": temperature,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                result = json.load(resp)
                return result["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # network/errors — surface a helpful message
            return f"(remote-error) {exc}"
