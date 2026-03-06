"""
model_caller.py — 统一模型调用封装
SmartRoute: 基于 Claude Code 的任务模型智能调度方案

从 smartroute.config.json 或 .env 读取配置，
支持 Anthropic 和 OpenAI 两种 API 格式。
"""

import os
import json
import requests
from pathlib import Path
from typing import Optional


def _find_config() -> Optional[dict]:
    """查找并加载 smartroute.config.json"""
    for search_dir in [Path.cwd(), Path.cwd().parent, Path(__file__).parent.parent]:
        config_path = search_dir / "smartroute.config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


class ModelCaller:
    """统一模型调用器 — 自动从 smartroute.config.json 读取配置"""

    def __init__(self):
        config = _find_config()

        if config:
            strong = config["models"]["strong"]
            fast = config["models"]["fast"]

            self.strong_name = strong["name"]
            self.strong_key = strong["api_key"]
            self.strong_url = strong["base_url"]
            self.strong_type = strong["provider_type"]
            self.strong_temperature = strong.get("temperature", 0.2)
            self.strong_max_tokens = strong.get("max_tokens", 8192)

            self.fast_name = fast["name"]
            self.fast_key = fast["api_key"]
            self.fast_url = fast["base_url"]
            self.fast_type = fast["provider_type"]
            self.fast_temperature = fast.get("temperature", 0.1)
            self.fast_max_tokens = fast.get("max_tokens", 4096)
        else:
            # Fallback: 从环境变量读取
            self.strong_name = os.environ.get("STRONG_MODEL_NAME", "claude-opus-4-5")
            self.strong_key = os.environ.get("STRONG_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
            self.strong_url = os.environ.get("STRONG_BASE_URL", "https://api.anthropic.com")
            self.strong_type = os.environ.get("STRONG_PROVIDER_TYPE", "anthropic")
            self.strong_temperature = float(os.environ.get("STRONG_TEMPERATURE", "0.2"))
            self.strong_max_tokens = int(os.environ.get("STRONG_MAX_TOKENS", "8192"))

            self.fast_name = os.environ.get("FAST_MODEL_NAME", "MiniMax-M2.5-highspeed")
            self.fast_key = os.environ.get("FAST_API_KEY", os.environ.get("MINIMAX_API_KEY", ""))
            self.fast_url = os.environ.get("FAST_BASE_URL", "https://api.minimaxi.com/v1")
            self.fast_type = os.environ.get("FAST_PROVIDER_TYPE", "openai")
            self.fast_temperature = float(os.environ.get("FAST_TEMPERATURE", "0.1"))
            self.fast_max_tokens = int(os.environ.get("FAST_MAX_TOKENS", "4096"))

    def call(self, role: str, system_prompt: str, user_message: str, **kwargs) -> str:
        """
        调用指定角色的模型

        Args:
            role: "strong" 或 "fast"
            system_prompt: 系统提示词
            user_message: 用户消息
        """
        if role == "strong":
            return self._dispatch(
                provider_type=self.strong_type,
                api_key=self.strong_key,
                base_url=self.strong_url,
                model=self.strong_name,
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=kwargs.get("temperature", self.strong_temperature),
                max_tokens=kwargs.get("max_tokens", self.strong_max_tokens),
            )
        elif role == "fast":
            return self._dispatch(
                provider_type=self.fast_type,
                api_key=self.fast_key,
                base_url=self.fast_url,
                model=self.fast_name,
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=kwargs.get("temperature", self.fast_temperature),
                max_tokens=kwargs.get("max_tokens", self.fast_max_tokens),
            )
        else:
            raise ValueError(f"未知角色: {role}，请使用 'strong' 或 'fast'")

    def _dispatch(self, provider_type: str, **kwargs) -> str:
        if provider_type == "anthropic":
            return self._call_anthropic(**kwargs)
        elif provider_type == "openai":
            return self._call_openai(**kwargs)
        else:
            raise ValueError(f"未知 provider_type: {provider_type}")

    def _call_anthropic(self, api_key, base_url, model, system_prompt,
                        user_message, temperature, max_tokens) -> str:
        url = f"{base_url.rstrip('/')}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            return "\n".join(
                b["text"] for b in data.get("content", []) if b.get("type") == "text"
            )
        except Exception as e:
            return f"[ERROR] Anthropic API: {e}"

    def _call_openai(self, api_key, base_url, model, system_prompt,
                     user_message, temperature, max_tokens) -> str:
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return "[ERROR] OpenAI API 返回空结果"
        except Exception as e:
            return f"[ERROR] OpenAI API: {e}"


# 全局便捷函数
_caller: Optional[ModelCaller] = None

def call_model(role: str, system_prompt: str, user_message: str, **kwargs) -> str:
    global _caller
    if _caller is None:
        _caller = ModelCaller()
    return _caller.call(role, system_prompt, user_message, **kwargs)
