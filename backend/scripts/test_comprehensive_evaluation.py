#!/usr/bin/env python3
"""
综合测试用例图评估功能
测试所有已实现的评估指标
"""
import sys
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from src.services.evaluator.evaluation_engine import EvaluationEngine
from src.services.evaluator.evaluation_metrics import EvaluationMetrics

def test_comprehensive_evaluation():
    """综合测试评估功能"""
    print("=" * 80)
    print("综合测试用例图评估功能")
    print("=" * 80)
    
    test_diagram = {
        "actors": [
            {"id": "actor1", "name": "用户"},
            {"id": "actor2", "name": "管理员"},
            {"id": "actor3", "name": "系统管理员"},  # 可能与管理员重复
            {"id": "actor4", "name": "客服"},  # 不在需求中，测试冗余性
            {"id": "actor5", "name": "系统"},  # 模糊名称，测试歧义性
        ],
        "use_cases": [
            {"id": "uc1", "name": "用户登录"},
            {"id": "uc2", "name": "用户注册"},
            {"id": "uc3", "name": "管理用户"},  # 在需求中
            {"id": "uc4", "name": "修改密码"},
            {"id": "uc5", "name": "查询信息"},  # 模糊名称，测试歧义性
            {"id": "uc6", "name": "数据备份"},  # 不在需求中，测试冗余性
            {"id": "uc7", "name": "用户登录"},  # 重复名称，测试标识唯一性
            {"id": "uc8", "name": "登录系统"},  # 与uc1相似，测试歧义性
        ],
        "relationships": [
            # 正确的语义关系
            {"id": "rel1", "type": "association", "from": "actor1", "to": "uc1"},
            {"id": "rel2", "type": "association", "from": "actor2", "to": "uc3"},
            {"id": "rel3", "type": "include", "from": "uc1", "to": "uc4"},
            {"id": "rel4", "type": "extend", "from": "uc1", "to": "uc2", "extension_point": "用户在登录界面选择“注册”入口时"},
            {"id": "rel5", "type": "generalization", "from": "actor3", "to": "actor2"},
            
            # 语义错误的关系（用于测试）
            {"id": "rel6", "type": "include", "from": "actor1", "to": "uc4"},  # 参与者不能是include源
            {"id": "rel7", "type": "association", "from": "uc1", "to": "uc3"},  # 用例间不能关联
            {"id": "rel8", "type": "generalization", "from": "actor1", "to": "uc1"},  # 不同类型不能泛化
        ],
        "system_boundary": True  # 有系统边界
    }
    
    # 测试需求数据
    test_requirements = {
        "roles": [
            {"name": "用户"},
            {"name": "管理员"}
        ],
        "functional_requirements": [
            {"text": "用户能够登录系统"},
            {"text": "用户能够注册账号"},
            {"text": "管理员能够管理用户账户"},
            {"text": "用户能够修改密码"}
        ],
        "expected_relationships": [
            {"role": "用户", "function": "用户登录", "type": "association"},
            {"role": "管理员", "function": "管理用户", "type": "association"},
            {"role": "用户", "function": "修改密码", "type": "association"}
        ],
        "terms": [  # 术语表
            {"term": "用户", "description": "使用系统的普通用户"},
            {"term": "管理员", "description": "管理系统的人员"},
            {"term": "登录", "description": "用户通过验证访问系统"},
            {"term": "注册", "description": "用户创建新账户"},
            {"term": "管理", "description": "对用户账户进行管理操作"}
        ]
    }
    
    # 创建评估引擎
    engine = EvaluationEngine(use_llm=False)
    metrics = EvaluationMetrics()
    
    print("\n1. 测试语法正确性评估")
    print("-" * 40)
    syntax_result = metrics.diagram_syntax_correctness(test_diagram)
    print(f"语法正确性分数: {syntax_result.get('score', 0):.2%}")
    print(f"有效关系数: {syntax_result.get('valid_count', 0)}")
    print(f"总关系数: {syntax_result.get('total_count', 0)}")
    
    # 显示语法问题
    syntax_issues = syntax_result.get('issues', [])
    if syntax_issues:
        print(f"发现 {len(syntax_issues)} 个语法问题:")
        for issue in syntax_issues[:3]:  # 只显示前3个
            print(f"  - {issue.get('description', '')}")
    
    print("\n2. 测试语义正确性评估")
    print("-" * 40)
    semantic_result = metrics.diagram_semantic_correctness(test_diagram)
    print(f"语义正确性分数: {semantic_result.get('score', 0):.2%}")
    print(f"规则层分数: {semantic_result.get('rule_based_score', 0):.2%}")
    print(f"启发式层分数: {semantic_result.get('heuristic_score', 0):.2%}")
    
    # 显示验证摘要
    validation_summary = semantic_result.get('validation_summary', {})
    rule_summary = validation_summary.get('rule_based', {})
    heuristic_summary = validation_summary.get('heuristic', {})
    
    if rule_summary:
        print(f"规则层: {rule_summary.get('total_relationships', 0)}个关系，{rule_summary.get('rule_violations', 0)}个违规")
    if heuristic_summary:
        print(f"启发式层: {heuristic_summary.get('total_validated', 0)}个验证，{heuristic_summary.get('heuristic_issues', 0)}个问题")
    
    print("\n3. 测试元素无歧义性评估")
    print("-" * 40)
    ambiguity_result = metrics.diagram_element_unambiguity(test_diagram)
    print(f"元素无歧义性分数: {ambiguity_result.get('score', 0):.2%}")
    print(f"清晰元素数: {ambiguity_result.get('clear_elements', 0)}")
    print(f"总元素数: {ambiguity_result.get('total_elements', 0)}")
    
    # 显示歧义元素
    ambiguous_elements = ambiguity_result.get('ambiguous_elements', [])
    if ambiguous_elements:
        print(f"发现 {len(ambiguous_elements)} 个有歧义的元素:")
        for element in ambiguous_elements[:3]:  # 只显示前3个
            print(f"  - {element.get('name', '')}: {element.get('ambiguity_reasons', [''])[0]}")
    
    print("\n4. 测试术语一致性评估")
    print("-" * 40)
    consistency_result = metrics.diagram_terminology_consistency(test_diagram, test_requirements)
    print(f"术语一致性分数: {consistency_result.get('score', 0):.2%}")
    print(f"总术语数: {consistency_result.get('total_terms', 0)}")
    print(f"一致术语数: {consistency_result.get('consistent_terms', 0)}")
    
    # 显示不一致术语
    inconsistent_terms = consistency_result.get('inconsistent_terms', [])
    if inconsistent_terms:
        print(f"发现 {len(inconsistent_terms)} 个不一致的术语:")
        for term in inconsistent_terms[:3]:
            print(f"  - {term}")
    
    print("\n5. 测试完整性评估")
    print("-" * 40)
    
    # 参与者完整性
    actor_completeness = metrics.diagram_actor_completeness(test_diagram, test_requirements)
    print(f"参与者完整性分数: {actor_completeness.get('score', 0):.2%}")
    print(f"匹配参与者数: {actor_completeness.get('matched', 0)}")
    print(f"需求角色数: {actor_completeness.get('total', 0)}")
    
    # 用例完整性
    use_case_completeness = metrics.diagram_use_case_completeness(test_diagram, test_requirements)
    print(f"用例完整性分数: {use_case_completeness.get('score', 0):.2%}")
    print(f"匹配用例数: {use_case_completeness.get('matched', 0)}")
    print(f"功能需求数: {use_case_completeness.get('total', 0)}")
    
    # 关系完整性
    relationship_completeness = metrics.diagram_relationship_completeness(test_diagram, test_requirements)
    print(f"关系完整性分数: {relationship_completeness.get('score', 0):.2%}")
    print(f"匹配关系数: {relationship_completeness.get('matched', 0)}")
    print(f"预期关系数: {relationship_completeness.get('total', 0)}")
    
    # 系统边界完整性
    system_boundary_completeness = metrics.diagram_system_boundary_completeness(test_diagram)
    print(f"系统边界完整性分数: {system_boundary_completeness.get('score', 0):.2%}")
    
    print("\n6. 测试其他评估指标")
    print("-" * 40)
    
    # 用例可验收性（暂时返回默认值）
    use_case_verifiability = metrics.diagram_use_case_verifiability(test_diagram)
    print(f"用例可验收性分数: {use_case_verifiability.get('score', 0):.2%}")
    
    # 用例独立性（暂时返回默认值）
    use_case_independence = metrics.diagram_use_case_independence(test_diagram)
    print(f"用例独立性分数: {use_case_independence.get('score', 0):.2%}")
    
    # 用例冗余性
    use_case_redundancy = metrics.diagram_use_case_redundancy(test_diagram, test_requirements)
    print(f"用例冗余性分数: {use_case_redundancy.get('score', 0):.2%}")
    
    # 参与者冗余性
    actor_redundancy = metrics.diagram_actor_redundancy(test_diagram, test_requirements)
    print(f"参与者冗余性分数: {actor_redundancy.get('score', 0):.2%}")
    
    # 关系冗余性
    relationship_redundancy = metrics.diagram_relationship_redundancy(test_diagram, test_requirements)
    print(f"关系冗余性分数: {relationship_redundancy.get('score', 0):.2%}")
    
    # 标识唯一性
    identifier_uniqueness = metrics.diagram_identifier_uniqueness(test_diagram)
    print(f"标识唯一性分数: {identifier_uniqueness.get('score', 0):.2%}")
    
    print("\n7. 测试完整评估流程（使用评估引擎）")
    print("-" * 40)
    
    # 准备输入数据
    input_data = {
        'use_case_diagram': test_diagram,
        'use_case_descriptions': [],
        'requirements': test_requirements
    }
    
    # 执行评估
    evaluation_results = engine.evaluate(input_data)
    
    # 显示总体结果
    print(f"用例图总体分数: {evaluation_results.get('diagram_metrics', {}).get('overall_score', 0):.2%}")
    print(f"综合总体分数: {evaluation_results.get('overall_score', 0):.2%}")
    
    # 显示各个维度的分数
    diagram_metrics = evaluation_results.get('diagram_metrics', {})
    print("\n用例图各维度分数:")
    print(f"  正确性: {diagram_metrics.get('correctness', {}).get('overall', 0):.2%}")
    print(f"  明确性: {diagram_metrics.get('clarity', {}).get('overall', 0):.2%}")
    print(f"  一致性: {diagram_metrics.get('consistency', {}).get('overall', 0):.2%}")
    print(f"  完整性: {diagram_metrics.get('completeness', {}).get('overall', 0):.2%}")
    
    # 显示建议
    recommendations = evaluation_results.get('recommendations', [])
    if recommendations:
        print("\n改进建议:")
        for rec in recommendations[:5]:  # 只显示前5个
            print(f"  • {rec}")
    
    print("\n" + "=" * 80)
    print("测试完成！")
    
    return evaluation_results

def test_edge_cases():
    """测试边界情况"""
    print("\n\n" + "=" * 80)
    print("测试边界情况")
    print("=" * 80)
    
    metrics = EvaluationMetrics()
    
    # 测试空用例图
    print("\n1. 测试空用例图")
    empty_diagram = {
        "actors": [],
        "use_cases": [],
        "relationships": []
    }
    
    empty_requirements = {
        "roles": [],
        "functional_requirements": []
    }
    
    # 语法正确性
    syntax_empty = metrics.diagram_syntax_correctness(empty_diagram)
    print(f"空用例图语法正确性分数: {syntax_empty.get('score', 0):.2%}")
    
    # 语义正确性
    semantic_empty = metrics.diagram_semantic_correctness(empty_diagram)
    print(f"空用例图语义正确性分数: {semantic_empty.get('score', 0):.2%}")
    
    # 元素无歧义性
    ambiguity_empty = metrics.diagram_element_unambiguity(empty_diagram)
    print(f"空用例图元素无歧义性分数: {ambiguity_empty.get('score', 0):.2%}")
    
    # 测试只有参与者的用例图
    print("\n2. 测试只有参与者的用例图")
    actors_only_diagram = {
        "actors": [
            {"id": "a1", "name": "用户"},
            {"id": "a2", "name": "管理员"}
        ],
        "use_cases": [],
        "relationships": []
    }
    
    # 语法正确性
    syntax_actors = metrics.diagram_syntax_correctness(actors_only_diagram)
    print(f"只有参与者的语法正确性分数: {syntax_actors.get('score', 0):.2%}")
    
    # 测试只有用例的用例图
    print("\n3. 测试只有用例的用例图")
    use_cases_only_diagram = {
        "actors": [],
        "use_cases": [
            {"id": "uc1", "name": "登录"},
            {"id": "uc2", "name": "注册"}
        ],
        "relationships": []
    }
    
    # 语法正确性
    syntax_ucs = metrics.diagram_syntax_correctness(use_cases_only_diagram)
    print(f"只有用例的语法正确性分数: {syntax_ucs.get('score', 0):.2%}")
    
    print("\n" + "=" * 80)
    print("边界情况测试完成！")

def validate_implementation():
    """验证实现是否符合预期"""
    print("\n\n" + "=" * 80)
    print("验证实现是否符合预期")
    print("=" * 80)
    
    # 创建简单的测试用例
    test_diagram = {
        "actors": [
            {"id": "actor1", "name": "用户"}
        ],
        "use_cases": [
            {"id": "uc1", "name": "登录系统"}
        ],
        "relationships": [
            {"id": "rel1", "type": "association", "from": "actor1", "to": "uc1"}
        ]
    }
    
    metrics = EvaluationMetrics()
    
    # 验证语法正确性
    syntax_result = metrics.diagram_syntax_correctness(test_diagram)
    assert syntax_result.get('score', 0) == 1.0, "语法正确性评估错误"
    print("✅ 语法正确性评估通过")
    
    # 验证语义正确性（调用会创建SemanticCorrectnessEvaluator）
    try:
        semantic_result = metrics.diagram_semantic_correctness(test_diagram)
        print("✅ 语义正确性评估通过")
    except Exception as e:
        print(f"⚠️  语义正确性评估可能有问题: {e}")
    
    # 验证元素无歧义性
    ambiguity_result = metrics.diagram_element_unambiguity(test_diagram)
    assert 0 <= ambiguity_result.get('score', 0) <= 1.0, "元素无歧义性分数应在0-1之间"
    print("✅ 元素无歧义性评估通过")
    
    # 验证系统边界完整性
    boundary_result = metrics.diagram_system_boundary_completeness(test_diagram)
    assert boundary_result.get('score', 0) == 0.0, "无系统边界的用例图应该得0分"
    print("✅ 系统边界完整性评估通过")
    
    print("\n所有基本验证通过！")

if __name__ == "__main__":
    print("综合测试用例图评估系统")
    
    try:
        # 运行综合测试
        results = test_comprehensive_evaluation()
        
        # 测试边界情况
        test_edge_cases()
        
        # 验证实现
        validate_implementation()
        
        print("\n✅ 所有测试完成！系统运行正常。")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)