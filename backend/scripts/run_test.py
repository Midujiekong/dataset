#!/usr/bin/env python3
"""
测试脚本 - 运行评估系统的完整测试
"""
import sys
import os
import json
from pathlib import Path

# 添加项目根目录到Python路径
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from src.services.evaluator.evaluation_engine import EvaluationEngine

def load_test_data():
    """加载测试数据"""
    test_data_dir = current_dir / "tests" / "test_data"
    
    with open(test_data_dir / "sample_diagram.json", "r", encoding="utf-8") as f:
        diagram = json.load(f)
    
    with open(test_data_dir / "sample_descriptions.json", "r", encoding="utf-8") as f:
        descriptions = json.load(f)
    
    with open(test_data_dir / "sample_requirements.json", "r", encoding="utf-8") as f:
        requirements = json.load(f)
    
    return {
        "use_case_diagram": diagram,
        "use_case_descriptions": descriptions,
        "requirements": requirements
    }

def run_semantic_correctness_test():
    """运行语义正确性测试"""
    print("=" * 80)
    print("UML语义正确性测试")
    print("=" * 80)
    
    # 加载测试数据
    test_data = load_test_data()
    
    # 创建评估引擎（使用模拟LLM）
    print("\n创建评估引擎（模拟LLM模式）...")
    engine = EvaluationEngine(use_llm=False)
    
    # 执行评估
    print("执行评估...")
    results = engine.evaluate(test_data)
    
    # 显示关键结果
    diagram_metrics = results.get("diagram_metrics", {})
    correctness = diagram_metrics.get("correctness", {})
    
    print(f"\n语法正确性分数: {correctness.get('syntax_correctness', 0):.2%}")
    print(f"语义正确性分数: {correctness.get('semantic_correctness', 0):.2%}")
    print(f"整体正确性分数: {correctness.get('overall', 0):.2%}")
    
    # 显示语义错误详情
    issues = correctness.get("issues", [])
    semantic_issues = [issue for issue in issues 
                      if isinstance(issue, dict) and 
                      issue.get("issue_type") in ["semantic_error", "SYNTAX_ERROR"]]
    
    if semantic_issues:
        print(f"\n发现 {len(semantic_issues)} 个语义/语法问题:")
        for i, issue in enumerate(semantic_issues[:5], 1):  # 只显示前5个
            desc = issue.get('description', '')[:100] + "..." if len(issue.get('description', '')) > 100 else issue.get('description', '')
            print(f"  {i}. [{issue.get('severity', 0):.1f}] {issue.get('element_type', '')}: {desc}")
    else:
        print("\n没有发现语义/语法问题")
    
    # LLM验证结果
    llm_results = results.get("llm_validation_results", {})
    validated = llm_results.get("validated_relationships", [])
    
    if validated:
        print(f"\nLLM语义验证结果 (验证了 {len(validated)} 个关系):")
        valid_count = sum(1 for r in validated if r.get("is_valid", False))
        invalid_count = len(validated) - valid_count
        print(f"  有效: {valid_count} 个，无效: {invalid_count} 个")
        
        if invalid_count > 0:
            print("\n无效关系详情:")
            for result in validated:
                if not result.get("is_valid", True):
                    print(f"  - 关系 {result.get('relationship_id', '')}: {result.get('reason', '')}")
    
    # 保存完整结果
    output_dir = current_dir / "test_output"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "semantic_test_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n完整结果已保存到: {output_file}")
    
    return results

def run_complete_evaluation_test():
    """运行完整的评估测试"""
    print("\n" + "=" * 80)
    print("完整用例模型质量评估测试")
    print("=" * 80)
    
    # 加载测试数据
    test_data = load_test_data()
    
    # 创建评估引擎
    engine = EvaluationEngine(use_llm=False)
    
    # 执行完整评估
    results = engine.evaluate(test_data)
    
    # 显示总体结果
    overall_score = results.get("overall_score", 0)
    diagram_score = results.get("diagram_metrics", {}).get("overall_score", 0)
    description_score = results.get("description_metrics", {}).get("overall_score", 0)
    
    print(f"\n总体评估分数: {overall_score:.2%}")
    print(f"用例图评估分数: {diagram_score:.2%}")
    print(f"用例描述评估分数: {description_score:.2%}")
    
    # 显示质量特性分数
    print("\n用例图质量特性分数:")
    diagram_metrics = results.get("diagram_metrics", {})
    for metric in ["correctness", "clarity", "consistency", "completeness"]:
        score = diagram_metrics.get(metric, {}).get("overall", 0)
        print(f"  {metric}: {score:.2%}")
    
    # 显示建议
    recommendations = results.get("recommendations", [])
    if recommendations:
        print(f"\n改进建议 ({len(recommendations)} 条):")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")
    
    # 保存结果
    output_dir = current_dir / "test_output"
    output_file = output_dir / "complete_evaluation_results.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n完整评估报告已保存到: {output_file}")
    
    return results

def run_specific_test_cases():
    """运行特定的测试用例"""
    print("\n" + "=" * 80)
    print("特定测试用例验证")
    print("=" * 80)
    
    from src.services.evaluator.evaluation_metrics import EvaluationMetrics
    from src.services.evaluator.semantic_matcher import WeakSemanticMatcher
    
    # 测试弱语义匹配器
    print("\n1. 测试弱语义匹配器:")
    test_pairs = [
        ("用户登录", "登录系统"),
        ("用户登录", "用户登入"),
        ("用户登录", "用户登录系统"),
        ("管理用户", "用户管理")
    ]
    
    for a, b in test_pairs:
        result = WeakSemanticMatcher.weak_match(a, b)
        print(f"  '{a}' vs '{b}': {result}")
    
    # 测试特定的评估指标
    print("\n2. 测试用例图语法正确性:")
    metrics = EvaluationMetrics()
    
    # 创建一个简单的用例图
    test_diagram = {
        "actors": [{"id": "a1", "name": "用户"}],
        "use_cases": [{"id": "uc1", "name": "登录"}],
        "relationships": [
            {"id": "r1", "type": "association", "from": "a1", "to": "uc1"},
            {"id": "r2", "type": "include", "from": "a1", "to": "uc1"}  # 错误：参与者不能是include源
        ]
    }
    
    result = metrics.diagram_syntax_correctness(test_diagram)
    print(f"  语法正确性分数: {result.get('score', 0):.2%}")
    
    if result.get('issues'):
        print(f"  发现问题: {len(result['issues'])} 个")
        for issue in result['issues']:
            print(f"    - {issue.get('description', '')}")

def main():
    """主函数"""
    print("用例模型质量评估系统 - 测试套件")
    print("版本: 1.0.0")
    print("=" * 80)
    
    # 创建输出目录
    output_dir = current_dir / "test_output"
    output_dir.mkdir(exist_ok=True)
    
    # 运行测试
    try:
        # 1. 语义正确性测试
        run_semantic_correctness_test()
        
        # 2. 完整评估测试
        run_complete_evaluation_test()
        
        # 3. 特定测试用例
        run_specific_test_cases()
        
        print("\n" + "=" * 80)
        print("所有测试完成！")
        print(f"结果保存在: {output_dir}")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())