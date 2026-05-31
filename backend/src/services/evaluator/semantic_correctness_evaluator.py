"""
语义正确性评估器 - 三层验证策略
提供基于UML 2.5规范的语义正确性评估，采用规则层、启发式层、LLM层三层验证策略
"""

from typing import Dict, Any, List, Tuple
from enum import Enum
import json


class ValidationLevel(Enum):
    """验证级别枚举"""
    RULE_BASED = "rule_based"
    HEURISTIC = "heuristic"
    LLM_ENHANCED = "llm_enhanced"


class SemanticIssue:
    """
    语义问题描述类
    
    用于记录在语义验证过程中发现的问题，包括问题级别、元素信息、描述和建议等
    """

    def __init__(self, level: ValidationLevel, element_id: str, 
                 element_type: str, description: str, 
                 severity: float, suggestion: str = ""):
        """
        初始化语义问题
        
        Args:
            level: 验证级别
            element_id: 元素ID
            element_type: 元素类型
            description: 问题描述
            severity: 严重程度（0-1）
            suggestion: 改进建议（可选）
        """
        self.level = level
        self.element_id = element_id
        self.element_type = element_type
        self.description = description
        self.severity = severity
        self.suggestion = suggestion

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            Dict[str, Any]: 字典格式的问题描述
        """
        return {
            "level": self.level.value,
            "element_id": self.element_id,
            "element_type": self.element_type,
            "description": self.description,
            "severity": self.severity,
            "suggestion": self.suggestion
        }


class SemanticCorrectnessEvaluator:
    """
    语义正确性评估器
    
    采用三层验证策略评估用例图的语义正确性：
    1. 规则层验证：100%可编码的硬性语义规则
    2. 启发式层验证：基于启发式规则的语义推断
    3. LLM层验证：使用大语言模型进行深度语义分析（可选）
    
    根据三层验证结果计算综合分数，并提供详细的问题报告
    """

    def __init__(self, use_llm: bool = False):
        """
        初始化评估器
        
        Args:
            use_llm: 是否启用LLM验证层（默认False）
        """
        self.use_llm = use_llm
        self.issues: List[SemanticIssue] = []
        self.validation_results = {}
        
        from .uml_semantic_rules import UMLSemanticRules
        self.rules = UMLSemanticRules

    def evaluate_diagram(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估用例图的语义正确性
        
        Args:
            diagram: 用例图数据
            
        Returns:
            Dict[str, Any]: 评估结果，包含分数、问题和验证摘要
        """
        self.issues.clear()
        
        rule_results = self._rule_based_validation(diagram)
        
        heuristic_results = self._heuristic_validation(diagram)
        
        llm_results = {}
        if self.use_llm:
            llm_results = self._llm_enhanced_validation(diagram)
        
        scores = self._calculate_scores_fixed(rule_results, heuristic_results, llm_results)
        
        return {
            "overall_score": scores["overall"],
            "rule_based_score": scores["rule_based"],
            "heuristic_score": scores["heuristic"],
            "llm_score": scores.get("llm", 0.0) if self.use_llm else None,
            "issues": [issue.to_dict() for issue in self.issues],
            "validation_summary": {
                "rule_based": rule_results.get("summary", {}),
                "heuristic": heuristic_results.get("summary", {}),
                "llm_enhanced": llm_results.get("summary", {}) if llm_results else {}
            },
            "needs_llm_verification": self._get_llm_verification_needs()
        }

    def _rule_based_validation(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """
        规则层验证 - 100%可编码的硬性语义规则
        
        Args:
            diagram: 用例图数据
            
        Returns:
            Dict[str, Any]: 规则层验证结果
        """
        results = {
            "validated_relationships": [],
            "issues": [],
            "summary": {}
        }
        
        relationships = diagram.get("relationships", [])
        actors = {a["id"]: a for a in diagram.get("actors", [])}
        use_cases = {uc["id"]: uc for uc in diagram.get("use_cases", [])}
        
        rule_violations = 0
        total_relationships = len(relationships)
        
        if total_relationships == 0:
            results["summary"] = {
                "total_relationships": 0,
                "rule_violations": 0,
                "valid_count": 0,
                "rule_score": 1.0,
                "coverage": "100% - 硬性语义规则"
            }
            return results
        
        for rel in relationships:
            rel_id = rel.get("id", "")
            rel_type = rel.get("type", "")
            src_id = rel.get("from", "")
            tgt_id = rel.get("to", "")
            
            src_elem = actors.get(src_id) or use_cases.get(src_id)
            tgt_elem = actors.get(tgt_id) or use_cases.get(tgt_id)
            
            if not src_elem or not tgt_elem:
                # 元素不存在，跳过此关系
                continue
            
            src_type = "actor" if src_id in actors else "use_case"
            tgt_type = "actor" if tgt_id in actors else "use_case"
            src_name = src_elem.get("name", src_id)
            tgt_name = tgt_elem.get("name", tgt_id)
            
            # 硬性语义规则检查
            rule_valid = True
            issue_desc = ""
            
            if rel_type == "include":
                # 规则: include只能在use case之间
                if src_type != "use_case" or tgt_type != "use_case":
                    rule_valid = False
                    issue_desc = f"include关系只能在用例之间，不能在'{src_name}'({src_type})和'{tgt_name}'({tgt_type})之间"
            
            elif rel_type == "extend":
                # 规则: extend只能在use case之间
                if src_type != "use_case" or tgt_type != "use_case":
                    rule_valid = False
                    issue_desc = f"extend关系只能在用例之间，不能在'{src_name}'({src_type})和'{tgt_name}'({tgt_type})之间"
            
            elif rel_type == "generalization":
                # 规则: 泛化只能在同类型元素之间
                if src_type != tgt_type:
                    rule_valid = False
                    issue_desc = f"泛化关系只能在同类型元素之间，不能在'{src_name}'({src_type})和'{tgt_name}'({tgt_type})之间"
            
            elif rel_type == "association":
                # 规则: 关联必须在actor和use case之间
                if not ({src_type, tgt_type} == {"actor", "use_case"}):
                    rule_valid = False
                    issue_desc = f"关联关系必须在参与者和用例之间，不能在'{src_name}'({src_type})和'{tgt_name}'({tgt_type})之间"
            
            if not rule_valid:
                rule_violations += 1
                issue = SemanticIssue(
                    level=ValidationLevel.RULE_BASED,
                    element_id=rel_id,
                    element_type="relationship",
                    description=f"语义规则违反: {issue_desc}",
                    severity=0.9,
                    suggestion="根据UML 2.5规范修正关系"
                )
                self.issues.append(issue)
            
            results["validated_relationships"].append({
                "id": rel_id,
                "type": rel_type,
                "rule_valid": rule_valid,
                "source": src_name,
                "target": tgt_name
            })
        
        # 有效关系数 = 总关系数 - 违规数
        valid_count = total_relationships - rule_violations
        rule_score = valid_count / total_relationships if total_relationships > 0 else 1.0
        
        results["summary"] = {
            "total_relationships": total_relationships,
            "rule_violations": rule_violations,
            "valid_count": valid_count,
            "rule_score": rule_score,  # 统一键名为 rule_score
            "coverage": "100% - 硬性语义规则"
        }
        
        return results

    def _heuristic_validation(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """
        启发式层验证 - 基于启发式规则的语义推断
        
        Args:
            diagram: 用例图数据
            
        Returns:
            Dict[str, Any]: 启发式层验证结果
        """
        results = {
            "validated_relationships": [],
            "issues": [],
            "summary": {}
        }
        
        relationships = diagram.get("relationships", [])
        actors = {a["id"]: a for a in diagram.get("actors", [])}
        use_cases = {uc["id"]: uc for uc in diagram.get("use_cases", [])}
        
        heuristic_issues = 0
        total_validated = 0
        
        for rel in relationships:
            rel_id = rel.get("id", "")
            rel_type = rel.get("type", "")
            src_id = rel.get("from", "")
            tgt_id = rel.get("to", "")
            description = rel.get("description", "")
            extension_point = rel.get("extension_point", "")
            
            src_elem = actors.get(src_id) or use_cases.get(src_id)
            tgt_elem = actors.get(tgt_id) or use_cases.get(tgt_id)
            
            if not src_elem or not tgt_elem:
                continue
            
            src_name = src_elem.get("name", src_id)
            tgt_name = tgt_elem.get("name", tgt_id)
            
            # 应用启发式规则
            validation_result = None
            
            if rel_type == "include":
                validation_result = self.rules.validate_include_semantics(
                    src_name, tgt_name, description
                )
            
            elif rel_type == "extend":
                validation_result = self.rules.validate_extend_semantics(
                    src_name, tgt_name, description, extension_point
                )
            
            elif rel_type == "generalization":
                validation_result = self.rules.validate_generalization_semantics(
                    src_name, tgt_name, description
                )
            
            elif rel_type == "association":
                validation_result = self.rules.validate_association_semantics(
                    src_name, tgt_name, description
                )
            
            if validation_result:
                total_validated += 1
                
                if not validation_result.get("is_valid", True):
                    heuristic_issues += 1
                    
                    for violation in validation_result.get("violations", []):
                        issue = SemanticIssue(
                            level=ValidationLevel.HEURISTIC,
                            element_id=rel_id,
                            element_type="relationship",
                            description=f"启发式语义问题: {violation}",
                            severity=0.6,
                            suggestion=validation_result.get("suggestions", [""])[0]
                        )
                        self.issues.append(issue)
                
                results["validated_relationships"].append({
                    "id": rel_id,
                    "type": rel_type,
                    "heuristic_valid": validation_result.get("is_valid", True),
                    "confidence": validation_result.get("confidence", 0.0),
                    "violations": validation_result.get("violations", []),
                    "suggestions": validation_result.get("suggestions", [])
                })
        
        heuristic_score = 1.0 - (heuristic_issues / total_validated) if total_validated > 0 else 1.0
        
        results["summary"] = {
            "total_validated": total_validated,
            "heuristic_issues": heuristic_issues,
            "heuristic_score": heuristic_score,
            "coverage": "约80-90% - 基于启发式规则"
        }
        
        return results

    def _llm_enhanced_validation(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM增强验证 - 使用真实LLM进行深度语义分析（基于LLM的语义验证）。
        use_llm=True 时调用 LLMEvaluator.evaluate_semantic_correctness，不再使用模拟实现。
        """
        if not self.use_llm:
            return {
                "validated_relationships": [],
                "issues": [],
                "summary": {"total_validated": 0, "llm_issues": 0, "llm_score": 1.0, "coverage": "0%"}
            }
        try:
            from .llm_evaluator import LLMEvaluator
            evaluator = LLMEvaluator()
            result = evaluator.evaluate_semantic_correctness(diagram)
        except Exception as e:
            raise RuntimeError("LLM语义正确性评估失败，请检查API配置") from e
        llm_evaluations = result.get("llm_evaluations", [])
        summary = result.get("summary", {})
        total_validated = summary.get("total_relationships", len(llm_evaluations))
        valid_count = summary.get("valid_count", 0)
        llm_issues = total_validated - valid_count if total_validated else 0
        llm_score = result.get("score", 1.0)
        validated_relationships = []
        for eval_item in llm_evaluations:
            validated_relationships.append({
                "id": eval_item.get("relationship_id", ""),
                "type": eval_item.get("relationship_type", ""),
                "is_valid": eval_item.get("is_valid", True),
                "reason": eval_item.get("reason", ""),
                "suggestion": eval_item.get("suggestion", ""),
                "confidence": eval_item.get("confidence", 0.8),
            })
            if not eval_item.get("is_valid", True):
                self.issues.append(SemanticIssue(
                    level=ValidationLevel.LLM_ENHANCED,
                    element_id=eval_item.get("relationship_id", ""),
                    element_type="relationship",
                    description=f"LLM语义验证: {eval_item.get('reason', '')}",
                    severity=0.7,
                    suggestion=eval_item.get("suggestion", "")
                ))
        return {
            "validated_relationships": validated_relationships,
            "issues": [],
            "summary": {
                "total_validated": total_validated,
                "llm_issues": llm_issues,
                "llm_score": llm_score,
                "coverage": "基于LLM的语义验证"
            }
        }

    def _calculate_scores_fixed(self, rule_results: Dict[str, Any], 
                               heuristic_results: Dict[str, Any],
                               llm_results: Dict[str, Any]) -> Dict[str, float]:
        """
        计算综合分数 - 修复版本
        
        权重分配：
        - 不使用LLM时：规则层60%，启发式层40%
        - 使用LLM时：规则层50%，启发式层30%，LLM层20%
        
        Args:
            rule_results: 规则层验证结果
            heuristic_results: 启发式层验证结果
            llm_results: LLM层验证结果
            
        Returns:
            Dict[str, float]: 各层分数及综合分数
        """
        # 获取分数
        rule_summary = rule_results.get("summary", {})
        heuristic_summary = heuristic_results.get("summary", {})
        
        # 使用正确的键名获取分数
        rule_score = rule_summary.get("rule_score", 1.0)
        heuristic_score = heuristic_summary.get("heuristic_score", 1.0)
        
        # LLM分数
        if self.use_llm and llm_results:
            llm_summary = llm_results.get("summary", {})
            llm_score = llm_summary.get("llm_score", 1.0)
        else:
            llm_score = 1.0  # 未使用LLM时，LLM层视为完美
        
        # 权重分配
        if self.use_llm:
            # 使用LLM时：规则层50%，启发式层30%，LLM层20%
            overall_score = (
                rule_score * 0.5 +
                heuristic_score * 0.3 +
                llm_score * 0.2
            )
        else:
            # 不使用LLM时：规则层60%，启发式层40%
            overall_score = (
                rule_score * 0.6 +
                heuristic_score * 0.4
            )
        
        return {
            "overall": overall_score,
            "rule_based": rule_score,
            "heuristic": heuristic_score,
            "llm": llm_score if self.use_llm else None
        }

    def _identify_complex_cases(self, diagram: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        识别需要LLM验证的复杂案例
        
        Args:
            diagram: 用例图数据
            
        Returns:
            List[Dict[str, Any]]: 复杂关系列表
        """
        complex_cases = []
        relationships = diagram.get("relationships", [])
        
        for rel in relationships:
            rel_type = rel.get("type", "")
            
            # 需要LLM验证的情况：
            # 1. 语义模糊的关系
            # 2. 启发式验证置信度低的关系
            # 3. 涉及复杂业务逻辑的关系
            
            if rel_type in ["include", "extend", "generalization"]:
                # 简单启发式：如果关系描述复杂或包含条件逻辑
                description = rel.get("description", "")
                if len(description) > 50 or "如果" in description or "当" in description:
                    complex_cases.append(rel)
        
        return complex_cases

    def _simulate_llm_validation(self, relationship: Dict[str, Any]) -> Dict[str, Any]:
        """
        已弃用：仅保留供兼容。语义验证应使用 LLMEvaluator.evaluate_semantic_correctness（见 _llm_enhanced_validation）。
        """
        rel_type = relationship.get("type", "")
        
        # 模拟不同的验证结果
        import random
        is_valid = random.random() > 0.3  # 70%概率有效
        
        reasons = {
            "include": [
                "目标用例确实是源用例的必要部分",
                "目标用例可能不是必须包含的行为，考虑使用extend",
                "这种包含关系符合UML语义"
            ],
            "extend": [
                "扩展用例确实表示可选的扩展行为",
                "扩展点或条件不够明确",
                "这种扩展关系符合UML语义"
            ],
            "generalization": [
                "子用例确实是父用例的特化",
                "子用例和父用例之间没有明确的'是一种'关系",
                "这种泛化关系符合UML语义"
            ]
        }
        
        reason = random.choice(reasons.get(rel_type, ["关系语义需要进一步验证"]))
        
        return {
            "id": relationship.get("id", ""),
            "type": rel_type,
            "is_valid": is_valid,
            "reason": reason,
            "suggestion": "建议根据业务需求确认关系语义" if not is_valid else "",
            "confidence": random.uniform(0.6, 0.95)
        }

    def _get_llm_verification_needs(self) -> List[Dict[str, Any]]:
        """
        获取需要LLM验证的关系列表
        
        Returns:
            List[Dict[str, Any]]: 需要LLM验证的关系列表
        """
        needs = []
        
        # 收集启发式验证中置信度低的关系
        for issue in self.issues:
            if issue.level == ValidationLevel.HEURISTIC and issue.severity > 0.7:
                needs.append({
                    "element_id": issue.element_id,
                    "reason": issue.description,
                    "priority": "high" if issue.severity > 0.8 else "medium"
                })
        
        return needs