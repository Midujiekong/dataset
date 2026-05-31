"""
將前端/實驗統一輸入格式轉換為評估引擎既有結構。

支援：
- 需求：goal_level_requirements / interaction_level_requirements / non_functional_requirements
- 用例圖：關係 type 大小寫（Association → association）；關係端點支援 **source/target**（與 from/to 等價，常見於導出 JSON）
- 用例描述：{ "useCases": [...] } 或 { "use_cases": [...] } 包裝；main_flow 為 { id, actor, action } 物件；
  從備選流步驟文字推斷 return_to_step（如 MF-03 return_to_step）。
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Tuple


_REL_TYPE_MAP = {
    "association": "association",
    "include": "include",
    "extend": "extend",
    "generalization": "generalization",
}


def _norm_rel_type(t: Any) -> str:
    if not isinstance(t, str) or not t.strip():
        return "association"
    key = t.strip().lower()
    return _REL_TYPE_MAP.get(key, key)


def relationship_endpoints(rel: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """
    統一解析關係兩端 ID。
    常見變體：from/to（引擎內建）、source/target（UML 工具／專案標準樣例 图.json）、fromId/toId。
    """
    if not isinstance(rel, dict):
        return None, None

    def _pick(*keys: str) -> Optional[str]:
        for k in keys:
            v = rel.get(k)
            if v is None:
                continue
            s = str(v).strip()
            if s:
                return s
        return None

    fr = _pick("from", "source", "from_id", "fromId", "fromRef")
    to = _pick("to", "target", "to_id", "toId", "toRef")
    return fr, to


def _norm_priority(p: Any) -> str:
    if p is None:
        return "medium"
    s = str(p).strip().lower()
    if s in ("critical", "high", "must"):
        return "high"
    if s in ("medium", "med", "should"):
        return "medium"
    if s in ("low", "optional", "could"):
        return "low"
    return "medium"


def _norm_cmp_label(s: str) -> str:
    """比對系統邊界名、標題等時用的歸一化（去空白、大小寫）。"""
    return re.sub(r"[\s_\-]+", "", (s or "").strip().lower())


def _system_subject_reference_labels(
    diagram: Optional[Dict[str, Any]], project_name: Optional[str]
) -> set[str]:
    """從圖與專案名收集「待建系統」可能的名稱，用於排除誤當參與者的 actor/role。"""
    labs: set[str] = set()
    if project_name and str(project_name).strip():
        labs.add(_norm_cmp_label(str(project_name)))
    if not diagram or not isinstance(diagram, dict):
        return {x for x in labs if x}
    for key in ("title", "name"):
        v = diagram.get(key)
        if isinstance(v, str) and v.strip():
            labs.add(_norm_cmp_label(v))
    sb = diagram.get("system_boundary")
    if isinstance(sb, dict):
        for k in ("name", "title", "label"):
            v = sb.get(k)
            if isinstance(v, str) and v.strip():
                labs.add(_norm_cmp_label(v))
    elif isinstance(sb, str) and sb.strip():
        labs.add(_norm_cmp_label(sb))
    meta = diagram.get("diagram_metadata")
    if isinstance(meta, dict):
        for k in ("system_name", "name", "title", "system"):
            v = meta.get(k)
            if isinstance(v, str) and v.strip():
                labs.add(_norm_cmp_label(v))
    return {x for x in labs if x}


def is_subject_system_role_name(
    name: str,
    diagram: Optional[Dict[str, Any]],
    project_name: Optional[str],
    *,
    type_hint: Any = None,
) -> bool:
    """
    判斷名稱是否表示待建系統本體（不應計入「外部參與者完整性」分母）。
    規則：與 system_boundary / 圖 title / project_name 等引用一致；UML type 標為 System；
    僅為泛指的「系統」「System」亦排除。
    """
    name = (name or "").strip()
    if not name:
        return False
    n = _norm_cmp_label(name)
    if not n:
        return False

    th = (str(type_hint).strip().lower() if type_hint is not None else "")
    if th:
        if "system actor" in th.replace(" ", ""):
            return True
        if th in ("system", "subsystem") and "external" not in th:
            return True

    refs = _system_subject_reference_labels(diagram, project_name)
    for r in refs:
        if not r:
            continue
        if n == r:
            return True
        # 邊界名為前綴且餘字極短（如「銀行系統」與「銀行系統後台」同指一類）
        if len(r) >= 4 and n.startswith(r) and len(n) - len(r) <= 2:
            return True
        if len(n) >= 4 and r.startswith(n) and len(r) - len(n) <= 2:
            return True

    if n in {
        "系统",
        "系統",
        "system",
        "thesystem",
        "本系统",
        "本系統",
        "该系统",
        "該系統",
        "sut",
    } or name.strip() in ("系统", "系統", "System", "SUT"):
        return True
    return False


# 含此類詞且非「人員角色」時，視為系統邊界內組件（資料層、持久化等），非 UML Actor
_HUMAN_ACTOR_MARKERS = (
    "admin",
    "administrator",
    "operator",
    "manager",
    "analyst",
    "staff",
    "user",
    "customer",
    "client",
    "clerk",
    "teller",
    "person",
    "people",
    "管理员",
    "管理員",
    "操作员",
    "操作員",
    "客户",
    "客戶",
    "柜员",
    "櫃員",
    "用户",
    "用戶",
    "人员",
    "人員",
    "员",
    "員",
    "owner",
    "guest",
    "visitor",
    "driver",
    "patient",
    "student",
    "teacher",
    "医生",
    "醫生",
    "护士",
    "護士",
)

_INTERNAL_COMPONENT_SUBSTRINGS = (
    "database",
    "data base",
    "数据库",
    "資料庫",
    "repository",
    "仓储",
    "倉儲",
    "datastore",
    "data store",
    "存储服务",
    "存儲服務",
    "storageservice",
    "持久化",
    "persistence",
    "filesystem",
    "file system",
    "文件系统",
    "檔案系統",
    "messagequeue",
    "message queue",
    "消息队列",
    "訊息佇列",
    "middleware",
    "中间件",
    "中間件",
    "ledger",
    "总账",
    "總賬",
)

_INTERNAL_COMPONENT_EXACT_NORMS = frozenset(
    {
        "db",
        "bankdb",
        "bankdatabase",
        "centraldatabase",
        "transactiondb",
        "corebankingdb",
        "atmbackend",
        "backend",
        "internalservice",
    }
)


def _role_name_has_human_actor_marker(name: str) -> bool:
    lower = (name or "").lower()
    for m in _HUMAN_ACTOR_MARKERS:
        if m.isascii():
            if m in lower:
                return True
        elif m in name:
            return True
    return False


def is_internal_system_component_role_name(
    name: str,
    *,
    type_hint: Any = None,
) -> bool:
    """
    判斷名稱是否表示系統邊界內的技術組件（資料庫、倉儲、訊息佇列等），
    不應作為用例圖上的外部 Actor，也不計入「外部參與者完整性」分母。
    「Database Administrator」等含人員語義的名稱仍視為外部角色。
    """
    name = (name or "").strip()
    if not name:
        return False
    if _role_name_has_human_actor_marker(name):
        return False

    th = (str(type_hint).strip().lower() if type_hint is not None else "")
    if th:
        compact = th.replace(" ", "")
        if compact in (
            "database",
            "datastore",
            "repository",
            "storage",
            "component",
            "subsystem",
            "service",
            "internal",
        ):
            return True
        if "internal" in compact and "external" not in compact:
            return True

    n = _norm_cmp_label(name)
    if n in _INTERNAL_COMPONENT_EXACT_NORMS:
        return True

    lower = name.lower()
    for sub in _INTERNAL_COMPONENT_SUBSTRINGS:
        if sub.isascii():
            if sub.replace(" ", "") in n or sub in lower:
                return True
        elif sub in name:
            return True

    # Bank Database / Core Banking Server（資料或核心後台，非對外業務系統）
    if re.search(
        r"(bank|core|account|transaction|central|atm)\s*(data\s*)?(base|db|database|server|service)",
        lower,
    ):
        return True
    if re.search(r"(银行|銀行|核心|账户|賬戶|交易).*(数据库|資料庫|库|庫|服务|服務)", name):
        return True

    return False


def should_exclude_from_external_actor_role(
    name: str,
    diagram: Optional[Dict[str, Any]],
    project_name: Optional[str],
    *,
    type_hint: Any = None,
) -> bool:
    """待建系統本體或邊界內技術組件：不計入外部參與者完整性。"""
    return is_subject_system_role_name(
        name, diagram, project_name, type_hint=type_hint
    ) or is_internal_system_component_role_name(name, type_hint=type_hint)


def is_subject_system_actor(
    actor: Dict[str, Any],
    diagram: Optional[Dict[str, Any]],
    project_name: Optional[str],
) -> bool:
    """圖中 actor 是否應視為待建系統本體（不複製到 roles、不參與外部參與者完整性）。"""
    if not isinstance(actor, dict):
        return False
    nm = (actor.get("name") or "").strip()
    if not nm:
        return False
    return should_exclude_from_external_actor_role(
        nm, diagram, project_name, type_hint=actor.get("type")
    )


def normalize_diagram(diagram: Any) -> Any:
    if not isinstance(diagram, dict):
        return diagram
    out = dict(diagram)
    rels: List[Dict[str, Any]] = []
    for r in diagram.get("relationships") or []:
        if not isinstance(r, dict):
            continue
        rr = dict(r)
        rr["type"] = _norm_rel_type(rr.get("type"))
        fr, to = relationship_endpoints(rr)
        if fr is not None:
            rr["from"] = fr
        if to is not None:
            rr["to"] = to
        rid = rr.get("id")
        if rid is None or str(rid).strip() == "":
            if fr and to:
                rr["id"] = f"{fr}→{to}"
            elif fr or to:
                rr["id"] = f"{fr or '(?)'}→{to or '(?)'}"
        rels.append(rr)
    out["relationships"] = rels
    return out


def _infer_expected_associations(diagram: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not diagram or not isinstance(diagram, dict):
        return []
    actors = {
        a["id"]: a
        for a in diagram.get("actors") or []
        if isinstance(a, dict) and a.get("id")
    }
    ucs = {
        u["id"]: u
        for u in diagram.get("use_cases") or []
        if isinstance(u, dict) and u.get("id")
    }
    out: List[Dict[str, Any]] = []
    for r in diagram.get("relationships") or []:
        if not isinstance(r, dict):
            continue
        if _norm_rel_type(r.get("type")) != "association":
            continue
        f, t = relationship_endpoints(r)
        if f in actors and t in ucs:
            out.append(
                {
                    "role": actors[f].get("name", ""),
                    "function": ucs[t].get("name", ""),
                    "type": "association",
                }
            )
        elif f in ucs and t in actors:
            out.append(
                {
                    "role": actors[t].get("name", ""),
                    "function": ucs[f].get("name", ""),
                    "type": "association",
                }
            )
    return out


def _flow_step_to_text(step: Any) -> Optional[str]:
    if isinstance(step, str):
        s = step.strip()
        return s if s else None
    if isinstance(step, dict):
        parts: List[str] = []
        sid = step.get("id")
        if sid is not None and str(sid).strip():
            parts.append(str(sid).strip())
        actor = step.get("actor")
        action = step.get("action")
        if actor and action:
            parts.append(f"{actor}: {action}")
        elif action:
            parts.append(str(action).strip())
        elif actor:
            parts.append(str(actor).strip())
        s = " ".join(parts).strip()
        return s if s else None
    return None


def _infer_alt_return_to_step(alt: Dict[str, Any], main_flow_len: int) -> Any:
    if alt.get("return_to_step") is not None:
        return alt.get("return_to_step")
    if main_flow_len <= 0:
        return "end"
    steps = alt.get("steps") or []
    for st in steps:
        if not isinstance(st, str):
            continue
        m = re.search(r"\(?MF-(\d+)\s*return_to_step\)?", st, re.I)
        if m:
            n = int(m.group(1))
            if 1 <= n <= main_flow_len:
                return n
        m = re.search(r"return_to_step[:\s]*(?:step\s*)?(\d+)", st, re.I)
        if m:
            n = int(m.group(1))
            if 1 <= n <= main_flow_len:
                return n
    joined = " ".join(s for s in steps if isinstance(s, str)).lower()
    if any(
        k in joined
        for k in (
            "terminates",
            "terminate",
            "termination",
            "locked",
            "locks the",
            "鎖定",
            "終止",
        )
    ):
        return "end"
    return None


def normalize_one_use_case_description(d: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(d)
    if not out.get("actors") and out.get("primary_actor"):
        out["actors"] = [out["primary_actor"]]

    mf: List[str] = []
    for s in out.get("main_flow") or []:
        t = _flow_step_to_text(s)
        if t:
            mf.append(t)
    out["main_flow"] = mf

    alts: List[Dict[str, Any]] = []
    for alt in out.get("alternative_flows") or []:
        if not isinstance(alt, dict):
            continue
        aa = dict(alt)
        if not aa.get("name") and aa.get("id") is not None:
            aa["name"] = str(aa["id"])
        mlen = len(mf)
        if aa.get("return_to_step") is None:
            inferred = _infer_alt_return_to_step(aa, mlen)
            if inferred is not None:
                aa["return_to_step"] = inferred
        alts.append(aa)
    out["alternative_flows"] = alts
    return out


def normalize_use_case_descriptions(raw: Any) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    lst: Optional[List[Any]] = None
    if isinstance(raw, list):
        lst = raw
    elif isinstance(raw, dict):
        if isinstance(raw.get("useCases"), list):
            lst = raw["useCases"]
        elif isinstance(raw.get("use_cases"), list):
            lst = raw["use_cases"]
        elif isinstance(raw.get("use_case_descriptions"), list):
            lst = raw["use_case_descriptions"]
        elif isinstance(raw.get("descriptions"), list):
            lst = raw["descriptions"]
        elif "main_flow" in raw or ("name" in raw and "id" in raw):
            lst = [raw]
        else:
            lst = []
    else:
        return []

    return [normalize_one_use_case_description(d) for d in lst if isinstance(d, dict)]


# 從需求正文識別外部參與者（用於參與者完整性分母，不可僅取自用例圖）
_EXTERNAL_ROLE_SIGNATURES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bcustomers?\b", re.I), "Customer"),
    (re.compile(r"\bclients?\b", re.I), "Client"),
    (re.compile(r"\badministrators?\b", re.I), "Administrator"),
    (re.compile(r"\boperators?\b", re.I), "Operator"),
    (re.compile(r"\btellers?\b", re.I), "Teller"),
    (re.compile(r"\bmembers?\b", re.I), "Member"),
    (re.compile(r"\busers?\b", re.I), "User"),
    (re.compile(r"客户"), "客户"),
    (re.compile(r"顾客"), "顾客"),
    (re.compile(r"用户"), "用户"),
    (re.compile(r"管理员"), "管理员"),
    (re.compile(r"操作员"), "操作员"),
    (re.compile(r"柜员"), "柜员"),
    (re.compile(r"会员"), "会员"),
]


def _requirements_text_corpus(req: Dict[str, Any]) -> str:
    """彙總需求各層級文本，供角色抽取。"""
    parts: List[str] = []
    for g in req.get("goal_level_requirements") or []:
        if isinstance(g, dict):
            parts.extend([str(g.get("title") or ""), str(g.get("description") or "")])
    for fr in req.get("functional_requirements") or []:
        if isinstance(fr, dict):
            parts.extend([str(fr.get("title") or ""), str(fr.get("text") or "")])
        else:
            parts.append(str(fr))
    for ir in req.get("interaction_level_requirements") or []:
        if isinstance(ir, dict):
            parts.append(str(ir.get("description") or ""))
    for nfr in req.get("non_functional_requirements") or []:
        if isinstance(nfr, dict):
            parts.append(str(nfr.get("description") or nfr.get("text") or ""))
    return "\n".join(p for p in parts if p and str(p).strip())


def extract_external_roles_from_requirements(
    req: Dict[str, Any],
    diagram: Optional[Dict[str, Any]] = None,
    project_name: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    從需求文檔識別應出現在用例圖上的外部參與者（不依賴圖中是否已畫）。
    """
    if not isinstance(req, dict):
        return []

    corpus = _requirements_text_corpus(req)
    found: Dict[str, Dict[str, str]] = {}

    def _add_role(name: str, source: str, description: str = "") -> None:
        name = (name or "").strip()
        if not name:
            return
        if should_exclude_from_external_actor_role(name, diagram, project_name):
            return
        key = _norm_cmp_label(name)
        if key not in found:
            found[key] = {
                "name": name,
                "description": description or f"来源：{source}",
                "source": source,
            }

    if corpus.strip():
        for pattern, canonical in _EXTERNAL_ROLE_SIGNATURES:
            if pattern.search(corpus):
                _add_role(canonical, "requirements_text")

    for r in req.get("roles") or []:
        if isinstance(r, dict):
            _add_role(r.get("name", ""), "requirements.roles", r.get("description", ""))
        else:
            _add_role(str(r), "requirements.roles")

    # ATM/銀行場景：customers 與 users 多指同一主體，避免要求圖中同時有 User 與 Customer
    keys = {_norm_cmp_label(v["name"]) for v in found.values()}
    if "customer" in keys and "user" in keys:
        found = {k: v for k, v in found.items() if _norm_cmp_label(v["name"]) != "user"}

    return list(found.values())


def resolve_required_external_roles(
    requirements: Dict[str, Any],
    diagram: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """參與者完整性用：需求聲明 + 文本抽取的外部角色列表。"""
    if not isinstance(requirements, dict):
        return []
    pn = (requirements.get("project_name") or "").strip() or None
    if not pn and diagram and isinstance(diagram, dict):
        pn = (diagram.get("title") or "").strip() or None
    roles = requirements.get("roles") or []
    if roles:
        return [r if isinstance(r, dict) else {"name": str(r), "description": ""} for r in roles]
    extracted = extract_external_roles_from_requirements(requirements, diagram, pn)
    if extracted:
        return extracted
    if diagram and isinstance(diagram, dict):
        fallback: List[Dict[str, str]] = []
        for a in diagram.get("actors") or []:
            if not isinstance(a, dict) or is_subject_system_actor(a, diagram, pn):
                continue
            fallback.append(
                {
                    "name": (a.get("name") or "").strip(),
                    "description": (a.get("description") or "").strip(),
                }
            )
        return fallback
    return []


def normalize_requirements(
    req: Dict[str, Any],
    diagram: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    統一需求 schema：goal_level_requirements 等 → roles / functional_requirements / expected_relationships

    互動層與非功能需求保留在鍵名中，但不併入 functional_requirements，以免破壞「需求↔用例」集合匹配。
    """
    if not isinstance(req, dict):
        return req

    if req.get("goal_level_requirements"):
        goals = req.get("goal_level_requirements") or []
        functional: List[Dict[str, Any]] = []
        for g in goals:
            if not isinstance(g, dict):
                continue
            title = (g.get("title") or "").strip()
            desc = (g.get("description") or "").strip()
            text = desc or title
            entry: Dict[str, Any] = {
                "id": g.get("id", ""),
                "text": text,
                "priority": _norm_priority(g.get("priority")),
            }
            if title:
                entry["title"] = title
            src = g.get("source")
            if src:
                entry["source"] = src
            functional.append(entry)

        project_name = (req.get("project_name") or "").strip() or None
        if diagram and isinstance(diagram, dict):
            t = (diagram.get("title") or "").strip()
            if t:
                project_name = project_name or t
        roles = extract_external_roles_from_requirements(req, diagram, project_name)
        seen_role_keys = {_norm_cmp_label(r["name"]) for r in roles}
        if diagram and isinstance(diagram, dict):
            for a in diagram.get("actors") or []:
                if not isinstance(a, dict):
                    continue
                if is_subject_system_actor(a, diagram, project_name):
                    continue
                an = (a.get("name") or "").strip()
                if not an or _norm_cmp_label(an) in seen_role_keys:
                    continue
                roles.append(
                    {
                        "name": an,
                        "description": (a.get("description") or "").strip(),
                    }
                )
                seen_role_keys.add(_norm_cmp_label(an))

        expected = _infer_expected_associations(diagram)
        if not project_name and diagram and isinstance(diagram, dict):
            project_name = (diagram.get("title") or "").strip() or None

        return {
            "project_name": project_name or req.get("project_name"),
            "version": req.get("version"),
            "roles": roles,
            "functional_requirements": functional,
            "expected_relationships": expected,
            "glossary": req.get("glossary") if isinstance(req.get("glossary"), dict) else {},
            "interaction_level_requirements": req.get("interaction_level_requirements"),
            "non_functional_requirements": req.get("non_functional_requirements"),
            "goal_level_requirements": goals,
        }

    patched = copy.deepcopy(req)
    if diagram and isinstance(diagram, dict):
        if not patched.get("expected_relationships"):
            patched["expected_relationships"] = _infer_expected_associations(diagram)
    roles_in = patched.get("roles")
    if isinstance(roles_in, list) and roles_in:
        pn = (patched.get("project_name") or "").strip() or None
        if not pn and diagram and isinstance(diagram, dict):
            pn = (diagram.get("title") or "").strip() or None
        kept: List[Dict[str, Any]] = []
        for role in roles_in:
            if isinstance(role, dict):
                rn = (role.get("name") or "").strip()
                th = role.get("type")
            else:
                rn = str(role).strip()
                th = None
            if not rn:
                continue
            if should_exclude_from_external_actor_role(rn, diagram, pn, type_hint=th):
                continue
            kept.append(role if isinstance(role, dict) else {"name": rn, "description": ""})
        patched["roles"] = kept
    return patched


def normalize_evaluation_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """在評估前轉換整份請求體（淺拷貝頂層鍵，避免改動調用方原始 dict 的引用意義混亂）。"""
    out = dict(data)
    if "use_case_diagram" in out and out["use_case_diagram"] is not None:
        out["use_case_diagram"] = normalize_diagram(out["use_case_diagram"])
    diagram = out.get("use_case_diagram")
    if isinstance(diagram, dict):
        pass
    else:
        diagram = None

    if "use_case_descriptions" in out:
        out["use_case_descriptions"] = normalize_use_case_descriptions(
            out["use_case_descriptions"]
        )

    req = out.get("requirements")
    if req is not None and isinstance(req, dict):
        out["requirements"] = normalize_requirements(req, diagram)
    return out
