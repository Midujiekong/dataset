#!/usr/bin/env python3
"""
修复后的语义正确性测试
"""
import sys
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from src.services.evaluator.semantic_correctness_evaluator import SemanticCorrectnessEvaluator

def test_fixed_semantic_correctness():
    """测试修复后的语义正确性评估"""
    print("修复后的语义正确性评估测试")
    print("=" * 80)
    
    # 修复后的测试用例图
    test_diagram = {
        "actors": [
            {"id": "actor1", "name": "用户"},
            {"id": "actor2", "name": "管理员"}
        ],
        "use_cases": [
            {"id": "uc1", "name": "用户登录", "description": "用户使用凭据登录系统"},
            {"id": "uc2", "name": "验证密码", "description": "验证用户密码的正确性"},
            {"id": "uc3", "name": "可选双重认证", "description": "可选的额外安全验证"},
            {"id": "uc4", "name": "VIP用户登录", "description": "VIP用户的特殊登录方式"},
            {"id": "uc5", "name": "管理用户账户", "description": "管理员管理用户账户"}
        ],
        "relationships": [
            # 正确的语义关系（应该通过）
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
                "description": "如果启用双重认证，则扩展登录流程"
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
                "id": "rel5",
                "type": "association",
                "from": "actor2", 
                "to": "uc5",
                "description": "管理员管理用户账户"
            },
            
            # 语义问题关系（应该被检测）
            {
                "id": "rel6",
                "type": "include",
                "from": "actor1",  # 错误：参与者不能是include源
                "to": "uc2"
            },
            {
                "id": "rel7",
                "type": "extend", 
                "from": "actor1",  # 错误：参与者不能是extend源
                "to": "uc3"
            },
            {
                "id": "rel8",
                "type": "association",
                "from": "uc1",  # 错误：用例之间不能关联
                "to": "uc5"
            }
        ]
    }
    
    # 创建评估器
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
        
        rule_issues = [i for i in issues if i.get("level") == "rule_based"]
        heuristic_issues = [i for i in issues if i.get("level") == "heuristic"]
        
        if rule_issues:
            print(f"  规则层问题 ({len(rule_issues)} 个):")
            for issue in rule_issues:
                print(f"    • [{issue.get('severity', 0):.1f}] {issue.get('description', '')}")
        
        if heuristic_issues:
            print(f"  启发式层问题 ({len(heuristic_issues)} 个):")
            for issue in heuristic_issues:
                print(f"    • [{issue.get('severity', 0):.1f}] {issue.get('description', '')}")
    else:
        print("  未发现语义问题")
    
    # 显示验证摘要 - 修复显示问题
    summary = results.get("validation_summary", {})
    print(f"\n验证摘要:")
    
    rule_summary = summary.get("rule_based", {})
    if rule_summary:
        print(f"  规则层: {rule_summary.get('coverage', '')}")
        print(f"    总关系数: {rule_summary.get('total_relationships', 0)}")
        print(f"    违规数: {rule_summary.get('rule_violations', 0)}")
        print(f"    分数: {rule_summary.get('rule_score', 0):.2%}")
    
    heuristic_summary = summary.get("heuristic", {})
    if heuristic_summary:
        print(f"  启发式层: {heuristic_summary.get('coverage', '')}")
        print(f"    验证数: {heuristic_summary.get('total_validated', 0)}")
        print(f"    问题数: {heuristic_summary.get('heuristic_issues', 0)}")
        print(f"    分数: {heuristic_summary.get('heuristic_score', 0):.2%}")
    
    # 验证正确的关系是否通过
    correct_relations = ["rel1", "rel2", "rel3", "rel4", "rel5"]
    wrong_relations = ["rel6", "rel7", "rel8"]
    
    print(f"\n验证关系正确性:")
    for rel_id in correct_relations:
        issue_found = any(issue.get("element_id") == rel_id for issue in issues)
        status = "✅ 通过" if not issue_found else "❌ 失败"
        print(f"  {rel_id}: {status}")
    
    for rel_id in wrong_relations:
        issue_found = any(issue.get("element_id") == rel_id for issue in issues)
        status = "✅ 检测到问题" if issue_found else "❌ 未检测到问题"
        print(f"  {rel_id}: {status}")
    
    # 期望：5个正确关系应该通过，3个错误关系应该被检测
    expected_passed = 5
    expected_detected = 3
    
    actual_passed = sum(1 for rel_id in correct_relations 
                       if not any(issue.get("element_id") == rel_id for issue in issues))
    actual_detected = sum(1 for rel_id in wrong_relations 
                         if any(issue.get("element_id") == rel_id for issue in issues))
    
    print(f"\n测试总结:")
    print(f"  正确关系: {actual_passed}/{expected_passed} 通过")
    print(f"  错误关系: {actual_detected}/{expected_detected} 被检测")
    
    if actual_passed == expected_passed and actual_detected == expected_detected:
        print("✅ 所有测试通过！")
        return True
    else:
        print("❌ 测试失败")
        return False

if __name__ == "__main__":
    success = test_fixed_semantic_correctness()
    sys.exit(0 if success else 1)