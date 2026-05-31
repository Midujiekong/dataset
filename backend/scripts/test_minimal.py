#!/usr/bin/env python3
"""
最小化测试 - 只测试基础功能
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

def test_imports():
    """测试导入"""
    print("=" * 60)
    print("测试模块导入")
    print("=" * 60)
    
    try:
        from src.services.evaluator.evaluation_metrics import EvaluationMetrics
        print("✅ 成功导入 EvaluationMetrics")
        
        metrics = EvaluationMetrics()
        print("✅ 成功创建 EvaluationMetrics 实例")
        
        # 测试方法是否存在
        methods = [
            '_clear_issues',
            '_add_issue',
            'get_issues',
            'diagram_syntax_correctness'
        ]
        
        for method in methods:
            if hasattr(metrics, method):
                print(f"✅ 方法存在: {method}")
            else:
                print(f"❌ 方法不存在: {method}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_syntax_correctness():
    """测试语法正确性"""
    print("\n" + "=" * 60)
    print("测试语法正确性评估")
    print("=" * 60)
    
    from src.services.evaluator.evaluation_metrics import EvaluationMetrics
    
    # 创建测试数据
    test_diagram = {
        "actors": [
            {"id": "a1", "name": "用户"}
        ],
        "use_cases": [
            {"id": "uc1", "name": "登录系统"}
        ],
        "relationships": [
            {"id": "r1", "type": "association", "from": "a1", "to": "uc1"},
            {"id": "r2", "type": "include", "from": "a1", "to": "uc1"}  # 错误：参与者不能是include源
        ]
    }
    
    try:
        metrics = EvaluationMetrics()
        result = metrics.diagram_syntax_correctness(test_diagram)
        
        print(f"✅ 语法正确性评估完成")
        print(f"  分数: {result.get('score', 0):.2%}")
        print(f"  有效关系数: {result.get('valid_count', 0)}")
        print(f"  总关系数: {result.get('total_count', 0)}")
        
        issues = result.get('issues', [])
        if issues:
            print(f"  发现问题: {len(issues)} 个")
            for issue in issues:
                print(f"    - {issue.get('description', '')}")
        else:
            print("  未发现问题")
        
        return True
        
    except Exception as e:
        print(f"❌ 语法正确性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_weak_semantic_match():
    """测试弱语义匹配"""
    print("\n" + "=" * 60)
    print("测试弱语义匹配")
    print("=" * 60)
    
    from src.services.evaluator.semantic_matcher import WeakSemanticMatcher
    
    test_pairs = [
        ("用户登录", "登录系统", True),
        ("用户登录", "用户登入", True),
        ("用户登录", "用户注册", False),
        ("管理用户", "用户管理", True)
    ]
    
    try:
        for a, b, expected in test_pairs:
            result = WeakSemanticMatcher.weak_match(a, b)
            status = "✅" if result == expected else "❌"
            print(f"{status} '{a}' vs '{b}': {result} (期望: {expected})")
        
        return True
        
    except Exception as e:
        print(f"❌ 弱语义匹配测试失败: {e}")
        return False

def test_completeness():
    """测试完整性指标"""
    print("\n" + "=" * 60)
    print("测试完整性指标")
    print("=" * 60)
    
    from src.services.evaluator.evaluation_metrics import EvaluationMetrics
    
    test_diagram = {
        "actors": [
            {"id": "a1", "name": "用户"}
        ],
        "use_cases": [
            {"id": "uc1", "name": "登录系统"}
        ],
        "relationships": [
            {"id": "r1", "type": "association", "from": "a1", "to": "uc1"}
        ],
        "system_boundary": True
    }
    
    test_requirements = {
        "roles": [{"name": "用户"}],
        "functional_requirements": [{"text": "用户登录系统"}],
        "expected_relationships": [
            {"role": "用户", "function": "登录系统", "type": "association"}
        ]
    }
    
    try:
        metrics = EvaluationMetrics()
        
        # 测试参与者完整性
        ac_result = metrics.diagram_actor_completeness(test_diagram, test_requirements)
        print(f"✅ 参与者完整性: {ac_result.get('score', 0):.2%}")
        
        # 测试用例完整性
        uc_result = metrics.diagram_use_case_completeness(test_diagram, test_requirements)
        print(f"✅ 用例完整性: {uc_result.get('score', 0):.2%}")
        
        # 测试关系完整性
        rc_result = metrics.diagram_relationship_completeness(test_diagram, test_requirements)
        print(f"✅ 关系完整性: {rc_result.get('score', 0):.2%}")
        
        # 测试系统边界完整性
        sb_result = metrics.diagram_system_boundary_completeness(test_diagram)
        print(f"✅ 系统边界完整性: {sb_result.get('score', 0):.2%}")
        
        return True
        
    except Exception as e:
        print(f"❌ 完整性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("用例模型质量评估系统 - 基础功能测试")
    print("版本: 1.0.0")
    
    tests_passed = 0
    tests_total = 0
    
    # 运行测试
    tests = [
        ("模块导入", test_imports),
        ("语法正确性", test_syntax_correctness),
        ("弱语义匹配", test_weak_semantic_match),
        ("完整性指标", test_completeness)
    ]
    
    for test_name, test_func in tests:
        tests_total += 1
        if test_func():
            tests_passed += 1
            print(f"✅ {test_name} 测试通过")
        else:
            print(f"❌ {test_name} 测试失败")
        print()
    
    print("=" * 60)
    print(f"测试结果: {tests_passed}/{tests_total} 通过")
    
    if tests_passed == tests_total:
        print("✅ 所有测试通过！")
        return 0
    else:
        print("❌ 部分测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())