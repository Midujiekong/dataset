"""
LLM集成模块 - 支持多个LLM供应商
支持：DeepSeek、OpenAI、本地模型等
"""

import os
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from abc import ABC, abstractmethod
import openai
from openai import OpenAI


def _llm_http_timeout_seconds() -> float:
    try:
        return float(os.getenv("LLM_HTTP_TIMEOUT", "120"))
    except ValueError:
        return 120.0


def _flatten_openai_content(content: Any) -> str:
    """OpenAI 兼容接口中 message.content 可能为 str 或 content-parts 列表。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif isinstance(block.get("text"), str):
                    parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts).strip()
    return str(content).strip()


def _openai_response_meta_line(response: Any) -> str:
    """便于排查：空 content、截断、推理模型等。"""
    try:
        ch = response.choices[0]
        fr = getattr(ch, "finish_reason", "") or ""
        msg = ch.message
        mid = getattr(response, "model", "") or ""
        c = getattr(msg, "content", None)
        flat = _flatten_openai_content(c)
        cl = len(flat)
        rc = getattr(msg, "reasoning_content", None)
        rlen = len(rc) if isinstance(rc, str) else 0
        u = getattr(response, "usage", None)
        ctok = getattr(u, "completion_tokens", None) if u else None
        ptok = getattr(u, "prompt_tokens", None) if u else None
        return (
            f"model={mid} finish_reason={fr} content_chars={cl} reasoning_chars={rlen} "
            f"prompt_tokens={ptok} completion_tokens={ctok}"
        )
    except Exception as e:
        return f"meta_error={e}"


def _openai_completion_text(response: Any) -> str:
    """从 chat.completions 响应取出正文；兼容 list content 与部分推理模型异常响应。"""
    try:
        msg = response.choices[0].message
    except (AttributeError, IndexError, TypeError):
        return ""
    text = _flatten_openai_content(getattr(msg, "content", None))
    if text:
        return text
    rc = getattr(msg, "reasoning_content", None)
    if isinstance(rc, str):
        rs = rc.strip()
        if rs.startswith("{") or "```json" in rs[:200] or ('"' in rs and "{" in rs and "score" in rs.lower()):
            return rs
    return ""


def _finalize_openai_chat(provider: Any, response: Any) -> str:
    """写入 provider.last_response_meta 并返回正文。"""
    setattr(provider, "last_response_meta", _openai_response_meta_line(response))
    return _openai_completion_text(response)


class LLMProvider(ABC):
    """LLM供应商抽象基类"""
    
    @abstractmethod
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """聊天补全接口"""
        pass
    
    @abstractmethod
    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """计算调用成本"""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """获取模型名称"""
        pass


class DeepSeekProvider(LLMProvider):
    """DeepSeek API集成"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.deepseek.com"):
        """
        初始化DeepSeek客户端
        
        Args:
            api_key: DeepSeek API密钥，从环境变量DEEPSEEK_API_KEY读取
            base_url: API基础URL
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DeepSeek API密钥未设置，请设置环境变量DEEPSEEK_API_KEY")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=base_url,
            timeout=_llm_http_timeout_seconds(),
        )
        self.model = (os.getenv("DEEPSEEK_MODEL", "deepseek-chat") or "deepseek-chat").strip()
        self.base_url = base_url
        
        self.pricing = {
            "input": 0.14,
            "output": 0.28,
        }
    
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        调用DeepSeek聊天补全API
        
        Args:
            messages: 消息列表，格式如 [{"role": "user", "content": "你好"}]
            **kwargs: 其他参数如 temperature, max_tokens 等
            
        Returns:
            LLM回复内容
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs
            )
            return _finalize_openai_chat(self, response)
        except Exception as e:
            print(f"DeepSeek API调用失败: {e}")
            raise
    
    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        计算调用成本（美元）
        
        Args:
            prompt_tokens: 输入token数
            completion_tokens: 输出token数
            
        Returns:
            成本（美元）
        """
        input_cost = (prompt_tokens / 1_000_000) * self.pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * self.pricing["output"]
        return input_cost + output_cost
    
    def get_model_name(self) -> str:
        return f"DeepSeek-{self.model}"


class OpenAIProvider(LLMProvider):
    """OpenAI API集成"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API密钥未设置")
        
        self.client = OpenAI(api_key=self.api_key, timeout=_llm_http_timeout_seconds())
        self.model = "gpt-3.5-turbo"
        
        self.pricing = {
            "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
            "gpt-4": {"input": 30.00, "output": 60.00},
            "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        }
    
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """OpenAI聊天补全"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs
        )
        return _finalize_openai_chat(self, response)

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        model_pricing = self.pricing.get(self.model, self.pricing["gpt-3.5-turbo"])
        input_cost = (prompt_tokens / 1_000_000) * model_pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * model_pricing["output"]
        return input_cost + output_cost
    
    def get_model_name(self) -> str:
        return f"OpenAI-{self.model}"


class QwenProvider(LLMProvider):
    """阿里通义千问 API 集成（OpenAI 兼容）"""

    def __init__(self, api_key: Optional[str] = None, model: str = "qwen-plus"):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("通义千问 API 密钥未设置，请设置环境变量 DASHSCOPE_API_KEY")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            timeout=_llm_http_timeout_seconds(),
        )
        self.model = model

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs
            )
            return _finalize_openai_chat(self, response)
        except Exception as e:
            print(f"通义千问 API 调用失败: {e}")
            raise

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return 0.0

    def get_model_name(self) -> str:
        return f"Qwen-{self.model}"


class ZhipuProvider(LLMProvider):
    """智谱 ChatGLM API 集成（OpenAI 兼容）"""

    def __init__(self, api_key: Optional[str] = None, model: str = "glm-5"):
        self.api_key = api_key or os.getenv("ZHIPUAI_API_KEY")
        if not self.api_key:
            raise ValueError("智谱 API 密钥未设置，请设置环境变量 ZHIPUAI_API_KEY")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4",
            timeout=_llm_http_timeout_seconds(),
        )
        self.model = model

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs
            )
            return _finalize_openai_chat(self, response)
        except Exception as e:
            print(f"智谱 API 调用失败: {e}")
            raise

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return 0.0

    def get_model_name(self) -> str:
        return f"Zhipu-{self.model}"


class MoonshotProvider(LLMProvider):
    """月之暗面 Kimi API 集成（OpenAI 兼容）"""

    def __init__(self, api_key: Optional[str] = None, model: str = "moonshot-v1-8k"):
        self.api_key = api_key or os.getenv("MOONSHOT_API_KEY")
        if not self.api_key:
            raise ValueError("Moonshot API 密钥未设置，请设置环境变量 MOONSHOT_API_KEY")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.moonshot.cn/v1",
            timeout=_llm_http_timeout_seconds(),
        )
        self.model = model

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs
            )
            return _finalize_openai_chat(self, response)
        except Exception as e:
            print(f"Moonshot API 调用失败: {e}")
            raise

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return 0.0

    def get_model_name(self) -> str:
        return f"Moonshot-{self.model}"


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API 集成（海外，国内可能不可用）"""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API 密鑰未設置，請設置環境變量 ANTHROPIC_API_KEY")
        try:
            self.client = __import__("anthropic").Anthropic(api_key=self.api_key)
        except ImportError:
            raise ValueError("請安裝 anthropic: pip install anthropic")
        self.model = model

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        system = ""
        user_content = ""
        for m in messages:
            if m.get("role") == "system":
                system = m.get("content", "")
            elif m.get("role") == "user":
                user_content = m.get("content", "")
        if not user_content:
            raise ValueError("無用戶消息")
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=kwargs.get("max_tokens", 2000),
                system=system or None,
                messages=[{"role": "user", "content": user_content}],
            )
            text = ""
            if resp.content:
                text = (getattr(resp.content[0], "text", None) or "").strip()
            u = getattr(resp, "usage", None)
            ot = getattr(u, "output_tokens", None) if u else None
            self.last_response_meta = (
                f"model={self.model} output_chars={len(text)} output_tokens={ot}"
            )
            return text
        except Exception as e:
            print(f"Anthropic API 調用失敗: {e}")
            raise

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return 0.0

    def get_model_name(self) -> str:
        return f"Anthropic-{self.model}"


class LocalLLMProvider(LLMProvider):
    """本地LLM集成（如Ollama、vLLM等）"""
    
    def __init__(self, base_url: str = "http://localhost:11434/api"):
        self.base_url = base_url
        self.model = "qwen:7b"
        self.client = None
    
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        self.last_response_meta = "local_stub"
        return "本地LLM响应（模拟）"
    
    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return 0.0
    
    def get_model_name(self) -> str:
        return f"Local-{self.model}"


class LLMManager:
    """
    LLM管理器 - 统一管理所有LLM调用
    提供缓存、重试、成本控制等功能
    """
    
    def __init__(self, provider: str = "deepseek", **kwargs):
        """
        初始化LLM管理器
        
        Args:
            provider: LLM提供商，支持 deepseek, openai, local
            **kwargs: 提供商特定参数
        """
        self.provider = self._create_provider(provider, kwargs)
        self.cache = {}
        self.total_cost = 0.0
        self.total_calls = 0
        
        self.enable_cache = True
        try:
            self.max_retries = int(os.getenv("LLM_MAX_RETRIES", "5"))
        except ValueError:
            self.max_retries = 5
        self.timeout = int(_llm_http_timeout_seconds())
        
        self.stats = {
            "total_tokens": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "cache_hits": 0,
        }
    
    def _create_provider(self, provider: str, kwargs: Dict[str, Any]) -> LLMProvider:
        """创建LLM提供商实例"""
        if provider.lower() == "deepseek":
            return DeepSeekProvider(**kwargs)
        elif provider.lower() == "openai":
            return OpenAIProvider(**kwargs)
        elif provider.lower() in ("qwen", "dashscope"):
            return QwenProvider(**kwargs)
        elif provider.lower() in ("zhipu", "zhipuai"):
            return ZhipuProvider(**kwargs)
        elif provider.lower() == "moonshot":
            return MoonshotProvider(**kwargs)
        elif provider.lower() == "anthropic":
            return AnthropicProvider(**kwargs)
        elif provider.lower() == "local":
            return LocalLLMProvider(**kwargs)
        else:
            raise ValueError(f"不支持的LLM提供商: {provider}")
    
    def call_with_retry(self, prompt: str, system_prompt: str = "", 
                       temperature: float = 0.1, max_tokens: int = 4096) -> str:
        """
        带重试机制的LLM调用
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大生成token数
            
        Returns:
            LLM响应内容
        """
        cache_key = f"{system_prompt}||{prompt}||{temperature}"
        
        if self.enable_cache and cache_key in self.cache:
            cached = self.cache[cache_key]
            if isinstance(cached, str) and cached.strip():
                self.stats["cache_hits"] += 1
                return cached
            del self.cache[cache_key]
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            cap = int(os.getenv("LLM_MAX_TOKENS_CAP", "16384"))
        except ValueError:
            cap = 16384
        effective_max = max(1, min(int(max_tokens), cap))

        for attempt in range(self.max_retries):
            try:
                mt = min(max(effective_max, 1), cap)
                response = self.provider.chat_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=mt,
                )
                text = (response or "").strip() if isinstance(response, str) else str(response or "").strip()
                if not text:
                    meta = getattr(self.provider, "last_response_meta", None)
                    print(
                        f"LLM 返回空内容（第 {attempt + 1}/{self.max_retries} 次），"
                        "可能是限流、内容过滤、max_tokens 截断仅产出推理链等；稍后重试…"
                    )
                    if meta:
                        print(f"  [诊断] {meta}")
                    if attempt < self.max_retries - 1:
                        boosted = min(max(mt * 2, mt + 2048), cap)
                        if boosted > mt:
                            effective_max = boosted
                            print(f"  将 max_tokens 从 {mt} 提高到 {boosted} 后重试…")
                        time.sleep(1.5 * (attempt + 1) + 1.0)
                        continue
                    self.stats["failed_calls"] += 1
                    return ""

                self.total_calls += 1
                self.stats["successful_calls"] += 1

                if self.enable_cache:
                    self.cache[cache_key] = text

                return text

            except Exception as e:
                print(f"LLM调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    self.stats["failed_calls"] += 1
                    raise
                time.sleep(1 * (attempt + 1))
    
    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        解析LLM的JSON响应。支持去除 Markdown 代码块；若 JSON 被截断则尝试补全后解析。
        """
        import re
        if response is None:
            response = ""
        if not isinstance(response, str):
            response = str(response)
        text = response.strip()
        if not text:
            print("JSON解析失败: LLM 返回空字符串（请检查 API Key、额度、网络或模型是否限流）")
            return {"error": "empty_response", "raw_response": ""}
        if text.startswith("```"):
            match = re.match(r"^```(?:json)?\s*\n?(.*?)```\s*$", text, re.DOTALL)
            if match:
                text = match.group(1).strip()
            else:
                text = re.sub(r"^```(?:json)?\s*\n?", "", text)
                text = re.sub(r"```\s*$", "", text).strip()
        try:
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            return json.loads(text)
        except json.JSONDecodeError as e:
            repaired = self._try_repair_truncated_json(text, e)
            if repaired is not None:
                return repaired
            print(f"JSON解析失败: {e}")
            print(f"原始响应（前500字）: {response[:500]}...")
            return {"error": "JSON解析失败", "raw_response": response}

    def _try_repair_truncated_json(self, text: str, parse_error: json.JSONDecodeError) -> Optional[Dict[str, Any]]:
        """尝试修复被截断的 JSON（如 term_evaluations / evaluations 数组未闭合）。"""
        import re
        for key in ("term_evaluations", "evaluations"):
            pattern = rf'"{key}"\s*:\s*\['
            m = re.search(pattern, text)
            if not m:
                continue
            start = m.end()
            depth = 1
            i = start
            last_complete = start
            in_string = None
            escape = False
            while i < len(text) and depth > 0:
                c = text[i]
                if escape:
                    escape = False
                    i += 1
                    continue
                if c == "\\" and in_string:
                    escape = True
                    i += 1
                    continue
                if in_string:
                    if c == in_string:
                        in_string = None
                    i += 1
                    continue
                if c in ('"', "'"):
                    in_string = c
                    i += 1
                    continue
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 1:
                        last_complete = i + 1
                elif c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                i += 1
            if depth != 0 and last_complete > start:
                try:
                    prefix = text[:last_complete].rstrip()
                    if prefix.endswith(","):
                        prefix = prefix[:-1].rstrip()
                    prefix = prefix + "]}"
                    return json.loads(prefix)
                except json.JSONDecodeError:
                    pass
        for key in ("term_evaluations", "evaluations"):
            if f'"{key}"' not in text:
                continue
            for pos in reversed([m.start() for m in re.finditer(r"}", text)]):
                try:
                    prefix = text[: pos + 1].rstrip().rstrip(",").rstrip()
                    candidate = prefix + "]}"
                    parsed = json.loads(candidate)
                    if key in parsed and isinstance(parsed.get(key), list):
                        return parsed
                except json.JSONDecodeError:
                    continue
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        return {
            "provider": self.provider.get_model_name(),
            "total_calls": self.total_calls,
            "successful_calls": self.stats["successful_calls"],
            "failed_calls": self.stats["failed_calls"],
            "cache_hits": self.stats["cache_hits"],
            "total_cost": self.total_cost,
            "enable_cache": self.enable_cache,
        }
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()