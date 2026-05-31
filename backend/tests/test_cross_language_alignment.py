"""跨语言需求与用例图对齐"""
import sys
import unittest
from pathlib import Path

_backend_src = Path(__file__).resolve().parent.parent / "src"
if _backend_src.is_dir() and str(_backend_src) not in sys.path:
    sys.path.insert(0, str(_backend_src))

from services.evaluator.cross_language_alignment import (  # noqa: E402
    analyze_cross_language_context,
    relationship_plausible_under_cross_language,
)
from services.evaluator.evaluation_metrics import EvaluationMetrics  # noqa: E402


class TestCrossLanguageAlignment(unittest.TestCase):
    def test_detect_en_requirements_zh_diagram(self):
        diagram = {
            "actors": [{"id": "A1", "name": "Customer"}],
            "use_cases": [
                {"id": "U1", "name": "取款"},
                {"id": "U2", "name": "Validate PIN"},
            ],
            "relationships": [
                {"id": "R1", "from": "A1", "to": "U1", "type": "association"},
                {"id": "R2", "from": "U1", "to": "U2", "type": "include"},
            ],
        }
        requirements = {
            "roles": [{"name": "Customer"}],
            "functional_requirements": [
                {
                    "title": "Cash Withdrawal",
                    "text": "The system shall allow customers to withdraw money.",
                },
                {
                    "title": "ATM Login",
                    "text": "The system shall authenticate customers using card number and PIN.",
                },
            ],
        }
        ctx = analyze_cross_language_context(diagram, requirements)
        self.assertTrue(ctx.cross_language)
        self.assertTrue(
            relationship_plausible_under_cross_language(diagram, diagram["relationships"][0], ctx)
        )
        self.assertTrue(
            relationship_plausible_under_cross_language(diagram, diagram["relationships"][1], ctx)
        )

    def test_semantic_heuristic_suppressed_when_cross_language(self):
        metrics = EvaluationMetrics(use_real_llm=False)
        diagram = {
            "actors": [{"id": "A1", "name": "Customer"}],
            "use_cases": [
                {"id": "U1", "name": "取款"},
                {"id": "U2", "name": "存款"},
                {"id": "U3", "name": "Validate PIN"},
            ],
            "relationships": [
                {"id": "R1", "from": "A1", "to": "U1", "type": "association"},
                {"id": "R2", "from": "A1", "to": "U2", "type": "association"},
                {"id": "R3", "from": "U1", "to": "U3", "type": "include"},
            ],
        }
        requirements = {
            "roles": [{"name": "Customer"}],
            "functional_requirements": [
                {"text": "The system shall allow customers to withdraw money."},
                {"text": "The system shall allow customers to deposit money."},
                {"text": "The system shall authenticate customers using PIN."},
            ],
        }
        out = metrics.diagram_semantic_correctness(diagram, requirements)
        for issue in out.get("issues") or []:
            self.assertNotIn("可能不能启动用例", issue.get("description", ""))
        self.assertTrue(out.get("cross_language_alignment"))


if __name__ == "__main__":
    unittest.main()
