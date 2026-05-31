"""
多智能體評估框架
協作模式：初評（模型1）→ 審核（模型2、3）→ 再評估（模型1 結合反饋修正）
支援：DeepSeek、通义千问、智谱等
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Callable
from .llm_evaluator import LLMEvaluator
from .llm_integration import LLMManager
from .llm_prompts import LLMPromptTemplates

log = logging.getLogger(__name__)


class MultiAgentLLMEvaluator:
    """
    多智能體 LLM 評估器（協作模式）
    模型1 初評 → 模型2、3 審核並給建議 → 模型1 結合反饋再評估
    """

    def __init__(
        self,
        agent_configs: Optional[List[Dict[str, Any]]] = None,
        score_aggregation: str = "median",
        min_agents_for_consensus: int = 2,
    ):
        """
        Args:
            agent_configs: 智能體配置列表，每項為 {"provider": "deepseek"|"openai"|"anthropic", "model": "可選覆蓋"}。
                          若為 None，使用預設三模型：DeepSeek、OpenAI、Anthropic（依 API Key 可用性）。
            score_aggregation: 分數聚合方式，"median"（中位數，抗異常）或 "mean"（平均）。
            min_agents_for_consensus: 離散結果（如 VALID/INVALID）至少幾票一致才採納。
        """
        self.agent_configs = agent_configs or self._default_agent_configs()
        self.score_aggregation = score_aggregation
        self.min_agents_for_consensus = min_agents_for_consensus
        self.evaluators: List[LLMEvaluator] = []
        self._init_evaluators()
        # 加速選項：MULTI_AGENT_SCOPE=diagram_only 時，用例描述僅用單一模型
        import os
        self.scope = os.getenv("MULTI_AGENT_SCOPE", "all").strip().lower()

    def _default_agent_configs(self) -> List[Dict[str, Any]]:
        """預設三模型配置：DeepSeek、通义千问、智谱（國內可用的模型，僅包含 API Key 已配置的）"""
        import os
        try:
            from dotenv import load_dotenv
            from pathlib import Path
            _dir = Path(__file__).resolve().parents[3]  # backend/
            load_dotenv(_dir / ".env")
        except Exception:
            pass
        configs = []
        if os.getenv("DEEPSEEK_API_KEY", "").strip():
            configs.append({"provider": "deepseek", "name": "DeepSeek"})
        if os.getenv("DASHSCOPE_API_KEY", "").strip():
            configs.append({"provider": "qwen", "model": "qwen-plus", "name": "通义千问"})
        if os.getenv("ZHIPUAI_API_KEY", "").strip():
            configs.append({"provider": "zhipu", "model": "glm-5", "name": "智谱"})
        if os.getenv("MOONSHOT_API_KEY", "").strip():
            configs.append({"provider": "moonshot", "model": "moonshot-v1-8k", "name": "Kimi"})
        if len(configs) < 2:
            return configs if configs else [{"provider": "deepseek", "name": "DeepSeek"}]
        max_models = int(os.getenv("MULTI_AGENT_MAX_MODELS", "3") or "3")
        max_models = max(2, min(max_models, len(configs)))
        return configs[:max_models]

    def _init_evaluators(self):
        """建立各智能體對應的 LLMEvaluator"""
        self.evaluators.clear()
        for cfg in self.agent_configs:
            name = cfg.get("name", cfg.get("provider", "?"))
            try:
                provider = cfg.get("provider", "deepseek")
                kwargs = {k: v for k, v in cfg.items() if k not in ("provider", "name")}
                mgr = LLMManager(provider=provider, **kwargs)
                ev = LLMEvaluator(llm_manager=mgr)
                self.evaluators.append(ev)
                log.info(f"多智能體：已啟用 {name} ({mgr.provider.get_model_name()})")
            except Exception as e:
                log.warning(f"多智能體：跳過 {name}，原因: {e}")
                print(f"多智能體：跳過 {name}: {e}")
        if len(self.evaluators) < 2:
            log.warning("多智能體僅有 %d 個模型可用，建議配置至少 2 個 API Key", len(self.evaluators))

    def _evaluate_with_review(
        self,
        task_name: str,
        eval_method: Callable[[LLMEvaluator], Dict[str, Any]],
        original_input: Dict[str, Any],
        result_to_input_fn: Optional[Callable[[Dict], Dict]] = None,
    ) -> Dict[str, Any]:
        """
        協作流程：初評 → 審核 → 再評估
        eval_method(ev) 返回評估結果；result_to_input_fn 可將結果轉為審核用的 input 摘要。
        """
        if not self.evaluators:
            return {"score": 0.5, "summary": {"note": "無可用模型"}}
        primary = self.evaluators[0]
        reviewers = self.evaluators[1:3] if len(self.evaluators) >= 3 else self.evaluators[1:]

        # 1. 初評
        try:
            initial = eval_method(primary)
        except Exception as e:
            log.warning("多智能體初評失敗: %s", e)
            return {"score": 0.5, "summary": {"note": f"初評失敗: {e}"}}

        if not reviewers:
            return initial

        # 審核用輸入：可精簡以避免 token 過多
        review_input = original_input
        if result_to_input_fn:
            review_input = result_to_input_fn(initial)

        # 2. 審核者並行調用
        def _run_review(ev: LLMEvaluator) -> Optional[Dict]:
            try:
                sp, up = LLMPromptTemplates.review_evaluation_prompt(
                    task_name, review_input, initial
                )
                resp = ev.llm_manager.call_with_retry(
                    prompt=up, system_prompt=sp, temperature=0.2, max_tokens=2000
                )
                return ev.llm_manager.parse_json_response(resp)
            except Exception as e:
                log.warning("審核調用失敗 %s: %s", ev.llm_manager.provider.get_model_name(), e)
                return None

        feedbacks = []
        with ThreadPoolExecutor(max_workers=len(reviewers)) as ex:
            futures = {ex.submit(_run_review, ev): ev for ev in reviewers}
            for f in as_completed(futures):
                r = f.result()
                if r:
                    feedbacks.append(r)

        if not feedbacks:
            return initial

        # 3. 初評者再評估
        try:
            sp, up = LLMPromptTemplates.reevaluate_with_feedback_prompt(
                task_name, review_input, initial, feedbacks
            )
            resp = primary.llm_manager.call_with_retry(
                prompt=up, system_prompt=sp, temperature=0.1, max_tokens=3000
            )
            final = primary.llm_manager.parse_json_response(resp)
            if isinstance(final, dict) and "score" in final:
                final.setdefault("summary", {})["collaboration"] = "review_reevaluate"
                return final
        except Exception as e:
            log.warning("再評估失敗，回退初評: %s", e)
        return initial

    def evaluate_semantic_correctness(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """多智能體語義正確性評估（協作：初評→審核→再評估）"""
        return self._evaluate_with_review(
            "用例圖語義正確性",
            lambda ev: ev.evaluate_semantic_correctness(diagram),
            {"diagram": diagram},
        )

    def evaluate_element_ambiguity(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """多智能體元素無歧義性評估（協作）"""
        return self._evaluate_with_review(
            "用例圖元素無歧義性",
            lambda ev: ev.evaluate_element_ambiguity(diagram),
            {"diagram": diagram},
        )

    def evaluate_terminology_consistency(
        self, diagram: Dict[str, Any], requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """多智能體術語一致性評估（協作）"""
        return self._evaluate_with_review(
            "用例圖術語一致性",
            lambda ev: ev.evaluate_terminology_consistency(diagram, requirements),
            {"diagram": diagram, "requirements": requirements},
        )

    def evaluate_use_case_verifiability(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """多智能體用例可驗收性評估（協作）"""
        return self._evaluate_with_review(
            "用例圖可驗收性",
            lambda ev: ev.evaluate_use_case_verifiability(diagram),
            {"diagram": diagram},
        )

    def evaluate_use_case_independence(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """多智能體用例獨立性評估（協作）"""
        return self._evaluate_with_review(
            "用例圖用例獨立性",
            lambda ev: ev.evaluate_use_case_independence(diagram),
            {"diagram": diagram},
        )

    def _desc_evs(self) -> List[LLMEvaluator]:
        """用例描述評估時使用的 evaluators：diagram_only 時僅用首個模型以加速"""
        if self.scope == "diagram_only" and self.evaluators:
            return [self.evaluators[0]]
        return self.evaluators

    def evaluate_description_semantic_correctness(
        self, description: Dict[str, Any], requirements: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """多智能體用例描述語義正確性（協作）"""
        evs = self._desc_evs()
        if len(evs) < 2:
            return evs[0].evaluate_description_semantic_correctness(description, requirements) if evs else {"score": 0.5}
        return self._evaluate_with_review(
            "用例描述語義正確性",
            lambda ev: ev.evaluate_description_semantic_correctness(description, requirements),
            {"description": description, "requirements": requirements or {}},
        )

    def evaluate_description_expression_unambiguity(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """多智能體表達無歧義性（協作）"""
        evs = self._desc_evs()
        if len(evs) < 2:
            return evs[0].evaluate_description_expression_unambiguity(description) if evs else {"score": 0.5}
        return self._evaluate_with_review(
            "用例描述表達無歧義性",
            lambda ev: ev.evaluate_description_expression_unambiguity(description),
            {"description": description},
        )

    def evaluate_description_internal_logical_consistency(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """多智能體內部邏輯一致性（協作）"""
        evs = self._desc_evs()
        if len(evs) < 2:
            return evs[0].evaluate_description_internal_logical_consistency(description) if evs else {"score": 0.5}
        return self._evaluate_with_review(
            "用例描述內部邏輯一致性",
            lambda ev: ev.evaluate_description_internal_logical_consistency(description),
            {"description": description},
        )

    def evaluate_description_step_verifiability(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """多智能體步驟可測試性（協作）"""
        evs = self._desc_evs()
        if len(evs) < 2:
            return evs[0].evaluate_description_step_verifiability(description) if evs else {"score": 0.5}
        return self._evaluate_with_review(
            "用例描述步驟可測試性",
            lambda ev: ev.evaluate_description_step_verifiability(description),
            {"description": description},
        )

    def evaluate_description_functional_cohesion(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """多智能體功能內聚性（協作）"""
        evs = self._desc_evs()
        if len(evs) < 2:
            return evs[0].evaluate_description_functional_cohesion(description) if evs else {"score": 0.5}
        return self._evaluate_with_review(
            "用例描述功能內聚性",
            lambda ev: ev.evaluate_description_functional_cohesion(description),
            {"description": description},
        )

    def evaluate_description_information_relevance(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """多智能體信息相關性（協作）"""
        evs = self._desc_evs()
        if len(evs) < 2:
            return evs[0].evaluate_description_information_relevance(description) if evs else {"score": 0.5}
        return self._evaluate_with_review(
            "用例描述信息相關性",
            lambda ev: ev.evaluate_description_information_relevance(description),
            {"description": description},
        )

    def evaluate_diagram_necessity_four_category(
        self, diagram: Dict[str, Any], requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        用例圖必要性四分類（結構化 JSON，非單一 score）。
        多智能體審核流程不適用此返回格式，統一交首個模型執行，避免缺失方法與審核再評 JSON 不匹配。
        """
        if not self.evaluators:
            return {
                "use_case_evaluations": [],
                "actor_evaluations": [],
                "relationship_evaluations": [],
                "summary": {"note": "無可用模型"},
            }
        return self.evaluators[0].evaluate_diagram_necessity_four_category(diagram, requirements or {})

    def evaluate_diagram_quality_batch(
        self, diagram: Dict[str, Any], requirements: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """與單模型一致；多智能體下由首模型執行批量 prompt。"""
        if not self.evaluators:
            return {}
        return self.evaluators[0].evaluate_diagram_quality_batch(diagram, requirements or {})

    def evaluate_description_quality_batch(self, description: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        if not self.evaluators:
            return {}
        return self.evaluators[0].evaluate_description_quality_batch(description)
