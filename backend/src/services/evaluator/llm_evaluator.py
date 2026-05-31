"""
LLM增强的评估器
将真实LLM集成到现有评估框架中
"""

from typing import Dict, Any, List, Optional
from .llm_integration import LLMManager
from .llm_prompts import LLMPromptTemplates


class LLMEvaluator:
    """LLM增强评估器"""
    
    def __init__(self, llm_manager: Optional[LLMManager] = None):
        """
        初始化LLM评估器
        
        Args:
            llm_manager: LLM管理器实例，如为None则创建默认实例
        """
        if llm_manager is None:
            # 默认使用DeepSeek
            self.llm_manager = LLMManager(provider="deepseek")
        else:
            self.llm_manager = llm_manager
        
        self.temperature = 0.1
        self.max_tokens = 2000
        self.max_tokens_batch = 6500
        self.evaluation_stats = {}

    def evaluate_diagram_quality_batch(
        self, diagram: Dict[str, Any], requirements: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """整合調用：語義 + 歧義 + 獨立性 + 完整性 + 術語一致性，一次 LLM 調用"""
        system_prompt, user_prompt = LLMPromptTemplates.diagram_quality_batch_prompt(
            diagram, requirements or {}
        )
        try:
            response = self.llm_manager.call_with_retry(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens_batch,
            )
            result = self.llm_manager.parse_json_response(response)
        except Exception as e:
            raise RuntimeError("用例圖質量整合評估失敗") from e

        provider = self.llm_manager.provider.get_model_name()

        def _semantic_from_batch(b):
            sc_block = b.get("semantic_correctness") if isinstance(b.get("semantic_correctness"), dict) else {}
            evals = sc_block.get("evaluations", []) or []
            summ = sc_block.get("summary", {}) if isinstance(sc_block.get("summary"), dict) else {}
            total = summ.get("total_relationships", len(evals))
            valid = summ.get("valid_count", sum(1 for e in evals if e.get("is_valid", True)))
            return {
                "score": valid / total if total else 0.5,
                "llm_evaluations": evals,
                "summary": summ,
                "provider": provider,
            }

        def _ambiguity_from_batch(b):
            amb = b.get("element_ambiguity") if isinstance(b.get("element_ambiguity"), dict) else {}
            elems = amb.get("ambiguous_elements", [])
            score = amb.get("score", 0.5)
            total = amb.get("summary", {}).get("total_elements", len(diagram.get("actors", [])) + len(diagram.get("use_cases", [])))
            return {
                "score": score,
                "ambiguous_elements": elems,
                "summary": {"total_elements": total, "ambiguous_count": len(elems)},
                "provider": provider,
            }

        def _independence_from_batch(b):
            ind = b.get("use_case_independence") if isinstance(b.get("use_case_independence"), dict) else {}
            return {
                "score": ind.get("score", 0.5),
                "dependent_cases": ind.get("dependent_cases", []),
                "summary": ind.get("summary", {}),
                "provider": provider,
            }

        def _completeness_from_batch(b):
            dc = b.get("diagram_completeness")
            return dc if isinstance(dc, dict) else {}

        def _terminology_from_batch(b):
            tc = b.get("terminology_consistency") if isinstance(b.get("terminology_consistency"), dict) else {}
            evals = tc.get("term_evaluations", []) or []
            summ = tc.get("summary", {}) if isinstance(tc.get("summary"), dict) else {}
            total = summ.get("total_terms", len(evals))
            consistent = summ.get(
                "consistent_count",
                sum(1 for e in evals if e.get("is_consistent", True)),
            )
            score = tc.get("score")
            if score is None:
                score = consistent / total if total else 1.0
            return {
                "score": score,
                "llm_evaluations": evals,
                "inconsistent_terms": tc.get("inconsistent_terms", []),
                "undefined_terms": tc.get("undefined_terms", []),
                "summary": summ,
                "provider": provider,
            }

        return {
            "semantic_correctness": _semantic_from_batch(result),
            "element_ambiguity": _ambiguity_from_batch(result),
            "use_case_independence": _independence_from_batch(result),
            "diagram_completeness": _completeness_from_batch(result),
            "terminology_consistency": _terminology_from_batch(result),
        }

    def evaluate_description_quality_batch(self, description: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """整合调用：单条用例描述一次 LLM 请求返回多个子指标结果。"""
        system_prompt, user_prompt = LLMPromptTemplates.description_quality_batch_prompt(description)
        try:
            response = self.llm_manager.call_with_retry(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens_batch,
            )
            result = self.llm_manager.parse_json_response(response)
        except Exception as e:
            raise RuntimeError("用例描述质量整合评估失败") from e

        def _as_dict(v):
            return v if isinstance(v, dict) else {}

        return {
            "semantic_correctness": _as_dict(result.get("semantic_correctness")),
            "expression_unambiguity": _as_dict(result.get("expression_unambiguity")),
            "internal_logical_consistency": _as_dict(result.get("internal_logical_consistency")),
            "step_verifiability": _as_dict(result.get("step_verifiability")),
            "functional_cohesion": _as_dict(result.get("functional_cohesion")),
            "information_relevance": _as_dict(result.get("information_relevance")),
            "description_completeness": _as_dict(result.get("description_completeness")),
        }
    
    def evaluate_semantic_correctness(
        self,
        diagram: Dict[str, Any],
        requirements: Optional[Dict[str, Any]] = None,
        lang_ctx: Any = None,
    ) -> Dict[str, Any]:
        """
        LLM增强的语义正确性评估
        
        Args:
            diagram: 用例图数据
            requirements: 需求（跨语言对齐时必传）
            lang_ctx: analyze_cross_language_context 结果
            
        Returns:
            语义正确性评估结果
        """
        relationships = diagram.get("relationships", [])
        
        if not relationships:
            return {
                "score": 1.0,
                "llm_evaluations": [],
                "summary": {"note": "没有需要评估的关系"}
            }

        cross = bool(lang_ctx and getattr(lang_ctx, "cross_language", False))
        system_prompt, user_prompt = LLMPromptTemplates.semantic_correctness_prompt(
            diagram_context=diagram,
            relationships=relationships,
            requirements=requirements,
            cross_language=cross,
        )
        
        try:
            response = self.llm_manager.call_with_retry(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            result = self.llm_manager.parse_json_response(response)
            
            if "evaluations" in result:
                llm_evaluations = result["evaluations"]
                summary = result.get("summary", {})
                
                total = summary.get("total_relationships", len(relationships))
                valid = summary.get("valid_count", 0)
                score = valid / total if total > 0 else 1.0
                
                return {
                    "score": score,
                    "llm_evaluations": llm_evaluations,
                    "summary": summary,
                    "llm_response": response,
                    "provider": self.llm_manager.provider.get_model_name()
                }
            else:
                return {
                    "score": 0.5,
                    "llm_evaluations": [],
                    "summary": {"note": "LLM响应解析失败"},
                    "error": "解析失败",
                    "raw_response": response
                }
                
        except Exception as e:
            raise RuntimeError("LLM语义正确性评估失败，请检查API配置") from e
    
    def evaluate_element_ambiguity(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM增强的元素无歧义性评估
        
        Args:
            diagram: 用例图数据
            
        Returns:
            元素无歧义性评估结果
        """
        actors = diagram.get("actors", [])
        use_cases = diagram.get("use_cases", [])
        
        elements = []
        for actor in actors:
            elements.append({
                "id": actor.get("id", ""),
                "name": actor.get("name", ""),
                "type": "actor",
                "description": actor.get("description", "")
            })
        
        for uc in use_cases:
            elements.append({
                "id": uc.get("id", ""),
                "name": uc.get("name", ""),
                "type": "use_case",
                "description": uc.get("description", "")
            })
        
        if not elements:
            return {
                "score": 1.0,
                "llm_evaluations": [],
                "summary": {"note": "没有需要评估的元素"}
            }
        
        system_prompt, user_prompt = LLMPromptTemplates.element_ambiguity_prompt(
            elements=elements,
            diagram_context=diagram
        )
        
        try:
            response = self.llm_manager.call_with_retry(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            result = self.llm_manager.parse_json_response(response)
            
            if "evaluations" in result:
                llm_evaluations = result["evaluations"]
                summary = result.get("summary", {})
                
                ambiguous_elements = []
                for eval_item in llm_evaluations:
                    if eval_item.get("is_ambiguous", False):
                        ambiguous_elements.append({
                            "id": eval_item.get("element_id", ""),
                            "name": eval_item.get("element_name", ""),
                            "type": eval_item.get("element_type", ""),
                            "reasons": eval_item.get("ambiguity_reasons", []),
                            "suggestions": eval_item.get("suggested_names", [])
                        })
                
                # 優先從 evaluations 計算分數，避免 LLM summary 缺失或錯誤導致 0 分
                total = len(llm_evaluations) if llm_evaluations else len(elements)
                ambiguous_count = len(ambiguous_elements)
                clear_count = total - ambiguous_count
                score = clear_count / total if total > 0 else 1.0
                
                summary["total_elements"] = total
                summary["clear_count"] = clear_count
                summary["ambiguous_count"] = ambiguous_count
                return {
                    "score": score,
                    "llm_evaluations": llm_evaluations,
                    "ambiguous_elements": ambiguous_elements,
                    "summary": summary,
                    "llm_response": response,
                    "provider": self.llm_manager.provider.get_model_name()
                }
            else:
                return {
                    "score": 0.5,
                    "llm_evaluations": [],
                    "summary": {"note": "LLM响应解析失败"},
                    "error": "解析失败",
                    "raw_response": response
                }
                
        except Exception as e:
            raise RuntimeError("LLM元素歧义评估失败，请检查API配置") from e
    
    def evaluate_terminology_consistency(self, diagram: Dict[str, Any],
                                        requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM增强的术语一致性评估
        
        Args:
            diagram: 用例图数据
            requirements: 需求数据
            
        Returns:
            术语一致性评估结果
        """
        from .evaluation_metrics import EvaluationMetrics
        metrics = EvaluationMetrics(use_real_llm=False)
        
        all_terms = metrics._extract_terms_from_diagram(diagram)

        if not all_terms:
            return {
                "score": 1.0,
                "llm_evaluations": [],
                "summary": {"note": "没有需要评估的术语"}
            }

        system_prompt, user_prompt = LLMPromptTemplates.terminology_consistency_prompt(
            terms=all_terms,
            diagram_context=diagram,
            requirements=requirements,
        )
        
        try:
            response = self.llm_manager.call_with_retry(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=self.temperature,
                max_tokens=4000
            )
            
            result = self.llm_manager.parse_json_response(response)
            
            if "term_evaluations" in result:
                llm_evaluations = result["term_evaluations"]
                summary = result.get("summary", {})
                
                total = summary.get("total_terms", len(llm_evaluations))
                consistent = summary.get("consistent_count", sum(1 for e in llm_evaluations if e.get("is_consistent", True)))
                score = consistent / total if total > 0 else 1.0
                
                return {
                    "score": score,
                    "llm_evaluations": llm_evaluations,
                    "inconsistent_terms": result.get("inconsistent_terms", []),
                    "undefined_terms": result.get("undefined_terms", []),
                    "summary": summary,
                    "llm_response": response,
                    "provider": self.llm_manager.provider.get_model_name()
                }
            else:
                return {
                    "score": 0.5,
                    "llm_evaluations": [],
                    "summary": {"note": "LLM响应解析失败"},
                    "error": "解析失败",
                    "raw_response": response
                }
                
        except Exception as e:
            raise RuntimeError("LLM术语一致性评估失败，请检查API配置") from e

    def evaluate_diagram_necessity_four_category(self, diagram: Dict[str, Any], requirements: Dict[str, Any]) -> Dict[str, Any]:
        """用例图必要性四分类评估（用例/参与者/关系）。"""
        system_prompt, user_prompt = LLMPromptTemplates.diagram_necessity_four_category_prompt(
            diagram=diagram,
            requirements=requirements or {},
        )
        try:
            response = self.llm_manager.call_with_retry(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=self.temperature,
                max_tokens=4000,
            )
            result = self.llm_manager.parse_json_response(response)
            return {
                "use_case_evaluations": result.get("use_case_evaluations", []) or [],
                "actor_evaluations": result.get("actor_evaluations", []) or [],
                "relationship_evaluations": result.get("relationship_evaluations", []) or [],
                "summary": result.get("summary", {}) or {},
                "provider": self.llm_manager.provider.get_model_name(),
            }
        except Exception as e:
            raise RuntimeError("LLM用例图必要性四分类评估失败，请检查API配置") from e
    
    
    def _fallback_semantic_evaluation(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """语义评估的降级方案"""
        from .semantic_correctness_evaluator import SemanticCorrectnessEvaluator
        evaluator = SemanticCorrectnessEvaluator(use_llm=False)
        results = evaluator.evaluate_diagram(diagram)
        
        return {
            "score": results.get("overall_score", 0.5),
            "llm_evaluations": [],
            "summary": {"note": "使用规则层降级评估"},
            "fallback": True
        }
    
    def _fallback_ambiguity_evaluation(self, elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """歧义评估的降级方案"""
        clear_count = 0
        ambiguous_elements = []
        
        for element in elements:
            element_name = element.get("name", "")
            
            vague_terms = ["处理", "操作", "系统", "功能", "内容"]
            is_clear = True
            
            for term in vague_terms:
                if term in element_name:
                    is_clear = False
                    ambiguous_elements.append({
                        "id": element.get("id", ""),
                        "name": element_name,
                        "type": element.get("type", ""),
                        "reasons": [f"包含模糊术语'{term}'"]
                    })
                    break
            
            if is_clear:
                clear_count += 1
        
        total = len(elements)
        score = clear_count / total if total > 0 else 1.0
        
        return {
            "score": score,
            "llm_evaluations": [],
            "ambiguous_elements": ambiguous_elements,
            "summary": {
                "total_elements": total,
                "clear_count": clear_count,
                "ambiguous_count": total - clear_count,
                "note": "使用规则降级评估"
            },
            "fallback": True
        }
    
    def _fallback_terminology_evaluation(self, terms: List[str],
                                         term_table: Dict[str, Any]) -> Dict[str, Any]:
        """术语一致性评估的降级方案"""
        from .evaluation_metrics import EvaluationMetrics
        metrics = EvaluationMetrics(use_real_llm=False)
        
        matched = 0
        for term in terms:
            if metrics._term_matches_table(term, term_table):
                matched += 1
        
        total = len(terms)
        score = matched / total if total > 0 else 1.0
        
        return {
            "score": score,
            "llm_evaluations": [],
            "summary": {
                "total_terms": total,
                "consistent_count": matched,
                "inconsistent_count": total - matched,
                "note": "使用规则降级评估"
            },
            "fallback": True
        }

    def evaluate_use_case_verifiability(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """用例图：用例可验收性（LLM）。"""
        use_cases = diagram.get("use_cases", [])
        if not use_cases:
            return {"score": 1.0, "verifiable_count": 0, "total_use_cases": 0, "unverifiable_cases": [], "issues": [], "summary": {}}
        system_prompt, user_prompt = LLMPromptTemplates.use_case_verifiability_prompt(use_cases)
        try:
            response = self.llm_manager.call_with_retry(
                prompt=user_prompt, system_prompt=system_prompt,
                temperature=self.temperature, max_tokens=self.max_tokens
            )
            result = self.llm_manager.parse_json_response(response)
            if "evaluations" not in result:
                raise ValueError("LLM用例可验收性响应格式无效：缺少 evaluations")
            evals = result["evaluations"]
            summary = result.get("summary", {})
            total = summary.get("total_use_cases", len(use_cases))
            valid = summary.get("verifiable_count", sum(1 for e in evals if e.get("is_verifiable", True)))
            score = valid / total if total > 0 else 1.0
            unverifiable = [{"id": e.get("use_case_id"), "name": e.get("use_case_name"), "reasons": e.get("unverifiable_reasons", [])} for e in evals if not e.get("is_verifiable", True)]
            return {
                "score": score, "verifiable_count": int(valid), "total_use_cases": int(total),
                "unverifiable_cases": unverifiable, "issues": [], "summary": summary,
                "llm_response": response, "provider": self.llm_manager.provider.get_model_name()
            }
        except Exception as e:
            raise RuntimeError("LLM用例可验收性评估失败，请检查API配置") from e

    def _fallback_use_case_verifiability(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        use_cases = diagram.get("use_cases", [])
        total = len(use_cases)
        if total == 0:
            return {"score": 1.0, "verifiable_count": 0, "total_use_cases": 0, "unverifiable_cases": [], "issues": [], "summary": {}, "fallback": True}
        vague = ["处理", "操作", "管理", "查看", "设置"]
        verifiable = sum(1 for uc in use_cases if not any(v in (uc.get("name") or "") for v in vague))
        return {"score": verifiable / total, "verifiable_count": verifiable, "total_use_cases": total, "unverifiable_cases": [], "issues": [], "summary": {}, "fallback": True}

    def evaluate_use_case_independence(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        """用例图：用例独立性（LLM）。"""
        use_cases = diagram.get("use_cases", [])
        if not use_cases:
            return {"score": 1.0, "independent_count": 0, "total_use_cases": 0, "dependent_cases": [], "issues": [], "summary": {}}
        system_prompt, user_prompt = LLMPromptTemplates.use_case_independence_prompt(use_cases, diagram)
        try:
            response = self.llm_manager.call_with_retry(
                prompt=user_prompt, system_prompt=system_prompt,
                temperature=self.temperature, max_tokens=4000
            )
            result = self.llm_manager.parse_json_response(response)
            if result.get("error"):
                raise ValueError(result.get("error", "JSON解析失败"))
            if "evaluations" not in result:
                raise ValueError("LLM用例独立性响应格式无效：缺少 evaluations")
            evals = result["evaluations"]
            summary = result.get("summary", {})
            total = summary.get("total", len(use_cases))
            indep = summary.get("independent_count", sum(1 for e in evals if e.get("is_independent", True)))
            score = indep / total if total > 0 else 1.0
            dependent = [{"id": e.get("use_case_id"), "name": e.get("use_case_name"), "reasons": e.get("reasons", [])} for e in evals if not e.get("is_independent", True)]
            return {
                "score": score, "independent_count": int(indep), "total_use_cases": int(total),
                "dependent_cases": dependent, "issues": [], "summary": summary,
                "llm_response": response, "provider": self.llm_manager.provider.get_model_name()
            }
        except Exception as e:
            raise RuntimeError("LLM用例独立性评估失败，请检查API配置") from e

    def _fallback_use_case_independence(self, diagram: Dict[str, Any]) -> Dict[str, Any]:
        use_cases = diagram.get("use_cases", [])
        total = len(use_cases)
        if total == 0:
            return {"score": 1.0, "independent_count": 0, "total_use_cases": 0, "dependent_cases": [], "issues": [], "summary": {}, "fallback": True}
        indep = sum(1 for uc in use_cases if "和" not in (uc.get("name") or "") and "与" not in (uc.get("name") or ""))
        return {"score": indep / total, "independent_count": indep, "total_use_cases": total, "dependent_cases": [], "issues": [], "summary": {}, "fallback": True}

    def _call_description_llm(self, description: Dict[str, Any], prompt_method: str) -> Dict[str, Any]:
        """通用：对单条用例描述调用 LLM prompt 并解析 JSON。"""
        if prompt_method == "semantic_correctness":
            system_prompt, user_prompt = LLMPromptTemplates.description_semantic_correctness_prompt(description)
        elif prompt_method == "internal_logical_consistency":
            system_prompt, user_prompt = LLMPromptTemplates.description_internal_logical_consistency_prompt(description)
        elif prompt_method == "step_verifiability":
            system_prompt, user_prompt = LLMPromptTemplates.description_step_verifiability_prompt(description)
        elif prompt_method == "functional_cohesion":
            system_prompt, user_prompt = LLMPromptTemplates.description_functional_cohesion_prompt(description)
        elif prompt_method == "information_relevance":
            system_prompt, user_prompt = LLMPromptTemplates.description_information_relevance_prompt(description)
        else:
            return {"score": 0.5, "issues": []}
        try:
            response = self.llm_manager.call_with_retry(
                prompt=user_prompt, system_prompt=system_prompt,
                temperature=self.temperature, max_tokens=self.max_tokens
            )
            return self.llm_manager.parse_json_response(response)
        except Exception as e:
            print(f"LLM用例描述评估失败({prompt_method}): {e}")
            return {}

    def evaluate_description_semantic_correctness(self, description: Dict[str, Any], requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """用例描述语义正确性（LLM）。"""
        result = self._call_description_llm(description, "semantic_correctness")
        score = float(result.get("score", 0.5))
        evals = result.get("evaluations", [])
        issues = []
        for e in evals:
            if isinstance(e, dict) and not e.get("is_executable", True):
                step = e.get("step_index", "?")
                text = (e.get("step_text") or "")[:40]
                reason = e.get("reason", "")
                issues.append({"description": f"步骤{step}「{text}」: {reason}" if reason else f"步骤{step}不可执行", **e})
        return {"score": score, "issues": issues}

    def evaluate_description_expression_unambiguity(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """用例描述表达无歧义性（LLM）。"""
        expressions = []
        for s in (description.get("main_flow") or []):
            if isinstance(s, str):
                expressions.append(s)
        for alt in (description.get("alternative_flows") or []):
            if isinstance(alt, dict):
                expressions.extend(alt.get("steps") or [])
        expressions.extend(description.get("preconditions") or [])
        expressions.extend(description.get("postconditions") or [])
        if not expressions:
            return {"score": 1.0, "issues": []}
        system_prompt, user_prompt = LLMPromptTemplates.expression_ambiguity_prompt(expressions, {"use_case": description.get("name"), "id": description.get("id")})
        try:
            response = self.llm_manager.call_with_retry(
                prompt=user_prompt, system_prompt=system_prompt,
                temperature=self.temperature, max_tokens=self.max_tokens
            )
            result = self.llm_manager.parse_json_response(response)
            summary = result.get("summary", {})
            total = summary.get("total_expressions", len(expressions))
            unamb = summary.get("unambiguous_count", total)
            score = unamb / total if total > 0 else 1.0
            return {"score": score, "issues": result.get("evaluations", [])}
        except Exception as e:
            print(f"LLM表达无歧义性评估失败: {e}")
            return {"score": 0.5, "issues": []}

    def evaluate_description_internal_logical_consistency(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """用例描述内部逻辑一致性（LLM）。"""
        result = self._call_description_llm(description, "internal_logical_consistency")
        score = float(result.get("score", 1.0))
        conflicts = result.get("conflicts", [])
        issues = [{"description": c if isinstance(c, str) else c.get("description", str(c))} for c in conflicts]
        return {"score": score, "issues": issues}

    def evaluate_description_step_verifiability(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """用例描述步骤可测试性（LLM）。"""
        result = self._call_description_llm(description, "step_verifiability")
        score = float(result.get("score", 0.5))
        evals = result.get("evaluations", [])
        issues = []
        for e in evals:
            if isinstance(e, dict) and not e.get("is_verifiable", True):
                text = (e.get("step_text") or "")[:40]
                reason = e.get("reason", "")
                issues.append({"description": f"「{text}」: {reason}" if reason else "步骤不可测", **e})
        return {"score": score, "issues": issues}

    def evaluate_description_functional_cohesion(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """用例描述功能内聚性（LLM）。"""
        result = self._call_description_llm(description, "functional_cohesion")
        score = float(result.get("score", 0.5))
        cross = result.get("cross_functionality", [])
        issues = [{"description": x if isinstance(x, str) else x.get("description", str(x))} for x in cross]
        return {"score": score, "issues": issues}

    def evaluate_description_information_relevance(self, description: Dict[str, Any]) -> Dict[str, Any]:
        """用例描述信息相关性（LLM）。"""
        result = self._call_description_llm(description, "information_relevance")
        score = float(result.get("score", 0.5))
        evals = result.get("evaluations", [])
        issues = []
        for e in evals:
            if isinstance(e, dict) and not e.get("is_relevant", True):
                frag = (e.get("fragment") or "")[:50]
                category = e.get("category", "")
                reason = e.get("reason", "")
                label = f"[{category}] " if category else ""
                suffix = f"：{reason}" if reason else ""
                issues.append({"description": f"{label}无关片段「{frag}」与用例目标不直接相关{suffix}", **e})
        return {"score": score, "issues": issues}

    def get_stats(self) -> Dict[str, Any]:
        """获取评估统计"""
        llm_stats = self.llm_manager.get_stats()
        return {
            "llm_stats": llm_stats,
            "evaluation_stats": self.evaluation_stats
        }