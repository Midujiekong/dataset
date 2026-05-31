# 创建新的LLM集成模块
# llm_semantic_validator.py

"""
基于LLM的UML语义验证器
"""
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class LLMVerificationResult:
    """LLM验证结果"""
    relationship_id: str
    is_valid: bool
    reason: str
    confidence: float  # 0-1之间的置信度
    suggested_fix: Optional[str] = None

class LLMSemanticValidator:
    """
    LLM语义验证器 - 模拟版本
    实际使用时需要集成真正的LLM API
    """
    
    # UML 2.5语义规范知识库
    UML_SEMANTIC_RULES = {
        "include": {
            "description": "表示基础用例必须包含被包含用例的行为",
            "keywords": ["必须包含", "始终包含", "包含行为", "部分功能"],
            "examples": ["登录 include 验证密码", "下单 include 验证库存"],
            "antipatterns": ["可选包含", "条件包含", "可能包含"]
        },
        "extend": {
            "description": "表示扩展用例可选地在特定条件下扩展基础用例",
            "keywords": ["可选扩展", "条件扩展", "特殊情况", "扩展点"],
            "examples": ["支付 extend 优惠券支付", "登录 extend 忘记密码"],
            "antipatterns": ["必须扩展", "始终扩展", "无条件扩展"]
        },
        "generalization": {
            "description": "表示特殊用例继承一般用例的行为",
            "keywords": ["是一种", "继承", "特化", "泛化"],
            "examples": ["VIP用户登录 泛化 用户登录", "在线支付 泛化 支付"],
            "antipatterns": ["包含关系", "扩展关系", "关联关系"]
        }
    }
    
    def __init__(self, use_real_llm: bool = False):
        """
        初始化验证器
        
        Args:
            use_real_llm: 是否使用真实LLM（需要配置API）
        """
        self.use_real_llm = use_real_llm
    
    def validate_relationships(self, relationships_data: List[Dict[str, Any]], 
                              diagram_context: Dict[str, Any]) -> List[LLMVerificationResult]:
        """
        验证关系语义是否符合UML 2.5规范
        
        Args:
            relationships_data: 需要验证的关系列表
            diagram_context: 用例图上下文信息
            
        Returns:
            验证结果列表
        """
        results = []
        
        for rel_data in relationships_data:
            rel_id = rel_data.get("relationship_id", "")
            rel_type = rel_data.get("type", "")
            
            if self.use_real_llm:
                # 实际LLM集成
                result = self._validate_with_real_llm(rel_data, diagram_context)
            else:
                # 模拟验证（基于规则）
                result = self._validate_with_rules(rel_data, diagram_context)
            
            results.append(result)
        
        return results
    
    def _validate_with_rules(self, rel_data: Dict[str, Any], 
                            diagram_context: Dict[str, Any]) -> LLMVerificationResult:
        """
        基于规则的模拟验证（在没有真实LLM的情况下）
        这是启发式规则，实际应用应该使用LLM
        """
        rel_type = rel_data.get("type", "")
        src = rel_data.get("from", {})
        tgt = rel_data.get("to", {})
        
        src_name = src.get("name", "")
        tgt_name = tgt.get("name", "")
        rel_id = rel_data.get("relationship_id", f"{src_name}-{tgt_name}")
        
        # 获取UML规则
        uml_rule = self.UML_SEMANTIC_RULES.get(rel_type, {})
        
        # 启发式检查
        if rel_type == "include":
            # include关系：基础用例必须包含被包含用例
            # 检查是否都是用例
            if src.get("type") == "use_case" and tgt.get("type") == "use_case":
                # 简单规则：目标用例名称是否在源用例名称中（启发式）
                if tgt_name and src_name and tgt_name in src_name:
                    return LLMVerificationResult(
                        relationship_id=rel_id,
                        is_valid=True,
                        reason=f"'{src_name}' 可能包含 '{tgt_name}' 的行为",
                        confidence=0.6,
                        suggested_fix=None
                    )
                else:
                    return LLMVerificationResult(
                        relationship_id=rel_id,
                        is_valid=False,
                        reason=f"include关系语义不明显：'{src_name}' 不一定必须包含 '{tgt_name}' 的行为",
                        confidence=0.5,
                        suggested_fix=f"确认 '{tgt_name}' 是否是 '{src_name}' 必须包含的部分，否则考虑使用extend或关联关系"
                    )
        
        elif rel_type == "extend":
            # extend关系：可选扩展
            if src.get("type") == "use_case" and tgt.get("type") == "use_case":
                # 扩展用例通常是可选的、条件性的
                extend_keywords = ["可选", "条件", "如果", "扩展", "特殊"]
                tgt_has_keywords = any(kw in tgt_name for kw in extend_keywords)
                
                if tgt_has_keywords:
                    return LLMVerificationResult(
                        relationship_id=rel_id,
                        is_valid=True,
                        reason=f"'{tgt_name}' 看起来是一个可选的扩展行为",
                        confidence=0.6,
                        suggested_fix=None
                    )
                else:
                    return LLMVerificationResult(
                        relationship_id=rel_id,
                        is_valid=False,
                        reason=f"extend关系语义不明显：'{tgt_name}' 可能不是 '{src_name}' 的可选扩展",
                        confidence=0.5,
                        suggested_fix=f"如果 '{tgt_name}' 是必须的，考虑使用include关系；如果是可选的，在名称中明确其可选性"
                    )
        
        elif rel_type == "generalization":
            # 泛化关系：特殊用例继承一般用例
            if src.get("type") == tgt.get("type"):  # 同类型元素
                # 检查是否是"是一种"的关系
                # 简单启发式：目标名称是否在源名称中
                if tgt_name and src_name and (tgt_name in src_name or src_name in tgt_name):
                    return LLMVerificationResult(
                        relationship_id=rel_id,
                        is_valid=True,
                        reason=f"'{src_name}' 可能是 '{tgt_name}' 的一种特化",
                        confidence=0.7,
                        suggested_fix=None
                    )
                else:
                    return LLMVerificationResult(
                        relationship_id=rel_id,
                        is_valid=False,
                        reason=f"泛化关系语义不明显：'{src_name}' 可能不是 '{tgt_name}' 的特化",
                        confidence=0.5,
                        suggested_fix=f"确认 '{src_name}' 是否是 '{tgt_name}' 的一种特殊类型，否则考虑其他关系类型"
                    )
        
        # 默认情况
        return LLMVerificationResult(
            relationship_id=rel_id,
            is_valid=True,  # 假设有效，因为语法检查已经通过
            reason="通过基本语义检查，建议使用LLM进行深入验证",
            confidence=0.3,
            suggested_fix=None
        )
    
    def _validate_with_real_llm(self, rel_data: Dict[str, Any], 
                               diagram_context: Dict[str, Any]) -> LLMVerificationResult:
        """
        使用真实LLM进行验证
        需要集成OpenAI、Azure OpenAI、本地LLM等
        """
        # TODO: 集成真实LLM API
        # 示例代码结构：
        """
        prompt = self._build_llm_prompt(rel_data, diagram_context)
        
        try:
            # 调用LLM API
            response = llm_client.complete(prompt)
            
            # 解析响应
            is_valid, reason, confidence = self._parse_llm_response(response)
            
            return LLMVerificationResult(
                relationship_id=rel_data.get("relationship_id", ""),
                is_valid=is_valid,
                reason=reason,
                confidence=confidence
            )
        except Exception as e:
            # 错误处理
            return LLMVerificationResult(
                relationship_id=rel_data.get("relationship_id", ""),
                is_valid=False,
                reason=f"LLM验证失败: {str(e)}",
                confidence=0.0
            )
        """
        
        # 临时返回模拟结果
        return self._validate_with_rules(rel_data, diagram_context)
    
    def _build_llm_prompt(self, rel_data: Dict[str, Any], 
                         diagram_context: Dict[str, Any]) -> str:
        """
        构建LLM提示词
        基于你的表格中的示例Prompt模板
        """
        src = rel_data.get("from", {})
        tgt = rel_data.get("to", {})
        rel_type = rel_data.get("type", "")
        
        prompt_template = """
基于UML 2.5规范，评估以下用例图元素的语义使用是否正确：

用例图结构：
{diagram_structure}

需要评估的关系：
{relationship_description}

评估标准：
1. include关系：必须表示基础用例"必须"包含被包含用例的行为
2. extend关系：必须表示扩展用例"可选地"在特定条件下扩展基础用例  
3. 泛化关系：必须表示特殊用例继承一般用例的行为
4. 用例间不能有普通关联关系
5. 参与者只能通过关联关系连接用例

请评估该关系是否符合UML 2.5语义规范，并说明原因。

输出格式：
关系ID: [VALID/INVALID] - 原因

开始评估：
"""
        
        diagram_structure = json.dumps(diagram_context, ensure_ascii=False, indent=2)
        relationship_desc = f"{src.get('name', '')} ({src.get('type', '')}) --[{rel_type}]--> {tgt.get('name', '')} ({tgt.get('type', '')})"
        
        return prompt_template.format(
            diagram_structure=diagram_structure,
            relationship_description=relationship_desc
        )
    
    def _parse_llm_response(self, response: str) -> Tuple[bool, str, float]:
        """
        解析LLM响应
        期望格式：关系ID: [VALID/INVALID] - 原因
        """
        # 简化解析逻辑
        lines = response.strip().split('\n')
        for line in lines:
            if 'VALID' in line:
                return True, line, 0.8
            elif 'INVALID' in line:
                return False, line, 0.8
        
        # 默认处理
        return False, "无法解析LLM响应", 0.0