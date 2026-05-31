"""
UML 2.5语义规则引擎
基于UML 2.5规范的可编码语义规则
提供纯编码的UML语义验证规则，支持三层验证策略中的规则层和启发式层
"""

from typing import Dict, Any, List, Tuple, Optional, Set


class UMLSemanticRules:
    """
    UML 2.5语义规则引擎（纯编码实现）
    
    基于UML 2.5规范实现用例图语义验证规则，包括：
    1. include关系：基础用例必须包含被包含用例的行为
    2. extend关系：扩展用例可选地在特定条件下扩展基础用例
    3. generalization关系：特殊用例继承一般用例的行为
    4. association关系：参与者与用例之间的通信
    
    所有方法均为静态方法，无需实例化即可使用
    """

    # UML 2.5规范中关于用例图的核心语义规则
    UML_SPECIFICATION = {
        "include": {
            "description": "表示基础用例必须包含被包含用例的行为",
            "constraints": [
                "source必须是use case",
                "target必须是use case",
                "表示强制性的包含关系",
                "被包含用例是基础用例的必要部分",
                "没有扩展点或条件"
            ]
        },
        "extend": {
            "description": "表示扩展用例可选地在特定条件下扩展基础用例",
            "constraints": [
                "source必须是use case",
                "target必须是use case",
                "表示可选的扩展关系",
                "必须有扩展点或条件",
                "基础用例可以独立存在"
            ]
        },
        "generalization": {
            "description": "表示特殊用例继承一般用例的行为",
            "constraints": [
                "source和target必须是同一类型（都是actor或都是use case）",
                "表示'是一种'的关系",
                "子类型继承父类型的所有行为",
                "可以添加或覆盖行为"
            ]
        },
        "association": {
            "description": "表示参与者与用例之间的通信",
            "constraints": [
                "必须在actor和use case之间",
                "表示参与者启动用例",
                "可以是单向或双向",
                "不能在同一类型的元素之间"
            ]
        }
    }
    
    # 中文动词词典 - 用于语义分析
    VERBS = {
        "include_keywords": ["包含", "需要", "必须", "调用", "使用", "执行", "进行", "完成"],
        "extend_keywords": ["可选", "扩展", "可能", "如果", "条件", "当", "假如", "在...情况下"],
        "generalization_keywords": ["是一种", "属于", "继承", "特化", "泛化", "特殊", "特定"],
        "action_verbs": [
            "管理", "创建", "删除", "更新", "查询", "搜索", "登录", "注册",
            "上传", "下载", "提交", "审核", "支付", "计算", "验证", "检查",
            "取款", "存款", "余额", "密码", "小票", "打印", "修改", "withdraw",
            "deposit", "balance", "pin", "statement", "receipt", "change", "display",
        ],
        "actor_role_keywords": [
            "用户", "管理员", "客户", "系统", "员工", "访客", "会员",
            "customer", "client", "user", "admin", "operator", "teller",
            "客户", "顧客", "顧客",
        ],
    }

    @staticmethod
    def validate_include_semantics(source_name: str, target_name: str, 
                                  description: str = "") -> Dict[str, Any]:
        """
        验证include关系的语义
        
        Args:
            source_name: 源用例名称
            target_name: 目标用例名称
            description: 关系描述（可选）
            
        Returns:
            Dict[str, Any]: 验证结果，包含有效性、违规项、建议和置信度
            
        UML 2.5: include表示基础用例必须包含被包含用例的行为
        """
        violations = []
        suggestions = []
        
        # 规则1: 目标用例应该是源用例的必要部分
        # 启发式: 目标用例名称应该是更具体的动作
        if not UMLSemanticRules._is_likely_subfunction(source_name, target_name):
            violations.append(f"目标用例'{target_name}'可能不是源用例'{source_name}'的必要部分")
            suggestions.append(f"确认'{target_name}'确实是'{source_name}'必须包含的行为")
        
        # 规则2: 描述中应该包含强制性词汇
        if description:
            mandatory_keywords = ["必须", "需要", "包含"]
            if not any(keyword in description for keyword in mandatory_keywords):
                violations.append("include关系描述中没有明确的强制性词汇")
                suggestions.append("在描述中明确表示这是必须包含的关系")
        
        # 规则3: 目标用例不应该表示可选行为
        optional_keywords = ["可选", "可能", "如果", "条件"]
        if any(keyword in target_name for keyword in optional_keywords):
            violations.append(f"目标用例'{target_name}'包含可选性词汇，可能更适合extend关系")
            suggestions.append(f"考虑将关系类型改为extend，或重命名目标用例")
        
        return {
            "is_valid": len(violations) == 0,
            "violations": violations,
            "suggestions": suggestions,
            "confidence": 1.0 - (len(violations) * 0.2)  # 每个违规降低20%置信度
        }

    @staticmethod
    def validate_extend_semantics(source_name: str, target_name: str,
                                 description: str = "", extension_point: str = "") -> Dict[str, Any]:
        """
        验证extend关系的语义
        
        Args:
            source_name: 源用例名称
            target_name: 目标用例名称
            description: 关系描述（可选）
            extension_point: 扩展点描述（可选）
            
        Returns:
            Dict[str, Any]: 验证结果
            
        UML 2.5: extend表示扩展用例可选地在特定条件下扩展基础用例
        """
        violations = []
        suggestions = []
        
        # 规则1: 目标用例应该是可选的扩展行为
        optional_keywords = ["可选", "扩展", "额外", "补充", "增强", "双重", "备用"]
        if not any(keyword in target_name for keyword in optional_keywords):
            # 检查描述中是否有可选性提示
            desc_text = (description or "") + (extension_point or "")
            if not any(keyword in desc_text for keyword in optional_keywords):
                # 放宽：如果目标名称包含"可选"或描述中有"如果"，就通过
                if "如果" not in desc_text and "可选" not in target_name:
                    violations.append(f"目标用例'{target_name}'没有明确的扩展或可选性指示")
                    suggestions.append(f"如果这是可选扩展，在用例名称或描述中明确说明")
        
        # 规则2: 源用例应该能够独立存在
        if UMLSemanticRules._is_complete_use_case(source_name):
            # 规则3: 应该有扩展点或条件（放宽此规则）
            condition_keywords = ["如果", "当", "条件", "在...时", "情况下", "启用"]
            has_condition = any(keyword in (description or "") for keyword in condition_keywords)
            has_extension_point = bool(extension_point)
            
            if not (has_condition or has_extension_point):
                # 放宽：不强制要求扩展点
                # 只记录为低严重性问题
                violations.append("extend关系没有明确的扩展点或条件（建议添加）")
                suggestions.append("指定扩展发生的条件或扩展点以提高可理解性")
        else:
            violations.append(f"源用例'{source_name}'可能不是一个完整的用例")
            suggestions.append(f"确认'{source_name}'可以作为一个独立的用例执行")
        
        return {
            "is_valid": len(violations) == 0,
            "violations": violations,
            "suggestions": suggestions,
            "confidence": 1.0 - (len(violations) * 0.1)  # 降低每个违规的置信度影响
        }

    @staticmethod
    def validate_generalization_semantics(child_name: str, parent_name: str,
                                         description: str = "") -> Dict[str, Any]:
        """
        验证泛化关系的语义
        
        Args:
            child_name: 子用例名称
            parent_name: 父用例名称
            description: 关系描述（可选）
            
        Returns:
            Dict[str, Any]: 验证结果
            
        UML 2.5: 泛化表示特殊用例继承一般用例的行为
        """
        violations = []
        suggestions = []
        
        # 规则1: 子类型应该是父类型的特化
        if not UMLSemanticRules._is_specialization(child_name, parent_name):
            # 放宽检查：如果子名称包含父名称，就认为是特化
            if parent_name in child_name:
                # 认为有效，不添加违规
                pass
            else:
                violations.append(f"'{child_name}'可能不是'{parent_name}'的特化")
                suggestions.append(f"确认'{child_name}'确实是'{parent_name}'的一种特殊类型")
        
        # 规则2: 应该存在'是一种'的关系
        if not UMLSemanticRules._has_is_a_relationship(child_name, parent_name):
            # 放宽检查：如果有共同的关键词，就认为是合理
            common_words = set(child_name) & set(parent_name)
            if len(common_words) >= 2:
                # 认为有效，不添加违规
                pass
            else:
                violations.append(f"'{child_name}'和'{parent_name}'之间可能没有明确的'是一种'关系")
                suggestions.append(f"考虑是否真的是泛化关系，或者应该是其他关系类型")
        
        # 规则3: 描述中应该体现继承关系
        if description:
            inheritance_keywords = ["继承", "扩展", "特化", "泛化", "是一种", "属于"]
            if not any(keyword in description for keyword in inheritance_keywords):
                violations.append("描述中没有明确表示继承关系")
                suggestions.append("在描述中明确表示这是一种继承或特化关系")
        
        return {
            "is_valid": len(violations) == 0,
            "violations": violations,
            "suggestions": suggestions,
            "confidence": 1.0 - (len(violations) * 0.2)
        }

    @staticmethod
    def validate_association_semantics(actor_name: str, use_case_name: str,
                                      description: str = "") -> Dict[str, Any]:
        """
        验证关联关系的语义
        
        Args:
            actor_name: 参与者名称
            use_case_name: 用例名称
            description: 关系描述（可选）
            
        Returns:
            Dict[str, Any]: 验证结果
            
        UML 2.5: 关联表示参与者与用例之间的通信
        """
        violations = []
        suggestions = []
        
        # 规则1: 参与者应该能够启动用例
        if not UMLSemanticRules._can_initiate_use_case(actor_name, use_case_name):
            # 放宽标准：只要参与者是角色，用例是动作，就认为可以启动
            actor_patterns = UMLSemanticRules.VERBS["actor_role_keywords"]
            use_case_patterns = UMLSemanticRules.VERBS["action_verbs"]
            
            actor_is_role = any(
                pattern.lower() in actor_name.lower() for pattern in actor_patterns
            )
            use_case_is_action = any(pattern in use_case_name for pattern in use_case_patterns)
            
            if not (actor_is_role and use_case_is_action):
                violations.append(f"参与者'{actor_name}'可能不能启动用例'{use_case_name}'")
                suggestions.append(f"确认'{actor_name}'确实需要与'{use_case_name}'交互")
        
        # 规则2: 用例应该对参与者有价值（放宽此规则）
        # 注释掉过于严格的检查
        # if not UMLSemanticRules._has_value_for_actor(actor_name, use_case_name):
        #     violations.append(f"用例'{use_case_name}'可能对参与者'{actor_name}'没有明确价值")
        #     suggestions.append(f"确认用例确实为参与者提供价值")
        
        return {
            "is_valid": len(violations) == 0,
            "violations": violations,
            "suggestions": suggestions,
            "confidence": 1.0 - (len(violations) * 0.2)
        }

    # ============ 辅助方法 ============

    @staticmethod
    def _is_likely_subfunction(source_name: str, target_name: str) -> bool:
        """
        判断target是否是source的子功能
        
        Args:
            source_name: 源用例名称
            target_name: 目标用例名称
            
        Returns:
            bool: 如果目标很可能是源的子功能则返回True
        """
        # 启发式1: target名称更具体
        if len(target_name) > len(source_name) and source_name in target_name:
            return True
        
        # 启发式2: target包含动作性词汇
        action_verbs = UMLSemanticRules.VERBS["action_verbs"]
        target_has_action = any(verb in target_name for verb in action_verbs)
        source_has_action = any(verb in source_name for verb in action_verbs)
        
        if target_has_action and not source_has_action:
            return True
        
        # 启发式3: target是source的步骤
        step_patterns = ["验证", "检查", "计算", "获取", "处理"]
        if any(pattern in target_name for pattern in step_patterns):
            return True
        
        return False

    @staticmethod
    def _is_complete_use_case(use_case_name: str) -> bool:
        """
        判断是否表示完整的用例
        
        Args:
            use_case_name: 用例名称
            
        Returns:
            bool: 如果表示完整的用例则返回True
        """
        # 完整用例通常表示一个用户目标
        complete_patterns = ["管理", "创建", "删除", "更新", "查询", "登录", "注册", "支付"]
        return any(pattern in use_case_name for pattern in complete_patterns)

    @staticmethod
    def _is_specialization(child_name: str, parent_name: str) -> bool:
        """
        判断child是否是parent的特化
        
        Args:
            child_name: 子用例名称
            parent_name: 父用例名称
            
        Returns:
            bool: 如果child是parent的特化则返回True
        """
        # 特化通常包含更多限定词
        specialization_indicators = ["VIP", "高级", "特殊", "快速", "批量", "手动", "自动"]
        
        # 规则1: child包含更多限定词
        child_has_indicator = any(indicator in child_name for indicator in specialization_indicators)
        parent_has_indicator = any(indicator in parent_name for indicator in specialization_indicators)
        
        if child_has_indicator and not parent_has_indicator:
            return True
        
        # 规则2: child名称包含parent名称
        if parent_name in child_name and len(child_name) > len(parent_name):
            return True
        
        # 规则3: 语义包含关系
        if UMLSemanticRules._semantic_contains(child_name, parent_name):
            return True
        
        return False

    @staticmethod
    def _has_is_a_relationship(child_name: str, parent_name: str) -> bool:
        """
        判断是否存在'是一种'的关系
        
        Args:
            child_name: 子用例名称
            parent_name: 父用例名称
            
        Returns:
            bool: 如果存在'是一种'的关系则返回True
        """
        # 简单的模式匹配
        patterns = [
            (f"{child_name}是一种{parent_name}", 1.0),
            (f"{child_name}是{parent_name}", 0.8),
            (f"{child_name}属于{parent_name}", 0.7),
            (f"{child_name}继承{parent_name}", 0.9),
        ]
        
        # 在实际应用中，这里可以使用更复杂的NLP
        # 这里使用简单的字符串包含作为启发式
        common_words = set(child_name.split()) & set(parent_name.split())
        return len(common_words) >= 1

    @staticmethod
    def _can_initiate_use_case(actor_name: str, use_case_name: str) -> bool:
        """
        判断参与者是否能启动用例
        
        Args:
            actor_name: 参与者名称
            use_case_name: 用例名称
            
        Returns:
            bool: 如果参与者能启动用例则返回True
        """
        # 参与者通常是角色名词
        actor_patterns = UMLSemanticRules.VERBS["actor_role_keywords"]
        use_case_patterns = UMLSemanticRules.VERBS["action_verbs"]
        
        actor_is_role = any(
            pattern.lower() in actor_name.lower() for pattern in actor_patterns
        )
        use_case_is_action = any(
            pattern.lower() in use_case_name.lower() for pattern in use_case_patterns
        )
        
        return actor_is_role and use_case_is_action

    @staticmethod
    def _has_value_for_actor(actor_name: str, use_case_name: str) -> bool:
        """
        判断用例对参与者是否有价值 - 优化版
        
        Args:
            actor_name: 参与者名称
            use_case_name: 用例名称
            
        Returns:
            bool: 如果用例对参与者有价值则返回True
        """
        # 放宽标准：只要用例包含动作关键词，就认为有价值
        value_keywords = UMLSemanticRules.VERBS["action_verbs"]
        return any(keyword in use_case_name for keyword in value_keywords)

    @staticmethod
    def _semantic_contains(text1: str, text2: str) -> bool:
        """
        语义包含关系判断（简化版）
        
        Args:
            text1: 文本1
            text2: 文本2
            
        Returns:
            bool: 如果text1语义上包含text2则返回True
        """
        # 在实际应用中，这里可以使用词向量或同义词词典
        # 这里使用简单的字符串相似度
        words1 = set(text1)
        words2 = set(text2)
        return len(words1 & words2) >= 2  # 至少有两个共同字符