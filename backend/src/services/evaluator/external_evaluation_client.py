"""
外部用例模型质量评估平台 HTTP 客户端
"""
import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class ExternalEvaluationError(Exception):
    """外部评估接口调用失败"""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class ExternalEvaluationClient:
    """调用外部 /uc_model/quality 等多智能体评估接口"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        evaluation_mode: Optional[str] = None,
    ):
        try:
            from config import Config

            default_url = getattr(
                Config,
                "EXTERNAL_EVALUATION_URL",
                "http://127.0.0.1:5000/uc_model/quality",
            )
            default_timeout = int(getattr(Config, "EXTERNAL_EVALUATION_TIMEOUT", 3600))
            default_mode = getattr(Config, "EXTERNAL_EVALUATION_MODE", "detailed")
        except Exception:
            default_url = "http://127.0.0.1:5000/uc_model/quality"
            default_timeout = 3600
            default_mode = "detailed"

        self.base_url = (base_url or default_url).strip()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else default_timeout
        self.evaluation_mode = (evaluation_mode or default_mode or "detailed").strip()

    def build_payload(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """将本系统输入格式映射为外部平台请求体。"""
        requirements_text = (input_data.get("requirements_text") or "").strip()
        requirements = input_data.get("requirements")
        if not requirements_text and isinstance(requirements, dict):
            requirements_text = json.dumps(requirements, ensure_ascii=False, indent=2)

        payload: Dict[str, Any] = {
            "requirements_text": requirements_text,
            "use_case_diagram": input_data.get("use_case_diagram") or {},
            "use_case_descriptions": input_data.get("use_case_descriptions") or [],
            "evaluation_mode": input_data.get("evaluation_mode") or self.evaluation_mode,
            "multi_agent_enabled": True,
            "agent_count": 3,
        }
        if isinstance(requirements, dict):
            payload["requirements"] = requirements
        return payload

    def evaluate(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """POST 到外部评估接口并返回完整评估报告 JSON。"""
        payload = self.build_payload(input_data)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base_url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                status = getattr(response, "status", 200)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            parsed = self._try_parse_json(raw)
            message = self._extract_error_message(parsed, raw) or f"外部评估接口 HTTP {exc.code}"
            raise ExternalEvaluationError(message, status_code=exc.code, response_body=parsed or raw) from exc
        except urllib.error.URLError as exc:
            raise ExternalEvaluationError(
                f"无法连接外部评估服务 {self.base_url}: {exc.reason}"
            ) from exc

        parsed = self._try_parse_json(raw)
        if parsed is None:
            raise ExternalEvaluationError(
                "外部评估接口返回非 JSON 响应",
                status_code=status,
                response_body=raw[:500],
            )
        if status >= 400:
            message = self._extract_error_message(parsed, raw) or f"外部评估接口 HTTP {status}"
            raise ExternalEvaluationError(message, status_code=status, response_body=parsed)

        return self._normalize_response(parsed)

    @staticmethod
    def _try_parse_json(raw: str) -> Optional[Any]:
        text = (raw or "").strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _extract_error_message(parsed: Any, raw: str) -> str:
        if isinstance(parsed, dict):
            for key in ("error", "message", "detail", "msg"):
                value = parsed.get(key)
                if value:
                    return str(value)
        return (raw or "").strip()[:500]

    @staticmethod
    def _normalize_response(parsed: Any) -> Dict[str, Any]:
        if not isinstance(parsed, dict):
            raise ExternalEvaluationError("外部评估接口返回格式无效：期望 JSON 对象")

        if parsed.get("success") is False:
            raise ExternalEvaluationError(
                ExternalEvaluationClient._extract_error_message(parsed, ""),
                response_body=parsed,
            )

        if parsed.get("success") is True and isinstance(parsed.get("data"), dict):
            return parsed["data"]

        if any(key in parsed for key in ("diagram_metrics", "description_metrics", "overall_score")):
            return parsed

        if isinstance(parsed.get("result"), dict):
            return parsed["result"]

        raise ExternalEvaluationError(
            "外部评估接口返回格式无效：缺少 data / diagram_metrics / overall_score",
            response_body=parsed,
        )


def use_external_evaluation() -> bool:
    """是否启用外部评估平台。"""
    env = os.environ.get("USE_EXTERNAL_EVALUATION", "").strip().lower()
    if env in ("false", "0", "no", "off"):
        return False
    if env in ("true", "1", "yes", "on"):
        return True
    try:
        from config import Config

        return bool(getattr(Config, "USE_EXTERNAL_EVALUATION", True))
    except Exception:
        return True
