#!/usr/bin/env python3
"""
专门测试分数计算逻辑
"""
import sys
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

def test_score_logic_directly():
    """直接测试分数计算逻辑"""
    print("分数计算逻辑测试")
    print("=" * 80)
    
    # 模拟测试数据
    test_cases = [
        {
            "name": "测试用例1：8个关系，3个规则违规，4个启发式问题",
            "total_relationships": 8,
            "rule_violations": 3,
            "heuristic_issues": 4,
            "expected_rule_score": (8-3)/8,  # 5/8 = 0.625
            "expected_heuristic_score": (8-4)/8,  # 4/8 = 0.5
            "expected_overall_no_llm": (8-3)/8 * 0.6 + (8-4)/8 * 0.4,  # 0.625*0.6 + 0.5*0.4 = 0.575
            "expected_overall_with_llm": (8-3)/8 * 0.5 + (8-4)/8 * 0.3 + 1.0 * 0.2  # 0.625*0.5 + 0.5*0.3 + 0.2 = 0.7125
        },
        {
            "name": "测试用例2：完美用例图",
            "total_relationships": 5,
            "rule_violations": 0,
            "heuristic_issues": 0,
            "expected_rule_score": 1.0,
            "expected_heuristic_score": 1.0,
            "expected_overall_no_llm": 1.0 * 0.6 + 1.0 * 0.4,  # 1.0
            "expected_overall_with_llm": 1.0 * 0.5 + 1.0 * 0.3 + 1.0 * 0.2  # 1.0
        },
        {
            "name": "测试用例3：全部错误",
            "total_relationships": 4,
            "rule_violations": 4,
            "heuristic_issues": 4,
            "expected_rule_score": 0.0,
            "expected_heuristic_score": 0.0,
            "expected_overall_no_llm": 0.0 * 0.6 + 0.0 * 0.4,  # 0.0
            "expected_overall_with_llm": 0.0 * 0.5 + 0.0 * 0.3 + 1.0 * 0.2  # 0.2（LLM层救了一点）
        }
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        print(f"\n{test_case['name']}:")
        print(f"  总关系数: {test_case['total_relationships']}")
        print(f"  规则违规数: {test_case['rule_violations']}")
        print(f"  启发式问题数: {test_case['heuristic_issues']}")
        
        # 计算规则层分数
        rule_score = (test_case['total_relationships'] - test_case['rule_violations']) / test_case['total_relationships']
        print(f"  计算规则层分数: {rule_score:.2%}")
        
        # 计算启发式层分数
        heuristic_score = (test_case['total_relationships'] - test_case['heuristic_issues']) / test_case['total_relationships']
        print(f"  计算启发式层分数: {heuristic_score:.2%}")
        
        # 不使用LLM的总体分数
        overall_no_llm = rule_score * 0.6 + heuristic_score * 0.4
        print(f"  不使用LLM的总体分数: {overall_no_llm:.2%}")
        
        # 使用LLM的总体分数
        overall_with_llm = rule_score * 0.5 + heuristic_score * 0.3 + 1.0 * 0.2
        print(f"  使用LLM的总体分数: {overall_with_llm:.2%}")
        
        # 验证
        rule_correct = abs(rule_score - test_case['expected_rule_score']) < 0.001
        heuristic_correct = abs(heuristic_score - test_case['expected_heuristic_score']) < 0.001
        overall_no_llm_correct = abs(overall_no_llm - test_case['expected_overall_no_llm']) < 0.001
        overall_with_llm_correct = abs(overall_with_llm - test_case['expected_overall_with_llm']) < 0.001
        
        if all([rule_correct, heuristic_correct, overall_no_llm_correct, overall_with_llm_correct]):
            print("  ✅ 分数计算正确")
        else:
            print("  ❌ 分数计算错误")
            all_passed = False
    
    return all_passed

def test_actual_evaluator():
    """测试实际的评估器"""
    print("\n" + "=" * 80)
    print("测试实际评估器")
    print("=" * 80)
    
    from src.services.evaluator.semantic_correctness_evaluator import SemanticCorrectnessEvaluator
    
    # 创建测试用例图
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
            {"id": "rel6", "type": "include", "from": "actor1", "to": "uc2"},
            {"id": "rel7", "type": "association", "from": "uc1", "to": "uc3"},
            {"id": "rel8", "type": "generalization", "from": "actor1", "to": "uc1"}
        ]
    }
    
    # 测试不使用LLM的评估器
    evaluator_no_llm = SemanticCorrectnessEvaluator(use_llm=False)
    results_no_llm = evaluator_no_llm.evaluate_diagram(test_diagram)
    
    print("不使用LLM的评估结果:")
    print(f"  规则层分数: {results_no_llm['rule_based_score']:.2%}")
    print(f"  启发式层分数: {results_no_llm['heuristic_score']:.2%}")
    print(f"  总体分数: {results_no_llm['overall_score']:.2%}")
    
    # 验证摘要
    summary = results_no_llm.get("validation_summary", {})
    rule_summary = summary.get("rule_based", {})
    heuristic_summary = summary.get("heuristic", {})
    
    print(f"\n规则层验证摘要:")
    print(f"  总关系数: {rule_summary.get('total_relationships', 0)}")
    print(f"  违规数: {rule_summary.get('rule_violations', 0)}")
    print(f"  规则层分数(摘要): {rule_summary.get('rule_score', 0):.2%}")
    
    print(f"\n启发式层验证摘要:")
    print(f"  验证数: {heuristic_summary.get('total_validated', 0)}")
    print(f"  问题数: {heuristic_summary.get('heuristic_issues', 0)}")
    print(f"  启发式层分数(摘要): {heuristic_summary.get('heuristic_score', 0):.2%}")
    
    # 理论计算
    total_relationships = 8
    rule_violations = rule_summary.get('rule_violations', 0)
    heuristic_issues = heuristic_summary.get('heuristic_issues', 0)
    
    expected_rule_score = (total_relationships - rule_violations) / total_relationships
    expected_heuristic_score = (total_relationships - heuristic_issues) / total_relationships
    expected_overall = expected_rule_score * 0.6 + expected_heuristic_score * 0.4
    
    print(f"\n理论计算:")
    print(f"  预期规则层分数: {expected_rule_score:.2%}")
    print(f"  预期启发式层分数: {expected_heuristic_score:.2%}")
    print(f"  预期总体分数: {expected_overall:.2%}")
    
    # 验证
    rule_match = abs(results_no_llm['rule_based_score'] - expected_rule_score) < 0.01
    heuristic_match = abs(results_no_llm['heuristic_score'] - expected_heuristic_score) < 0.01
    overall_match = abs(results_no_llm['overall_score'] - expected_overall) < 0.01
    
    print(f"\n验证结果:")
    print(f"  规则层分数: {'✅ 匹配' if rule_match else '❌ 不匹配'}")
    print(f"  启发式层分数: {'✅ 匹配' if heuristic_match else '❌ 不匹配'}")
    print(f"  总体分数: {'✅ 匹配' if overall_match else '❌ 不匹配'}")
    
    return all([rule_match, heuristic_match, overall_match])

if __name__ == "__main__":
    print("语义正确性评估分数计算测试")
    print("版本: 修复版")
    
    # 测试理论计算逻辑
    theoretical_passed = test_score_logic_directly()
    
    # 测试实际评估器
    actual_passed = test_actual_evaluator()
    
    if theoretical_passed and actual_passed:
        print("\n✅ 所有测试通过！")
        sys.exit(0)
    else:
        print("\n❌ 测试失败")
        sys.exit(1)