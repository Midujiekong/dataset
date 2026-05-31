"""
评估服务主类
"""
import os
import time
from typing import Dict, Any, List, Optional
from .evaluation_engine import EvaluationEngine
from .external_evaluation_client import ExternalEvaluationClient, use_external_evaluation
from .report_generator import ReportGenerator
from .requirements_parser import extract_structured_requirements
from .input_normalizer import normalize_evaluation_payload, normalize_requirements


def _use_multi_agent() -> bool:
    """是否啟用多智能體（需至少 2 個模型的 API Key）"""
    try:
        from config import Config
        if not getattr(Config, "MULTI_AGENT_ENABLED", False):
            return False
    except Exception:
        if os.environ.get("MULTI_AGENT_ENABLED", "").lower() not in ("true", "1", "yes"):
            return False
    keys = [
        os.environ.get("DEEPSEEK_API_KEY", "").strip(),
        os.environ.get("DASHSCOPE_API_KEY", "").strip(),
        os.environ.get("ZHIPUAI_API_KEY", "").strip(),
        os.environ.get("MOONSHOT_API_KEY", "").strip(),
    ]
    return sum(1 for k in keys if k) >= 2


class EvaluationService:
    """用例模型质量评估服务"""

    def __init__(self, use_llm: bool = False, use_multi_agent: Optional[bool] = None):
        """
        Args:
            use_llm: 是否在评估中启用真实 LLM
            use_multi_agent: 預設多智能體策略。None 時依 evaluation_mode 與環境變量動態決定。
        """
        self.use_llm = use_llm
        self._default_multi = use_multi_agent if use_multi_agent is not None else _use_multi_agent()
        self.use_external = use_external_evaluation()
        self.external_client = ExternalEvaluationClient() if self.use_external else None
        self.report_generator = ReportGenerator()
        self.evaluation_engine = EvaluationEngine(use_llm=use_llm, use_multi_agent=self._default_multi)

    def evaluate(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行评估。evaluation_mode: "quick"=單模型（整合 batch prompt），"detailed"=可配合多智能體。
        若传入 force_single_llm=True，则禁用多智能体（即便 mode 为 detailed 且环境已开启）。
        默认通过外部平台 http://127.0.0.1:5000/uc_model/quality 执行 3 Agent 评估。
        """
        start = time.perf_counter()
        data = dict(input_data)
        policy_seen = str(input_data.get("overall_score_policy", "mean") or "mean").lower()
        mode = data.pop("evaluation_mode", None)
        force_single = bool(data.pop("force_single_llm", False))

        # 統一輸入格式：用例圖關係類型、用例描述包裝與主流程物件、goal_level 需求等
        data = normalize_evaluation_payload(data)

        if self.use_external:
            if not mode:
                mode = self.external_client.evaluation_mode if self.external_client else "detailed"
            report = self._evaluate_external(data, mode=mode)
        else:
            if not mode:
                mode = "quick"
            use_multi = (mode == "detailed") and _use_multi_agent() and not force_single
            self.evaluation_engine = EvaluationEngine(use_llm=self.use_llm, use_multi_agent=use_multi)
            data = self._prepare_local_requirements(data)
            evaluation_results = self.evaluation_engine.evaluate(data)
            report = self.report_generator.generate(evaluation_results, data)

        report["evaluation_mode"] = mode
        report["overall_score_policy"] = policy_seen
        duration_seconds = max(0.0, time.perf_counter() - start)
        report["evaluation_duration_seconds"] = round(duration_seconds, 3)
        if self.use_external:
            report["evaluation_backend"] = "external"
            report["external_evaluation_url"] = self.external_client.base_url if self.external_client else ""
        return report

    def _prepare_local_requirements(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if data.get("requirements") is None and data.get("requirements_text"):
            raw = (data.get("requirements_text") or "").strip()
            if not raw:
                raise ValueError("requirements_text 为空")
            use_llm_extract = data.get("use_llm_for_extraction", False)
            data["requirements"] = extract_structured_requirements(raw, use_llm=use_llm_extract)
            diagram = data.get("use_case_diagram")
            d = diagram if isinstance(diagram, dict) else None
            if isinstance(data.get("requirements"), dict):
                data["requirements"] = normalize_requirements(data["requirements"], d)
        return data

    def _evaluate_external(self, data: Dict[str, Any], mode: str) -> Dict[str, Any]:
        if not (data.get("requirements_text") or data.get("requirements")):
            raise ValueError("缺少需求输入：请提供 requirements（结构化）或 requirements_text（文本）")
        payload = dict(data)
        payload["evaluation_mode"] = mode
        return self.external_client.evaluate(payload)

    def evaluate_from_raw_text(
        self,
        raw_requirements: str,
        use_case_diagram: Dict[str, Any],
        use_case_descriptions: Optional[List[Dict[str, Any]]] = None,
        use_llm_for_extraction: bool = False,
    ) -> Dict[str, Any]:
        """
        从非规格化需求文本到评估的一站式调用：先抽取需求，再评估用例图与用例描述。
        """
        structured_req = extract_structured_requirements(raw_requirements, use_llm=use_llm_for_extraction)
        input_data = {
            "use_case_diagram": use_case_diagram,
            "use_case_descriptions": use_case_descriptions or [],
            "requirements": structured_req,
        }
        return self.evaluate(input_data)
