"""语义正确性 issue 文案格式"""
import sys
import unittest
from pathlib import Path

_backend_src = Path(__file__).resolve().parent.parent / "src"
if _backend_src.is_dir() and str(_backend_src) not in sys.path:
    sys.path.insert(0, str(_backend_src))

from services.evaluator.evaluation_metrics import format_semantic_relationship_issue  # noqa: E402


class TestSemanticIssueFormat(unittest.TestCase):
    def test_no_generic_extend_include_boilerplate(self):
        loc = "关系「Deposit Cash - Validate PIN」（include）"
        out = format_semantic_relationship_issue(
            loc,
            reason="语义可能不当（如应 extend 却用了 include）",
            suggestion="",
        )
        self.assertNotIn("如应 extend", out)
        self.assertIn(loc, out)

    def test_specific_reason_preserved(self):
        loc = "关系「Deposit Cash - Validate PIN」（include）"
        out = format_semantic_relationship_issue(
            loc,
            reason="当前为 include，建议改为 extend：PIN 校验为存款的可选分支。",
            suggestion="将 include 改为 extend。",
        )
        self.assertIn("当前为 include", out)
        self.assertIn("建议改为 extend", out)


if __name__ == "__main__":
    unittest.main()
