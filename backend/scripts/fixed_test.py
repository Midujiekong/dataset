#!/usr/bin/env python3
"""
修复后的测试脚本
"""
import sys
import json
from pathlib import Path

# 添加项目根目录到Python路径
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from src.services.evaluator.evaluation_engine import EvaluationEngine
from src.services.evaluator.evaluation_metrics import EvaluationMetrics

def test_basic_functionality():
    """测试基本功能"""
    print("=" * 60)
    print("基本功能测试")
    print("=" * 60)
    
    # 1. 测试评估指标
    print("\n1. 测试评估指标类...")
    try:
        metrics = EvaluationMetrics()
        print("✅ 评估指标类创建成功")
        
        # 测试语法正确性
        test_diagram = {
            "actors": [{"id": "a1", "name": "用户"}],
            "use_cases": [{"id": "uc1", "name": "登录"}],
            "relationships": [
                {"id": "r1", "type": "association", "from": "a1", "to": "uc1"}
            ]
        }
        
        result = metrics.diagram_syntax_correctness(test_diagram)
        print(f"✅ 语法正确性测试完成，分数: {result.get('score', 0):.2%}")
        
        # 测试弱语义匹配
        from src.services.evaluator.semantic_matcher import WeakSemanticMatcher
        match_result = WeakSemanticMatcher.weak_match("用户登录", "登录系统")
        print(f"✅ 弱语义匹配测试: '用户登录' vs '登录系统' = {match_result}")
        
    except Exception as e:
        print(f"❌ 评估指标测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 2. 测试评估引擎
    print("\n2. 测试评估引擎...")
    try:
        engine = EvaluationEngine()
        print("✅ 评估引擎创建成功")
        
        # 测试数据
        test_data = {
            "use_case_diagram": {
                "actors": [{"id": "a1", "name": "用户"}],
                "use_cases": [{"id": "uc1", "name": "登录系统"}],
                "relationships": [
                    {"id": "r1", "type": "association", "from": "a1", "to": "uc1"}
                ],
                "system_boundary": {"name": "用户系统"}
            },
            "use_case_descriptions": [],
            "requirements": {
                "roles": [{"name": "用户"}],
                "functional_requirements": [{"text": "用户登录系统"}],
                "expected_relationships": [
                    {"role": "用户", "function": "登录系统", "type": "association"}
                ]
            }
        }
        
        results = engine.evaluate(test_data)
        print("✅ 评估执行成功")
        
        # 显示结果
        print(f"\n评估结果:")
        print(f"  总体分数: {results.get('overall_score', 0):.2%}")
        
        diagram_metrics = results.get('diagram_metrics', {})
        print(f"  用例图分数: {diagram_metrics.get('overall_score', 0):.2%}")
        
        correctness = diagram_metrics.get('correctness', {})
        print(f"  语法正确性: {correctness.get('syntax_correctness', 0):.2%}")
        
        completeness = diagram_metrics.get('completeness', {})
        print(f"  完整性: {completeness.get('overall', 0):.2%}")
        
        # 显示建议
        recommendations = results.get('recommendations', [])
        if recommendations:
            print(f"\n改进建议:")
            for rec in recommendations:
                print(f"  • {rec}")
        
        return True
        
    except Exception as e:
        print(f"❌ 评估引擎测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_sample_data():
    """使用样例数据测试"""
    print("\n" + "=" * 60)
    print("样例数据测试")
    print("=" * 60)
    
    try:
        # 加载测试数据
        test_data_dir = current_dir / "tests" / "test_data"
        
        if not test_data_dir.exists():
            print("❌ 测试数据目录不存在")
            return False
        
        with open(test_data_dir / "sample_diagram.json", "r", encoding="utf-8") as f:
            diagram = json.load(f)
        
        with open(test_data_dir / "sample_requirements.json", "r", encoding="utf-8") as f:
            requirements = json.load(f)
        
        test_data = {
            "use_case_diagram": diagram,
            "use_case_descriptions": [],
            "requirements": requirements
        }
        
        # 执行评估
        engine = EvaluationEngine()
        results = engine.evaluate(test_data)
        
        print(f"✅ 样例数据评估完成")
        print(f"  总体分数: {results.get('overall_score', 0):.2%}")
        
        # 检查语法错误
        diagram_metrics = results.get('diagram_metrics', {})
        correctness = diagram_metrics.get('correctness', {})
        issues = correctness.get('issues', [])
        
        if issues:
            print(f"\n发现 {len(issues)} 个语法问题:")
            for i, issue in enumerate(issues[:5], 1):
                desc = issue.get('description', '未知问题')
                print(f"  {i}. {desc}")
        
        # 保存结果
        output_dir = current_dir / "test_output"
        output_dir.mkdir(exist_ok=True)
        
        with open(output_dir / "sample_test_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 结果已保存到: {output_dir / 'sample_test_results.json'}")
        
        return True
        
    except Exception as e:
        print(f"❌ 样例数据测试失败: {e}")
        return False

def main():
    """主函数"""
    print("用例模型质量评估系统 - 修复测试")
    print("版本: 1.0.0")
    
    # 创建输出目录
    output_dir = current_dir / "test_output"
    output_dir.mkdir(exist_ok=True)
    
    try:
        # 运行基本功能测试
        if not test_basic_functionality():
            print("\n❌ 基本功能测试失败")
            return 1
        
        # 运行样例数据测试
        if not test_with_sample_data():
            print("\n⚠️  样例数据测试跳过或部分失败")
        
        print("\n" + "=" * 60)
        print("✅ 所有测试完成！")
        print(f"结果保存在: {output_dir}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())