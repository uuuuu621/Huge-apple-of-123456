# -*- coding: utf-8 -*-
"""
OpenAI 兼容接口的 LLM 客户端。
可接 DeepSeek / Qwen / 豆包 / 通义 / Moonshot 等任何提供 /chat/completions 的服务。
"""
import requests


class LLMClient:
    def __init__(self, base_url="", api_key="", model="", timeout=90):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.model = model or ""
        self.timeout = timeout

    @property
    def available(self):
        return bool(self.base_url and self.api_key and self.model)

    def chat(self, messages, temperature=0.0, json_mode=False, max_tokens=2000):
        """发送对话请求，返回文本内容。"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        r = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
