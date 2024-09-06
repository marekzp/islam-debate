import os
from abc import ABC, abstractmethod
from typing import Optional

from anthropic import Anthropic
from openai import OpenAI


class LLMClient(ABC):
    @abstractmethod
    def get_response(self, prompt: str, model: str) -> str:
        pass

class OpenAIClient(LLMClient):
    def __init__(self) -> None:
        self.api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.client: OpenAI = OpenAI(api_key=self.api_key)

    def get_response(self, prompt: str, model: str) -> str:
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

class AnthropicClient(LLMClient):
    def __init__(self) -> None:
        self.api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.client: Anthropic = Anthropic(api_key=self.api_key)

    def get_response(self, prompt: str, model: str) -> str:
        response = self.client.messages.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
        return response.content[0].text

def get_llm_client(llm_type: str) -> LLMClient:
    if llm_type == "openai":
        return OpenAIClient()
    elif llm_type == "anthropic":
        return AnthropicClient()
    else:
        raise ValueError(f"Unsupported LLM type: {llm_type}")