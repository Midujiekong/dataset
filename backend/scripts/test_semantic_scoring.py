#!/usr/bin/env python3
"""
测试语义正确性评估的分数计算
"""
import sys
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from src.services.evaluator.semantic_correctness_evaluator import SemanticCorrectnessEvaluator

def test_scoring_logic():
    """测试分数计算逻辑"""
    print("语义正确性评估分数计算测试")
    print("=" * 80)
    
    # 简单测试用例：8个关系，3个规则错误，1个启发式问题
    test_diagram = {
        "actors": [
            {"id": "actor1", "name": "用户"},
            {"id": "actor2", "name": "管理员"}
        ],
        "use_cases": [
            {"id": "uc1", "name": "登录"},
            {"id": "uc2", "name": "验证"},
            {"id": "uc3", "name": "管理"}
        ],
        "relationships": [
            # 5个正确的关系
            {"id": "rel1", "type": "association", "from": "actor1", "to": "uc1"},
            {"id": "rel2", "type": "association", "from": "actor2", "to": "uc3"},
            {"id": "rel3", "type": "include", "from": "uc1", "to": "uc2"},
            {"id": "rel4", "type": "extend", "from": "uc1", "to": "uc3"},
            {"id": "rel5", "type": "generalization", "from": "uc2", "to": "uc1"},
            
            # 3个规则错误的关系
            {"id": "rel6", "type": "include", "from": "actor1", "to": "uc2"},  # 参与者不能是include源
            {"id": "rel7", "type": "association", "from": "uc1", "to": "uc3"},  # 用例之间不能关联
            {"id": "rel8", "type": "generalization", "from": "actor1", "to": "uc1"}  # 参与者与用例不能泛化
        ]
    }
    
    # 创建评估器
    evaluator = SemanticCorrectnessEvaluator(use_llm=False)
    results = evaluator.evaluate_diagram(test_diagram)
    
    # 理论计算
    total_relationships = 8
    rule_violations = 3  # rel6, rel7, rel8
    expected_rule_score = (total_relationships - rule_violations) / total_relationships  # 5/8 = 0.625
    
    # 启发式层：8个关系都会被验证，假设发现1个问题
    heuristic_issues = 1
    expected_heuristic_score = (total_relationships - heuristic_issues) / total_relationships  # 7/8 = 0.875
    
    # 总体分数：规则层权重0.5，启发式层0.3，LLM层0.2（未启用=1.0）
    expected_overall = (expected_rule_score * 0.5 + expected_heuristic_score * 0.3 + 1.0 * 0.2)
    
    print(f"理论计算:")
    print(f"  总关系数: {total_relationships}")
    print(f"  规则违规数: {rule_violations}")
    print(f"  预期规则层分数: {expected_rule_score:.2%}")
    print(f"  预期启发式层分数: {expected_heuristic_score:.2%}")
    print(f"  预期总体分数: {expected_overall:.2%}")
    
    print(f"\n实际结果:")
    print(f"  规则层分数: {results['rule_based_score']:.2%}")
    print(f"  启发式层分数: {results['heuristic_score']:.2%}")
    print(f"  总体分数: {results['overall_score']:.2%}")
    
    # 验证摘要
    summary = results.get("validation_summary", {})
    rule_summary = summary.get("rule_based", {})
    heuristic_summary = summary.get("heuristic", {})
    
    print(f"\n规则层验证摘要:")
    if rule_summary:
        print(f"  总关系数: {rule_summary.get('total_relationships', 0)}")
        print(f"  违规数: {rule_summary.get('rule_violations', 0)}")
        print(f"  有效数: {rule_summary.get('valid_count', 0)}")
    
    print(f"\n启发式层验证摘要:")
    if heuristic_summary:
        print(f"  验证数: {heuristic_summary.get('total_validated', 0)}")
        print(f"  问题数: {heuristic_summary.get('heuristic_issues', 0)}")
    
    # 检查分数是否合理
    rule_score_correct = abs(results['rule_based_score'] - expected_rule_score) < 0.01
    heuristic_score_correct = abs(results['heuristic_score'] - expected_heuristic_score) < 0.01
    overall_score_correct = abs(results['overall_score'] - expected_overall) < 0.01
    
    print(f"\n分数验证:")
    print(f"  规则层分数: {'✅ 正确' if rule_score_correct else '❌ 错误'}")
    print(f"  启发式层分数: {'✅ 正确' if heuristic_score_correct else '❌ 错误'}")
    print(f"  总体分数: {'✅ 正确' if overall_score_correct else '❌ 错误'}")
    
    return all([rule_score_correct, heuristic_score_correct, overall_score_correct])

if __name__ == "__main__":
    success = test_scoring_logic()
    if success:
        print("\n✅ 所有分数计算正确！")
        sys.exit(0)
    else:
        print("\n❌ 分数计算有误")
        sys.exit(1)