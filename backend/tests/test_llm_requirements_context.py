"""LLM 需求上下文构建（避免 [:20] 截断误报）"""
import json
import sys
import unittest
from pathlib import Path

_backend_src = Path(__file__).resolve().parent.parent / "src"
if _backend_src.is_dir() and str(_backend_src) not in sys.path:
    sys.path.insert(0, str(_backend_src))

from services.evaluator.evaluation_engine import (  # noqa: E402
    _issue_is_false_truncated_requirement_complaint,
)
from services.evaluator.llm_prompts import build_requirements_context_for_llm  # noqa: E402


class TestLlmRequirementsContext(unittest.TestCase):
    def test_functional_requirements_not_truncated_to_20_chars(self):
        requirements = {
            "project_name": "ATM",
            "roles": [{"name": "Customer", "description": ""}],
            "functional_requirements": [
                {
                    "id": "FR-01",
                    "title": "User Registration",
                    "text": "The system shall allow new users to register ATM accounts.",
                },
                {
                    "id": "FR-02",
                    "title": "ATM Login",
                    "text": "The system shall authenticate customers using card number and PIN.",
                },
            ],
        }
        body = build_requirements_context_for_llm(None, requirements)
        parsed = json.loads(body)
        texts = [f["text"] for f in parsed["functional_requirements"]]
        self.assertGreater(len(texts[0]), 40)
        self.assertGreater(len(texts[1]), 40)
        self.assertTrue(texts[0].endswith("register ATM accounts."))
        self.assertIn("card number and PIN", texts[1])

    def test_filter_false_truncated_complaint(self):
        bad = (
            "需求摘要中功能 'The system shall all' 和 'The system shall aut' 不完整，"
            "无法判断是否遗漏用例。建议补充完整需求描述以进一步验证。"
        )
        self.assertTrue(_issue_is_false_truncated_requirement_complaint(bad))
        good = "功能需求 FR-03 Cash Withdrawal 在用例图中无对应用例 Withdraw。"
        self.assertFalse(_issue_is_false_truncated_requirement_complaint(good))


if __name__ == "__main__":
    unittest.main()
