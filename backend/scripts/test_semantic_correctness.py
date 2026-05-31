# test_semantic_correctness.py
"""
测试语义正确性评估
"""
import sys
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from src.services.evaluator.semantic_correctness_evaluator import SemanticCorrectnessEvaluator

def test_semantic_correctness():
    """测试语义正确性评估"""
    print("语义正确性评估测试")
    print("=" * 80)
    
    # 测试用例图 - 包含各种语义问题
    test_diagram = {
        "actors": [
            {"id": "actor1", "name": "用户"},
            {"id": "actor2", "name": "管理员"},
            {"id": "actor3", "name": "支付系统"}
        ],
        "use_cases": [
            {"id": "uc1", "name": "用户登录", "description": "用户使用凭据登录系统"},
            {"id": "uc2", "name": "验证密码", "description": "验证用户密码的正确性"},
            {"id": "uc3", "name": "双重认证", "description": "可选的额外安全验证"},
            {"id": "uc4", "name": "VIP用户登录", "description": "VIP用户的特殊登录方式"},
            {"id": "uc5", "name": "管理用户账户", "description": "管理员管理用户账户"}
        ],
        "relationships": [
            # 正确的语义关系
            {
                "id": "rel1",
                "type": "include",
                "from": "uc1",
                "to": "uc2",
                "description": "登录必须包含密码验证"
            },
            {
                "id": "rel2", 
                "type": "extend",
                "from": "uc1",
                "to": "uc3",
                "description": "如果启用双重认证，则扩展登录流程",
                "extension_point": "安全设置启用时"
            },
            {
                "id": "rel3",
                "type": "generalization", 
                "from": "uc4",
                "to": "uc1",
                "description": "VIP用户登录是一种特殊的用户登录"
            },
            {
                "id": "rel4",
                "type": "association",
                "from": "actor1", 
                "to": "uc1",
                "description": "用户执行登录操作"
            },
            {
                "id": "rel9",
                "type": "association",
                "from": "actor2", 
                "to": "uc5",
                "description": "管理员管理用户账户"
            },
            
            # 语义问题关系
            {
                "id": "rel5",
                "type": "include",
                "from": "actor1",  # 错误：参与者不能是include源
                "to": "uc2",
                "description": "用户包含验证密码"
            },
            {
                "id": "rel6",
                "type": "extend", 
                "from": "uc1",
                "to": "uc5",  # 可能错误：管理用户可能不是登录的可选扩展
                "description": "登录可能扩展用户管理"
            },
            {
                "id": "rel7",
                "type": "generalization",
                "from": "actor1",  # 错误：参与者与用例之间不能泛化
                "to": "uc1",
                "description": "用户是一种登录"
            },
            {
                "id": "rel8",
                "type": "association",
                "from": "uc1",  # 错误：用例之间不能关联
                "to": "uc5",
                "description": "登录关联管理"
            }
        ]
    }
    
    # 创建评估器（不使用LLM）
    evaluator = SemanticCorrectnessEvaluator(use_llm=False)
    
    print("执行语义正确性评估...")
    results = evaluator.evaluate_diagram(test_diagram)
    
    # 显示结果
    print(f"\n评估结果:")
    print(f"  总体分数: {results['overall_score']:.2%}")
    print(f"  规则层分数: {results['rule_based_score']:.2%}")
    print(f"  启发式层分数: {results['heuristic_score']:.2%}")
    
    # 显示问题
    issues = results.get("issues", [])
    if issues:
        print(f"\n发现 {len(issues)} 个语义问题:")
        
        # 按验证级别分组
        rule_issues = [i for i in issues if i.get("level") == "rule_based"]
        heuristic_issues = [i for i in issues if i.get("level") == "heuristic"]
        
        if rule_issues:
            print(f"  规则层问题 ({len(rule_issues)} 个):")
            for issue in rule_issues[:3]:  # 显示前3个
                print(f"    • [{issue.get('severity', 0):.1f}] {issue.get('description', '')}")
        
        if heuristic_issues:
            print(f"  启发式层问题 ({len(heuristic_issues)} 个):")
            for issue in heuristic_issues[:3]:
                print(f"    • [{issue.get('severity', 0):.1f}] {issue.get('description', '')}")
    else:
        print("  未发现语义问题")
    
    # 显示验证摘要
    summary = results.get("validation_summary", {})
    print(f"\n验证摘要:")
    for layer, layer_summary in summary.items():
        if layer_summary:
            print(f"  {layer}: {layer_summary.get('coverage', '')}")
            print(f"    分数: {layer_summary.get(f'{layer}_score', 0):.2%}")
    
    # 显示需要LLM验证的关系
    llm_needs = results.get("needs_llm_verification", [])
    if llm_needs:
        print(f"\n建议使用LLM进一步验证的关系 ({len(llm_needs)} 个):")
        for need in llm_needs[:3]:
            print(f"  • {need.get('element_id')}: {need.get('reason', '')}")
    
    # 保存详细结果
    output_file = current_dir / "semantic_validation_results.json"
    import json
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细结果已保存到: {output_file}")
    
    return results

def test_uml_rules():
    """测试UML语义规则"""
    print("\n" + "=" * 80)
    print("UML语义规则测试")
    print("=" * 80)
    
    from src.services.evaluator.uml_semantic_rules import UMLSemanticRules
    
    test_cases = [
        {
            "name": "include关系验证",
            "type": "include",
            "source": "用户登录",
            "target": "验证密码",
            "expected_valid": True
        },
        {
            "name": "extend关系验证", 
            "type": "extend",
            "source": "用户登录",
            "target": "可选的双重认证",
            "expected_valid": True
        },
        {
            "name": "泛化关系验证",
            "type": "generalization",
            "source": "VIP用户登录",
            "target": "用户登录",
            "expected_valid": True
        },
        {
            "name": "关联关系验证",
            "type": "association",
            "source": "用户",
            "target": "登录系统",
            "expected_valid": True
        }
    ]
    
    for test_case in test_cases:
        print(f"\n测试: {test_case['name']}")
        print(f"  关系: {test_case['source']} --[{test_case['type']}]--> {test_case['target']}")
        
        if test_case["type"] == "include":
            result = UMLSemanticRules.validate_include_semantics(
                test_case["source"], test_case["target"]
            )
        elif test_case["type"] == "extend":
            result = UMLSemanticRules.validate_extend_semantics(
                test_case["source"], test_case["target"]
            )
        elif test_case["type"] == "generalization":
            result = UMLSemanticRules.validate_generalization_semantics(
                test_case["source"], test_case["target"]
            )
        elif test_case["type"] == "association":
            result = UMLSemanticRules.validate_association_semantics(
                test_case["source"], test_case["target"]
            )
        
        is_valid = result.get("is_valid", False)
        confidence = result.get("confidence", 0.0)
        
        status = "✅" if is_valid == test_case["expected_valid"] else "❌"
        print(f"  {status} 验证结果: {is_valid} (置信度: {confidence:.2%})")
        
        if not is_valid:
            print(f"    违规: {result.get('violations', [])}")
            print(f"    建议: {result.get('suggestions', [])}")

if __name__ == "__main__":
    print("语义正确性评估系统测试")
    print("版本: 1.0.0 - 三层验证策略")
    
    # 测试UML规则
    test_uml_rules()
    
    # 测试完整评估
    test_semantic_correctness()