"""
评估指标计算类（IEEE 830 体系）
提供用例图和用例描述的各项质量指标计算
"""
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .cross_language_alignment import (
    analyze_cross_language_context,
    language_mismatch_consistency_issue,
    should_suppress_heuristic_semantic_issue,
)
from .semantic_matcher import WeakSemanticMatcher
from .input_normalizer import (
    is_internal_system_component_role_name,
    is_subject_system_role_name,
    resolve_required_external_roles,
    should_exclude_from_external_actor_role,
)


def _norm_elem_id(val: Any) -> Optional[str]:
    """關係 from/to 與元素 id 的規範化鍵；空值返回 None。"""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


_GENERIC_SEMANTIC_BOILERPLATE = (
    "语义可能不当",
    "語義可能不當",
    "如应 extend 却用了 include",
    "如應 extend 卻用了 include",
    "如应extend却用了include",
    "语义错误 - ",
    "语义错误-",
    "語義錯誤 - ",
    "建议检查",
    "建議檢查",
)


def _strip_generic_semantic_boilerplate(text: str) -> str:
    s = (text or "").strip()
    for phrase in _GENERIC_SEMANTIC_BOILERPLATE:
        s = s.replace(phrase, "").strip()
    s = re.sub(r"^[：:\-—\s]+", "", s)
    s = re.sub(r"[；;，,]\s*$", "", s)
    return s.strip()


def format_semantic_relationship_issue(
    loc_desc: str,
    *,
    reason: str = "",
    suggestion: str = "",
    violation: str = "",
) -> str:
    """
    生成语义正确性 issue 文案：只写具体问题，禁止套话「如应 extend 却用了 include」。
    """
    parts: List[str] = []
    for raw in (violation, reason, suggestion):
        cleaned = _strip_generic_semantic_boilerplate(raw)
        if cleaned.startswith("启发式语义问题"):
            cleaned = cleaned.split(":", 1)[-1].strip()
        if cleaned and cleaned not in parts:
            parts.append(cleaned)
    detail = "；".join(parts)
    if detail and not detail.endswith(("。", ".")):
        detail += "。"
    elif not detail:
        detail = "语义不符合 UML 规范，请核对关系类型与用例职责是否匹配。"
    return f"【用例图·正确性】{loc_desc}：{detail}"


def _safe_ui_str(val: Any, *, if_none: str = "") -> str:
    """避免 issues 中出現字面值「None」或空白。"""
    if val is None:
        return if_none
    if isinstance(val, str):
        s = val.strip()
        return s if s else if_none
    s = str(val).strip()
    return s if s else if_none


def diagram_id_to_display_labels(diagram: Dict[str, Any]) -> Dict[str, str]:
    """元素 id -> 展示標籤（優先 name，否則 id；不產生 Python None 字樣）。"""
    out: Dict[str, str] = {}
    for a in diagram.get("actors") or []:
        if not isinstance(a, dict):
            continue
        eid = _norm_elem_id(a.get("id"))
        if not eid:
            continue
        name = _safe_ui_str(a.get("name"))
        out[eid] = name if name else eid
    for u in diagram.get("use_cases") or []:
        if not isinstance(u, dict):
            continue
        eid = _norm_elem_id(u.get("id"))
        if not eid:
            continue
        name = _safe_ui_str(u.get("name"))
        out[eid] = name if name else eid
    return out


class EvaluationMetrics:
    """评估指标计算类（IEEE 830 体系）"""

    def __init__(self, use_real_llm: bool = True, llm_provider: str = "deepseek", use_multi_agent: bool = False):
        self.issues: List[Dict[str, Any]] = []
        self.use_real_llm = use_real_llm
        self.use_batch_prompts = os.environ.get("USE_BATCH_LLM_PROMPTS", "true").lower() in ("true", "1", "yes")
        self._batch_diagram_cache: Optional[Dict[str, Any]] = None
        self._batch_description_cache: Dict[int, Dict[str, Any]] = {}
        self._diagram_necessity_llm_cache: Optional[Dict[str, Any]] = None

        if use_real_llm:
            try:
                if use_multi_agent:
                    from .multi_agent_evaluator import MultiAgentLLMEvaluator
                    self.llm_evaluator = MultiAgentLLMEvaluator()
                else:
                    from .llm_evaluator import LLMEvaluator
                    self.llm_evaluator = LLMEvaluator()
            except Exception as e:
                print(f"警告: 真实LLM不可用，将使用非LLM模式: {e}")
                self.use_real_llm = False
                self.llm_evaluator = None
        else:
            self.llm_evaluator = None
    
    def _clear_issues(self):
        """清空问题列表"""
        self.issues.clear()

    def _ensure_diagram_batch(self, diagram: Dict[str, Any], requirements: Optional[Dict[str, Any]] = None) -> None:
        """若啟用整合 prompt 且為單模型，預先執行一次調用並緩存"""
        if not self.use_batch_prompts or self._batch_diagram_cache is not None:
            return
        if not self.use_real_llm or not self.llm_evaluator:
            return
        if getattr(self.llm_evaluator, "evaluators", None):
            return
        try:
            self._batch_diagram_cache = self.llm_evaluator.evaluate_diagram_quality_batch(
                diagram, requirements
            )
        except Exception as e:
            print(f"整合 prompt 調用失敗，回退單獨調用: {e}")
            self._batch_diagram_cache = {}

    def _ensure_description_batch(self, description: Dict[str, Any]) -> None:
        """若启用整合 prompt 且为单模型，单条描述仅调用一次并缓存。"""
        if not self.use_batch_prompts:
            return
        if not self.use_real_llm or not self.llm_evaluator:
            return
        if getattr(self.llm_evaluator, "evaluators", None):
            return
        k = id(description)
        if k in self._batch_description_cache:
            return
        try:
            self._batch_description_cache[k] = self.llm_evaluator.evaluate_description_quality_batch(description)
        except Exception as e:
            print(f"描述整合 prompt 调用失败，回退单独调用: {e}")
            self._batch_description_cache[k] = {}

    def _ensure_diagram_necessity_llm(self, diagram: Dict[str, Any], requirements: Optional[Dict[str, Any]] = None) -> None:
        """必要性四分类 LLM 缓存（避免用例/参与者/关系三次重复调用）。"""
        if self._diagram_necessity_llm_cache is not None:
            return
        if not self.use_real_llm or not self.llm_evaluator or not requirements:
            self._diagram_necessity_llm_cache = {}
            return
        try:
            self._diagram_necessity_llm_cache = self.llm_evaluator.evaluate_diagram_necessity_four_category(diagram, requirements)
        except Exception as e:
            print(f"用例图必要性四分类 LLM 调用失败，回退规则: {e}")
            self._diagram_necessity_llm_cache = {}
    
    def _add_issue(self, issue: Dict[str, Any]):
        """添加问题到问题列表"""
        self.issues.append(issue)
    
    def get_issues(self) -> List[Dict[str, Any]]:
        """获取所有问题"""
        return self.issues.copy()

    def _relationship_id_to_display_names(self, diagram: Dict[str, Any]) -> Dict[str, str]:
        """关系 id -> 可读描述「from_name - to_name（type）」；缺 id/空名稱時不顯示 None-None。"""
        labels = diagram_id_to_display_labels(diagram)
        out: Dict[str, str] = {}
        missing_ep = "(未指定端点)"
        for r in diagram.get("relationships") or []:
            if not isinstance(r, dict):
                continue
            fk = _norm_elem_id(r.get("from"))
            tk = _norm_elem_id(r.get("to"))
            from_name = labels.get(fk) if fk else None
            to_name = labels.get(tk) if tk else None
            if not from_name:
                from_name = fk or missing_ep
            if not to_name:
                to_name = tk or missing_ep
            rel_type = _safe_ui_str(r.get("type"), if_none="association") or "association"
            rid = _norm_elem_id(r.get("id"))
            if not rid:
                rid = f"{fk or missing_ep}→{tk or missing_ep}"
            out[rid] = f"关系「{from_name} - {to_name}」（{rel_type}）"
        return out

    def _count_include_extend_per_use_case(self, diagram: Dict[str, Any]) -> Dict[str, int]:
        """每个用例参与的 include/extend 关系数量（作为 from 或 to）。"""
        from collections import defaultdict
        count = defaultdict(int)
        for r in diagram.get("relationships", []):
            if r.get("type") not in ("include", "extend"):
                continue
            count[r.get("from", "")] += 1
            count[r.get("to", "")] += 1
        return dict(count)

    # ==================== 用例图评估指标 ====================
    # --- 正确性 (Correctness) ---

    def diagram_syntax_correctness(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """
        语法正确性
        
        用例图符合 UML 用例图语法规范的程度。
        measurement: no. of elements following UML syntax / total no. of elements
        评估方式: 自动化规则检查
        
        Args:
            diagram: 用例图数据
            
        Returns:
            Dict[str, Any]: 语法正确性评估结果
        """
        self._clear_issues()
        
        actors = diagram.get("actors", [])
        use_cases = diagram.get("use_cases", [])
        relationships = diagram.get("relationships", [])
        
        # 建立 element id -> type 映射（跳過缺少 id 的項，避免 KeyError）
        element_type: Dict[str, str] = {}
        element_name: Dict[str, str] = {}
        labels = diagram_id_to_display_labels(diagram)

        for actor in actors:
            if not isinstance(actor, dict):
                continue
            aid = _norm_elem_id(actor.get("id"))
            if not aid:
                continue
            element_type[aid] = "actor"
            element_name[aid] = _safe_ui_str(actor.get("name"))

        for uc in use_cases:
            if not isinstance(uc, dict):
                continue
            uid = _norm_elem_id(uc.get("id"))
            if not uid:
                continue
            element_type[uid] = "use_case"
            element_name[uid] = _safe_ui_str(uc.get("name"))

        # 同名元素视为语法错误（标识唯一性归入语法正确性）
        name_count = {}
        for elem_id, etype in element_type.items():
            name = element_name.get(elem_id, "")
            if not name:
                continue
            norm = self._normalize_identifier(name)
            if norm:
                key = f"{etype}::{norm}"
                name_count[key] = name_count.get(key, 0) + 1
        duplicate_name_ids = set()
        for actor in actors:
            if not isinstance(actor, dict):
                continue
            aid = _norm_elem_id(actor.get("id"))
            if not aid:
                continue
            name = actor.get("name", "")
            if not name:
                continue
            key = f"actor::{self._normalize_identifier(name)}"
            if name_count.get(key, 0) > 1:
                duplicate_name_ids.add(aid)
        for uc in use_cases:
            if not isinstance(uc, dict):
                continue
            uid = _norm_elem_id(uc.get("id"))
            if not uid:
                continue
            name = uc.get("name", "")
            if not name:
                continue
            key = f"use_case::{self._normalize_identifier(name)}"
            if name_count.get(key, 0) > 1:
                duplicate_name_ids.add(uid)
        for eid in duplicate_name_ids:
            etype = element_type.get(eid, "")
            ename = element_name.get(eid) or eid
            self._add_issue({
                "issue_type": "syntax_error",
                "element_id": eid,
                "element_name": ename,
                "element_type": etype,
                "location": f"{etype} {eid}",
                "description": f"【用例图·正确性】{etype}「{ename}」（id: {eid}）与图中其他元素重名，违反标识唯一性。",
                "severity": 0.8,
                "suggestion": "为每个元素使用唯一名称"
            })

        def _in_dup(elem: Dict[str, Any]) -> bool:
            eid = _norm_elem_id(elem.get("id")) if isinstance(elem, dict) else None
            return bool(eid and eid in duplicate_name_ids)

        valid_elements = (
            sum(1 for a in actors if isinstance(a, dict) and not _in_dup(a))
            + sum(1 for u in use_cases if isinstance(u, dict) and not _in_dup(u))
        )
        total_elements = len(actors) + len(use_cases)

        # 无关系时仅按元素唯一性计分
        if not relationships:
            total = max(1, total_elements)
            score = valid_elements / total if total else 1.0
            return {
                "score": score,
                "valid_count": valid_elements,
                "total_count": total_elements,
                "issues": self.get_issues()
            }

        valid = 0

        for rel in relationships:
            if not isinstance(rel, dict):
                continue
            rel_type = rel.get("type")
            src = rel.get("from")
            tgt = rel.get("to")
            nk_from = _norm_elem_id(src)
            nk_to = _norm_elem_id(tgt)
            rel_id = _norm_elem_id(rel.get("id")) or f"{nk_from or '(未指定端点)'}→{nk_to or '(未指定端点)'}"

            src_type = element_type.get(nk_from) if nk_from else None
            tgt_type = element_type.get(nk_to) if nk_to else None
            src_name = (labels.get(nk_from) if nk_from else None) or nk_from or "(未指定端点)"
            tgt_name = (labels.get(nk_to) if nk_to else None) or nk_to or "(未指定端点)"

            is_valid = True
            issue_description = ""

            # include/extend 只能连接 use case
            if rel_type in {"include", "extend"}:
                if src_type != "use_case" or tgt_type != "use_case":
                    is_valid = False
                    issue_description = f"include/extend关系只能在用例之间，不能连接参与者"

            # association 只能发生在 actor 与 use case 之间
            elif rel_type == "association":
                if {src_type, tgt_type} != {"actor", "use_case"}:
                    is_valid = False
                    issue_description = f"关联关系必须在参与者和用例之间"

            # 泛化关系检查
            elif rel_type == "generalization":
                # 泛化关系只能在同类型元素之间
                if src_type != tgt_type:
                    is_valid = False
                    issue_description = f"泛化关系只能在同类型元素之间"

            if is_valid:
                valid += 1
            else:
                loc_desc = f"关系「{src_name} - {tgt_name}」（{rel_type}）"
                issue = {
                    "issue_type": "syntax_error",
                    "element_id": rel_id,
                    "element_name": f"{src_name} → {tgt_name}",
                    "element_type": "relationship",
                    "location": f"关系 {rel_id}",
                    "description": f"【用例图·正确性】{loc_desc}：语法错误 - {issue_description}",
                    "severity": 0.8,
                    "suggestion": "请根据UML规范修正关系类型和连接元素"
                }
                self._add_issue(issue)

        total_count = total_elements + len(relationships)
        valid_count = valid_elements + valid
        score = valid_count / total_count if total_count else 1.0

        return {
            "score": score,
            "valid_count": valid_count,
            "total_count": total_count,
            "issues": self.get_issues()
        }

    def diagram_semantic_correctness(
        self,
        diagram: Dict[str, Any],
        requirements: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        语义正确性 - 使用真实LLM（或整合 prompt 緩存）
        需求与用例图跨语言时：先对齐语义，抑制启发式误报，并提高 LLM 权重。
        """
        self._clear_issues()
        lang_ctx = analyze_cross_language_context(diagram, requirements)

        if self.use_real_llm and self.llm_evaluator:
            llm_result = None
            if self._batch_diagram_cache and "semantic_correctness" in self._batch_diagram_cache:
                llm_result = self._batch_diagram_cache["semantic_correctness"]
            else:
                llm_result = self.llm_evaluator.evaluate_semantic_correctness(
                    diagram, requirements=requirements, lang_ctx=lang_ctx
                )
            llm_evaluations = llm_result.get("llm_evaluations", []) if llm_result else []
            rel_id_to_names = self._relationship_id_to_display_names(diagram)
            rel_keys_in_order = list(rel_id_to_names.keys())
            reported_rel_ids: set[str] = set()

            def _resolve_loc_desc(rel_id: str, idx: int) -> str:
                loc = rel_id_to_names.get(rel_id)
                if not loc and idx < len(rel_keys_in_order):
                    loc = rel_id_to_names.get(rel_keys_in_order[idx])
                if not loc:
                    loc = f"关系（relationship_id={rel_id or '缺失或未匹配'}）"
                return loc

            for idx, eval_item in enumerate(llm_evaluations):
                if not eval_item.get("is_valid", True):
                    rel_id = str(eval_item.get("relationship_id", "") or "").strip()
                    if lang_ctx.cross_language and should_suppress_heuristic_semantic_issue(
                        diagram, rel_id, requirements, lang_ctx
                    ):
                        continue
                    loc_desc = _resolve_loc_desc(rel_id, idx)
                    if rel_id:
                        reported_rel_ids.add(rel_id)
                    desc = format_semantic_relationship_issue(
                        loc_desc,
                        reason=str(eval_item.get("reason", "") or ""),
                        suggestion=str(eval_item.get("suggestion", "") or ""),
                    )
                    self._add_issue({
                        "issue_type": "semantic_error",
                        "element_id": rel_id,
                        "element_name": "",
                        "element_type": "relationship",
                        "location": f"关系 {rel_id}",
                        "description": desc,
                        "severity": 0.8,
                        "suggestion": eval_item.get("suggestion", ""),
                        "llm_evaluated": True,
                    })

            from .semantic_correctness_evaluator import SemanticCorrectnessEvaluator
            evaluator = SemanticCorrectnessEvaluator(use_llm=False)
            rule_results = evaluator._rule_based_validation(diagram)
            heuristic_results = evaluator._heuristic_validation(diagram)

            for issue in evaluator.issues:
                rid = str(issue.element_id or "").strip()
                if lang_ctx.cross_language and should_suppress_heuristic_semantic_issue(
                    diagram, rid, requirements, lang_ctx
                ):
                    continue
                if rid and rid in reported_rel_ids:
                    continue
                if rid:
                    reported_rel_ids.add(rid)
                loc_desc = rel_id_to_names.get(rid) or f"关系（element_id={rid or '未知'}）"
                violation = issue.description or ""
                self._add_issue({
                    "issue_type": "semantic_error",
                    "element_id": rid,
                    "element_name": "",
                    "element_type": "relationship",
                    "location": f"关系 {rid}",
                    "description": format_semantic_relationship_issue(
                        loc_desc,
                        violation=violation,
                        suggestion=issue.suggestion or "",
                    ),
                    "severity": issue.severity,
                    "suggestion": issue.suggestion or "",
                    "llm_evaluated": False,
                })
            
            llm_score = llm_result.get("score", 1.0)
            llm_results = {
                "validated_relationships": llm_evaluations,
                "summary": {
                    "total_validated": len(llm_evaluations),
                    "llm_issues": sum(1 for e in llm_evaluations if not e.get("is_valid", True)),
                    "llm_score": llm_score
                }
            }
            
            rule_score = rule_results.get("summary", {}).get("rule_score", 1.0)
            heuristic_score = heuristic_results.get("summary", {}).get("heuristic_score", 1.0)
            if lang_ctx.cross_language:
                # 跨语言：启发式规则易误报，以 LLM（已含需求全文）为主
                overall_score = llm_score * 0.75 + rule_score * 0.25
                heuristic_score = 1.0
            else:
                overall_score = (
                    rule_score * 0.5 + heuristic_score * 0.3 + llm_score * 0.2
                )

            return {
                "score": overall_score,
                "rule_based_score": rule_score,
                "heuristic_score": heuristic_score,
                "llm_score": llm_score,
                "cross_language_alignment": lang_ctx.cross_language,
                "issues": self.get_issues(),
                "validation_summary": {
                    "rule_based": rule_results.get("summary", {}),
                    "heuristic": heuristic_results.get("summary", {}),
                    "llm_enhanced": llm_results.get("summary", {})
                },
                "llm_result": llm_result,
                "llm_used": True,
                "provider": llm_result.get("provider", "unknown"),
                "note": "语义正确性评估完成（使用真实LLM）"
            }
        else:
            from .semantic_correctness_evaluator import SemanticCorrectnessEvaluator
            evaluator = SemanticCorrectnessEvaluator(use_llm=False)
            results = evaluator.evaluate_diagram(diagram)
            rel_id_to_names = self._relationship_id_to_display_names(diagram)
            for issue in evaluator.issues:
                if lang_ctx.cross_language and should_suppress_heuristic_semantic_issue(
                    diagram, str(issue.element_id or ""), requirements, lang_ctx
                ):
                    continue
                loc_desc = rel_id_to_names.get(issue.element_id)
                if not loc_desc:
                    loc_desc = f"关系（element_id={issue.element_id or '未知'}）"
                desc = (
                    issue.description
                    if issue.description.startswith("【")
                    else format_semantic_relationship_issue(
                        loc_desc,
                        violation=issue.description,
                        suggestion=issue.suggestion or "",
                    )
                )
                self._add_issue({
                    "issue_type": "semantic_error",
                    "element_id": issue.element_id,
                    "element_name": "",
                    "element_type": issue.element_type,
                    "location": f"关系 {issue.element_id}",
                    "description": desc,
                    "severity": issue.severity,
                    "suggestion": issue.suggestion,
                    "llm_evaluated": False
                })
            
            score = results["overall_score"]
            if lang_ctx.cross_language:
                if not self.get_issues():
                    score = max(score, 1.0)
                else:
                    score = max(score, results.get("rule_based_score", score))

            return {
                "score": score,
                "rule_based_score": results["rule_based_score"],
                "heuristic_score": results["heuristic_score"],
                "llm_score": results.get("llm_score"),
                "cross_language_alignment": lang_ctx.cross_language,
                "issues": self.get_issues(),
                "validation_summary": results["validation_summary"],
                "llm_used": False,
                "note": "语义正确性评估完成（使用模拟LLM）",
            }

    def diagram_element_unambiguity(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """
        元素无歧义性 - 使用真实LLM
        """
        self._clear_issues()
        
        if self.use_real_llm and self.llm_evaluator:
            llm_result = None
            if self._batch_diagram_cache and "element_ambiguity" in self._batch_diagram_cache:
                llm_result = self._batch_diagram_cache["element_ambiguity"]
            else:
                llm_result = self.llm_evaluator.evaluate_element_ambiguity(diagram)
            ambiguous_elements = llm_result.get("ambiguous_elements", []) if llm_result else []
            for element in ambiguous_elements:
                self._add_issue({
                    "issue_type": "ambiguity",
                    "element_id": element.get("id", ""),
                    "element_name": element.get("name", ""),
                    "element_type": element.get("type", ""),
                    "location": f"{element.get('type', '')} {element.get('id', '')}",
                    "description": f"【用例图·明确性】{element.get('type', '')}「{element.get('name', '')}」可能存在歧义: {', '.join(element.get('reasons', []))}",
                    "severity": 0.5,
                    "suggestion": f"考虑使用更明确的名称，如: {', '.join(element.get('suggestions', ['重命名以明确含义']))}",
                    "llm_evaluated": True
                })
            
            return {
                "score": llm_result.get("score", 0.0),
                "clear_elements": llm_result.get("summary", {}).get("clear_count", 0),
                "total_elements": llm_result.get("summary", {}).get("total_elements", 0),
                "ambiguous_elements": ambiguous_elements,
                "issues": self.get_issues(),
                "llm_result": llm_result,
                "llm_used": True,
                "provider": llm_result.get("provider", "unknown")
            }
        else:
            return self._original_diagram_element_unambiguity(diagram)

    def _original_diagram_element_unambiguity(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """
        元素无歧义性（非LLM回退版本）

        以简单启发式识别明显歧义/过度笼统命名，避免因未配置LLM而无法运行评估。
        """
        self._clear_issues()

        actors = diagram.get("actors", []) if isinstance(diagram, dict) else []
        use_cases = diagram.get("use_cases", []) if isinstance(diagram, dict) else []

        elements = []
        for a in actors:
            elements.append(
                {
                    "id": a.get("id", ""),
                    "name": a.get("name", ""),
                    "type": "actor",
                    "description": a.get("description", ""),
                }
            )
        for uc in use_cases:
            elements.append(
                {
                    "id": uc.get("id", ""),
                    "name": uc.get("name", ""),
                    "type": "use_case",
                    "description": uc.get("description", ""),
                }
            )

        if not elements:
            return {
                "score": 1.0,
                "clear_elements": 0,
                "total_elements": 0,
                "ambiguous_elements": [],
                "issues": [],
                "llm_used": False,
                "note": "没有需要评估的元素",
            }

        # 從寬認定：僅最模糊的裸詞才算歧義；「管理」「查詢」「查看」等常見用例詞不判歧義
        too_generic_actor_names = {"系统", "平台", "模块"}
        too_generic_use_case_names = {"处理", "操作"}  # 不含管理、查詢、查看

        ambiguous_elements = []
        for e in elements:
            name = (e.get("name") or "").strip()
            if not name:
                ambiguous_elements.append(
                    {
                        "id": e.get("id", ""),
                        "name": name,
                        "type": e.get("type", ""),
                        "reasons": ["名称为空"],
                        "suggestions": ["补充明确名称（动词+对象或明确角色）"],
                    }
                )
                continue

            reasons = []
            if e.get("type") == "actor":
                if name in too_generic_actor_names:
                    reasons.append("参与者名称过于笼统")
            else:
                if name in too_generic_use_case_names:
                    reasons.append("用例名称过于笼统（缺少动作对象）")

            if reasons:
                ambiguous_elements.append(
                    {
                        "id": e.get("id", ""),
                        "name": name,
                        "type": e.get("type", ""),
                        "reasons": reasons,
                        "suggestions": ["使用更明确的名称（动词+对象/补充限定词）"],
                    }
                )
                self._add_issue(
                    {
                        "issue_type": "ambiguity",
                        "element_id": e.get("id", ""),
                        "element_name": name,
                        "element_type": e.get("type", ""),
                        "location": f"{e.get('type', '')} {e.get('id', '')}",
                        "description": f"【用例图·明确性】{e.get('type', '')}「{name}」可能存在歧义/过度笼统: {', '.join(reasons)}",
                        "severity": 0.5,
                        "suggestion": "使用更明确的名称（动词+对象或补充限定词）",
                        "llm_evaluated": False,
                    }
                )

        total = len(elements)
        ambiguous_count = len(ambiguous_elements)
        clear_count = total - ambiguous_count
        score = clear_count / total if total > 0 else 1.0

        return {
            "score": score,
            "clear_elements": clear_count,
            "total_elements": total,
            "ambiguous_elements": ambiguous_elements,
            "issues": self.get_issues(),
            "llm_used": False,
            "note": "元素无歧义性评估完成（非LLM回退）",
        }

    def _is_pedantic_terminology_reason(self, reason: str) -> bool:
        """过滤「标准术语表」「部分匹配」等机械挑刺理由。"""
        r = (reason or "").strip()
        if not r:
            return False
        lower = r.lower()
        pedantic_markers = (
            "标准术语表",
            "標準術語表",
            "术语表中没有",
            "術語表中沒有",
            "部分匹配",
            "部分匹配",
            "没有'error message'",
            "沒有'error message'",
            "没有'validate'",
            "沒有'validate'",
            "概念不同",
            "含义不一致",
            "含義不一致",
            "两者概念",
            "兩者概念",
        )
        if any(m in r for m in pedantic_markers):
            return True
        if "打印小票" in r and "transaction history" in lower:
            return True
        if "修改密码" in r and ("change" in lower and "pin" in lower):
            return True
        if "validate pin" in lower and ("authenticate" in lower or "pin" in lower):
            return True
        if "display error message" in lower and ("display" in lower or "balance" in lower):
            return True
        return False

    def _terminology_result_from_llm_payload(
        self, res: Dict[str, Any], all_terms: List[str]
    ) -> Dict[str, Any]:
        """将 LLM / 整合 batch 的术语结果转为指标输出，并过滤苛刻误报。"""
        self._clear_issues()
        llm_evals = res.get("llm_evaluations", []) or []
        accepted_inconsistent: List[str] = []

        for e in llm_evals:
            if not isinstance(e, dict) or e.get("is_consistent", True):
                continue
            term = (e.get("term") or "").strip()
            if not term:
                continue
            reason = (e.get("reason", "") or e.get("suggestion", "")).strip()
            if self._is_pedantic_terminology_reason(reason):
                continue
            accepted_inconsistent.append(term)
            desc = f"【用例图·一致性】术语「{term}」与需求业务表述存在明显冲突"
            if reason:
                desc += "；" + reason.rstrip("。.")
            desc = desc.rstrip("。.") + "。"
            self._add_issue({"issue_type": "terminology", "description": desc, "severity": 0.3})

        if not llm_evals:
            for t in res.get("inconsistent_terms", []) + res.get("undefined_terms", []):
                if not isinstance(t, str) or not t.strip():
                    continue
                if t.strip() in accepted_inconsistent:
                    continue
                accepted_inconsistent.append(t.strip())
                self._add_issue({
                    "issue_type": "terminology",
                    "description": f"【用例图·一致性】术语「{t.strip()}」与需求业务表述存在明显冲突，建议核对需求全文后统一用语。",
                    "severity": 0.3,
                })

        total = len(all_terms)
        inconsistent_count = len(accepted_inconsistent)
        consistent_count = max(0, total - inconsistent_count)
        score = consistent_count / total if total else 1.0
        try:
            llm_score = float(res.get("score", score))
            if inconsistent_count == 0:
                score = max(score, llm_score, 1.0)
            elif llm_score > score:
                score = llm_score
        except (TypeError, ValueError):
            pass

        return {
            "score": score,
            "total_terms": total,
            "consistent_terms": consistent_count,
            "inconsistent_terms": accepted_inconsistent,
            "issues": self.get_issues(),
            "note": "术语一致性评估完成（LLM）",
        }

    def diagram_terminology_consistency(self, diagram: Dict[str, Any],
                                       requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        术语一致性
        measurement: no. of terms used consistently / total no. of terms
        评估方式: 优先整合 batch / 单独 LLM 对照需求全文；规则层不再使用碎片化术语表
        """
        self._clear_issues()
        if not diagram:
            return {"score": 0.0, "issues": []}
        all_terms = self._extract_terms_from_diagram(diagram)
        if not all_terms:
            return {"score": 1.0, "issues": [], "note": "没有发现需要评估的术语"}

        lang_issue = language_mismatch_consistency_issue(
            analyze_cross_language_context(diagram, requirements)
        )

        if self._batch_diagram_cache and isinstance(
            self._batch_diagram_cache.get("terminology_consistency"), dict
        ):
            out = self._terminology_result_from_llm_payload(
                self._batch_diagram_cache["terminology_consistency"], all_terms
            )
            if lang_issue:
                out["issues"] = [lang_issue] + (out.get("issues") or [])
            return out

        if self.use_real_llm and self.llm_evaluator and requirements:
            try:
                res = self.llm_evaluator.evaluate_terminology_consistency(diagram, requirements)
                out = self._terminology_result_from_llm_payload(res, all_terms)
                if lang_issue:
                    out["issues"] = [lang_issue] + (out.get("issues") or [])
                return out
            except Exception:
                pass

        issues = [lang_issue] if lang_issue else []
        return {
            "score": 1.0,
            "total_terms": len(all_terms),
            "consistent_terms": len(all_terms),
            "inconsistent_terms": [],
            "issues": issues,
            "note": "术语一致性需启用 LLM；已跳过机械术语表规则以免误报",
        }

    # --- 完整性 ---

    def diagram_actor_completeness(self, diagram, requirements) -> Dict[str, Any]:
        """
        参与者完整性
        
        measurement: no. of correct actors in UCD that match requirement roles / total no. of requirement roles
        评估方式: 自动化集合匹配
        """
        self._clear_issues()
        if not requirements:
            return {"score": 0.0, "details": "无需求数据", "issues": []}

        roles = resolve_required_external_roles(requirements, diagram)
        actors = diagram.get("actors", [])
        lang_ctx = analyze_cross_language_context(diagram, requirements)

        if not roles:
            return {"score": 1.0, "matched": 0, "total": 0, "details": "无角色需求"}

        project_name = (requirements.get("project_name") or "").strip() or None
        excluded_subject: List[str] = []
        excluded_internal: List[str] = []
        effective_roles: List[Any] = []
        for role in roles:
            role_name = role["name"] if isinstance(role, dict) else role
            if not role_name or not str(role_name).strip():
                continue
            th = role.get("type") if isinstance(role, dict) else None
            rn = str(role_name).strip()
            if should_exclude_from_external_actor_role(rn, diagram, project_name, type_hint=th):
                if is_internal_system_component_role_name(rn, type_hint=th):
                    excluded_internal.append(rn)
                else:
                    excluded_subject.append(rn)
                continue
            effective_roles.append(role)

        details_ex: List[str] = []
        if excluded_subject:
            details_ex.append(
                f"已排除待建系统主体角色（不计入外部参与者完整性）：{', '.join(excluded_subject)}"
            )
        if excluded_internal:
            details_ex.append(
                f"已排除系统边界内技术组件（非外部参与者，如数据库/仓储）：{', '.join(excluded_internal)}"
            )

        if not effective_roles:
            return {
                "score": 1.0,
                "matched": 0,
                "total": 0,
                "coverage_basis": "roles",
                "denominator_note": "需求中角色在排除待建系统主体与内部技术组件后为空，不扣分",
                "excluded_subject_system_roles": excluded_subject,
                "excluded_internal_component_roles": excluded_internal,
                "details": details_ex or ["无外部角色需求（已排除待建系统主体与内部组件）"],
            }

        matched = 0
        details = list(details_ex)
        
        for role in effective_roles:
            role_name = role["name"] if isinstance(role, dict) else role
            role_found = False
            
            for actor in actors:
                aname = actor.get("name") if isinstance(actor, dict) else None
                if not aname:
                    continue
                if self._actor_matches_required_role(aname, role_name, lang_ctx):
                    matched += 1
                    role_found = True
                    details.append(f"角色 '{role_name}' 匹配到参与者 '{aname}'")
                    break

            if not role_found:
                details.append(f"角色 '{role_name}' 未在用例图中找到对应参与者")
                self._add_issue({
                    "issue_type": "missing_actor",
                    "description": (
                        f"【用例图·完整性】需求要求外部参与者「{role_name}」，"
                        f"但用例图中缺少该参与者（或仅有无法对应的名称）。"
                    ),
                    "severity": 0.85,
                })

        score = matched / len(effective_roles) if len(effective_roles) > 0 else 0.0
        
        return {
            "score": score,
            "matched": matched,
            "total": len(effective_roles),
            "coverage_basis": "roles",
            "denominator_note": (
                f"以需求中外部角色共 {len(effective_roles)} 條為分母"
                f"（已排除待建系统主体及边界内数据库/仓储等技术组件）"
            ),
            "excluded_subject_system_roles": excluded_subject,
            "excluded_internal_component_roles": excluded_internal,
            "details": details,
            "issues": self.get_issues(),
        }

    def diagram_use_case_completeness(self, diagram, requirements) -> Dict[str, Any]:
        """
        用例完整性
        
        measurement: no. of correct use cases in UCD / total no. of functional requirements
        评估方式: 自动化集合匹配
        """
        if not requirements:
            return {"score": 0.0, "details": "无需求数据"}
        
        use_cases = diagram.get("use_cases", [])
        frs = requirements.get("functional_requirements", [])

        if not frs:
            return {"score": 1.0, "matched": 0, "total": 0, "details": "无功能需求"}
        
        if not use_cases:
            return {"score": 0.0, "matched": 0, "total": len(frs), "details": ["用例图中无用例"]}

        matched = 0
        details = []
        
        for fr in frs:
            if isinstance(fr, dict):
                tx = (fr.get("text") or "").strip()
                tl = (fr.get("title") or "").strip()
                fr_text = tx or tl or (fr.get("id") or "")
            else:
                fr_text = fr
            uc_found = False
            
            for uc in use_cases:
                if not isinstance(uc, dict):
                    continue
                uc_name = uc.get("name") or uc.get("id") or ""
                if uc_name and self._weak_match(fr_text, uc_name):
                    matched += 1
                    uc_found = True
                    details.append(f"功能需求 '{fr_text}' 匹配到用例 '{uc_name}'")
                    break
            
            if not uc_found:
                details.append(f"功能需求 '{fr_text}' 未找到匹配的用例")

        score = matched / len(frs) if len(frs) > 0 else 0.0
        
        return {
            "score": score,
            "matched": matched,
            "total": len(frs),
            "coverage_basis": "functional_requirements",
            "denominator_note": f"以需求中 functional_requirements 共 {len(frs)} 條為分母計算用例覆蓋率（goal_level_requirements 經轉換後併入此列表）",
            "details": details,
        }

    def diagram_relationship_completeness(self, diagram, requirements,
                                          redundant_actor_ids: Optional[Set[str]] = None,
                                          redundant_use_case_ids: Optional[Set[str]] = None) -> Dict[str, Any]:
        """
        关系完整性（仅统计双方均为非冗余参与者/用例的预期关系）
        
        measurement: no. of correct relationships / total no. of expected relationships (non-redundant only)
        评估方式: 自动化三元组匹配
        """
        redundant_actor_ids = redundant_actor_ids or set()
        redundant_use_case_ids = redundant_use_case_ids or set()

        if not requirements:
            return {"score": 0.0, "details": "无需求数据"}
        
        expected = requirements.get("expected_relationships", [])
        if not expected:
            return {"score": 1.0, "matched": 0, "total": 0, "details": "无预期关系"}

        actors = diagram.get("actors", [])
        use_cases = diagram.get("use_cases", [])
        relationships = diagram.get("relationships", [])

        if not actors or not use_cases or not relationships:
            return {"score": 0.0, "matched": 0, "total": len(expected), "details": ["缺少必要的元素或关系"]}

        matched = 0
        effective_total = 0
        details = []

        for er in expected:
            role_text = er.get("role", "")
            func_text = er.get("function", "")
            rel_type = er.get("type", "association")

            actor = None
            for a in actors:
                if self._weak_match(role_text, a.get("name", "")):
                    actor = a
                    break

            uc = None
            for u in use_cases:
                if self._weak_match(func_text, u.get("name", "")):
                    uc = u
                    break

            if not actor or not uc:
                details.append(f"预期关系 '{role_text} - {func_text}' 未找到匹配的元素")
                continue
            if actor.get("id") in redundant_actor_ids or uc.get("id") in redundant_use_case_ids:
                details.append(f"预期关系 '{role_text} - {func_text}' 涉及冗余元素，不计入完整性")
                continue

            effective_total += 1
            relationship_found = False
            for r in relationships:
                if (r.get("from") == actor.get("id") and r.get("to") == uc.get("id") and 
                    r.get("type", "association") == rel_type):
                    matched += 1
                    relationship_found = True
                    details.append(f"预期关系 '{role_text} - {func_text}' 已匹配")
                    break
            
            if not relationship_found:
                details.append(f"预期关系 '{role_text} - {func_text}' 未在图中找到")

        score = matched / effective_total if effective_total > 0 else 1.0
        
        return {
            "score": score,
            "matched": matched,
            "total": effective_total,
            "coverage_basis": "expected_relationships",
            "denominator_note": f"以需求中 expected_relationships 有效條數共 {effective_total} 條（排除無法對應到圖中元素的預期）為分母",
            "details": details
        }

    def diagram_system_boundary_completeness(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """
        系统边界完整性
        
        measurement: exists(System_Boundary) ? 1 : 0
        评估方式: 自动化规则检查
        
        Args:
            diagram: 用例图数据
            
        Returns:
            Dict[str, Any]: 系统边界完整性评估结果
        """
        if not diagram:
            return {"score": 0.0, "details": "无用例图数据"}
        
        v = diagram.get('system_boundary')
        if v is None:
            return {"score": 0.0, "details": "未定义系统边界"}
        
        if isinstance(v, bool):
            score = 1.0 if v else 0.0
            return {"score": score, "details": f"系统边界: {v}"}
        
        if isinstance(v, (dict, list)):
            return {"score": 1.0, "details": "已定义系统边界结构"}
        
        score = 1.0 if v else 0.0
        return {"score": score, "details": f"系统边界: {v}"}

    # --- 其他指标 ---

    def diagram_use_case_verifiability(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """
        用例可验收性
        measurement: no. of verifiable use cases / total no. of use cases
        评估方式: 基于LLM的验收条件推断；未启用LLM时使用规则回退。
        """
        self._clear_issues()
        use_cases = diagram.get("use_cases", [])
        total_use_cases = len(use_cases)
        if total_use_cases == 0:
            return {
                "score": 1.0, "verifiable_count": 0, "total_use_cases": 0,
                "issues": [], "note": "没有需要评估的用例"
            }
        if self.use_real_llm and self.llm_evaluator:
            try:
                res = self.llm_evaluator.evaluate_use_case_verifiability(diagram)
                for u in res.get("unverifiable_cases", []):
                    for reason in u.get("reasons", []):
                        self._add_issue({
                            "issue_type": "unverifiable_use_case",
                            "element_id": u.get("id", ""),
                            "element_name": u.get("name", ""),
                            "element_type": "use_case",
                            "location": f"用例 {u.get('id', '')}",
                            "description": f"用例'{u.get('name', '')}'可能难以验证: {reason}",
                            "severity": 0.6,
                            "suggestion": "确保用例有明确的成功条件和可观察的结果"
                        })
                return {
                    "score": res.get("score", 0.5),
                    "verifiable_count": res.get("verifiable_count", 0),
                    "total_use_cases": res.get("total_use_cases", total_use_cases),
                    "unverifiable_cases": res.get("unverifiable_cases", []),
                    "issues": self.get_issues(),
                    "summary": res.get("summary", {}),
                    "note": "基于LLM的用例可验收性评估完成"
                }
            except Exception as e:
                raise RuntimeError("LLM用例可验收性评估失败，请检查API配置") from e
        verifiable_count = 0
        unverifiable_cases = []
        for uc in use_cases:
            uc_id = uc.get("id", "")
            uc_name = uc.get("name", "")
            uc_description = uc.get("description", "")
            is_verifiable, reasons = self._rule_based_verifiability_check(uc_name, uc_description)
            if is_verifiable:
                verifiable_count += 1
            else:
                unverifiable_cases.append({"id": uc_id, "name": uc_name, "reasons": reasons})
                for reason in reasons:
                    self._add_issue({
                        "issue_type": "unverifiable_use_case",
                        "element_id": uc_id, "element_name": uc_name, "element_type": "use_case",
                        "location": f"用例 {uc_id}", "description": f"用例'{uc_name}'可能难以验证: {reason}",
                        "severity": 0.6, "suggestion": "确保用例有明确的成功条件和可观察的结果"
                    })
        score = verifiable_count / total_use_cases if total_use_cases > 0 else 1.0
        return {
            "score": score, "verifiable_count": verifiable_count, "total_use_cases": total_use_cases,
            "unverifiable_cases": unverifiable_cases, "issues": self.get_issues(),
            "summary": {"total_analyzed": total_use_cases, "verifiable": verifiable_count, "unverifiable": total_use_cases - verifiable_count, "verifiability_rate": score, "note": "规则回退"},
        }

    def diagram_use_case_independence(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """
        用例独立性
        measurement: no. of use cases with single responsibility / total no. of use cases
        评估方式: 自动化结构分析 + 基于LLM的语义分析；未启用LLM时使用规则回退。
        """
        self._clear_issues()
        use_cases = diagram.get("use_cases", [])
        relationships = diagram.get("relationships", [])
        total_use_cases = len(use_cases)
        if total_use_cases == 0:
            return {"score": 1.0, "independent_count": 0, "total_use_cases": 0, "issues": [], "note": "没有需要评估的用例"}
        if self.use_real_llm and self.llm_evaluator:
            try:
                res = None
                if self._batch_diagram_cache and "use_case_independence" in self._batch_diagram_cache:
                    b = self._batch_diagram_cache["use_case_independence"]
                    dep = b.get("dependent_cases", [])
                    summ = b.get("summary", {})
                    total = summ.get("total_use_cases", total_use_cases)
                    indep = summ.get("independent_count", total - len(dep))
                    res = {
                        "score": b.get("score", 0.5),
                        "independent_count": indep,
                        "total_use_cases": total,
                        "dependent_cases": dep,
                        "summary": summ,
                    }
                else:
                    res = self.llm_evaluator.evaluate_use_case_independence(diagram)
                rel_count = self._count_include_extend_per_use_case(diagram)
                for d in res.get("dependent_cases", []):
                    uc_id = d.get("id", "")
                    if rel_count.get(uc_id, 0) < 3:
                        continue
                    for reason in d.get("reasons", []):
                        self._add_issue({
                            "issue_type": "dependent_use_case",
                            "element_id": uc_id,
                            "element_name": d.get("name", ""),
                            "element_type": "use_case",
                            "location": f"用例 {uc_id}",
                            "description": f"【用例图·可修改性】用例「{d.get('name', '')}」可能缺乏独立性（涉及 3 个以上 include/extend 关系）: {reason}",
                            "severity": 0.5,
                            "suggestion": "考虑将用例拆分为更小的、独立的用例，或重新设计用例边界"
                        })
                return {
                    "score": res.get("score", 0.5),
                    "independent_count": res.get("independent_count", 0),
                    "total_use_cases": res.get("total_use_cases", total_use_cases),
                    "dependent_cases": res.get("dependent_cases", []),
                    "dependency_graph": {},
                    "rel_count": rel_count,
                    "issues": self.get_issues(),
                    "summary": res.get("summary", {}),
                    "note": "基于LLM的用例独立性评估完成"
                }
            except Exception as e:
                raise RuntimeError("LLM用例独立性评估失败，请检查API配置") from e
        rel_count = self._count_include_extend_per_use_case(diagram)
        independent_count = 0
        dependent_cases = []
        dependency_graph = self._build_use_case_dependency_graph(use_cases, relationships)
        for uc in use_cases:
            uc_id = uc.get("id", "")
            uc_name = uc.get("name", "")
            has_single_responsibility = self._analyze_use_case_independence(
                uc_id, uc_name, dependency_graph, use_cases, relationships
            )
            if has_single_responsibility["is_independent"]:
                independent_count += 1
            else:
                dependent_cases.append({
                    "id": uc_id, "name": uc_name,
                    "dependencies": has_single_responsibility.get("dependencies", []),
                    "reasons": has_single_responsibility.get("reasons", [])
                })
                if rel_count.get(uc_id, 0) >= 3:
                    for reason in has_single_responsibility.get("reasons", []):
                        self._add_issue({
                            "issue_type": "dependent_use_case",
                            "element_id": uc_id, "element_name": uc_name, "element_type": "use_case",
                            "location": f"用例 {uc_id}", "description": f"【用例图·可修改性】用例「{uc_name}」可能缺乏独立性（涉及 3 个以上 include/extend 关系）: {reason}",
                            "severity": 0.5, "suggestion": "考虑将用例拆分为更小的、独立的用例，或重新设计用例边界"
                        })
        score = independent_count / total_use_cases if total_use_cases > 0 else 1.0
        return {
            "score": score, "independent_count": independent_count, "total_use_cases": total_use_cases,
            "dependent_cases": dependent_cases, "dependency_graph": dependency_graph,
            "rel_count": rel_count,
            "issues": self.get_issues(),
            "summary": {"total_analyzed": total_use_cases, "independent": independent_count, "dependent": total_use_cases - independent_count, "independence_rate": score, "note": "规则回退"},
        }

    def diagram_use_case_redundancy(self, diagram: Dict[str, Any], 
                                requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        用例冗余性
        
        用例图中出现需求中未提及的功能的程度。
        measurement: 1 - (no. of redundant use cases / total no. of use cases)
        评估方式: 自动化集合差集计算
        
        Args:
            diagram: 用例图数据
            requirements: 需求数据（可选）
            
        Returns:
            Dict[str, Any]: 用例冗余性评估结果
        """
        self._clear_issues()
        
        use_cases = diagram.get("use_cases", [])
        total_use_cases = len(use_cases)
        
        if total_use_cases == 0:
            return {
                "score": 1.0,
                "redundant_count": 0,
                "total_use_cases": 0,
                "issues": [],
                "note": "没有需要评估的用例"
            }
        
        if not requirements:
            return {
                "score": 0.5,
                "redundant_count": 0,
                "total_use_cases": total_use_cases,
                "issues": [],
                "note": "没有需求数据，无法计算用例冗余性"
            }

        # LLM四分类优先：合理细化/有依据补充 视为必要；无依据不合理/与需求矛盾 视为可能冗余
        if self.use_real_llm and self.llm_evaluator:
            self._ensure_diagram_necessity_llm(diagram, requirements)
            evs = (self._diagram_necessity_llm_cache or {}).get("use_case_evaluations", [])
            if evs:
                by_name = {}
                by_id = {}
                for e in evs:
                    if not isinstance(e, dict):
                        continue
                    if e.get("name"):
                        by_name[str(e.get("name")).strip()] = e
                    if e.get("id"):
                        by_id[str(e.get("id")).strip()] = e
                redundant_names = set()
                for uc in use_cases:
                    uid = str(uc.get("id", "")).strip()
                    name = str(uc.get("name", "")).strip()
                    e = by_id.get(uid) or by_name.get(name)
                    if not e:
                        continue
                    if not bool(e.get("necessary", True)):
                        redundant_names.add(name)
                redundant_count = len(redundant_names)
                score = 1.0 - (redundant_count / total_use_cases) if total_use_cases > 0 else 1.0
                for uc in use_cases:
                    name = str(uc.get("name", "")).strip()
                    if name in redundant_names:
                        e = by_id.get(str(uc.get("id", "")).strip()) or by_name.get(name) or {}
                        category = e.get("category", "")
                        reason = e.get("reason", "")
                        evidence = e.get("evidence", "")
                        self._add_issue({
                            "issue_type": "redundant_use_case",
                            "element_id": uc.get("id", ""),
                            "element_name": name,
                            "element_type": "use_case",
                            "location": f"用例 {uc.get('id', '')}",
                            "description": f"【用例图·可追溯性】[{category}] 用例「{name}」可能为冗余：{reason}",
                            "severity": 0.45 if category != "与需求矛盾" else 0.6,
                            "suggestion": f"核对需求依据并处理（evidence: {evidence}）" if evidence else "核对需求依据并处理"
                        })
                return {
                    "score": score,
                    "redundant_count": redundant_count,
                    "total_use_cases": total_use_cases,
                    "redundant_use_cases": list(redundant_names),
                    "required_use_cases": [],
                    "issues": self.get_issues(),
                    "summary": {
                        "diagram_use_cases": total_use_cases,
                        "required_use_cases": 0,
                        "redundancy_rate": redundant_count / total_use_cases if total_use_cases > 0 else 0.0,
                        "note": f"LLM四分类发现{redundant_count}个可能冗余用例"
                    }
                }
        
        diagram_use_case_names = set()
        for uc in use_cases:
            name = uc.get("name", "")
            if name and name.strip():
                diagram_use_case_names.add(name.strip())
        
        # 优化需求提取：从功能需求文本抽取用例名 + 需求全文关键词（放宽匹配，减少误判冗余）
        required_use_case_names = set()
        requirement_text_chunks = []
        functional_requirements = requirements.get("functional_requirements", [])
        
        for fr in functional_requirements:
            if isinstance(fr, dict):
                text = fr.get("text", "")
            else:
                text = str(fr)
            if text and text.strip():
                requirement_text_chunks.append(text.strip())
            
            import re
            pattern = r'(?:能够|可以|应该)\s*([\u4e00-\u9fff]+)\s*([\u4e00-\u9fff]+)'
            matches = re.findall(pattern, text)
            
            for verb, obj in matches:
                use_case_name = f"{verb}{obj}"
                required_use_case_names.add(use_case_name)
            
            noun_phrases = re.findall(r'([\u4e00-\u9fff]{2,}系统|[\u4e00-\u9fff]{2,}功能|[\u4e00-\u9fff]{2,}模块)', text)
            for phrase in noun_phrases:
                required_use_case_names.add(phrase)
        
        from .semantic_matcher import WeakSemanticMatcher
        matched_use_cases = set()
        
        for uc_name in diagram_use_case_names:
            for required_name in required_use_case_names:
                if WeakSemanticMatcher.weak_match(uc_name, required_name):
                    matched_use_cases.add(uc_name)
                    break
            if uc_name in matched_use_cases:
                continue
            for text in requirement_text_chunks:
                if uc_name in text:
                    matched_use_cases.add(uc_name)
                    break
        
        redundant_use_cases = diagram_use_case_names - matched_use_cases
        redundant_count = len(redundant_use_cases)
        
        score = 1.0 - (redundant_count / total_use_cases) if total_use_cases > 0 else 1.0
        
        for uc in use_cases:
            uc_name = uc.get("name", "").strip()
            if uc_name in redundant_use_cases:
                self._add_issue({
                    "issue_type": "redundant_use_case",
                    "element_id": uc.get("id", ""),
                    "element_name": uc_name,
                    "element_type": "use_case",
                    "location": f"用例 {uc.get('id', '')}",
                    "description": f"【用例图·可追溯性】用例「{uc_name}」在当前需求抽取结果中未提及，可能为冗余功能。（基于需求抽取结果；若需求文档中实际有提及，可忽略）",
                    "severity": 0.4,
                    "suggestion": "确认该用例是否确实需要，或从需求中补充对应功能"
                })
        
        return {
            "score": score,
            "redundant_count": redundant_count,
            "total_use_cases": total_use_cases,
            "redundant_use_cases": list(redundant_use_cases),
            "required_use_cases": list(required_use_case_names),
            "issues": self.get_issues(),
            "summary": {
                "diagram_use_cases": len(diagram_use_case_names),
                "required_use_cases": len(required_use_case_names),
                "redundancy_rate": redundant_count / total_use_cases if total_use_cases > 0 else 0.0,
                "note": f"发现{redundant_count}个冗余用例（需求中未提及）"
            }
        }

    def diagram_actor_redundancy(self, diagram: Dict[str, Any], 
                                requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        参与者冗余性
        
        用例图中出现与系统无关的参与者的程度。
        measurement: 1 - (no. of redundant actors / total no. of actors)
        评估方式: 自动化集合差集计算
        
        Args:
            diagram: 用例图数据
            requirements: 需求数据（可选）
            
        Returns:
            Dict[str, Any]: 参与者冗余性评估结果
        """
        self._clear_issues()
        
        actors = diagram.get("actors", [])
        total_actors = len(actors)
        
        if total_actors == 0:
            return {
                "score": 1.0,
                "redundant_count": 0,
                "total_actors": 0,
                "issues": [],
                "note": "没有需要评估的参与者"
            }
        
        if not requirements:
            return {
                "score": 0.5,
                "redundant_count": 0,
                "total_actors": total_actors,
                "issues": [],
                "note": "没有需求数据，无法计算参与者冗余性"
            }

        if self.use_real_llm and self.llm_evaluator:
            self._ensure_diagram_necessity_llm(diagram, requirements)
            evs = (self._diagram_necessity_llm_cache or {}).get("actor_evaluations", [])
            if evs:
                by_name = {}
                by_id = {}
                for e in evs:
                    if not isinstance(e, dict):
                        continue
                    if e.get("name"):
                        by_name[str(e.get("name")).strip()] = e
                    if e.get("id"):
                        by_id[str(e.get("id")).strip()] = e
                redundant_names = set()
                for actor in actors:
                    aid = str(actor.get("id", "")).strip()
                    name = str(actor.get("name", "")).strip()
                    e = by_id.get(aid) or by_name.get(name)
                    if not e:
                        continue
                    if not bool(e.get("necessary", True)):
                        redundant_names.add(name)
                redundant_count = len(redundant_names)
                score = 1.0 - (redundant_count / total_actors) if total_actors > 0 else 1.0
                for actor in actors:
                    name = str(actor.get("name", "")).strip()
                    if name in redundant_names:
                        e = by_id.get(str(actor.get("id", "")).strip()) or by_name.get(name) or {}
                        category = e.get("category", "")
                        reason = e.get("reason", "")
                        evidence = e.get("evidence", "")
                        self._add_issue({
                            "issue_type": "redundant_actor",
                            "element_id": actor.get("id", ""),
                            "element_name": name,
                            "element_type": "actor",
                            "location": f"参与者 {actor.get('id', '')}",
                            "description": f"【用例图·可追溯性】[{category}] 参与者「{name}」可能为冗余：{reason}",
                            "severity": 0.45 if category != "与需求矛盾" else 0.6,
                            "suggestion": f"核对需求依据并处理（evidence: {evidence}）" if evidence else "核对需求依据并处理"
                        })
                return {
                    "score": score,
                    "redundant_count": redundant_count,
                    "total_actors": total_actors,
                    "redundant_actors": list(redundant_names),
                    "required_roles": [],
                    "issues": self.get_issues(),
                    "summary": {
                        "diagram_actors": total_actors,
                        "required_roles": 0,
                        "redundancy_rate": redundant_count / total_actors if total_actors > 0 else 0.0,
                        "note": f"LLM四分类发现{redundant_count}个可能冗余参与者"
                    }
                }
        
        diagram_actor_names = set()
        for actor in actors:
            name = actor.get("name", "")
            if name and name.strip():
                diagram_actor_names.add(name.strip())
        
        required_role_names = set()
        roles = requirements.get("roles", [])
        project_name = (requirements.get("project_name") or "").strip() or None
        
        for role in roles:
            if isinstance(role, dict):
                role_name = role.get("name", "")
                th = role.get("type")
            else:
                role_name = str(role)
                th = None
            
            if role_name and role_name.strip():
                rn = role_name.strip()
                if should_exclude_from_external_actor_role(
                    rn, diagram, project_name, type_hint=th
                ):
                    continue
                required_role_names.add(rn)
        
        if not required_role_names:
            functional_requirements = requirements.get("functional_requirements", [])
            for fr in functional_requirements:
                if isinstance(fr, dict):
                    text = fr.get("text", "")
                else:
                    text = str(fr)
                
                common_roles = ["用户", "管理员", "客户", "系统", "操作员", "维护人员"]
                for role in common_roles:
                    if role in text:
                        if is_subject_system_role_name(role, diagram, project_name):
                            continue
                        required_role_names.add(role)
        
        role_text_chunks = list(required_role_names) + [fr.get("text", "") if isinstance(fr, dict) else str(fr) for fr in requirements.get("functional_requirements", [])]
        for actor_name in diagram_actor_names:
            if should_exclude_from_external_actor_role(
                actor_name, diagram, project_name
            ):
                continue
            if actor_name in required_role_names:
                continue
            for text in role_text_chunks:
                if actor_name in (text or ""):
                    required_role_names.add(actor_name)
                    break
        
        redundant_actors = diagram_actor_names - required_role_names
        redundant_count = len(redundant_actors)
        
        score = 1.0 - (redundant_count / total_actors) if total_actors > 0 else 1.0
        
        for actor in actors:
            actor_name = actor.get("name", "").strip()
            if actor_name in redundant_actors:
                self._add_issue({
                    "issue_type": "redundant_actor",
                    "element_id": actor.get("id", ""),
                    "element_name": actor_name,
                    "element_type": "actor",
                    "location": f"参与者 {actor.get('id', '')}",
                    "description": f"【用例图·可追溯性】参与者「{actor_name}」在当前需求抽取结果中未提及，可能为冗余角色。（基于需求抽取结果；若需求文档中实际有提及，可忽略）",
                    "severity": 0.4,
                    "suggestion": "确认该参与者是否确实需要，或从需求中补充对应角色"
                })
        
        return {
            "score": score,
            "redundant_count": redundant_count,
            "total_actors": total_actors,
            "redundant_actors": list(redundant_actors),
            "required_roles": list(required_role_names),
            "issues": self.get_issues(),
            "summary": {
                "diagram_actors": len(diagram_actor_names),
                "required_roles": len(required_role_names),
                "redundancy_rate": redundant_count / total_actors if total_actors > 0 else 0.0,
                "note": f"发现{redundant_count}个冗余参与者（需求中未提及）"
            }
        }

    def diagram_relationship_redundancy(self, diagram: Dict[str, Any], 
                                    requirements: Optional[Dict[str, Any]] = None,
                                    redundant_actor_ids: Optional[Set[str]] = None,
                                    redundant_use_case_ids: Optional[Set[str]] = None) -> Dict[str, Any]:
        """
        关系冗余性（仅评估两端均为非冗余参与者/用例的关系）
        
        用例图中存在根据需求不应出现的关系的程度。
        measurement: 1 - (no. of redundant relationships / total no. of relationships) 仅统计非冗余元素间的关系。
        """
        redundant_actor_ids = redundant_actor_ids or set()
        redundant_use_case_ids = redundant_use_case_ids or set()
        self._clear_issues()
        
        relationships = diagram.get("relationships", [])
        actors = {a["id"]: a for a in diagram.get("actors", [])}
        use_cases = {uc["id"]: uc for uc in diagram.get("use_cases", [])}

        # 只考虑两端都是非冗余元素的关系
        def is_redundant(eid: str) -> bool:
            if eid in redundant_actor_ids or eid in redundant_use_case_ids:
                return True
            return False

        filtered_rels = []
        for rel in relationships:
            from_id = rel.get("from", "")
            to_id = rel.get("to", "")
            if is_redundant(from_id) or is_redundant(to_id):
                continue
            filtered_rels.append(rel)

        total_relationships = len(filtered_rels)
        
        if total_relationships == 0:
            return {
                "score": 1.0,
                "redundant_count": 0,
                "total_relationships": 0,
                "issues": [],
                "note": "没有需要评估的关系（或所有关系均涉及冗余元素）"
            }
        
        if not requirements:
            return {
                "score": 0.5,
                "redundant_count": 0,
                "total_relationships": total_relationships,
                "issues": [],
                "note": "没有需求数据，无法计算关系冗余性"
            }

        if self.use_real_llm and self.llm_evaluator:
            self._ensure_diagram_necessity_llm(diagram, requirements)
            evs = (self._diagram_necessity_llm_cache or {}).get("relationship_evaluations", [])
            if evs:
                by_id = {}
                for e in evs:
                    if isinstance(e, dict) and e.get("id"):
                        by_id[str(e.get("id")).strip()] = e
                redundant_ids = set()
                for rel in filtered_rels:
                    rid = str(rel.get("id", "")).strip()
                    e = by_id.get(rid)
                    if e and not bool(e.get("necessary", True)):
                        redundant_ids.add(rid)
                redundant_count = len(redundant_ids)
                score = 1.0 - (redundant_count / total_relationships) if total_relationships > 0 else 1.0
                for rel in filtered_rels:
                    rid = str(rel.get("id", "")).strip()
                    if rid in redundant_ids:
                        e = by_id.get(rid, {})
                        from_id = rel.get("from", "")
                        to_id = rel.get("to", "")
                        from_elem = actors.get(from_id) or use_cases.get(from_id) or {}
                        to_elem = actors.get(to_id) or use_cases.get(to_id) or {}
                        from_name = _safe_ui_str(from_elem.get("name")) or _safe_ui_str(from_id, if_none="(?)")
                        to_name = _safe_ui_str(to_elem.get("name")) or _safe_ui_str(to_id, if_none="(?)")
                        category = e.get("category", "")
                        reason = e.get("reason", "")
                        evidence = e.get("evidence", "")
                        self._add_issue({
                            "issue_type": "redundant_relationship",
                            "element_id": rel.get("id", ""),
                            "element_name": f"{from_name} → {to_name}",
                            "element_type": "relationship",
                            "location": f"关系 {rel.get('id', '')}",
                            "description": f"【用例图·可追溯性】[{category}] 关系「{from_name} - {to_name}」可能冗余：{reason}",
                            "severity": 0.45 if category != "与需求矛盾" else 0.6,
                            "suggestion": f"核对需求依据并处理（evidence: {evidence}）" if evidence else "核对需求依据并处理"
                        })
                return {
                    "score": score,
                    "redundant_count": redundant_count,
                    "total_relationships": total_relationships,
                    "redundant_relationships": list(redundant_ids),
                    "expected_relationships": [],
                    "issues": self.get_issues(),
                    "summary": {
                        "diagram_relationships": total_relationships,
                        "expected_relationships": 0,
                        "redundancy_rate": redundant_count / total_relationships if total_relationships > 0 else 0.0,
                        "note": f"LLM四分类发现{redundant_count}个可能冗余关系"
                    }
                }
        
        diagram_relationships = set()
        for rel in filtered_rels:
            rel_type = rel.get("type", "")
            from_id = rel.get("from", "")
            to_id = rel.get("to", "")
            from_elem = actors.get(from_id) or use_cases.get(from_id)
            to_elem = actors.get(to_id) or use_cases.get(to_id)
            if from_elem and to_elem:
                from_name = _safe_ui_str(from_elem.get("name")) or _safe_ui_str(from_id, if_none="(?)")
                to_name = _safe_ui_str(to_elem.get("name")) or _safe_ui_str(to_id, if_none="(?)")
                triple = self._normalize_relationship_triple(from_name, to_name, rel_type)
                diagram_relationships.add(triple)
        
        expected_relationships = requirements.get("expected_relationships", [])
        expected_relationship_triples = set()
        for er in expected_relationships:
            role = er.get("role", "")
            function = er.get("function", "")
            rel_type = er.get("type", "association")
            if role and function:
                triple = self._normalize_relationship_triple(role, function, rel_type)
                expected_relationship_triples.add(triple)

        # 弱語義匹配：若圖中關係與預期在名稱上相似則視為匹配（減少誤報）
        def _triple_weakly_matched(d_triple: str, expected_triples: set) -> bool:
            parts = d_triple.split("::", 2)
            if len(parts) != 3:
                return False
            d_from, d_type, d_to = parts[0], parts[1], parts[2]
            for et in expected_triples:
                ep = et.split("::", 2)
                if len(ep) != 3 or ep[1] != d_type:
                    continue
                if WeakSemanticMatcher.weak_match(d_from, ep[0]) and WeakSemanticMatcher.weak_match(d_to, ep[2]):
                    return True
            return False

        redundant_relationships = set()
        for tr in diagram_relationships:
            if tr not in expected_relationship_triples and not _triple_weakly_matched(tr, expected_relationship_triples):
                redundant_relationships.add(tr)
        redundant_count = len(redundant_relationships)
        
        score = 1.0 - (redundant_count / total_relationships) if total_relationships > 0 else 1.0
        
        for rel in filtered_rels:
            rel_id = rel.get("id", "")
            rel_type = rel.get("type", "")
            from_id = rel.get("from", "")
            to_id = rel.get("to", "")
            from_elem = actors.get(from_id) or use_cases.get(from_id)
            to_elem = actors.get(to_id) or use_cases.get(to_id)
            if from_elem and to_elem:
                from_name = _safe_ui_str(from_elem.get("name")) or _safe_ui_str(from_id, if_none="(?)")
                to_name = _safe_ui_str(to_elem.get("name")) or _safe_ui_str(to_id, if_none="(?)")
                triple = self._normalize_relationship_triple(from_name, to_name, rel_type)
                if triple in redundant_relationships:
                    self._add_issue({
                        "issue_type": "redundant_relationship",
                        "element_id": rel_id,
                        "element_name": f"{from_name} → {to_name}",
                        "element_type": "relationship",
                        "location": f"关系 {rel_id}",
                        "description": f"【用例图·可追溯性】关系「{from_name} - {to_name}」在当前需求抽取结果中未提及，可能为冗余关系。（基于需求抽取结果；若项目中实际有需求，可忽略）",
                        "severity": 0.4,
                        "suggestion": "确认该关系是否确实需要，或从需求中补充对应关系"
                    })
        
        return {
            "score": score,
            "redundant_count": redundant_count,
            "total_relationships": total_relationships,
            "redundant_relationships": list(redundant_relationships),
            "expected_relationships": list(expected_relationship_triples),
            "issues": self.get_issues(),
            "summary": {
                "diagram_relationships": len(diagram_relationships),
                "expected_relationships": len(expected_relationship_triples),
                "redundancy_rate": redundant_count / total_relationships if total_relationships > 0 else 0.0,
                "note": f"发现{redundant_count}个冗余关系（需求中未提及）"
            }
        }

    def diagram_identifier_uniqueness(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """
        标识唯一性
        
        用例图中出现相同用例名称或参与者名称的占比。
        measurement: 1 - no. of elements with consistent names / total no. of elements
        评估方式: 自动化规则检查
        
        Args:
            diagram: 用例图数据
            
        Returns:
            Dict[str, Any]: 标识唯一性评估结果
        """
        self._clear_issues()
        
        actors = diagram.get("actors", [])
        use_cases = diagram.get("use_cases", [])
        
        all_elements = []
        for actor in actors:
            actor_copy = actor.copy()
            actor_copy["element_type"] = "actor"
            all_elements.append(actor_copy)
        
        for uc in use_cases:
            uc_copy = uc.copy()
            uc_copy["element_type"] = "use_case"
            all_elements.append(uc_copy)
        
        total_elements = len(all_elements)
        
        if total_elements == 0:
            return {
                "score": 1.0,
                "duplicate_count": 0,
                "total_elements": 0,
                "issues": [],
                "note": "没有需要评估的元素"
            }
        
        name_count = {}
        duplicate_names = set()
        
        for element in all_elements:
            element_name = element.get("name", "")
            element_type = element.get("element_type", "")
            
            if not element_name:
                continue
            
            normalized_name = self._normalize_identifier(element_name)
            
            if normalized_name:
                key = f"{element_type}::{normalized_name}"
                if key in name_count:
                    name_count[key] += 1
                    duplicate_names.add(normalized_name)
                else:
                    name_count[key] = 1
        
        elements_with_duplicates = 0
        for count in name_count.values():
            if count > 1:
                elements_with_duplicates += count
        
        duplicate_ratio = elements_with_duplicates / total_elements if total_elements > 0 else 0.0
        score = 1.0 - duplicate_ratio
        
        for element in all_elements:
            element_id = element.get("id", "")
            element_name = element.get("name", "")
            element_type = element.get("element_type", "")
            
            if not element_name:
                continue
            
            normalized_name = self._normalize_identifier(element_name)
            key = f"{element_type}::{normalized_name}"
            
            if name_count.get(key, 0) > 1:
                self._add_issue({
                    "issue_type": "duplicate_name",
                    "element_id": element_id,
                    "element_name": element_name,
                    "element_type": element_type,
                    "location": f"{element_type} {element_id}",
                    "description": f"{element_type}名称'{element_name}'与其他{name_count[key]-1}个元素重复",
                    "severity": 0.7,
                    "suggestion": "为每个元素使用唯一的名称，或添加限定词以区分"
                })
        
        return {
            "score": score,
            "duplicate_count": sum(1 for count in name_count.values() if count > 1),
            "elements_with_duplicates": elements_with_duplicates,
            "total_elements": total_elements,
            "duplicate_names": list(duplicate_names),
            "name_statistics": name_count,
            "issues": self.get_issues(),
            "summary": {
                "total_names": len(name_count),
                "duplicate_names_count": len(duplicate_names),
                "duplicate_ratio": duplicate_ratio,
                "note": f"发现{len(duplicate_names)}个重复的名称，涉及{elements_with_duplicates}个元素"
            }
        }

    # ==================== 用例描述评估指标 ====================

    def _desc_collect_all_steps(self, description: Dict[str, Any]) -> List[str]:
        """收集用例描述中所有步骤文本（主流程 + 备选流程）。"""
        steps = []
        for s in description.get("main_flow") or []:
            if isinstance(s, str) and s.strip():
                steps.append(s.strip())
        for alt in description.get("alternative_flows") or []:
            if isinstance(alt, dict):
                for s in alt.get("steps") or []:
                    if isinstance(s, str) and s.strip():
                        steps.append(s.strip())
            elif isinstance(alt, str):
                steps.append(alt.strip())
        return steps

    def _desc_collect_steps_with_location(self, description: Dict[str, Any]) -> List[Tuple[str, str]]:
        """收集用例描述中所有步骤及其精確位置，返回 [(step_text, location), ...]。"""
        out: List[Tuple[str, str]] = []
        for i, s in enumerate(description.get("main_flow") or []):
            if isinstance(s, str) and s.strip():
                out.append((s.strip(), f"主流程步骤{i + 1}"))
        for alt in description.get("alternative_flows") or []:
            if isinstance(alt, dict):
                alt_name = alt.get("name", "未命名")
                for i, s in enumerate(alt.get("steps") or []):
                    if isinstance(s, str) and s.strip():
                        out.append((s.strip(), f"备选流{alt_name}步骤{i + 1}"))
            elif isinstance(alt, str) and alt.strip():
                out.append((alt.strip(), "备选流步骤1"))
        return out

    def _desc_collect_expressions_with_location(self, description: Dict[str, Any]) -> List[Tuple[str, str]]:
        """收集用例描述中所有表述及其位置（主流程、备选流、前置、后置），用于精確定位。"""
        out: List[Tuple[str, str]] = []
        for i, s in enumerate(description.get("main_flow") or []):
            if isinstance(s, str) and s.strip():
                out.append((s.strip(), f"主流程步骤{i + 1}"))
        for alt in description.get("alternative_flows") or []:
            if isinstance(alt, dict):
                alt_name = alt.get("name", "未命名")
                for i, s in enumerate(alt.get("steps") or []):
                    if isinstance(s, str) and s.strip():
                        out.append((s.strip(), f"备选流{alt_name}步骤{i + 1}"))
        for i, p in enumerate(description.get("preconditions") or []):
            if isinstance(p, str) and p.strip():
                out.append((p.strip(), f"前置条件" if len(description.get("preconditions") or []) <= 1 else f"前置条件第{i + 1}项"))
        for i, p in enumerate(description.get("postconditions") or []):
            if isinstance(p, str) and p.strip():
                out.append((p.strip(), f"后置条件" if len(description.get("postconditions") or []) <= 1 else f"后置条件第{i + 1}项"))
        return out

    def _desc_check_step_numbering(self, steps: List[str]) -> Tuple[int, int, List[str]]:
        """
        检查步骤编号是否连续递增。返回 (合规数, 总数, 问题列表)。
        支持格式：1. 2. 3. / 1) 2) / 1、2、3 / 2a. 3a.
        """
        if not steps:
            return 0, 0, []
        issues = []
        valid = 0
        for i, s in enumerate(steps):
            stripped = re.sub(r"^\s*\d+[.)、]\s*", "", s)
            stripped = re.sub(r"^\s*\d+[a-zA-Z][.)、]?\s*", "", stripped)
            if not stripped:
                issues.append(f"步骤仅含编号无内容: {s[:50]}")
                continue
            if len(stripped) > 200:
                issues.append(f"步骤过长(>{200}字): {stripped[:30]}...")
            valid += 1
        return valid, len(steps), issues

    def _validate_return_to_step(self, return_to_step: Any, main_flow_len: int, alt_name: str = "") -> Tuple[bool, Optional[str]]:
        """
        校验异常/备选流字段 return_to_step。
        合法值：整数 1..main_flow_len（返回主事件流对应步骤），或 "end"（流程终止不返回）。
        返回 (是否合法, 不合法时的说明文案)。
        """
        if main_flow_len <= 0:
            return True, None
        if return_to_step is None:
            return False, f"备选流「{alt_name}」缺少 return_to_step 字段，应标明返回主事件流哪一步（1~{main_flow_len}）或 end 表示流程终止"
        if isinstance(return_to_step, str):
            s = return_to_step.strip().lower()
            if s in ("end", "exit", "终止", "结束"):
                return True, None
            try:
                n = int(s)
                if 1 <= n <= main_flow_len:
                    return True, None
                return False, f"备选流「{alt_name}」的 return_to_step={return_to_step} 超出主事件流步数范围（1~{main_flow_len}）"
            except ValueError:
                return False, f"备选流「{alt_name}」的 return_to_step 应为数字（1~{main_flow_len}）或 end，当前为: {return_to_step}"
        if isinstance(return_to_step, int):
            if 1 <= return_to_step <= main_flow_len:
                return True, None
            return False, f"备选流「{alt_name}」的 return_to_step={return_to_step} 超出主事件流步数范围（1~{main_flow_len}）"
        return False, f"备选流「{alt_name}」的 return_to_step 类型无效，应为数字或 end"

    def description_use_case_coverage(
        self, diagram: Dict[str, Any], descriptions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        用例覆盖完整性：用例图中的每个用例都应有对应用例描述。
        归入语法正确性检查点。
        """
        self._clear_issues()
        use_cases = diagram.get("use_cases") or []
        if not use_cases:
            return {"score": 1.0, "issues": [], "missing": []}
        desc_by_id = {str(d.get("id", "")).strip(): d for d in descriptions if d.get("id")}
        desc_by_name = {str(d.get("name", "")).strip(): d for d in descriptions if d.get("name")}
        missing = []
        for uc in use_cases:
            uc_id = str(uc.get("id", "")).strip()
            uc_name = str(uc.get("name", "")).strip()
            if uc_id in desc_by_id or uc_name in desc_by_name:
                continue
            missing.append({"id": uc_id, "name": uc_name})
        for m in missing:
            self._add_issue({
                "issue_type": "missing_description",
                "description": f"【用例描述·语法正确性】用例图中的用例「{m.get('name', m.get('id', '?'))}」缺少对应用例描述，每个用例都应有用例描述",
                "severity": 0.6,
            })
        covered = len(use_cases) - len(missing)
        score = covered / len(use_cases) if use_cases else 1.0
        return {"score": score, "issues": self.get_issues(), "missing": missing}

    def description_syntax_correctness(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """
        语法正确性（用例描述）
        measurement: no. of steps following template numbering / total steps
        规则：步骤编号连续、必填字段完整、主流程唯一、步骤结构基本合规；每个用例都应有用例描述（由 coverage 检查）。
        """
        self._clear_issues()
        issues = []
        name = description.get("name") or description.get("id") or "未命名"
        main_flow = description.get("main_flow") or []
        if not main_flow:
            issues.append(f"【用例描述·正确性】用例「{name}」缺少主事件流 main_flow")
        total_steps = len(main_flow) + sum(
            len(alt.get("steps") or []) for alt in (description.get("alternative_flows") or []) if isinstance(alt, dict)
        )
        if total_steps == 0:
            score = 0.0
        else:
            steps = self._desc_collect_all_steps(description)
            valid, total, num_issues = self._desc_check_step_numbering(steps)
            issues.extend(num_issues)
            score = valid / total if total > 0 else 0.0
        main_flow_len = len(main_flow)
        for alt in description.get("alternative_flows") or []:
            if not isinstance(alt, dict):
                continue
            alt_name = alt.get("name", "未命名备选流")
            # 检查 from_step：异常流从主流程哪一步分支（表6-1 扩展流：扩展位置标识是否稳定）
            from_step = alt.get("from_step")
            if from_step is not None and main_flow_len > 0:
                try:
                    fs = int(from_step) if not isinstance(from_step, int) else from_step
                    if fs < 1 or fs > main_flow_len:
                        issues.append(f"备选流「{alt_name}」的 from_step={from_step} 超出主流程步数范围（1~{main_flow_len}）")
                except (ValueError, TypeError):
                    issues.append(f"备选流「{alt_name}」的 from_step 应为数字（1~{main_flow_len}）")
            rt = alt.get("return_to_step")
            ok, msg = self._validate_return_to_step(rt, main_flow_len, alt_name)
            if not ok and msg:
                issues.append(msg)
        for iss in issues:
            if not isinstance(iss, str) or not iss.startswith("【"):
                iss = f"【用例描述·正确性】用例「{name}」{iss}"
            self._add_issue({"issue_type": "description_syntax", "description": iss, "severity": 0.5})
        return {"score": min(1.0, score), "issues": self.get_issues()}

    def description_semantic_correctness(self, description: Dict[str, Any],
                                         requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        语义正确性（用例描述）
        measurement: no. of steps representing executable behavior / total steps
        评估方式: 基于LLM的写作规范检查；未启用LLM时使用规则回退。
        """
        self._clear_issues()
        if self.use_real_llm and self.llm_evaluator:
            try:
                self._ensure_description_batch(description)
                batch_res = self._batch_description_cache.get(id(description), {})
                if batch_res and "semantic_correctness" in batch_res:
                    b = batch_res.get("semantic_correctness") or {}
                    evals = b.get("evaluations", []) or []
                    score = float(b.get("score", 0.5))
                    issues = []
                    for e in evals:
                        if isinstance(e, dict) and not e.get("is_executable", True):
                            issues.append(e)
                    res = {"score": score, "issues": issues}
                else:
                    res = self.llm_evaluator.evaluate_description_semantic_correctness(description, requirements)
                name = description.get("name") or description.get("id") or "未命名"
                steps_with_loc = self._desc_collect_steps_with_location(description)
                text_to_loc = {re.sub(r"^\s*\d+[.)、a-zA-Z]*\s*", "", t).strip(): loc for t, loc in steps_with_loc}
                for e in res.get("issues", []):
                    if not isinstance(e, dict) or e.get("is_executable", True):
                        continue
                    step_text = (e.get("step_text", "") or "").strip()
                    step_text_norm = re.sub(r"^\s*\d+[.)、a-zA-Z]*\s*", "", step_text).strip()
                    reason = e.get("reason", str(e))
                    loc = text_to_loc.get(step_text_norm) or text_to_loc.get(step_text) or next((loc for t, loc in steps_with_loc if step_text_norm in t or t in step_text_norm), None) or e.get("step_location") or f"步骤{e.get('step_index', '?')}"
                    snippet = f"「{step_text[:40]}…」" if step_text else ""
                    self._add_issue({
                        "issue_type": "description_semantic",
                        "description": f"【用例描述·正确性】用例「{name}」{loc}{snippet}：{reason}",
                        "severity": 0.4
                    })
                return {"score": res.get("score", 0.5), "issues": self.get_issues()}
            except Exception as e:
                raise RuntimeError("LLM用例描述语义正确性评估失败，请检查API配置") from e
        steps_with_loc = self._desc_collect_steps_with_location(description)
        if not steps_with_loc:
            return {"score": 0.0, "issues": self.get_issues()}
        name = description.get("name") or description.get("id") or "未命名"
        non_executable = []
        for s, loc in steps_with_loc:
            t = re.sub(r"^\s*\d+[.)、a-zA-Z]*\s*", "", s).strip()
            if "处理" in t and len(t) <= 6:
                non_executable.append((t, loc))
        valid = len(steps_with_loc) - len(non_executable)
        score = valid / len(steps_with_loc) if steps_with_loc else 0.0
        for t, loc in non_executable:
            self._add_issue({"issue_type": "description_semantic", "description": f"【用例描述·正确性】用例「{name}」{loc}「{t}」可能不可执行或过模糊", "severity": 0.4})
        return {"score": score, "issues": self.get_issues()}

    def description_expression_unambiguity(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """
        表达无歧义性
        measurement: no. of unambiguous expressions / total no. of expressions
        评估方式: 基于LLM的细粒度歧义检测；未启用LLM时使用规则回退。
        """
        self._clear_issues()
        if self.use_real_llm and self.llm_evaluator:
            try:
                self._ensure_description_batch(description)
                batch_res = self._batch_description_cache.get(id(description), {})
                if batch_res and "expression_unambiguity" in batch_res:
                    b = batch_res.get("expression_unambiguity") or {}
                    evals = b.get("evaluations", []) or []
                    score = float(b.get("score", 0.5))
                    issues = []
                    for e in evals:
                        if not isinstance(e, dict):
                            continue
                        is_amb = e.get("is_ambiguous", False)
                        is_unamb = e.get("is_unambiguous", True)
                        if is_amb or (not is_unamb):
                            issues.append(e)
                    res = {"score": score, "issues": issues}
                else:
                    res = self.llm_evaluator.evaluate_description_expression_unambiguity(description)
                name = description.get("name") or description.get("id") or "未命名"
                exprs_with_loc = self._desc_collect_expressions_with_location(description)
                expr_to_loc = {re.sub(r"^\s*\d+[.)、a-zA-Z]*\s*", "", t).strip(): loc for t, loc in exprs_with_loc}
                for e in res.get("issues", []):
                    if not isinstance(e, dict):
                        continue
                    is_amb = e.get("is_ambiguous", False)
                    is_unamb = e.get("is_unambiguous", True)
                    if not is_amb and is_unamb:
                        continue
                    expr = (e.get("expression", "") or e.get("step_text", "") or "").strip()
                    expr_norm = re.sub(r"^\s*\d+[.)、a-zA-Z]*\s*", "", expr).strip()
                    reasons = e.get("ambiguity_reasons", [])
                    reason_str = "；".join(str(r) for r in reasons) if isinstance(reasons, list) and reasons else "存在歧义"
                    loc = expr_to_loc.get(expr_norm) or expr_to_loc.get(expr) or next((loc for t, loc in exprs_with_loc if expr_norm in t or t in expr_norm), None) or "某表述"
                    snippet = f"「{expr[:40]}…」" if expr else ""
                    self._add_issue({
                        "issue_type": "ambiguity",
                        "description": f"【用例描述·明确性】用例「{name}」{loc}{snippet}：{reason_str}。",
                        "severity": 0.4
                    })
                return {"score": res.get("score", 0.5), "issues": self.get_issues()}
            except Exception as e:
                raise RuntimeError("LLM用例描述表达无歧义性评估失败，请检查API配置") from e
        exprs_with_loc = self._desc_collect_expressions_with_location(description)
        if not exprs_with_loc:
            return {"score": 1.0, "issues": self.get_issues()}
        name = description.get("name") or description.get("id") or "未命名"
        vague = ["快速", "大量", "友好", "高效", "及时", "简单", "方便", "灵活", "quick", "fast", "many", "friendly", "efficient", "timely", "easy", "convenient", "flexible"]
        ambiguous = 0
        for expr, loc in exprs_with_loc:
            for v in vague:
                if v in expr:
                    ambiguous += 1
                    self._add_issue({"issue_type": "ambiguity", "description": f"【用例描述·明确性】用例「{name}」{loc}「{expr[:40]}…」含模糊词「{v}」", "severity": 0.4})
                    break
        score = 1.0 - (ambiguous / len(exprs_with_loc)) if exprs_with_loc else 1.0
        return {"score": max(0.0, score), "issues": self.get_issues()}

    def description_terminology_consistency(self, descriptions: List[Dict[str, Any]],
                                           requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        术语一致性（用例描述）
        不再对描述正文做碎片化「术语表」匹配（误报率高）；保留占位，默认从宽。
        """
        self._clear_issues()
        if not descriptions:
            return {"score": 1.0, "issues": []}
        return {
            "score": 1.0,
            "issues": [],
            "note": "用例描述术语一致性暂不进行词表机械检查，避免与需求全文粒度不一致导致误报",
        }

    def description_internal_logical_consistency(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """
        内部逻辑一致性
        measurement: no. of steps without logical conflict / total no. of steps
        评估方式: 基于LLM的跨部分逻辑推理；未启用LLM时使用规则回退。
        """
        self._clear_issues()
        if self.use_real_llm and self.llm_evaluator:
            try:
                self._ensure_description_batch(description)
                batch_res = self._batch_description_cache.get(id(description), {})
                if batch_res and "internal_logical_consistency" in batch_res:
                    b = batch_res.get("internal_logical_consistency") or {}
                    conflicts = b.get("conflicts", []) or []
                    score = float(b.get("score", 1.0))
                    issues = [{"description": c if isinstance(c, str) else c.get("description", str(c))} for c in conflicts]
                    res = {"score": score, "issues": issues}
                else:
                    res = self.llm_evaluator.evaluate_description_internal_logical_consistency(description)
                for e in res.get("issues", []):
                    self._add_issue({"issue_type": "logical_consistency", "description": f"【用例描述·一致性】{e.get('description', str(e))}", "severity": 0.6})
                return {"score": res.get("score", 1.0), "issues": self.get_issues()}
            except Exception as e:
                raise RuntimeError("LLM用例描述内部逻辑一致性评估失败，请检查API配置") from e
        pre = " ".join(p for p in (description.get("preconditions") or []) if isinstance(p, str))
        post = " ".join(p for p in (description.get("postconditions") or []) if isinstance(p, str))
        issues = []
        pre_l = pre.lower()
        post_l = post.lower()
        name_l = (description.get("name", "") or "").lower()
        if ("已登录" in pre and "未登录" in post) or ("logged in" in pre_l and "not logged in" in post_l):
            issues.append("前置条件含「已登录」而后置条件含「未登录」，可能矛盾")
        if (("未登录" in pre and "已登录" in post and "登录" not in description.get("name", "")) or
            ("not logged in" in pre_l and "logged in" in post_l and "login" not in name_l)):
            issues.append("前置与后置登录状态可能矛盾")
        for iss in issues:
            self._add_issue({"issue_type": "logical_consistency", "description": f"【用例描述·一致性】{iss}", "severity": 0.6})
        return {"score": 0.0 if issues else 1.0, "issues": self.get_issues()}

    def description_main_flow_completeness(self, description: Dict[str, Any],
                                           requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        主事件流完整性（含表6-1/续表6-1：基本流检查项）
        - 是否有主事件流、步数是否过少；
        - 步骤数量是否过多（教材：是否步骤数量过多）；
        - 用例名称是否简单明了、是否像动宾词组（教材：用例名称是否动词词组）。
        """
        self._clear_issues()
        name = description.get("name") or description.get("id") or "未命名"
        main_flow = description.get("main_flow") or []
        if not main_flow:
            self._add_issue({"issue_type": "completeness", "description": f"【用例描述·完整性】用例「{name}」缺少主事件流", "severity": 0.8})
            return {"score": 0.0, "issues": self.get_issues()}
        expected = 2
        score = min(1.0, len(main_flow) / expected) if expected else 1.0
        if score < 1.0 and not self.get_issues():
            self._add_issue({"issue_type": "completeness", "description": f"【用例描述·完整性】用例「{name}」主事件流步数偏少（当前{len(main_flow)}步，建议至少{expected}步）", "severity": 0.5})
        if len(main_flow) > 15:
            self._add_issue({"issue_type": "completeness", "description": f"【用例描述·完整性】用例「{name}」基本流步骤数量过多（{len(main_flow)}步），建议简化或拆分子用例（表6-1 基本流检查项）", "severity": 0.4})
        name_str = (description.get("name") or "").strip()
        if name_str and len(name_str) >= 2:
            verb_indicators = ["登录", "注册", "浏览", "查看", "搜索", "创建", "删除", "提交", "发布", "申请", "支付", "退款", "开通", "上传", "下载", "管理", "配置", "审核", "验证", "打开", "输入", "点击", "重定向",
                              "login", "register", "browse", "view", "search", "create", "delete", "submit", "publish", "request", "pay", "refund", "enable", "upload", "download", "manage", "configure", "review", "verify", "open", "input", "click", "redirect"]
            if not any(v in name_str for v in verb_indicators) and len(name_str) < 3:
                self._add_issue({"issue_type": "clarity", "description": f"【用例描述·明确性】用例名称「{name_str}」建议使用动宾词组、简单明了（表6-1 用例名称检查项）", "severity": 0.3})
        return {"score": score, "issues": self.get_issues()}

    def description_alternative_flow_completeness(self, description: Dict[str, Any],
                                                 requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        备选流程/异常流程完整性
        measurement: no. of described alternative or exception steps / total expected；
        标准模板要求每条异常/备选流具备 return_to_step 字段，标明返回主事件流哪一步或 end 表示流程终止。
        """
        self._clear_issues()
        alts = description.get("alternative_flows") or []
        name = description.get("name") or description.get("id") or "未命名"
        main_flow = description.get("main_flow") or []
        main_flow_len = len(main_flow)
        if not alts:
            self._add_issue({"issue_type": "completeness", "description": f"【用例描述·完整性】用例「{name}」未描述备选流或异常流，建议补充 alternative_flows", "severity": 0.4})
            return {"score": 0.5, "issues": self.get_issues()}
        alts_with_return = 0
        for a in alts:
            if not isinstance(a, dict):
                continue
            alt_name = a.get("name", "未命名备选流")
            rt = a.get("return_to_step")
            if rt is None:
                self._add_issue({"issue_type": "completeness", "description": f"【用例描述·完整性】用例「{name}」备选流「{alt_name}」缺少 return_to_step 字段，应标明返回主事件流哪一步（1~{main_flow_len}）或 end 表示流程终止", "severity": 0.4})
            else:
                ok, msg = self._validate_return_to_step(rt, main_flow_len, alt_name)
                if ok:
                    alts_with_return += 1
                elif msg:
                    self._add_issue({"issue_type": "completeness", "description": f"【用例描述·完整性】{msg}", "severity": 0.4})
        total_steps = sum(len(a.get("steps") or []) for a in alts if isinstance(a, dict))
        step_score = min(1.0, 0.3 + 0.7 * (total_steps / 2)) if total_steps else 0.5
        return_score = (alts_with_return / len(alts)) if alts else 1.0
        score = (step_score + return_score) / 2.0
        if score < 1.0 and not self.get_issues():
            self._add_issue({"issue_type": "completeness", "description": f"【用例描述·完整性】用例「{name}」备选流步数较少，建议补充异常或分支步骤", "severity": 0.3})
        return {"score": score, "issues": self.get_issues()}

    def description_pre_post_condition_completeness(self, descriptions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        前置、后置条件完整性（含表6-1：简述是否编写）
        measurement: 具备前置/后置的用例占比；建议编写用例简述。
        """
        self._clear_issues()
        if not descriptions:
            return {"score": 1.0, "issues": []}
        ok = 0
        for d in descriptions:
            pre = d.get("preconditions") or []
            post = d.get("postconditions") or []
            has_pre = bool(pre and any(isinstance(p, str) and p.strip() for p in pre))
            has_post = bool(post and any(isinstance(p, str) and p.strip() for p in post))
            if has_pre and has_post:
                ok += 1
            else:
                name = d.get("name") or d.get("id") or "未命名"
                if not has_pre:
                    self._add_issue({"issue_type": "completeness", "description": f"【用例描述·完整性】用例「{name}」缺少前置条件", "severity": 0.4})
                if not has_post:
                    self._add_issue({"issue_type": "completeness", "description": f"【用例描述·完整性】用例「{name}」缺少后置条件", "severity": 0.4})
            brief = (d.get("description") or d.get("brief_description") or "").strip()
            if not brief:
                name = d.get("name") or d.get("id") or "未命名"
                self._add_issue({"issue_type": "completeness", "description": f"【用例描述·完整性】用例「{name}」未编写简述，建议补充 description 或 brief_description（表6-1 简述检查项）", "severity": 0.3})
        score = ok / len(descriptions) if descriptions else 1.0
        return {"score": score, "issues": self.get_issues()}

    def description_step_verifiability(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """
        步骤可测试性
        measurement: no. of verifiable steps / total steps
        评估方式: 基于LLM的测试可派生性评估；未启用LLM时使用规则回退。
        """
        self._clear_issues()
        if self.use_real_llm and self.llm_evaluator:
            try:
                res = self.llm_evaluator.evaluate_description_step_verifiability(description)
                name = description.get("name") or description.get("id") or "未命名"
                steps_with_loc = self._desc_collect_steps_with_location(description)
                text_to_loc = {re.sub(r"^\s*\d+[.)、a-zA-Z]*\s*", "", t).strip(): loc for t, loc in steps_with_loc}
                for e in res.get("issues", []):
                    if isinstance(e, dict) and not e.get("is_verifiable", True):
                        step_text = (e.get("step_text", "") or "").strip()
                        step_norm = re.sub(r"^\s*\d+[.)、a-zA-Z]*\s*", "", step_text).strip()
                        loc = text_to_loc.get(step_norm) or text_to_loc.get(step_text) or next((loc for t, loc in steps_with_loc if step_norm in t or t in step_norm), None) or "某步骤"
                        reason = e.get("reason", "")
                        self._add_issue({"issue_type": "verifiability", "description": f"【用例描述·可验证性】用例「{name}」{loc}「{step_text[:40]}…」{reason}", "severity": 0.4})
                return {"score": res.get("score", 0.5), "issues": self.get_issues()}
            except Exception as e:
                raise RuntimeError("LLM用例描述步骤可测试性评估失败，请检查API配置") from e
        steps_with_loc = self._desc_collect_steps_with_location(description)
        if not steps_with_loc:
            return {"score": 0.0, "issues": self.get_issues()}
        name = description.get("name") or description.get("id") or "未命名"
        unverifiable = ["快速", "友好", "大量", "高效", "及时", "简单", "方便", "灵活", "较好", "尽量"]
        verifiable = sum(1 for s, _ in steps_with_loc if not any(u in s for u in unverifiable))
        for s, loc in steps_with_loc:
            if any(u in s for u in unverifiable):
                self._add_issue({"issue_type": "verifiability", "description": f"【用例描述·可验证性】用例「{name}」{loc}「{s[:40]}…」含主观/模糊词难以测试", "severity": 0.4})
        return {"score": verifiable / len(steps_with_loc) if steps_with_loc else 0.0, "issues": self.get_issues()}

    def description_structure_clarity(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """
        结构清晰性
        measurement: no. of steps easy to read (short and clear) / total no. of steps
        规则：句长阈值（单步不超过 80 字为清晰）。
        """
        self._clear_issues()
        steps_with_loc = self._desc_collect_steps_with_location(description)
        if not steps_with_loc:
            return {"score": 1.0, "issues": []}
        max_len = 80
        long_steps = [(s, loc) for s, loc in steps_with_loc if len(s) > max_len]
        clear = len(steps_with_loc) - len(long_steps)
        score = clear / len(steps_with_loc) if steps_with_loc else 1.0
        name = description.get("name") or description.get("id") or "未命名"
        for s, loc in long_steps[:5]:
            self._add_issue({"issue_type": "structure", "description": f"【用例描述·可修改性】用例「{name}」{loc}「{s[:40]}…」过长（>{max_len}字），建议拆分", "severity": 0.3})
        if score < 1.0 and not self.get_issues():
            self._add_issue({"issue_type": "structure", "description": f"【用例描述·可修改性】用例「{name}」有{len(long_steps)}个步骤超过{max_len}字，建议拆分或精简", "severity": 0.3})
        return {"score": score, "issues": self.get_issues()}

    def description_content_redundancy(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """
        内容冗余度
        measurement: 1 - (no. of redundant steps / total no. of steps)
        规则：完全相同的步骤文本计为冗余。
        """
        self._clear_issues()
        steps_with_loc = self._desc_collect_steps_with_location(description)
        if not steps_with_loc:
            return {"score": 1.0, "issues": []}
        name = description.get("name") or description.get("id") or "未命名"
        seen: Dict[str, str] = {}  # text -> first location
        redundant = 0
        for s, loc in steps_with_loc:
            n = s.strip()
            if n in seen:
                redundant += 1
                self._add_issue({"issue_type": "redundancy", "description": f"【用例描述·可修改性】用例「{name}」{loc}「{n[:40]}…」与{seen[n]}重复", "severity": 0.3})
            else:
                seen[n] = loc
        score = 1.0 - (redundant / len(steps_with_loc)) if steps_with_loc else 1.0
        if score < 1.0 and not self.get_issues():
            self._add_issue({"issue_type": "redundancy", "description": f"【用例描述·可修改性】用例「{name}」存在{redundant}处重复步骤", "severity": 0.3})
        return {"score": max(0.0, score), "issues": self.get_issues()}

    def description_functional_cohesion(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """
        功能内聚性
        measurement: no. of use case descriptions without cross-use-case functionality / total no. of use cases
        评估方式: 基于LLM的目标专注度分析；未启用LLM时使用规则回退。
        """
        self._clear_issues()
        if self.use_real_llm and self.llm_evaluator:
            try:
                self._ensure_description_batch(description)
                batch_res = self._batch_description_cache.get(id(description), {})
                if batch_res and "functional_cohesion" in batch_res:
                    b = batch_res.get("functional_cohesion") or {}
                    cross = b.get("cross_functionality", []) or []
                    score = float(b.get("score", 0.5))
                    issues = [{"description": x if isinstance(x, str) else x.get("description", str(x))} for x in cross]
                    res = {"score": score, "issues": issues}
                else:
                    res = self.llm_evaluator.evaluate_description_functional_cohesion(description)
                for e in res.get("issues", []):
                    self._add_issue({"issue_type": "cohesion", "description": f"【用例描述·可修改性】{e.get('description', str(e))}", "severity": 0.5})
                return {"score": res.get("score", 0.5), "issues": self.get_issues()}
            except Exception as e:
                raise RuntimeError("LLM用例描述功能内聚性评估失败，请检查API配置") from e
        name = (description.get("name") or "").strip()
        steps = self._desc_collect_all_steps(description)
        text = " ".join(steps)
        cross_keywords = [("登录", "订单"), ("注册", "支付"), ("管理用户", "查询订单"), ("login", "order"), ("register", "payment"), ("user management", "order query")]
        for a, b in cross_keywords:
            if a in text and b in text and (a not in name and b not in name):
                self._add_issue({"issue_type": "cohesion", "description": f"【用例描述·可修改性】描述中可能混杂不同功能「{a}」与「{b}」", "severity": 0.5})
                return {"score": 0.5, "issues": self.get_issues()}
        return {"score": 1.0, "issues": []}

    def description_information_relevance(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """
        信息相关性
        measurement: 1 - (no. of irrelevant descriptions / total no. of descriptions)
        评估方式: 基于LLM的相关性过滤；未启用LLM时使用规则回退。
        """
        self._clear_issues()
        if self.use_real_llm and self.llm_evaluator:
            try:
                self._ensure_description_batch(description)
                batch_res = self._batch_description_cache.get(id(description), {})
                if batch_res and "information_relevance" in batch_res:
                    b = batch_res.get("information_relevance") or {}
                    evals = b.get("evaluations", []) or []
                    score = float(b.get("score", 0.5))
                    issues = []
                    for e in evals:
                        if isinstance(e, dict) and not e.get("is_relevant", True):
                            issues.append(e)
                    res = {"score": score, "issues": issues}
                else:
                    res = self.llm_evaluator.evaluate_description_information_relevance(description)
                name = description.get("name") or description.get("id") or "未命名"
                exprs_with_loc = self._desc_collect_expressions_with_location(description)
                text_to_loc = {re.sub(r"^\s*\d+[.)、a-zA-Z]*\s*", "", t).strip(): loc for t, loc in exprs_with_loc}
                for e in res.get("issues", []):
                    if isinstance(e, dict) and not e.get("is_relevant", True):
                        frag = (e.get("fragment", "") or "").strip()
                        frag_norm = re.sub(r"^\s*\d+[.)、a-zA-Z]*\s*", "", frag).strip()
                        loc = e.get("step_location") or text_to_loc.get(frag_norm) or text_to_loc.get(frag) or next((loc for t, loc in exprs_with_loc if frag_norm in t or t in frag_norm), None) or "某表述"
                        self._add_issue({"issue_type": "relevance", "description": f"【用例描述·可追溯性】用例「{name}」{loc}「{frag[:40]}…」与需求无关或弱相关", "severity": 0.3})
                return {"score": res.get("score", 0.5), "issues": self.get_issues()}
            except Exception as e:
                raise RuntimeError("LLM用例描述信息相关性评估失败，请检查API配置") from e
        name = (description.get("name") or "").strip()
        steps = self._desc_collect_all_steps(description)
        if not name or not steps:
            return {"score": 1.0, "issues": []}
        name_words = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}", name.lower()))
        irrelevant = sum(1 for s in steps if name_words and not (name_words & set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}", s.lower()))))
        total = len(steps)
        score = 1.0 - (irrelevant / total) if total else 1.0
        return {"score": max(0.0, score), "issues": []}

    def description_identifier_uniqueness(self, descriptions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        标识唯一性（用例描述）
        measurement: no. of use cases with unique ID / total no. of use cases
        """
        self._clear_issues()
        if not descriptions:
            return {"score": 1.0, "issues": []}
        id_counts = {}
        for d in descriptions:
            uid = d.get("id")
            if uid is not None and str(uid).strip():
                k = str(uid).strip()
                id_counts[k] = id_counts.get(k, 0) + 1
            else:
                self._add_issue({"issue_type": "identifier", "description": f"【用例描述·可追溯性】用例「{d.get('name','')}」缺少 id", "severity": 0.5})
        with_unique_id = sum(1 for d in descriptions if d.get("id") and id_counts.get(str(d.get("id")).strip(), 0) == 1)
        total = len(descriptions)
        if sum(id_counts.values()) > len(id_counts):
            self._add_issue({"issue_type": "identifier", "description": f"【用例描述·可追溯性】存在重复的用例 id", "severity": 0.6})
        score = with_unique_id / total if total else 0.0
        return {"score": score, "issues": self.get_issues()}

    # ==================== 辅助方法 ====================

    def _actor_matches_required_role(
        self,
        actor_name: str,
        role_name: str,
        lang_ctx: Optional[Any] = None,
    ) -> bool:
        if self._weak_match(role_name, actor_name):
            return True
        if lang_ctx and getattr(lang_ctx, "cross_language", False):
            for alt in lang_ctx.equivalent_labels(role_name):
                if self._weak_match(alt, actor_name):
                    return True
            for alt in lang_ctx.equivalent_labels(actor_name):
                if self._weak_match(role_name, alt):
                    return True
        return False

    def _weak_match(self, a, b) -> bool:
        """
        弱语义匹配
        
        Args:
            a: 字符串a
            b: 字符串b
            
        Returns:
            bool: 如果弱语义匹配则返回True
        """
        if not isinstance(a, str) or not isinstance(b, str):
            return False
        return WeakSemanticMatcher.weak_match(a, b)
    
    def _llm_ambiguity_detection(self, elements: List[Dict[str, Any]], 
                           diagram_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        规则回退：元素歧义检测（仅当未启用 LLM 时可供调用）。
        评估方式: 基于LLM的歧义检测；此处为规则回退，正式实现见 llm_evaluator.evaluate_element_ambiguity。
        """
        llm_results = []
        for element in elements:
            element_name = element.get("name", "")
            element_type = element.get("type", "")
            is_clear, reasons = self._rule_based_ambiguity_check(element_name, element_type)
            
            llm_results.append({
                "element_id": element.get("id", ""),
                "element_name": element_name,
                "element_type": element_type,
                "is_clear": is_clear,
                "ambiguity_reasons": reasons,
                "confidence": 0.8
            })
        
        return llm_results

    def _rule_based_ambiguity_check(self, element_name: str, element_type: str) -> Tuple[bool, List[str]]:
        """规则回退：元素名称歧义检查（仅当未启用 LLM 时使用）。"""
        reasons = []
        
        # 检查空名称
        if not element_name or element_name.strip() == "":
            return False, ["名称为空，无法确定其含义"]
        
        if element_type == "use_case":
            if len(element_name) < 4:
                reasons.append("用例名称过短，可能不完整")
        
        vague_terms = {
            "处理": ["处理什么？", "处理数据？处理文件？处理请求？"],
            "操作": ["什么操作？", "操作什么？"],
            "管理": ["管理什么？", "管理用户？管理订单？管理内容？"],
            "查看": ["查看什么？", "查看信息？查看报告？查看状态？"],
            "设置": ["设置什么？", "设置参数？设置权限？设置界面？"],
            "快速": ["多快算快速？", "这是一个主观形容词"],
            "友好": ["什么样的界面算友好？", "这是一个主观形容词"],
            "高效": ["什么样的效率算高效？", "这是一个主观形容词"]
        }
        
        for term, messages in vague_terms.items():
            if term in element_name:
                if element_name == term:
                    reasons.append(f"名称仅为模糊术语'{term}'，含义不明确")
                    break
                elif element_name.startswith(term) or element_name.endswith(term):
                    reasons.append(f"名称包含模糊术语'{term}'，{messages[0]}")
                    break
        
        return len(reasons) == 0, reasons

    def _extract_terms_from_diagram(self, diagram: Dict[str, Any]) -> List[str]:
        """
        从用例图中提取术语（仅限图中实际出现的名称，不包含 description 等注释字段）。
        description 为 JSON 中的说明/测试用文字，不代表用例图上的可见内容。
        """
        terms = set()
        for actor in diagram.get("actors", []):
            name = actor.get("name", "")
            if name and name.strip():
                terms.add(name.strip())
        for use_case in diagram.get("use_cases", []):
            name = use_case.get("name", "")
            if name and name.strip():
                terms.add(name.strip())
        return list(terms)

    def _build_term_table_from_requirements(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        从需求中构建术语表。始终从角色、功能需求正文中抽取用语，与显式 terms 合并，
        保证图中出现的术语只要在需求文档里出现过就能匹配。
        """
        import re
        term_table = {}
        stopwords = {"能够", "应该", "可以", "系统", "用户", "进行", "相关", "以及", "或者", "一种", "这个", "那个"}

        if "terms" in requirements:
            for term_info in requirements.get("terms", []):
                if isinstance(term_info, dict):
                    term = term_info.get("term", "")
                    if term and term.strip():
                        term_table[term.strip()] = term_info

        for role in requirements.get("roles", []):
            if isinstance(role, dict):
                role_name = role.get("name", "")
            else:
                role_name = str(role)
            if role_name and role_name.strip():
                t = role_name.strip()
                if t not in term_table:
                    term_table[t] = {"term": t, "type": "role", "description": f"角色: {t}"}

        for fr in requirements.get("functional_requirements", []):
            if isinstance(fr, dict):
                text = fr.get("text", "")
            else:
                text = str(fr)
            if not text:
                continue
            words = re.findall(r'[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}', text)
            for word in words:
                if word in stopwords or len(word) < 2:
                    continue
                if word not in term_table:
                    term_table[word] = {
                        "term": word,
                        "type": "functional_term",
                        "source": text[:80] + "..." if len(text) > 80 else text,
                    }

        for er in requirements.get("expected_relationships", []):
            if isinstance(er, dict):
                for key in ("role", "function"):
                    val = er.get(key, "")
                    if val and isinstance(val, str) and val.strip():
                        t = val.strip()
                        if t not in term_table:
                            term_table[t] = {"term": t, "type": "relationship_ref", "description": f"预期关系: {t}"}

        return term_table

    def _term_matches_table(self, term: str, term_table: Dict[str, Any]) -> bool:
        """
        检查术语是否匹配术语表
        
        Args:
            term: 要检查的术语
            term_table: 术语表
            
        Returns:
            bool: 如果匹配则返回True
        """
        if term in term_table:
            return True
        
        from .semantic_matcher import WeakSemanticMatcher
        
        for table_term in term_table.keys():
            if WeakSemanticMatcher.weak_match(term, table_term):
                return True
        
        for table_term in term_table.keys():
            if table_term in term or term in table_term:
                return True
        
        return False

    def _rule_based_verifiability_check(self, use_case_name: str, use_case_description: str = "") -> Tuple[bool, List[str]]:
        """
        规则回退：判断用例是否可验证（仅当未启用 LLM 时使用）。
        评估方式: 基于LLM的验收条件推断；此处为自动化规则回退。
        """
        reasons = []
        
        vague_terms = ["处理", "操作", "管理", "查看", "设置", "process", "operation", "manage", "view", "set"]
        for term in vague_terms:
            if use_case_name == term or use_case_name.endswith(term):
                reasons.append(f"用例名称'{use_case_name}'过于模糊，没有指定具体操作对象")
                break
        
        import re
        if not re.search(r'[\u4e00-\u9fff]+\s*[\u4e00-\u9fff]+|[A-Za-z]+(?:[\s_-]+[A-Za-z]+)+', use_case_name):
            reasons.append(f"用例名称可能缺乏明确的动作-对象结构")
        
        subjective_terms = ["快速", "高效", "友好", "方便", "简单", "美观", "quick", "efficient", "friendly", "convenient", "easy", "beautiful"]
        for term in subjective_terms:
            if term in use_case_name or (use_case_description and term in use_case_description):
                reasons.append(f"包含主观形容词'{term}'，难以客观验证")
                break
        
        return len(reasons) == 0, reasons

    def _build_use_case_dependency_graph(self, use_cases: List[Dict[str, Any]], 
                                        relationships: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        构建用例依赖图
        
        Args:
            use_cases: 用例列表
            relationships: 关系列表
            
        Returns:
            Dict[str, List[str]]: 用例ID到其依赖的用例ID列表的映射
        """
        graph = {uc["id"]: [] for uc in use_cases}
        
        for rel in relationships:
            rel_type = rel.get("type", "")
            from_id = rel.get("from", "")
            to_id = rel.get("to", "")
            
            if from_id in graph and to_id in graph:
                if rel_type == "include":
                    graph[from_id].append({
                        "target": to_id,
                        "type": "include",
                        "description": rel.get("description", "")
                    })
                elif rel_type == "extend":
                    graph[from_id].append({
                        "target": to_id,
                        "type": "extend",
                        "description": rel.get("description", "")
                    })
                elif rel_type == "generalization":
                    graph[from_id].append({
                        "target": to_id,
                        "type": "generalization",
                        "description": rel.get("description", "")
                    })
        
        return graph

    def _analyze_use_case_independence(self, use_case_id: str, use_case_name: str,
                                    dependency_graph: Dict[str, List[str]],
                                    use_cases: List[Dict[str, Any]],
                                    relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析用例的独立性
        
        Args:
            use_case_id: 用例ID
            use_case_name: 用例名称
            dependency_graph: 依赖图
            use_cases: 所有用例
            relationships: 所有关系
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        reasons = []
        dependencies = dependency_graph.get(use_case_id, [])
        
        if len(dependencies) > 3:
            reasons.append(f"用例依赖过多其他用例（{len(dependencies)}个），可能缺乏独立性")
        
        include_count = sum(1 for dep in dependencies if dep.get("type") == "include")
        extend_count = sum(1 for dep in dependencies if dep.get("type") == "extend")
        
        if include_count > 2:
            reasons.append(f"用例包含了过多其他用例（{include_count}个），可能承担了过多责任")
        
        compound_indicators = ["和", "与", "及", "以及", "并且", "同时"]
        for indicator in compound_indicators:
            if indicator in use_case_name:
                reasons.append(f"用例名称包含连接词'{indicator}'，可能表示复合功能")
                break
        
        actor_connections = 0
        for rel in relationships:
            if rel.get("type") == "association":
                if rel.get("to") == use_case_id:
                    actor_connections += 1
        
        if actor_connections > 1:
            reasons.append(f"用例被多个参与者（{actor_connections}个）关联，可能需要拆分")
        
        return {
            "is_independent": len(reasons) == 0,
            "reasons": reasons,
            "dependencies": dependencies,
            "dependency_count": len(dependencies),
            "actor_connections": actor_connections
        }

    def _normalize_relationship_triple(self, from_name: str, to_name: str, rel_type: str) -> str:
        """
        规范化关系三元组
        
        Args:
            from_name: 源元素名称
            to_name: 目标元素名称
            rel_type: 关系类型
            
        Returns:
            str: 规范化的关系三元组字符串
        """
        from_name_norm = from_name.strip().lower()
        to_name_norm = to_name.strip().lower()
        rel_type_norm = rel_type.strip().lower()
        
        return f"{from_name_norm}::{rel_type_norm}::{to_name_norm}"

    def _normalize_identifier(self, identifier: str) -> str:
        """
        规范化标识符
        
        规则化处理思路（根据表格）：
        1. 大小写规范化
        2. 去除复数/特殊字符
        3. 完全字符串一致性检查
        
        Args:
            identifier: 原始标识符
            
        Returns:
            str: 规范化后的标识符
        """
        if not identifier:
            return ""
        
        normalized = identifier.lower()
        
        normalized = normalized.strip()
        
        if normalized.endswith("们"):
            normalized = normalized[:-1]
        
        import re
        normalized = re.sub(r'[^\w\u4e00-\u9fff]', '', normalized)
        
        common_modifiers = ["系统", "功能", "模块", "组件", "服务"]
        for modifier in common_modifiers:
            if normalized.endswith(modifier):
                normalized = normalized[:-len(modifier)]
                break
        
        return normalized