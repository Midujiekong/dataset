#!/usr/bin/env python3
"""
端到端测试：从原始需求文档到用例图/用例描述质量评估

- 输入：非规格化需求文档（如 Markdown/纯文本）、用例图 JSON、用例描述 JSON
- 流程：原始需求 -> 需求抽取(规则或LLM) -> 结构化需求 -> 用例图+用例描述质量评估(规则+LLM)
- 不使用已规格化的 sample_requirements.json，需求一律从原始文档抽取。
"""
import sys
import json
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from src.services.evaluator.evaluation_service import EvaluationService
from src.services.evaluator.requirements_parser import extract_structured_requirements


def load_raw_requirements(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    test_data_dir = current_dir / "tests" / "test_data"
    raw_path = test_data_dir / "sample_requirements_raw_v2.md"
    diagram_path = test_data_dir / "sample_diagram_v2.json"
    descriptions_path = test_data_dir / "sample_descriptions.json"

    if not raw_path.exists():
        print(f"未找到原始需求文件: {raw_path}")
        sys.exit(1)
    if not diagram_path.exists():
        diagram_path = test_data_dir / "sample_diagram.json"
    if not descriptions_path.exists():
        descriptions_path = None

    raw_text = load_raw_requirements(raw_path)
    with open(diagram_path, "r", encoding="utf-8") as f:
        diagram = json.load(f)
    descriptions = []
    if descriptions_path and descriptions_path.exists():
        with open(descriptions_path, "r", encoding="utf-8") as f:
            descriptions = json.load(f)

    use_llm = "--llm" in sys.argv
    use_llm_extract = "--llm-extract" in sys.argv

    print("=" * 60)
    print("端到端测试：原始需求 -> 抽取 -> 评估")
    print("=" * 60)
    print(f"原始需求文件: {raw_path.name} ({len(raw_text)} 字)")
    print(f"用例图: {diagram_path.name} (参与者 {len(diagram.get('actors', []))}, 用例 {len(diagram.get('use_cases', []))})")
    print(f"用例描述条数: {len(descriptions)}")
    print(f"评估使用 LLM: {use_llm}")
    print(f"抽取使用 LLM: {use_llm_extract}")
    print("=" * 60)

    structured = extract_structured_requirements(raw_text, use_llm=use_llm_extract)
    print("\n抽取结果摘要:")
    print(f"  项目名: {structured.get('project_name', '')}")
    print(f"  角色数: {len(structured.get('roles', []))}")
    print(f"  功能需求数: {len(structured.get('functional_requirements', []))}")
    print(f"  预期关系数: {len(structured.get('expected_relationships', []))}")

    service = EvaluationService(use_llm=use_llm)
    input_data = {
        "use_case_diagram": diagram,
        "use_case_descriptions": descriptions,
        "requirements": structured,
    }
    report = service.evaluate(input_data)

    dm = report.get("diagram_metrics", {})
    if isinstance(dm, dict):
        print("\n评估结果:")
        print(f"  用例图总体分: {dm.get('overall_score', 0):.2%}")
    desc_m = report.get("description_metrics") or {}
    if isinstance(desc_m, dict):
        print(f"  用例描述总体分: {desc_m.get('overall_score', 0):.2%}")
    print(f"  综合总体分: {report.get('overall_score', 0):.2%}")

    rec = report.get("recommendations", [])
    if rec:
        print("\n改进建议 (前 5 条):")
        for i, r in enumerate(rec[:5], 1):
            print(f"  {i}. {r}")

    out_file = current_dir / "test_output" / "e2e_raw_requirements_result.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n完整结果已写入: {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
