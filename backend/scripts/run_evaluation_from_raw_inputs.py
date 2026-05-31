#!/usr/bin/env python3
"""
质量评估端到端脚本

输入：原始非规格需求文档、用例图 JSON、用例描述 JSON
输出：完整质量评估结果（控制台摘要 + JSON 报告文件）

用法示例：
  python scripts/run_evaluation_from_raw_inputs.py
  python scripts/run_evaluation_from_raw_inputs.py --raw tests/test_data/my_req.md --diagram tests/test_data/my_diagram.json --desc tests/test_data/my_desc.json
  python scripts/run_evaluation_from_raw_inputs.py --llm          # 评估时启用 LLM
  python scripts/run_evaluation_from_raw_inputs.py --llm-extract   # 需求抽取时启用 LLM
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from src.services.evaluator.evaluation_service import EvaluationService
from src.services.evaluator.requirements_parser import extract_structured_requirements


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_descriptions(path: Path):
    data = load_json(path)
    if isinstance(data, list):
        return data
    return data.get("use_case_descriptions", data.get("descriptions", []))


def main():
    parser = argparse.ArgumentParser(description="从原始需求文档 + 用例图 + 用例描述 运行质量评估")
    parser.add_argument("--raw", type=str, default=None, help="原始需求文档路径（.md/.txt）")
    parser.add_argument("--diagram", type=str, default=None, help="用例图 JSON 路径")
    parser.add_argument("--desc", type=str, default=None, help="用例描述 JSON 路径（可选）")
    parser.add_argument("--out", type=str, default=None, help="评估结果 JSON 输出路径（默认 test_output/evaluation_report_<时间>.json）")
    parser.add_argument("--llm", action="store_true", help="评估阶段使用 LLM")
    parser.add_argument("--llm-extract", action="store_true", help="需求抽取阶段使用 LLM")
    args = parser.parse_args()

    test_data_dir = current_dir / "tests" / "test_data"
    raw_path = Path(args.raw) if args.raw else (test_data_dir / "sample_requirements_raw_v2.md")
    diagram_path = Path(args.diagram) if args.diagram else (test_data_dir / "sample_diagram_v2.json")
    if not diagram_path.exists():
        diagram_path = test_data_dir / "sample_diagram.json"
    desc_path = Path(args.desc) if args.desc else (test_data_dir / "sample_descriptions.json")

    if not raw_path.exists():
        print(f"错误：未找到原始需求文件 {raw_path}")
        sys.exit(1)
    if not diagram_path.exists():
        print(f"错误：未找到用例图文件 {diagram_path}")
        sys.exit(1)

    raw_text = raw_path.read_text(encoding="utf-8")
    diagram = load_json(diagram_path)
    descriptions = load_descriptions(desc_path) if desc_path.exists() else []

    # 需求抽取（从非规格文档 -> 结构化需求）
    structured_requirements = extract_structured_requirements(raw_text, use_llm=args.llm_extract)

    # 质量评估
    service = EvaluationService(use_llm=args.llm)
    input_data = {
        "use_case_diagram": diagram,
        "use_case_descriptions": descriptions,
        "requirements": structured_requirements,
    }
    report = service.evaluate(input_data)

    # ---------- 控制台输出：评估效果摘要 ----------
    print()
    print("=" * 70)
    print("  质量评估结果摘要")
    print("=" * 70)
    print(f"  输入: 原始需求 {raw_path.name} | 用例图 {diagram_path.name} | 用例描述 {len(descriptions)} 条")
    print(f"  抽取: 项目名「{structured_requirements.get('project_name', '')}」| 角色 {len(structured_requirements.get('roles', []))} | 功能需求 {len(structured_requirements.get('functional_requirements', []))}")
    print("=" * 70)

    dm = report.get("diagram_metrics", {})
    if isinstance(dm, dict):
        overall_d = dm.get("overall_score", 0)
        print("\n【用例图】")
        print(f"  总体得分: {overall_d:.2%}")
        for dim in ("correctness", "clarity", "consistency", "completeness", "verifiability", "modifiability", "traceability"):
            d = dm.get(dim, {})
            if isinstance(d, dict) and "overall" in d:
                name = {"correctness": "正确性", "clarity": "明确性", "consistency": "一致性", "completeness": "完整性",
                        "verifiability": "可验证性", "modifiability": "可修改性", "traceability": "可追溯性"}.get(dim, dim)
                print(f"    {name}: {d['overall']:.2%}")

    desc_m = report.get("description_metrics", {})
    if isinstance(desc_m, dict) and (descriptions or desc_m.get("overall_score") is not None):
        overall_desc = desc_m.get("overall_score", 0)
        print("\n【用例描述】")
        print(f"  总体得分: {overall_desc:.2%}")
        for dim in ("correctness", "clarity", "consistency", "completeness", "verifiability", "modifiability", "traceability"):
            d = desc_m.get(dim, {})
            if isinstance(d, dict) and "overall" in d:
                name = {"correctness": "正确性", "clarity": "明确性", "consistency": "一致性", "completeness": "完整性",
                        "verifiability": "可验证性", "modifiability": "可修改性", "traceability": "可追溯性"}.get(dim, dim)
                print(f"    {name}: {d['overall']:.2%}")

    overall = report.get("overall_score", 0)
    print("\n【综合】")
    print(f"  综合总体得分: {overall:.2%}")
    print("=" * 70)

    rec = report.get("recommendations", [])
    if rec:
        print("\n改进建议:")
        for i, r in enumerate(rec[:10], 1):
            print(f"  {i}. {r}")
    else:
        print("\n暂无改进建议。")
    print()

    # ---------- 写入 JSON 报告 ----------
    out_dir = current_dir / "test_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.out:
        out_file = Path(args.out)
    else:
        out_file = out_dir / f"evaluation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"完整评估报告已保存: {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
