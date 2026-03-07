"""
model_caller.py — 统一模型调用封装
SmartRoute V3.0: 角色化配置（Planner/Coder/TestCoder/Fixer/DebugExpert）

配置来源:
1) smartroute.config.json.roles
2) 环境变量（ROLE_*）
"""

import json
import os
import time
from pathlib import Path
from typing import Callable, Dict, Optional

import requests


ROLE_SPECS = {
    "planner": {"provider": "anthropic", "temperature": 0.2, "max_tokens": 8192},
    "coder": {"provider": "openai", "temperature": 0.1, "max_tokens": 4096},
    "test_coder": {"provider": "openai", "temperature": 0.1, "max_tokens": 4096},
    "fixer": {"provider": "openai", "temperature": 0.1, "max_tokens": 4096},
    "debug_expert": {"provider": "anthropic", "temperature": 0.2, "max_tokens": 8192},
}
VALID_ROLES = tuple(ROLE_SPECS.keys())

# 兼容 V3 旧命名
LEGACY_ROLE_ALIASES = {
    "worker": "coder",
    "test": "fixer",
    "debug": "debug_expert",
}

_observer: Optional[Callable[[dict], None]] = None


def _find_config() -> Optional[dict]:
    """查找并加载 smartroute.config.json"""
    for search_dir in [Path.cwd(), Path.cwd().parent, Path(__file__).parent.parent]:
        config_path = search_dir / "smartroute.config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


def _normalize_role_name(role: str) -> str:
    if role in LEGACY_ROLE_ALIASES:
        return LEGACY_ROLE_ALIASES[role]
    if role not in VALID_ROLES:
        raise ValueError(
            "未知角色: "
            f"{role}，可用角色: {', '.join(VALID_ROLES)}"
        )
    return role


def _cfg(api_key: str, base_url: str, provider_type: str, model: str, temperature: float, max_tokens: int) -> dict:
    return {
        "api_key": api_key,
        "base_url": base_url,
        "provider_type": provider_type,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def _role_from_config(role_block: dict, role_name: str) -> dict:
    defaults = ROLE_SPECS[role_name]
    return _cfg(
        api_key=role_block.get("api_key", ""),
        base_url=role_block.get("base_url", ""),
        provider_type=role_block.get("provider_type", role_block.get("provider", defaults["provider"])),
        model=role_block.get("name", role_block.get("model_name", "")),
        temperature=role_block.get("temperature", defaults["temperature"]),
        max_tokens=role_block.get("max_tokens", defaults["max_tokens"]),
    )


def _env_role_cfg(prefix: str, role_name: str) -> dict:
    defaults = ROLE_SPECS[role_name]
    return _cfg(
        api_key=os.environ.get(f"{prefix}_API_KEY", ""),
        base_url=os.environ.get(f"{prefix}_BASE_URL", ""),
        provider_type=os.environ.get(f"{prefix}_PROVIDER_TYPE", defaults["provider"]),
        model=os.environ.get(f"{prefix}_MODEL", ""),
        temperature=float(os.environ.get(f"{prefix}_TEMPERATURE", str(defaults["temperature"]))),
        max_tokens=int(os.environ.get(f"{prefix}_MAX_TOKENS", str(defaults["max_tokens"]))),
    )


class ModelCaller:
    """统一模型调用器（纯角色化）"""

    def __init__(self):
        config = _find_config()
        self.roles = self._build_roles(config)

    def _build_roles(self, config: Optional[dict]) -> Dict[str, dict]:
        if config and "roles" in config:
            roles = config["roles"]

            # 新版角色齐全
            missing = [r for r in VALID_ROLES if r not in roles]
            if not missing:
                return {r: _role_from_config(roles[r], r) for r in VALID_ROLES}

            # 兼容旧版 worker/test/debug
            if all(k in roles for k in ("worker", "test", "debug")):
                return {
                    "planner": _role_from_config(roles["debug"], "planner"),
                    "coder": _role_from_config(roles["worker"], "coder"),
                    "test_coder": _role_from_config(roles["test"], "test_coder"),
                    "fixer": _role_from_config(roles["test"], "fixer"),
                    "debug_expert": _role_from_config(roles["debug"], "debug_expert"),
                }

            raise ValueError(
                "roles 配置不完整：需要 "
                "planner/coder/test_coder/fixer/debug_expert "
                "（或兼容旧版 worker/test/debug）"
            )

        # 环境变量兜底（优先新版前缀，兼容旧版）
        planner = _env_role_cfg("ROLE_PLANNER", "planner")
        coder = _env_role_cfg("ROLE_CODER", "coder")
        test_coder = _env_role_cfg("ROLE_TEST_CODER", "test_coder")
        fixer = _env_role_cfg("ROLE_FIXER", "fixer")
        debug_expert = _env_role_cfg("ROLE_DEBUG_EXPERT", "debug_expert")

        if not coder["model"] and os.environ.get("ROLE_WORKER_MODEL"):
            coder = _env_role_cfg("ROLE_WORKER", "coder")
        if not fixer["model"] and os.environ.get("ROLE_TEST_MODEL"):
            fixer = _env_role_cfg("ROLE_TEST", "fixer")
            test_coder = _env_role_cfg("ROLE_TEST", "test_coder")
        if not debug_expert["model"] and os.environ.get("ROLE_DEBUG_MODEL"):
            debug_expert = _env_role_cfg("ROLE_DEBUG", "debug_expert")
            planner = _env_role_cfg("ROLE_DEBUG", "planner")

        return {
            "planner": planner,
            "coder": coder,
            "test_coder": test_coder,
            "fixer": fixer,
            "debug_expert": debug_expert,
        }

    def has_valid_credentials(self) -> bool:
        for role in VALID_ROLES:
            cfg = self.roles[role]
            key = cfg.get("api_key", "")
            model = cfg.get("model", "")
            base_url = cfg.get("base_url", "")
            if not key or not model or not base_url:
                return False
            if "填入" in key or "YOUR_" in key:
                return False
        return True

    def call(self, role: str, system_prompt: str, user_message: str, **kwargs) -> str:
        role_name = _normalize_role_name(role)
        role_cfg = self.roles[role_name]
        started = time.time()
        result = self._dispatch(
            provider_type=role_cfg["provider_type"],
            api_key=role_cfg["api_key"],
            base_url=role_cfg["base_url"],
            model=role_cfg["model"],
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=kwargs.get("temperature", role_cfg["temperature"]),
            max_tokens=kwargs.get("max_tokens", role_cfg["max_tokens"]),
        )
        latency_ms = int((time.time() - started) * 1000)
        if _observer is not None:
            try:
                _observer(
                    {
                        "role": role_name,
                        "provider_type": role_cfg["provider_type"],
                        "model": role_cfg["model"],
                        "base_url": role_cfg["base_url"],
                        "system_prompt": system_prompt,
                        "user_message": user_message,
                        "response": result.get("text", ""),
                        "usage": result.get("usage", {}),
                        "latency_ms": latency_ms,
                    }
                )
            except Exception:
                pass
        return result.get("text", "")

    def _dispatch(self, provider_type: str, **kwargs) -> dict:
        if provider_type == "anthropic":
            return self._call_anthropic(**kwargs)
        if provider_type == "openai":
            return self._call_openai(**kwargs)
        raise ValueError(f"未知 provider_type: {provider_type}")

    def _resolve_anthropic_url(self, base_url: str) -> str:
        url = base_url.rstrip("/")
        if url.endswith("/v1/messages") or url.endswith("/messages"):
            return url
        if url.endswith("/v1"):
            return f"{url}/messages"
        return f"{url}/v1/messages"

    def _resolve_openai_url(self, base_url: str) -> str:
        url = base_url.rstrip("/")
        lower = url.lower()
        known_endings = (
            "/chat/completions",
            "/v1/chat/completions",
            "/responses",
            "/v1/responses",
            "/text/chatcompletion_v2",
            "/v1/text/chatcompletion_v2",
        )
        if any(lower.endswith(suffix) for suffix in known_endings):
            return url
        return f"{url}/chat/completions"

    def _call_anthropic(self, api_key, base_url, model, system_prompt,
                        user_message, temperature, max_tokens) -> dict:
        url = self._resolve_anthropic_url(base_url)
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
            text = "\n".join(
                b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
            )
            return {"text": text, "usage": self._normalize_usage(data)}
        except requests.RequestException as e:
            detail = ""
            if getattr(e, "response", None) is not None:
                detail = f" | body={e.response.text[:300]}"
            return {"text": f"[ERROR] Anthropic API: {e}{detail}", "usage": {}}
        except Exception as e:
            return {"text": f"[ERROR] Anthropic API: {e}", "usage": {}}

    def _extract_openai_text(self, data: dict) -> str:
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "\n".join(
                    item.get("text", "") for item in content if isinstance(item, dict)
                )

        if "output_text" in data and isinstance(data["output_text"], str):
            return data["output_text"]

        output = data.get("output", [])
        texts = []
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict):
                    continue
                for content in item.get("content", []):
                    if isinstance(content, dict) and "text" in content:
                        texts.append(content["text"])
        if texts:
            return "\n".join(texts)
        return ""

    def _call_openai(self, api_key, base_url, model, system_prompt,
                     user_message, temperature, max_tokens) -> dict:
        url = self._resolve_openai_url(base_url)
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
            text = self._extract_openai_text(data)
            if not text:
                text = "[ERROR] OpenAI API 返回空结果"
            return {"text": text, "usage": self._normalize_usage(data)}
        except requests.RequestException as e:
            detail = ""
            if getattr(e, "response", None) is not None:
                detail = f" | body={e.response.text[:300]}"
            return {"text": f"[ERROR] OpenAI API: {e}{detail}", "usage": {}}
        except Exception as e:
            return {"text": f"[ERROR] OpenAI API: {e}", "usage": {}}

    def _normalize_usage(self, data: dict) -> dict:
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        if not isinstance(usage, dict):
            return {}
        input_tokens = usage.get("input_tokens")
        if input_tokens is None:
            input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("output_tokens")
        if output_tokens is None:
            output_tokens = usage.get("completion_tokens")
        result = {}
        if input_tokens is not None:
            result["input_tokens"] = input_tokens
        if output_tokens is not None:
            result["output_tokens"] = output_tokens
        if usage:
            result["raw"] = usage
        return result


_caller: Optional[ModelCaller] = None


def call_model(role: str, system_prompt: str, user_message: str, **kwargs) -> str:
    global _caller
    if _caller is None:
        _caller = ModelCaller()
    return _caller.call(role, system_prompt, user_message, **kwargs)


def set_model_observer(observer: Optional[Callable[[dict], None]]):
    global _observer
    _observer = observer
