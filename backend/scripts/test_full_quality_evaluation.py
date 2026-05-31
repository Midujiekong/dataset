#!/usr/bin/env python3
"""
完整质量评估系统测试

输入：原始非规格需求文档、用例图 JSON、用例描述（文件或内置样例）
流程：原始需求（LLM 抽取）-> 用例图评估 + 用例描述评估（该用 LLM 的指标均使用 LLM）
输出：用例图/用例描述各维度分数、综合分、改进建议、问题统计；完整报告写入 test_output/

用法: python scripts/test_full_quality_evaluation.py
"""
import sys
import json
from pathlib import Path
from datetime import datetime

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from src.services.evaluator.evaluation_service import EvaluationService
from src.services.evaluator.requirements_parser import extract_structured_requirements


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_sample_descriptions():
    """用例描述测试样例（与常见用例图匹配：登录、验证凭据等）"""
    return [
        {
            "id": "uc_001",
            "name": "用户登录",
            "description": "用户使用用户名和密码登录系统",
            "actors": ["注册用户"],
            "preconditions": ["用户已注册账户", "用户知道自己的用户名和密码"],
            "postconditions": ["用户成功登录系统", "系统记录用户的登录状态", "用户被重定向到主页面"],
            "main_flow": [
                "1. 用户打开登录页面",
                "2. 用户在用户名输入框中输入用户名",
                "3. 用户在密码输入框中输入密码",
                "4. 用户点击登录按钮",
                "5. 系统验证用户凭据",
                "6. 系统显示登录成功消息",
                "7. 系统重定向用户到主页面",
            ],
            "alternative_flows": [
                {
                    "name": "用户名或密码错误",
                    "condition": "第5步中，用户名或密码验证失败",
                    "return_to_step": 5,
                    "steps": [
                        "5a. 系统显示错误消息：用户名或密码不正确",
                        "5b. 系统清空密码输入框",
                        "5c. 用户可以重新输入凭据",
                    ],
                },
            ],
            "priority": "high",
        },
        {
            "id": "uc_002",
            "name": "验证用户凭据",
            "description": "验证用户提供的用户名和密码是否正确",
            "actors": ["系统"],
            "preconditions": ["用户已输入用户名和密码", "系统数据库正常运行"],
            "postconditions": ["用户凭据被验证", "验证结果被返回"],
            "main_flow": [
                "1. 系统从登录请求中获取用户名和密码",
                "2. 系统在用户数据库中查找对应的用户记录",
                "3. 系统比较输入的密码与存储的密码哈希值",
                "4. 系统检查账户状态是否正常",
                "5. 系统返回验证结果",
            ],
            "alternative_flows": [],
            "priority": "medium",
        },
    ]


def run_full_quality_evaluation():
    """运行完整质量评估：原始需求（LLM 抽取）-> 用例图 + 用例描述评估（该用 LLM 处均用）"""
    test_data_dir = current_dir / "tests" / "test_data"
    raw_path = test_data_dir / "sample_requirements_raw_v2.md"
    diagram_path = test_data_dir / "sample_diagram_v2.json"
    desc_path = test_data_dir / "sample_descriptions.json"

    if not diagram_path.exists():
        diagram_path = test_data_dir / "sample_diagram.json"
    if not raw_path.exists():
        print(f"未找到原始需求文件: {raw_path}")
        sys.exit(1)

    raw_text = raw_path.read_text(encoding="utf-8")
    diagram = load_json(diagram_path)
    if desc_path.exists():
        data = load_json(desc_path)
        descriptions = data if isinstance(data, list) else data.get("use_case_descriptions", data.get("descriptions", []))
    else:
        descriptions = create_sample_descriptions()

    structured_requirements = extract_structured_requirements(raw_text, use_llm=True)
    service = EvaluationService(use_llm=True)
    input_data = {
        "use_case_diagram": diagram,
        "use_case_descriptions": descriptions,
        "requirements": structured_requirements,
    }
    report = service.evaluate(input_data)
    return report, diagram, descriptions, structured_requirements


def print_report(report: dict):
    """打印质量评估结果摘要（无冗余输出）"""
    dm = report.get("diagram_metrics", {})
    desc_m = report.get("description_metrics", {})

    print("\n【用例图】")
    print(f"  总体得分: {dm.get('overall_score', 0):.2%}")
    dim_names = (
        ("correctness", "正确性"),
        ("clarity", "明确性"),
        ("consistency", "一致性"),
        ("completeness", "完整性"),
        ("verifiability", "可验证性"),
        ("modifiability", "可修改性"),
        ("traceability", "可追溯性"),
    )
    for key, name in dim_names:
        d = dm.get(key, {})
        if isinstance(d, dict) and "overall" in d:
            print(f"    {name}: {d['overall']:.2%}")

    print("\n【用例描述】")
    print(f"  总体得分: {desc_m.get('overall_score', 0):.2%}")
    desc_dim_names = (
        ("correctness", "正确性"),
        ("clarity", "明确性"),
        ("consistency", "一致性"),
        ("completeness", "完整性"),
        ("verifiability", "可验证性"),
        ("modifiability", "可修改性"),
        ("traceability", "可追溯性"),
    )
    for key, name in desc_dim_names:
        d = desc_m.get(key, {})
        if isinstance(d, dict) and "overall" in d:
            print(f"    {name}: {d['overall']:.2%}")

    print("\n【综合】")
    print(f"  综合总体得分: {report.get('overall_score', 0):.2%}")

    rec = report.get("recommendations", [])
    if rec:
        print("\n改进建议:")
        for i, r in enumerate(rec[:8], 1):
            print(f"  {i}. {r}")
    else:
        print("\n改进建议: 暂无。")

    # 问题统计
    all_issues = []
    skip_keys = ("overall_score", "individual_scores")
    for dim in list(dm.keys()) + list(desc_m.keys()):
        if dim in skip_keys:
            continue
        d = dm.get(dim) or desc_m.get(dim)
        if isinstance(d, dict):
            all_issues.extend(d.get("issues", []))
    if all_issues:
        type_count = {}
        for iss in all_issues:
            if isinstance(iss, dict):
                t = iss.get("issue_type", "unknown")
                type_count[t] = type_count.get(t, 0) + 1
        print(f"\n问题统计: 共 {len(all_issues)} 条")
        for t, c in sorted(type_count.items(), key=lambda x: -x[1]):
            print(f"  - {t}: {c} 条")
    print()


def main():
    import os
    print("完整质量评估系统测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if os.getenv("DEEPSEEK_API_KEY"):
        print("已检测到 DEEPSEEK_API_KEY，将使用 LLM 进行抽取与评估")
    else:
        print("未设置 DEEPSEEK_API_KEY，需求抽取与评估中的 LLM 调用将失败")

    try:
        report, diagram, descriptions, requirements = run_full_quality_evaluation()
    except Exception as e:
        print("\n" + "=" * 60)
        print("评估过程出错，请检查：")
        print("  1. 环境变量 DEEPSEEK_API_KEY 是否已设置且有效")
        print("  2. 网络是否可访问 api.deepseek.com")
        print("  3. 下方堆栈信息")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1

    print("\n📊 输入统计:")
    print(f"  • 原始需求: 已抽取 -> 角色 {len(requirements.get('roles', []))}, 功能需求 {len(requirements.get('functional_requirements', []))}")
    print(f"  • 用例图: 参与者 {len(diagram.get('actors', []))}, 用例 {len(diagram.get('use_cases', []))}, 关系 {len(diagram.get('relationships', []))}")
    print(f"  • 用例描述: {len(descriptions)} 条")

    print_report(report)

    out_dir = current_dir / "test_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"full_quality_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"📁 完整报告已保存: {out_file}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
