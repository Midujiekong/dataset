#!/usr/bin/env python3
"""
最小化测试 - 验证基础功能
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

print("当前工作目录:", os.getcwd())
print("项目根目录:", current_dir)

# 尝试导入模块
try:
    print("\n尝试导入模块...")
    from src.services.evaluator.evaluation_engine import EvaluationEngine
    print("✅ 成功导入 EvaluationEngine")
    
    from src.services.evaluator.evaluation_metrics import EvaluationMetrics
    print("✅ 成功导入 EvaluationMetrics")
    
    from src.services.evaluator.semantic_matcher import WeakSemanticMatcher
    print("✅ 成功导入 WeakSemanticMatcher")
    
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("\n检查以下文件是否存在:")
    print(f"  1. {current_dir}/src/services/evaluator/evaluation_engine.py")
    print(f"  2. {current_dir}/src/services/evaluator/evaluation_metrics.py")
    print(f"  3. {current_dir}/src/services/evaluator/semantic_matcher.py")
    sys.exit(1)

# 运行最小化测试
def minimal_test():
    """最小化测试"""
    print("\n" + "=" * 60)
    print("最小化测试")
    print("=" * 60)
    
    # 创建最简单的测试数据
    test_data = {
        "use_case_diagram": {
            "actors": [
                {"id": "actor1", "name": "用户"}
            ],
            "use_cases": [
                {"id": "uc1", "name": "登录系统"}
            ],
            "relationships": [
                {"id": "rel1", "type": "association", "from": "actor1", "to": "uc1"}
            ]
        },
        "use_case_descriptions": [],
        "requirements": {
            "roles": [{"name": "用户"}],
            "functional_requirements": [{"text": "用户登录系统"}],
            "expected_relationships": [{"role": "用户", "function": "登录系统", "type": "association"}]
        }
    }
    
    try:
        # 创建评估引擎
        engine = EvaluationEngine(use_llm=False)
        print("✅ 成功创建评估引擎")
        
        # 执行评估
        results = engine.evaluate(test_data)
        print("✅ 成功执行评估")
        
        # 显示结果
        print(f"\n评估结果:")
        print(f"  总体分数: {results.get('overall_score', 0):.2%}")
        
        diagram_metrics = results.get('diagram_metrics', {})
        print(f"  用例图分数: {diagram_metrics.get('overall_score', 0):.2%}")
        
        correctness = diagram_metrics.get('correctness', {})
        print(f"  语法正确性: {correctness.get('syntax_correctness', 0):.2%}")
        
        # 显示问题
        issues = correctness.get('issues', [])
        if issues:
            print(f"\n发现问题 ({len(issues)} 个):")
            for issue in issues:
                if isinstance(issue, dict):
                    print(f"  - {issue.get('description', '')}")
        
        print("\n✅ 测试成功完成!")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    if minimal_test():
        print("\n✅ 所有测试通过！")
        sys.exit(0)
    else:
        print("\n❌ 测试失败")
        sys.exit(1)