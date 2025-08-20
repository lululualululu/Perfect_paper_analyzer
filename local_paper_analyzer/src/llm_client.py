import json
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

class LLMClient:
    def __init__(self, provider: str, endpoint: str, model: str):
        self.provider = provider.lower()
        self.endpoint = endpoint.rstrip('/')
        self.model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def chat(self, messages, temperature: float = 0.2, max_tokens: int = 1024) -> str:
        if self.provider == "ollama":
            url = f"{self.endpoint}/api/chat"
            payload = {
                "model": self.model,
                "messages": messages,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                },
                "stream": False
            }
            r = requests.post(url, json=payload, timeout=300)
            r.raise_for_status()
            data = r.json()
            if "message" in data and "content" in data["message"]:
                return data["message"]["content"]
            if "choices" in data and data["choices"]:
                return data["choices"][0]["message"]["content"]
            return json.dumps(data, ensure_ascii=False)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
