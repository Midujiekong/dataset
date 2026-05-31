#!/usr/bin/env python3
"""
运行 v2 测试样例

说明：
- v2 提供 raw 需求文本（sample_requirements_raw_v2.md）与期望结构化需求（expected_requirements_v2.json）。
- 评估引擎目前仍需要结构化 requirements；如果你实现了 requirements_extractor，
  也可以改用 requirements_text 走抽取路径。
"""

import sys
import json
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from src.services.evaluator.evaluation_engine import EvaluationEngine


def main() -> int:
    test_data_dir = current_dir / "tests" / "test_data"

    with open(test_data_dir / "sample_diagram_v2.json", "r", encoding="utf-8") as f:
        diagram = json.load(f)

    with open(test_data_dir / "expected_requirements_v2.json", "r", encoding="utf-8") as f:
        requirements = json.load(f)

    engine = EvaluationEngine(use_llm=False)
    results = engine.evaluate(
        {
            "use_case_diagram": diagram,
            "use_case_descriptions": [],
            "requirements": requirements,
        }
    )

    overall = results.get("overall_score", 0.0)
    diagram_score = results.get("diagram_metrics", {}).get("overall_score", 0.0)
    print(f"v2 overall_score: {overall:.2%}")
    print(f"v2 diagram_overall_score: {diagram_score:.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

