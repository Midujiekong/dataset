"""术语一致性：过滤苛刻误报、batch 结构"""
import sys
import unittest
from pathlib import Path

_backend_src = Path(__file__).resolve().parent.parent / "src"
if _backend_src.is_dir() and str(_backend_src) not in sys.path:
    sys.path.insert(0, str(_backend_src))

from services.evaluator.evaluation_metrics import EvaluationMetrics  # noqa: E402


class TestTerminologyConsistency(unittest.TestCase):
    def setUp(self):
        self.metrics = EvaluationMetrics(use_real_llm=False)

    def test_pedantic_reason_filtered(self):
        reason = (
            "用例图术语'修改密码'与标准术语表中的'change ATM PIN'含义不一致，"
            "'修改密码'可能指代更广泛的密码。"
        )
        self.assertTrue(self.metrics._is_pedantic_terminology_reason(reason))

    def test_validate_pin_authenticate_not_pedantic_filter(self):
        reason = "Validate PIN 与 authenticate customers using PIN 部分匹配"
        self.assertTrue(self.metrics._is_pedantic_terminology_reason(reason))

    def test_llm_payload_filters_pedantic_issues(self):
        res = {
            "score": 0.5,
            "llm_evaluations": [
                {
                    "term": "修改密码",
                    "is_consistent": False,
                    "reason": "与标准术语表中 change ATM PIN 含义不一致",
                },
                {"term": "Customer", "is_consistent": True},
            ],
            "inconsistent_terms": [],
        }
        out = self.metrics._terminology_result_from_llm_payload(res, ["修改密码", "Customer"])
        self.assertEqual(out["score"], 1.0)
        self.assertEqual(len(out["issues"]), 0)

    def test_rule_fallback_skips_term_table(self):
        diagram = {
            "actors": [{"name": "Customer"}],
            "use_cases": [{"name": "Validate PIN"}, {"name": "修改密码"}],
        }
        requirements = {
            "functional_requirements": [
                {"text": "The system shall authenticate customers using card number and PIN."},
                {"text": "The system shall allow customers to change ATM PIN."},
            ]
        }
        out = self.metrics.diagram_terminology_consistency(diagram, requirements)
        self.assertEqual(out["score"], 1.0)
        self.assertEqual(len(out.get("issues", [])), 0)
        self.assertIn("跳过", out.get("note", ""))


if __name__ == "__main__":
    unittest.main()
