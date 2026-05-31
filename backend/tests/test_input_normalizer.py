"""input_normalizer 單元測試（python -m unittest tests.test_input_normalizer）"""
import sys
import unittest
from pathlib import Path

_backend_src = Path(__file__).resolve().parent.parent / "src"
if _backend_src.is_dir() and str(_backend_src) not in sys.path:
    sys.path.insert(0, str(_backend_src))

from services.evaluator.evaluation_metrics import EvaluationMetrics  # noqa: E402
from services.evaluator.input_normalizer import (  # noqa: E402
    extract_external_roles_from_requirements,
    is_internal_system_component_role_name,
    normalize_diagram,
    normalize_evaluation_payload,
    normalize_requirements,
    normalize_use_case_descriptions,
    should_exclude_from_external_actor_role,
)


class TestInputNormalizer(unittest.TestCase):
    def test_diagram_rel_types_lower(self):
        d = {
            "relationships": [
                {"type": "Association", "from": "A1", "to": "U1"},
                {"type": "Include", "from": "U1", "to": "U0"},
            ]
        }
        out = normalize_diagram(d)
        self.assertEqual(out["relationships"][0]["type"], "association")
        self.assertEqual(out["relationships"][1]["type"], "include")

    def test_diagram_relationship_source_target_normalized(self):
        raw = {
            "actors": [{"id": "A1", "name": "User"}],
            "use_cases": [{"id": "U1", "name": "Login"}],
            "relationships": [
                {"type": "Association", "source": "A1", "target": "U1"},
                {"type": "include", "source": "U1", "target": "U2"},
            ],
        }
        out = normalize_diagram(raw)
        rels = out["relationships"]
        self.assertEqual(rels[0]["from"], "A1")
        self.assertEqual(rels[0]["to"], "U1")
        self.assertEqual(rels[0]["type"], "association")
        self.assertEqual(rels[1]["from"], "U1")
        self.assertEqual(rels[1]["to"], "U2")
        self.assertTrue(rels[0].get("id"))

    def test_descriptions_use_cases_camel_case_wrapper(self):
        raw = {
            "useCases": [
                {"id": "UC-01", "name": "Withdraw Cash", "main_flow": []},
                {"id": "UC-02", "name": "Deposit Cash", "main_flow": []},
            ]
        }
        lst = normalize_use_case_descriptions(raw)
        self.assertEqual(len(lst), 2)
        self.assertEqual(lst[0]["name"], "Withdraw Cash")

    def test_descriptions_use_cases_wrapper_and_main_flow(self):
        raw = {
            "use_cases": [
                {
                    "id": "UC-01",
                    "name": "Withdraw",
                    "main_flow": [
                        {"id": "MF-01", "actor": "Customer", "action": "Selects withdraw"},
                        {"id": "MF-02", "actor": "System", "action": "Validates PIN"},
                    ],
                    "alternative_flows": [
                        {
                            "id": "AF-03",
                            "condition": "Insufficient balance",
                            "steps": [
                                "System shows error (MF-02 return_to_step) or cancel",
                            ],
                        }
                    ],
                }
            ]
        }
        lst = normalize_use_case_descriptions(raw)
        self.assertEqual(len(lst), 1)
        self.assertTrue(all(isinstance(s, str) for s in lst[0]["main_flow"]))
        self.assertIn("Customer:", lst[0]["main_flow"][0])
        alts = lst[0]["alternative_flows"]
        self.assertEqual(alts[0].get("return_to_step"), 2)

    def test_requirements_goal_level_and_expected_assoc(self):
        diagram = normalize_diagram(
            {
                "title": "ATM",
                "actors": [{"id": "Actor-001", "name": "Customer"}],
                "use_cases": [{"id": "UC-01", "name": "Withdraw Cash"}],
                "relationships": [
                    {"type": "Association", "from": "Actor-001", "to": "UC-01"}
                ],
            }
        )
        req_in = {
            "goal_level_requirements": [
                {
                    "id": "FR-01",
                    "title": "Cash Withdrawal",
                    "description": "Allow withdraw.",
                    "priority": "Critical",
                    "source": "SourceCode",
                }
            ],
            "interaction_level_requirements": [{"id": "FR-01-1", "parent": "FR-01"}],
            "non_functional_requirements": [],
        }
        req_out = normalize_requirements(req_in, diagram)
        self.assertEqual(req_out["project_name"], "ATM")
        self.assertEqual(len(req_out["roles"]), 1)
        self.assertEqual(req_out["roles"][0]["name"], "Customer")
        self.assertEqual(req_out["functional_requirements"][0]["text"], "Allow withdraw.")
        self.assertEqual(req_out["functional_requirements"][0]["priority"], "high")
        self.assertEqual(len(req_out["expected_relationships"]), 1)
        self.assertEqual(
            req_out["expected_relationships"][0],
            {"role": "Customer", "function": "Withdraw Cash", "type": "association"},
        )

    def test_goal_level_roles_exclude_subject_system_actor(self):
        diagram = normalize_diagram(
            {
                "title": "银行系统",
                "actors": [
                    {"id": "A1", "name": "Customer"},
                    {"id": "A2", "name": "银行系统"},
                ],
                "use_cases": [{"id": "U1", "name": "Login"}],
                "relationships": [],
            }
        )
        req_out = normalize_requirements(
            {
                "goal_level_requirements": [
                    {"id": "FR-01", "title": "Login", "description": "User logs in.", "priority": "High"}
                ]
            },
            diagram,
        )
        names = {r["name"] for r in req_out["roles"]}
        self.assertIn("Customer", names)
        self.assertNotIn("银行系统", names)

    def test_bank_database_not_external_actor(self):
        self.assertTrue(is_internal_system_component_role_name("Bank Database"))
        self.assertTrue(is_internal_system_component_role_name("银行数据库"))
        self.assertFalse(is_internal_system_component_role_name("Database Administrator"))
        self.assertFalse(is_internal_system_component_role_name("数据库管理员"))

    def test_requirements_roles_filter_internal_component(self):
        diagram = normalize_diagram({"title": "ATM System", "actors": [], "use_cases": []})
        req_out = normalize_requirements(
            {
                "roles": [
                    {"name": "Customer", "description": ""},
                    {"name": "Bank Database", "description": "stores accounts"},
                ],
                "functional_requirements": [],
            },
            diagram,
        )
        names = [r["name"] for r in req_out["roles"]]
        self.assertEqual(names, ["Customer"])

    def test_actor_completeness_excludes_bank_database(self):
        metrics = EvaluationMetrics(use_real_llm=False)
        diagram = {
            "title": "ATM System",
            "actors": [{"id": "A1", "name": "Customer"}],
            "use_cases": [],
        }
        requirements = {
            "project_name": "ATM System",
            "roles": [
                {"name": "Customer"},
                {"name": "Bank Database"},
            ],
        }
        result = metrics.diagram_actor_completeness(diagram, requirements)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["score"], 1.0)
        self.assertIn("Bank Database", ",".join(result.get("excluded_internal_component_roles", [])))

    def test_extract_customer_from_goal_level_without_diagram_actor(self):
        req_in = {
            "goal_level_requirements": [
                {
                    "id": "FR-01",
                    "title": "Cash Withdrawal",
                    "description": "The system shall allow customers to withdraw money.",
                    "priority": "High",
                }
            ],
        }
        diagram = {"title": "ATM", "actors": [], "use_cases": [{"id": "U1", "name": "取款"}]}
        req_out = normalize_requirements(req_in, diagram)
        names = [r["name"] for r in req_out["roles"]]
        self.assertIn("Customer", names)

    def test_actor_completeness_flags_missing_customer(self):
        metrics = EvaluationMetrics(use_real_llm=False)
        diagram = {
            "title": "ATM",
            "actors": [],
            "use_cases": [{"id": "U1", "name": "取款"}],
            "relationships": [],
        }
        requirements = normalize_requirements(
            {
                "goal_level_requirements": [
                    {
                        "id": "FR-01",
                        "title": "Withdraw",
                        "description": "The system shall allow customers to withdraw.",
                        "priority": "High",
                    }
                ]
            },
            diagram,
        )
        result = metrics.diagram_actor_completeness(diagram, requirements)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["score"], 0.0)
        self.assertTrue(any("Customer" in str(i.get("description", "")) for i in result.get("issues", [])))

    def test_should_exclude_bank_database(self):
        diagram = {"title": "ATM System"}
        self.assertTrue(
            should_exclude_from_external_actor_role("Bank Database", diagram, "ATM System")
        )

    def test_full_payload(self):
        data = normalize_evaluation_payload(
            {
                "use_case_diagram": {
                    "relationships": [{"type": "Include", "from": "a", "to": "b"}],
                },
                "use_case_descriptions": {"use_cases": []},
                "requirements": {"goal_level_requirements": []},
            }
        )
        self.assertEqual(data["use_case_diagram"]["relationships"][0]["type"], "include")
        self.assertEqual(data["use_case_descriptions"], [])


if __name__ == "__main__":
    unittest.main()
