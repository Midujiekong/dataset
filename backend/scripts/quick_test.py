#!/usr/bin/env python3
"""
快速测试 - 最小化测试用例
"""
import sys
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from src.services.evaluator.evaluation_engine import EvaluationEngine

def quick_test():
    """快速测试"""
    # 最小化的测试数据
    test_data = {
        "use_case_diagram": {
            "actors": [
                {"id": "a1", "name": "用户"}
            ],
            "use_cases": [
                {"id": "uc1", "name": "登录"}
            ],
            "relationships": [
                {"id": "r1", "type": "association", "from": "a1", "to": "uc1"}
            ]
        },
        "use_case_descriptions": [
            {
                "id": "uc1",
                "name": "登录",
                "description": "用户登录系统",
                "main_flow": ["用户输入凭据", "系统验证", "登录成功"]
            }
        ],
        "requirements": {
            "roles": [{"name": "用户"}],
            "functional_requirements": [{"text": "用户登录系统"}],
            "expected_relationships": [{"role": "用户", "function": "登录", "type": "association"}]
        }
    }
    
    print("快速测试 - 最小化用例")
    print("-" * 40)
    
    engine = EvaluationEngine(use_llm=False)
    results = engine.evaluate(test_data)
    
    print(f"总体分数: {results.get('overall_score', 0):.2%}")
    
    # 检查语法正确性
    diagram_metrics = results.get("diagram_metrics", {})
    correctness = diagram_metrics.get("correctness", {})
    
    print(f"语法正确性: {correctness.get('syntax_correctness', 0):.2%}")
    print(f"语义正确性: {correctness.get('semantic_correctness', 0):.2%}")
    
    # 检查是否有问题
    issues = correctness.get("issues", [])
    if issues:
        print(f"发现问题: {len(issues)} 个")
    else:
        print("没有发现问题")
    
    return results

if __name__ == "__main__":
    quick_test()