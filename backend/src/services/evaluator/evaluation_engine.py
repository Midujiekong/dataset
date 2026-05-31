"""
评估引擎 - 按最新质量特性表组织评估流程
质量特性：一致性与规范性、完整性、必要性（可追溯性）、可修改性
"""
import re
from typing import Any, Dict, List, Optional

from .evaluation_metrics import (
    EvaluationMetrics,
    diagram_id_to_display_labels,
    format_semantic_relationship_issue,
)
from .input_normalizer import is_internal_system_component_role_name


def _desc_fallback_issue(desc: Dict, prefix: str, template: str) -> Dict:
    """为单个用例描述生成带上下文的 fallback issue"""
    name = desc.get("name") or desc.get("id") or "未命名"
    return {"description": f"【{prefix}】用例「{name}」{template}"}


def _diagram_fallback_issue(diagram: Dict, prefix: str, template: str, element_type: str = "用例", **kwargs) -> Dict:
    """为用例图生成带上下文的 fallback issue（引用图中第一个相关元素）"""
    id_to_name = diagram_id_to_display_labels(diagram)
    actor_ids = {a.get("id", "") for a in diagram.get("actors", [])}
    uc_ids = {u.get("id", "") for u in diagram.get("use_cases", [])}
    def _key(v):
        if v is None:
            return ""
        return str(v).strip()

    if element_type == "用例":
        # 仅引用参与 3+ include/extend 的用例（避免误判简单用例如「注册」）
        rel_count = kwargs.get("rel_count") or {}
        candidates = [u for u in diagram.get("use_cases", []) if rel_count.get(_key(u.get("id")), 0) >= 3]
        if not candidates:
            # 无高耦合用例时，不指名具体用例，避免误报
            return {"description": f"【用例图·{prefix}】{template}"}
        c0 = candidates[0]
        name = c0.get("name") or c0.get("id") or "未命名"
        return {"description": f"【用例图·{prefix}】{element_type}「{name}」{template}"}
    elif element_type == "参与者":
        items = diagram.get("actors", [])
        if not items:
            return {"description": f"【用例图·{prefix}】{template}"}
        a0 = items[0]
        name = a0.get("name") or a0.get("id") or "未命名"
        return {"description": f"【用例图·{prefix}】{element_type}「{name}」{template}"}
    else:  # 关系
        rels = diagram.get("relationships", [])
        # 优先引用 include/extend（用例间），避免对 association（参与者-用例）误用 extend/include 模板
        uc_to_uc = [r for r in rels if r.get("from") in uc_ids and r.get("to") in uc_ids and r.get("type") in ("include", "extend")]
        r = uc_to_uc[0] if uc_to_uc else (rels[0] if rels else None)
        tpl_assoc = kwargs.get("template_association")  # association 专用模板
        if r:
            fk = _key(r.get("from"))
            tk = _key(r.get("to"))
            fn = id_to_name.get(fk) or fk or "(未指定端点)"
            tn = id_to_name.get(tk) or tk or "(未指定端点)"
            rt = r.get("type", "")
            name = f"{fn} - {tn}（{rt}）"
            # association（参与者-用例）用不同模板，不提示 extend/include
            chosen_tpl = (tpl_assoc if tpl_assoc and rt == "association" else template)
            return {"description": f"【用例图·{prefix}】{element_type}「{name}」{chosen_tpl}"}
        return {"description": f"【用例图·{prefix}】{template}"}


def _details_to_issues(details, score: float) -> List[Dict]:
    """将 details（字符串或列表）转为 issues 格式；仅保留表示问题的项"""
    if not details:
        return []
    items = [details] if isinstance(details, str) else details
    issues = []
    for d in items:
        s = str(d).strip()
        if not s:
            continue
        if "未找到" in s or "未匹配" in s or "未定义" in s or "缺少" in s or "未在图中" in s:
            issues.append({"description": s})
    return issues


# 需从输出中移除的 meta 指令（避免 LLM 回显到用户界面）
_META_PHRASES_TO_STRIP = [
    "评估应在上方列出具体",
    "评估应在上方列出",
    "以示专业",
    "请勿将本指令输出",
]


def _sanitize_description(desc: str) -> str:
    """移除误入输出的 meta 指令片段"""
    if not desc or not isinstance(desc, str):
        return desc
    s = desc
    for phrase in _META_PHRASES_TO_STRIP:
        s = s.replace(phrase, "").strip()
    # 移除句尾残留的「，以示专业」「。以...」等
    s = re.sub(r'[，。、]*以[^。]*$', '', s).strip()
    # 清理多余标点
    while "。。" in s or "，。" in s or s.endswith("，"):
        s = s.replace("。。", "。").replace("，。", "。").rstrip("，").strip()
    return s


def _sanitize_issues_in_metrics(metrics: Dict[str, Any]) -> None:
    """递归清理 metrics 中所有 issue 的 description"""
    if not metrics or not isinstance(metrics, dict):
        return
    for dim_data in metrics.values():
        if not isinstance(dim_data, dict):
            continue
        for attr in (dim_data.get("attributes") or {}).values():
            if isinstance(attr, dict) and "issues" in attr:
                for i in attr.get("issues", []):
                    if isinstance(i, dict) and "description" in i:
                        i["description"] = _sanitize_description(i.get("description", ""))
        for i in dim_data.get("issues", []):
            if isinstance(i, dict) and "description" in i:
                i["description"] = _sanitize_description(i.get("description", ""))


def _llm_completeness_score(block: Any) -> Optional[float]:
    if not isinstance(block, dict) or "score" not in block:
        return None
    try:
        return max(0.0, min(1.0, float(block["score"])))
    except (TypeError, ValueError):
        return None


def _extract_role_names_from_issue_text(text: str) -> List[str]:
    """從 issue 描述中提取可能被誤判為參與者的名稱（引號內或常見句式）。"""
    if not text:
        return []
    names: List[str] = []
    for m in re.finditer(r"['\"「『]([^'\"」』]{2,80})['\"」』]", text):
        names.append(m.group(1).strip())
    for m in re.finditer(
        r"(?:角色|参与者|參與者|actor|role)\s*['\"]?([A-Za-z][\w\s\-]{1,60}|[\u4e00-\u9fff]{2,20})",
        text,
        re.IGNORECASE,
    ):
        names.append(m.group(1).strip())
    return names


def _issue_suggests_adding_internal_actor(
    description: str,
    diagram: Dict,
    requirements: Optional[Dict],
) -> bool:
    """
    過濾 LLM 誤報：建議把資料庫等內部組件畫成用例圖參與者。
    """
    desc = (description or "").strip()
    if not desc:
        return False
    lower = desc.lower()
    suggest_verbs = (
        "添加",
        "增加",
        "加入",
        "應包含",
        "应包含",
        "未包含",
        "缺少",
        "遺漏",
        "遗漏",
        "缺失",
        "建議",
        "建议",
        "需添加",
        "需要添加",
        "add ",
        "missing",
        "should include",
        "not included",
        "lack ",
    )
    if not any(v in desc or v in lower for v in suggest_verbs):
        return False

    project_name = None
    if requirements and isinstance(requirements, dict):
        project_name = (requirements.get("project_name") or "").strip() or None

    candidates = _extract_role_names_from_issue_text(desc)
    if requirements and isinstance(requirements, dict):
        for role in requirements.get("roles") or []:
            rn = role.get("name") if isinstance(role, dict) else str(role)
            if rn and rn.strip() and rn.strip() in desc:
                candidates.append(rn.strip())

    for name in candidates:
        if is_internal_system_component_role_name(name):
            return True

    if is_internal_system_component_role_name(desc):
        return True
    internal_hints = ("database", "数据库", "資料庫", "repository", "仓储", "消息队列")
    if any(h in lower or h in desc for h in internal_hints):
        if any(v in desc or v in lower for v in suggest_verbs):
            return True
    return False


_FALSE_TRUNCATED_REQ_ISSUE_MARKERS = (
    "不完整，无法判断",
    "不完整，無法判斷",
    "无法判断是否遗漏",
    "無法判斷是否遺漏",
    "建议补充完整需求",
    "建議補充完整需求",
    "补充完整需求描述",
    "補充完整需求描述",
    "需求摘要中功能",
    "需求摘要中的功能",
    "需求摘要中",
    "无法进一步验证",
    "無法進一步驗證",
)


def _looks_like_truncated_shall_fragment(text: str) -> bool:
    """检测 LLM 误引用的 20 字截断片段，如 'The system shall all'。"""
    return bool(
        re.search(
            r"the\s+system\s+shall\s+[a-z]{1,5}['\"]?\s*(和|与|、|,|$)",
            text,
            re.IGNORECASE,
        )
    )


def _issue_is_false_truncated_requirement_complaint(description: str) -> bool:
    """过滤因需求被错误截断而产生的用例完整性误报。"""
    desc = (description or "").strip()
    if not desc:
        return False
    if any(m in desc for m in _FALSE_TRUNCATED_REQ_ISSUE_MARKERS):
        return True
    if _looks_like_truncated_shall_fragment(desc) and (
        "不完整" in desc or "无法判断" in desc or "無法判斷" in desc
    ):
        return True
    return False


def _filter_misguided_use_case_completeness_issues(issues: List[Dict]) -> List[Dict]:
    kept: List[Dict] = []
    for issue in issues:
        desc = issue.get("description", "") if isinstance(issue, dict) else ""
        if _issue_is_false_truncated_requirement_complaint(str(desc)):
            continue
        kept.append(issue)
    return kept


def _filter_misguided_actor_completeness_issues(
    issues: List[Dict],
    diagram: Dict,
    requirements: Optional[Dict],
) -> List[Dict]:
    kept: List[Dict] = []
    for issue in issues:
        desc = issue.get("description", "") if isinstance(issue, dict) else ""
        if _issue_suggests_adding_internal_actor(str(desc), diagram, requirements):
            continue
        kept.append(issue)
    return kept


def _llm_completeness_issues_list(block: Any) -> List[Dict]:
    """將 LLM 輸出的 issues（字串或物件陣列）統一為 {description: ...}。"""
    out: List[Dict] = []
    if not isinstance(block, dict):
        return out
    raw = block.get("issues")
    if not isinstance(raw, list):
        return out
    for it in raw:
        if isinstance(it, str) and it.strip():
            out.append({"description": it.strip()})
        elif isinstance(it, dict):
            t = it.get("description") or it.get("text") or it.get("detail") or it.get("issue")
            if t is not None and str(t).strip():
                out.append({"description": str(t).strip()})
    return out


def _use_case_display_label(description: Dict) -> str:
    """用例描述在 issue 中的展示名：优先 name，附带 id。"""
    name = (description.get("name") or "").strip()
    uid = (description.get("id") or "").strip()
    if name and uid and name != uid:
        return f"{name}（{uid}）"
    return name or uid or "未命名"


def _tag_issues_with_use_case(
    description: Dict,
    issues: List[Dict],
    prefix: str = "用例描述·完整性",
) -> List[Dict]:
    """為 LLM 返回的 issue 补上用例名/id，避免多用例合并后无法定位。"""
    label = _use_case_display_label(description)
    marker = f"用例「{label}」"
    uid = (description.get("id") or "").strip()
    name = (description.get("name") or "").strip()
    out: List[Dict] = []
    for item in issues or []:
        if not isinstance(item, dict):
            text = str(item).strip()
            if not text:
                continue
            item = {"description": text}
        desc = (item.get("description") or "").strip()
        if not desc:
            continue
        already = marker in desc
        if not already and uid and uid in desc:
            already = True
        if not already and name and name in desc:
            already = True
        if already:
            out.append(dict(item))
            continue
        if desc.startswith("【"):
            out.append({"description": f"【{prefix}】{marker}：{desc}"})
        else:
            out.append({"description": f"【{prefix}】{marker}：{desc}"})
    return out


def _ensure_attr_issues(attr: Dict, attr_label: str, attr_key: str = "") -> None:
    """当属性得分 < 1.0 且无 issues 时，补上带上下文的 fallback（仅用于无 per-item 数据的 diagram 属性）"""
    try:
        raw_score = attr.get("score", 1.0)
        score = float(raw_score) if raw_score is not None else 1.0
    except (TypeError, ValueError):
        score = 1.0
    issues = attr.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    if score < 1.0 and len(issues) == 0:
        label = str(attr_label or "该项")
        attr["issues"] = [{"description": f"【{label}】得分 {score*100:.0f}%，请对照需求与规范检查并改进"}]


def _ensure_all_attr_have_issues(metrics: Dict[str, Any]) -> None:
    """遍历所有质量维度，确保每个非满分属性都有提示"""
    if not metrics or not isinstance(metrics, dict):
        return
    for dim_data in metrics.values():
        if not isinstance(dim_data, dict):
            continue
        attrs = dim_data.get("attributes")
        if not isinstance(attrs, dict):
            continue
        for ak, av in attrs.items():
            if isinstance(av, dict):
                _ensure_attr_issues(av, av.get("label") or ak, attr_key=ak)


class EvaluationEngine:
    """评估引擎类，负责执行各项评估算法"""

    def __init__(self, use_llm: bool = False, llm_provider: str = "deepseek", use_multi_agent: bool = False):
        self.metrics = EvaluationMetrics(
            use_real_llm=use_llm,
            llm_provider=llm_provider,
            use_multi_agent=use_multi_agent,
        )

    def evaluate(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行评估"""
        use_case_diagram = input_data.get('use_case_diagram', {})
        use_case_descriptions = input_data.get('use_case_descriptions', [])
        requirements = input_data.get('requirements')

        if requirements is None:
            raise ValueError("必须显式提供 requirements，评估不允许反推需求")

        score_policy = str(input_data.pop("overall_score_policy", "mean") or "mean").lower()

        diagram_metrics = self._evaluate_diagram(use_case_diagram, requirements)
        description_metrics = self._evaluate_descriptions(use_case_descriptions, requirements, use_case_diagram)

        results = {
            "diagram_metrics": diagram_metrics,
            "description_metrics": description_metrics,
        }
        results["overall_score"] = self._calculate_overall_score(results, score_policy)
        results["recommendations"] = self._generate_recommendations(results)
        return results

    def _evaluate_diagram(self, diagram: Dict[str, Any], requirements: Dict[str, Any] = None) -> Dict[str, Any]:
        """评估用例图质量 - 按质量特性分类"""
        m = self.metrics
        m._batch_diagram_cache = None
        if getattr(m, "use_batch_prompts", False):
            m._ensure_diagram_batch(diagram, requirements)

        # 1. 一致性与规范性
        syntax_result = m.diagram_syntax_correctness(diagram)
        semantic_result = m.diagram_semantic_correctness(diagram, requirements)
        terminology_result = m.diagram_terminology_consistency(diagram, requirements)
        unambiguity_result = m.diagram_element_unambiguity(diagram)

        cn_scores = [
            syntax_result.get('score', 0.0),
            semantic_result.get('score', 0.0),
            terminology_result.get('score', 0.0) if isinstance(terminology_result, dict) else terminology_result,
            unambiguity_result.get('score', 0.0) if isinstance(unambiguity_result, dict) else unambiguity_result,
        ]
        cn_issues = []
        for r in [syntax_result, semantic_result, terminology_result, unambiguity_result]:
            if isinstance(r, dict) and r.get('issues'):
                cn_issues.extend(r['issues'])

        def _diag_attr_issues(res, score_val, diagram, prefix, tpl, elem="关系", **kwargs):
            iss = res.get('issues', []) if isinstance(res, dict) else []
            if score_val < 1.0 and not iss:
                return [_diagram_fallback_issue(diagram, prefix, tpl, elem, **kwargs)]
            return iss

        def _semantic_correctness_issues(res, score_val, diagram):
            """语义正确性：有具体 issue 则展示；无则不再套「如应 extend 却用了 include」。"""
            iss = res.get("issues", []) if isinstance(res, dict) else []
            if iss:
                return iss
            if score_val >= 1.0:
                return []
            llm_result = (res or {}).get("llm_result") or {}
            rel_labels = EvaluationMetrics(use_real_llm=False)._relationship_id_to_display_names(
                diagram
            )
            rebuilt: List[Dict] = []
            for idx, ev in enumerate(llm_result.get("llm_evaluations") or []):
                if ev.get("is_valid", True):
                    continue
                rid = str(ev.get("relationship_id", "") or "").strip()
                loc = rel_labels.get(rid) or f"关系（{rid or '未匹配'}）"
                rebuilt.append({
                    "description": format_semantic_relationship_issue(
                        loc,
                        reason=str(ev.get("reason", "") or ""),
                        suggestion=str(ev.get("suggestion", "") or ""),
                    )
                })
            return rebuilt

        consistency_and_normativity = {
            "label": "一致性与规范性",
            "overall": sum(cn_scores) / len(cn_scores) if cn_scores else 0.0,
            "attributes": {
                "syntax_correctness": {"label": "语法规范性", "score": cn_scores[0], "issues": _diag_attr_issues(syntax_result, cn_scores[0], diagram, "正确性", "语法不符合 UML 规范（如 include/extend 连接了参与者）", "关系")},
                "semantic_correctness": {"label": "语义正确性", "score": cn_scores[1], "issues": _semantic_correctness_issues(semantic_result, cn_scores[1], diagram)},
                "terminology_consistency": {"label": "术语一致性", "score": cn_scores[2], "issues": _diag_attr_issues(terminology_result, cn_scores[2], diagram, "一致性", "术语与需求文档不一致", "用例") if isinstance(terminology_result, dict) else []},
                "element_unambiguity": {"label": "元素无歧义性", "score": cn_scores[3], "issues": _diag_attr_issues(unambiguity_result, cn_scores[3], diagram, "明确性", "名称存在歧义", "用例") if isinstance(unambiguity_result, dict) else []},
            },
            "issues": cn_issues,
        }

        # 2. 完整性
        use_case_redundancy_result = m.diagram_use_case_redundancy(diagram, requirements)
        actor_redundancy_result = m.diagram_actor_redundancy(diagram, requirements)
        redundant_actor_ids = {i['element_id'] for i in (actor_redundancy_result.get('issues') or []) if i.get('element_id')}
        redundant_uc_ids = {i['element_id'] for i in (use_case_redundancy_result.get('issues') or []) if i.get('element_id')}

        ac_result = m.diagram_actor_completeness(diagram, requirements)
        uc_result = m.diagram_use_case_completeness(diagram, requirements)
        rc_result = m.diagram_relationship_completeness(diagram, requirements, redundant_actor_ids=redundant_actor_ids, redundant_use_case_ids=redundant_uc_ids)
        sb_result = m.diagram_system_boundary_completeness(diagram)

        llm_dc = None
        if m.use_real_llm:
            cache = getattr(m, "_batch_diagram_cache", None) or {}
            cand = cache.get("diagram_completeness")
            if isinstance(cand, dict):
                llm_dc = cand

        ac = ac_result.get('score', 0.0) if isinstance(ac_result, dict) else ac_result
        uc = uc_result.get('score', 0.0) if isinstance(uc_result, dict) else uc_result
        rc = rc_result.get('score', 0.0) if isinstance(rc_result, dict) else rc_result
        sb = sb_result.get('score', 0.0) if isinstance(sb_result, dict) else sb_result

        ac_issues = _details_to_issues(ac_result.get("details"), ac) or []
        uc_issues = _details_to_issues(uc_result.get("details"), uc) or []
        rc_issues = _details_to_issues(rc_result.get("details"), rc) or []
        sb_issues = _details_to_issues(sb_result.get("details"), sb) or []

        if llm_dc:
            blk_a = llm_dc.get("actor_completeness")
            sa = _llm_completeness_score(blk_a)
            if sa is not None:
                rule_ac = ac_result.get("score", 0.0) if isinstance(ac_result, dict) else ac_result
                ac_issues_raw = _llm_completeness_issues_list(blk_a)
                ac_issues = _filter_misguided_actor_completeness_issues(
                    ac_issues_raw, diagram, requirements
                )
                rule_issues = ac_result.get("issues", []) if isinstance(ac_result, dict) else []
                if rule_issues:
                    seen = {i.get("description") for i in ac_issues if isinstance(i, dict)}
                    for ri in rule_issues:
                        d = ri.get("description") if isinstance(ri, dict) else ""
                        if d and d not in seen:
                            ac_issues.append(ri)
                            seen.add(d)
                if rule_ac is not None and float(rule_ac) < 1.0:
                    ac = min(sa, float(rule_ac))
                elif len(ac_issues) < len(ac_issues_raw) and (not ac_issues or sa < rule_ac):
                    ac = max(sa, float(rule_ac or 0.0))
                else:
                    ac = sa
            blk_u = llm_dc.get("use_case_completeness")
            su = _llm_completeness_score(blk_u)
            if su is not None:
                rule_uc = uc_result.get("score", 0.0) if isinstance(uc_result, dict) else uc_result
                uc_issues_raw = _llm_completeness_issues_list(blk_u)
                uc_issues = _filter_misguided_use_case_completeness_issues(uc_issues_raw)
                if len(uc_issues) < len(uc_issues_raw) and (not uc_issues or su < rule_uc):
                    uc = max(su, float(rule_uc or 0.0))
                else:
                    uc = su
            blk_r = llm_dc.get("relationship_completeness")
            sr = _llm_completeness_score(blk_r)
            if sr is not None:
                rc = sr
                rc_issues = _llm_completeness_issues_list(blk_r)
            blk_s = llm_dc.get("system_boundary_completeness")
            ss = _llm_completeness_score(blk_s)
            if ss is not None:
                sb = ss
                sb_issues = _llm_completeness_issues_list(blk_s)

        comp_scores = [ac, uc, rc, sb]
        if ac < 1.0 and not ac_issues:
            ac_issues = [_diagram_fallback_issue(diagram, "完整性", "需求中的角色未全部出现在图中", "参与者")]
        if uc < 1.0 and not uc_issues:
            uc_issues = [_diagram_fallback_issue(diagram, "完整性", "需求中的功能用例未全部出现在图中", "用例")]
        if rc < 1.0 and not rc_issues:
            rc_issues = [_diagram_fallback_issue(diagram, "完整性", "角色-用例关联或用例间关系有遗漏", "关系")]
        if sb < 1.0 and not sb_issues:
            sb_issues = [_diagram_fallback_issue(diagram, "完整性", "系统边界不清晰或用例未在边界内", "用例")]
        comp_issues_all = ac_issues + uc_issues + rc_issues + sb_issues

        completeness = {
            "label": "完整性",
            "overall": sum(comp_scores) / 4.0 if sum(comp_scores) > 0 else 0.0,
            "attributes": {
                "actor_completeness": {"label": "参与者完整性", "score": ac, "issues": ac_issues},
                "use_case_completeness": {"label": "用例完整性", "score": uc, "issues": uc_issues},
                "relationship_completeness": {"label": "关系完整性", "score": rc, "issues": rc_issues},
                "system_boundary_completeness": {"label": "系统边界完整性", "score": sb, "issues": sb_issues},
            },
            "issues": comp_issues_all,
        }

        # 3. 必要性（可追溯性）
        rel_redundancy_result = m.diagram_relationship_redundancy(diagram, requirements, redundant_actor_ids=redundant_actor_ids, redundant_use_case_ids=redundant_uc_ids)
        uc_red = use_case_redundancy_result.get('score', 0.0) if isinstance(use_case_redundancy_result, dict) else use_case_redundancy_result
        actor_red = actor_redundancy_result.get('score', 0.0) if isinstance(actor_redundancy_result, dict) else actor_redundancy_result
        rel_red = rel_redundancy_result.get('score', 0.0) if isinstance(rel_redundancy_result, dict) else rel_redundancy_result
        nec_scores = [uc_red, actor_red, rel_red]
        nec_issues = []
        for r in [use_case_redundancy_result, actor_redundancy_result, rel_redundancy_result]:
            if isinstance(r, dict) and r.get('issues'):
                nec_issues.extend(r['issues'])

        necessity_traceability = {
            "label": "必要性（可追溯性）",
            "overall": sum(nec_scores) / len(nec_scores) if nec_scores else 0.0,
            "attributes": {
                "use_case_redundancy": {"label": "用例冗余性", "score": uc_red, "issues": _diag_attr_issues(use_case_redundancy_result, uc_red, diagram, "可追溯性", "在需求中未提及，可能为冗余功能", "用例") if isinstance(use_case_redundancy_result, dict) else []},
                "actor_redundancy": {"label": "参与者冗余性", "score": actor_red, "issues": _diag_attr_issues(actor_redundancy_result, actor_red, diagram, "可追溯性", "在需求中未提及，可能为冗余角色", "参与者") if isinstance(actor_redundancy_result, dict) else []},
                "relationship_redundancy": {"label": "关系冗余性", "score": rel_red, "issues": _diag_attr_issues(rel_redundancy_result, rel_red, diagram, "可追溯性", "在需求中未提及，可能为冗余关系", "关系") if isinstance(rel_redundancy_result, dict) else []},
            },
            "issues": nec_issues,
        }

        # 4. 可修改性
        mod_result = m.diagram_use_case_independence(diagram)
        mod_score = mod_result.get('score', 0.0) if isinstance(mod_result, dict) else mod_result

        modifiability = {
            "label": "可修改性",
            "overall": mod_score,
            "attributes": {
                "use_case_independence": {"label": "用例独立性", "score": mod_score, "issues": _diag_attr_issues(mod_result, mod_score, diagram, "可修改性", "与多个用例耦合或边界模糊，建议拆分", "用例", rel_count=mod_result.get("rel_count", {})) if isinstance(mod_result, dict) else []},
            },
            "issues": mod_result.get('issues', []) if isinstance(mod_result, dict) else [],
        }

        # 加權總分
        dimension_scores = {
            'consistency_and_normativity': consistency_and_normativity['overall'] * 0.35,
            'completeness': completeness['overall'] * 0.25,
            'necessity_traceability': necessity_traceability['overall'] * 0.20,
            'modifiability': modifiability['overall'] * 0.20,
        }
        diagram_overall_score = sum(dimension_scores.values())

        diagram_result = {
            'consistency_and_normativity': consistency_and_normativity,
            'completeness': completeness,
            'necessity_traceability': necessity_traceability,
            'modifiability': modifiability,
            'overall_score': diagram_overall_score,
        }
        _ensure_all_attr_have_issues(diagram_result)
        _sanitize_issues_in_metrics(diagram_result)
        return diagram_result

    def _evaluate_descriptions(self, descriptions: List[Dict[str, Any]], requirements: Dict[str, Any] = None, diagram: Dict[str, Any] = None) -> Dict[str, Any]:
        """评估用例描述质量 - 按质量特性分类（已移除可验证性）"""
        m = self.metrics
        if not descriptions:
            return self._empty_description_metrics()
        m._batch_description_cache = {}
        if getattr(m, "use_batch_prompts", False):
            for d in descriptions:
                m._ensure_description_batch(d)

        def _avg(res_list):
            if not res_list:
                return 0.0
            return sum(r.get('score', 0.0) for r in res_list) / len(res_list)

        # 每个用例都要有用例描述（归入语法正确性）
        coverage_res = m.description_use_case_coverage(diagram, descriptions) if diagram else {"score": 1.0, "issues": []}

        # 1. 一致性与规范性
        syntax_list = [m.description_syntax_correctness(d) for d in descriptions]
        semantic_list = [m.description_semantic_correctness(d, requirements) for d in descriptions]
        term_res = m.description_terminology_consistency(descriptions, requirements)
        unamb_list = [m.description_expression_unambiguity(d) for d in descriptions]
        logic_list = [m.description_internal_logical_consistency(d) for d in descriptions]

        def _agg_with_fallback(res_list, desc_list, prefix, fallback_tpl):
            """聚合 issues，对 score<1 且无 issues 的项补上带用例名的 fallback"""
            out = []
            for d, r in zip(desc_list, res_list):
                out.extend(r.get('issues', []))
                if r.get('score', 1) < 1.0 and not r.get('issues'):
                    out.append(_desc_fallback_issue(d, prefix, fallback_tpl))
            return out

        syntax_avg = _avg(syntax_list)
        coverage_score = coverage_res.get("score", 1.0)
        syntax_combined_score = min(syntax_avg, coverage_score)
        syntax_issues = _agg_with_fallback(syntax_list, descriptions, "用例描述·规范性", "文档结构或步骤编号不符合模板要求，请检查")
        syntax_issues.extend(coverage_res.get("issues", []))

        cn_scores = [
            syntax_combined_score,
            _avg(semantic_list),
            term_res.get('score', 0.0),
            _avg(unamb_list),
            _avg(logic_list),
        ]
        cn_issues = []
        for r in syntax_list + semantic_list + unamb_list + logic_list:
            cn_issues.extend(r.get('issues', []))
        cn_issues.extend(term_res.get('issues', []))
        cn_issues.extend(coverage_res.get("issues", []))

        consistency_and_normativity = {
            "label": "一致性与规范性",
            "overall": sum(cn_scores) / len(cn_scores) if cn_scores else 0.0,
            "attributes": {
                "syntax_correctness": {"label": "语法正确性", "score": syntax_combined_score, "issues": syntax_issues},
                "semantic_correctness": {"label": "语义正确性", "score": cn_scores[1], "issues": _agg_with_fallback(semantic_list, descriptions, "用例描述·正确性", "存在不可执行或过模糊的步骤，请检查主流程与备选流")},
                "terminology_consistency": {"label": "术语一致性", "score": cn_scores[2], "issues": term_res.get('issues', [])},
                "expression_unambiguity": {"label": "表达无歧义性", "score": cn_scores[3], "issues": _agg_with_fallback(unamb_list, descriptions, "用例描述·明确性", "存在表述歧义或模糊词，请检查主流程与备选流中的步骤")},
                "internal_logical_consistency": {"label": "内部逻辑一致性", "score": cn_scores[4], "issues": _agg_with_fallback(logic_list, descriptions, "用例描述·一致性", "主流程、备选流或前置/后置条件之间存在逻辑矛盾")},
            },
            "issues": cn_issues,
        }

        # 2. 完整性（啟用整合 batch LLM 時，主/備選流與前後置以模型語義判斷為主；否則沿用規則）
        use_llm_desc_comp = bool(
            m.use_real_llm
            and m.llm_evaluator
            and getattr(m, "use_batch_prompts", False)
            and not getattr(m.llm_evaluator, "evaluators", None)
        )

        main_list = []
        alt_list = []
        for d in descriptions:
            if use_llm_desc_comp:
                m._ensure_description_batch(d)
                batch = m._batch_description_cache.get(id(d), {}) or {}
                comp = batch.get("description_completeness") or {}
                mf = comp.get("main_flow") if isinstance(comp.get("main_flow"), dict) else {}
                af = comp.get("alternative_flows") if isinstance(comp.get("alternative_flows"), dict) else {}
                smf = _llm_completeness_score(mf)
                saf = _llm_completeness_score(af)
                if smf is not None:
                    main_list.append({
                        "score": smf,
                        "issues": _tag_issues_with_use_case(d, _llm_completeness_issues_list(mf)),
                    })
                else:
                    main_list.append(m.description_main_flow_completeness(d, requirements))
                if saf is not None:
                    alt_list.append({
                        "score": saf,
                        "issues": _tag_issues_with_use_case(d, _llm_completeness_issues_list(af)),
                    })
                else:
                    alt_list.append(m.description_alternative_flow_completeness(d, requirements))
            else:
                main_list.append(m.description_main_flow_completeness(d, requirements))
                alt_list.append(m.description_alternative_flow_completeness(d, requirements))

        pre_post_res = m.description_pre_post_condition_completeness(descriptions)
        if use_llm_desc_comp and descriptions:
            pp_scores: List[float] = []
            pp_issues_all: List[Any] = []
            all_pp = True
            for d in descriptions:
                m._ensure_description_batch(d)
                batch = m._batch_description_cache.get(id(d), {}) or {}
                comp = batch.get("description_completeness") or {}
                pp = comp.get("pre_post_conditions") if isinstance(comp.get("pre_post_conditions"), dict) else {}
                sp = _llm_completeness_score(pp)
                if sp is None:
                    all_pp = False
                    break
                pp_scores.append(sp)
                pp_issues_all.extend(
                    _tag_issues_with_use_case(d, _llm_completeness_issues_list(pp))
                )
            if all_pp and pp_scores:
                # 保留规则层对「简述」等检查项（LLM 未覆盖时）
                rule_pp = m.description_pre_post_condition_completeness(descriptions)
                merged_pp_issues = list(pp_issues_all)
                for ri in rule_pp.get("issues", []) or []:
                    if isinstance(ri, dict) and ri.get("description"):
                        txt = str(ri["description"])
                        if txt not in {x.get("description") for x in merged_pp_issues if isinstance(x, dict)}:
                            merged_pp_issues.append(ri)
                pre_post_res = {
                    "score": sum(pp_scores) / len(pp_scores),
                    "issues": merged_pp_issues,
                }

        comp_scores = [_avg(main_list), _avg(alt_list), pre_post_res.get('score', 0.0)]
        comp_issues = list(pre_post_res.get('issues', []) or [])
        for r in main_list + alt_list:
            comp_issues.extend(r.get('issues', []))

        completeness = {
            "label": "完整性",
            "overall": sum(comp_scores) / 3.0 if comp_scores else 0.0,
            "attributes": {
                "main_flow_completeness": {"label": "主事件流完整性", "score": comp_scores[0], "issues": _agg_with_fallback(main_list, descriptions, "用例描述·完整性", "主事件流不完整或步数不足，请补充核心步骤")},
                "alternative_flow_completeness": {"label": "备选流程/异常流程完整性", "score": comp_scores[1], "issues": _agg_with_fallback(alt_list, descriptions, "用例描述·完整性", "未描述备选流或异常流，建议补充 alternative_flows")},
                "pre_post_condition_completeness": {"label": "前置、后置条件完整性", "score": comp_scores[2], "issues": pre_post_res.get('issues', []) or ([_desc_fallback_issue(descriptions[0], "用例描述·完整性", "缺少前置或后置条件")] if comp_scores[2] < 1.0 and descriptions else [])},
            },
            "issues": comp_issues,
        }

        # 3. 可修改性
        struct_list = [m.description_structure_clarity(d) for d in descriptions]
        redund_list = [m.description_content_redundancy(d) for d in descriptions]
        cohesion_list = [m.description_functional_cohesion(d) for d in descriptions]
        mod_scores = [_avg(struct_list), _avg(redund_list), _avg(cohesion_list)]
        mod_issues = []
        for r in struct_list + redund_list + cohesion_list:
            mod_issues.extend(r.get('issues', []))

        modifiability = {
            "label": "可修改性",
            "overall": sum(mod_scores) / 3.0 if mod_scores else 0.0,
            "attributes": {
                "structure_clarity": {"label": "结构清晰性", "score": mod_scores[0], "issues": _agg_with_fallback(struct_list, descriptions, "用例描述·可修改性", "存在过长步骤或结构混乱，建议拆分或精简")},
                "content_redundancy": {"label": "内容冗余度", "score": mod_scores[1], "issues": _agg_with_fallback(redund_list, descriptions, "用例描述·可修改性", "存在重复步骤，建议合并或精简")},
                "functional_cohesion": {"label": "功能内聚性", "score": mod_scores[2], "issues": _agg_with_fallback(cohesion_list, descriptions, "用例描述·可修改性", "描述混杂了其他用例功能，建议拆分")},
            },
            "issues": mod_issues,
        }

        # 4. 必要性（可追溯性）
        relev_list = [m.description_information_relevance(d) for d in descriptions]
        id_res = m.description_identifier_uniqueness(descriptions)
        # 提高 LLM 语义相关性在“必要性”中的比重：信息相关性 70%，标识唯一性 30%
        info_relevance_score = _avg(relev_list)
        identifier_score = id_res.get('score', 0.0)
        nec_scores = [info_relevance_score, identifier_score]
        nec_issues = list(id_res.get('issues', []))
        for r in relev_list:
            for iss in r.get('issues', []) or []:
                nec_issues.append(iss if isinstance(iss, dict) else {'description': str(iss)})

        id_issues = id_res.get('issues', [])
        if nec_scores[1] < 1.0 and not id_issues and descriptions:
            d0 = descriptions[0]
            name = d0.get('name') or d0.get('id') or '未命名'
            id_issues = [{"description": f"【用例描述·可追溯性】用例「{name}」存在 ID 重复或缺失"}]
        necessity_traceability = {
            "label": "必要性（可追溯性）",
            "overall": (info_relevance_score * 0.70 + identifier_score * 0.30),
            "attributes": {
                "information_relevance": {"label": "信息相关性", "score": nec_scores[0], "issues": _agg_with_fallback(relev_list, descriptions, "用例描述·可追溯性", "存在与用例目标无关的表述，请删除或移至相关用例")},
                "identifier_uniqueness": {"label": "标识唯一性", "score": nec_scores[1], "issues": id_issues},
            },
            "issues": nec_issues,
        }

        # 加权总分（已移除 verifiability、重要性）
        dimension_scores = {
            'consistency_and_normativity': consistency_and_normativity['overall'] * 0.35,
            'completeness': completeness['overall'] * 0.28,
            'modifiability': modifiability['overall'] * 0.17,
            'necessity_traceability': necessity_traceability['overall'] * 0.20,
        }
        description_overall_score = sum(dimension_scores.values())

        individual_scores = [{'use_case_id': d.get('id', ''), 'use_case_name': d.get('name', '')} for d in descriptions]

        desc_result = {
            'consistency_and_normativity': consistency_and_normativity,
            'completeness': completeness,
            'modifiability': modifiability,
            'necessity_traceability': necessity_traceability,
            'individual_scores': individual_scores,
            'overall_score': description_overall_score,
        }
        _ensure_all_attr_have_issues(desc_result)
        _sanitize_issues_in_metrics(desc_result)
        return desc_result

    def _empty_description_metrics(self) -> Dict[str, Any]:
        empty_attr = {"label": "", "overall": 0.0, "attributes": {}, "issues": []}
        return {
            'consistency_and_normativity': empty_attr.copy(),
            'completeness': empty_attr.copy(),
            'modifiability': empty_attr.copy(),
            'necessity_traceability': empty_attr.copy(),
            'individual_scores': [],
            'overall_score': 0.0,
        }

    def _calculate_overall_score(self, results: Dict[str, Any], policy: str = "mean") -> float:
        """
        综合得分：默认算术平均；harmonic 为调和平均，在一侧明显偏低时整体得分更低，减少「图好描述差仍高分」。
        """
        diagram_score = float(results.get('diagram_metrics', {}).get('overall_score', 0.0) or 0.0)
        description_score = float(results.get('description_metrics', {}).get('overall_score', 0.0) or 0.0)
        if diagram_score <= 0.0 and description_score <= 0.0:
            return 0.0
        if policy == "harmonic" and diagram_score > 1e-9 and description_score > 1e-9:
            return (2.0 * diagram_score * description_score) / (diagram_score + description_score)
        return (diagram_score + description_score) / 2.0

    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        recommendations = []
        diagram_metrics = results.get('diagram_metrics', {})
        desc_metrics = results.get('description_metrics', {})

        quality_keys = ['consistency_and_normativity', 'completeness', 'necessity_traceability', 'modifiability']
        dim_names = {
            'consistency_and_normativity': '一致性与规范性',
            'completeness': '完整性',
            'necessity_traceability': '必要性（可追溯性）',
            'modifiability': '可修改性',
        }

        all_issues = []
        for key in quality_keys:
            dim_data = diagram_metrics.get(key, {})
            if isinstance(dim_data, dict):
                all_issues.extend(dim_data.get('issues', []))
        for key in quality_keys:
            dim_data = desc_metrics.get(key, {})
            if isinstance(dim_data, dict):
                all_issues.extend(dim_data.get('issues', []))

        all_issues.sort(key=lambda x: x.get('severity', 0) if isinstance(x, dict) else 0, reverse=True)

        if all_issues:
            recommendations.append("发现以下问题：")
            for i, issue in enumerate(all_issues[:5], 1):
                if isinstance(issue, dict):
                    recommendations.append(f"  {i}. {issue.get('description', '未知问题')}")

        low_scores = []
        for key in quality_keys:
            dim_data = diagram_metrics.get(key, {})
            if isinstance(dim_data, dict) and dim_data.get('overall', 1.0) < 0.7:
                low_scores.append((f"用例图·{dim_names.get(key, key)}", dim_data['overall']))
        for key in quality_keys:
            dim_data = desc_metrics.get(key, {})
            if isinstance(dim_data, dict) and dim_data.get('overall', 1.0) < 0.7:
                low_scores.append((f"用例描述·{dim_names.get(key, key)}", dim_data['overall']))

        if low_scores:
            lines = ["需要重点改进的维度："]
            for name, score in low_scores:
                lines.append(f"  • {name}: {score:.2%}")
            recommendations.append("\n".join(lines))

        return recommendations
