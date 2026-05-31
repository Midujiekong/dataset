"""
需求與用例圖跨語言對齊：偵測中英混用，建立語義別名後再參與語義/術語判斷。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .semantic_matcher import WeakSemanticMatcher

# 常見 ATM / 銀行場景中英對照（補充自動對齊）
_ATM_BILINGUAL_GROUPS: List[List[str]] = [
    ["customer", "client", "bank customer", "客户", "客戶", "顾客", "顧客", "用户", "用戶"],
    ["withdraw", "withdrawal", "withdraw cash", "cash withdrawal", "取款", "提款", "取現"],
    ["deposit", "deposit cash", "cash deposit", "存款", "存現"],
    ["balance", "balance enquiry", "check balance", "enquiry", "查询余额", "查詢餘額", "余额", "餘額"],
    ["change pin", "pin change", "change password", "修改密码", "修改密碼", "改密", "更改pin"],
    ["mini statement", "generate mini statement", "statement", "receipt", "打印小票", "列印小票", "凭条", "憑條"],
    ["validate pin", "pin validation", "authenticate", "authentication", "验证", "驗證", "校验", "校驗"],
    ["display error", "display error message", "error message", "错误", "錯誤", "显示错误", "顯示錯誤"],
    ["login", "log in", "sign in", "登录", "登錄", "登入"],
    ["register", "registration", "注册", "註冊"],
]


def _norm_label(s: str) -> str:
    return re.sub(r"[\s_\-]+", "", (s or "").strip().lower())


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _contains_latin_word(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]{2,}", text or ""))


def detect_language_profile(texts: List[str]) -> str:
    """返回 'zh' | 'en' | 'mixed'。"""
    zh, en = 0, 0
    for t in texts:
        if not t or not str(t).strip():
            continue
        s = str(t)
        if _contains_cjk(s):
            zh += 1
        if _contains_latin_word(s):
            en += 1
    if zh > 0 and en > 0:
        return "mixed"
    if zh > en:
        return "zh"
    if en > zh:
        return "en"
    return "mixed"


def _collect_diagram_texts(diagram: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for a in diagram.get("actors") or []:
        if isinstance(a, dict):
            out.extend([a.get("name", ""), a.get("description", "")])
    for u in diagram.get("use_cases") or []:
        if isinstance(u, dict):
            out.extend([u.get("name", ""), u.get("description", "")])
    return [str(x) for x in out if x]


def _collect_requirements_texts(requirements: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for r in requirements.get("roles") or []:
        if isinstance(r, dict):
            out.extend([r.get("name", ""), r.get("description", "")])
    for fr in requirements.get("functional_requirements") or []:
        if isinstance(fr, dict):
            out.extend([fr.get("text", ""), fr.get("title", "")])
        else:
            out.append(str(fr))
    for g in requirements.get("goal_level_requirements") or []:
        if isinstance(g, dict):
            out.extend([g.get("title", ""), g.get("description", "")])
    gloss = requirements.get("glossary")
    if isinstance(gloss, dict):
        for k, vals in gloss.items():
            out.append(str(k))
            if isinstance(vals, list):
                out.extend(str(v) for v in vals)
    return [str(x) for x in out if x]


def _requirements_corpus(requirements: Dict[str, Any]) -> str:
    return " ".join(_collect_requirements_texts(requirements)).lower()


@dataclass
class CrossLanguageContext:
    cross_language: bool
    requirements_lang: str
    diagram_lang: str
    alias_index: Dict[str, Set[str]] = field(default_factory=dict)
    alignment_note: str = ""

    def equivalent_labels(self, name: str) -> Set[str]:
        key = _norm_label(name)
        found: Set[str] = {name.strip()} if name else set()
        if key in self.alias_index:
            found |= self.alias_index[key]
        for k, vals in self.alias_index.items():
            if key and (key in k or k in key):
                found |= vals
        return {x for x in found if x}

    def text_supported_by_requirements(self, *labels: str) -> bool:
        corpus = getattr(self, "_corpus", "") or ""
        if not corpus:
            return False
        for label in labels:
            if not label:
                continue
            for alt in self.equivalent_labels(label):
                if alt.lower() in corpus:
                    return True
                if WeakSemanticMatcher.weak_match(alt, corpus):
                    return True
        return False


def build_alias_index(diagram: Dict[str, Any], requirements: Dict[str, Any]) -> Dict[str, Set[str]]:
    index: Dict[str, Set[str]] = {}

    def _add_group(words: List[str]) -> None:
        clean = [w.strip() for w in words if w and str(w).strip()]
        if len(clean) < 2:
            return
        bucket: Set[str] = set(clean)
        for w in clean:
            index[_norm_label(w)] = bucket

    for group in _ATM_BILINGUAL_GROUPS:
        _add_group(group)

    gloss = requirements.get("glossary")
    if isinstance(gloss, dict):
        for k, vals in gloss.items():
            if k:
                group = [str(k)] + ([str(v) for v in vals] if isinstance(vals, list) else [])
                _add_group(group)

    frs = requirements.get("functional_requirements") or []
    ucs = diagram.get("use_cases") or []
    for fr in frs:
        if not isinstance(fr, dict):
            continue
        fr_text = (fr.get("text") or "").strip()
        fr_title = (fr.get("title") or "").strip()
        fr_label = fr_title or fr_text
        if not fr_label:
            continue
        for uc in ucs:
            if not isinstance(uc, dict):
                continue
            uc_name = (uc.get("name") or "").strip()
            if not uc_name:
                continue
            if WeakSemanticMatcher.weak_match(fr_label, uc_name) or WeakSemanticMatcher.weak_match(
                fr_text, uc_name
            ):
                _add_group([fr_label, fr_title, uc_name])

    roles = requirements.get("roles") or []
    actors = diagram.get("actors") or []
    for role in roles:
        rn = role.get("name") if isinstance(role, dict) else str(role)
        if not rn:
            continue
        for actor in actors:
            an = actor.get("name") if isinstance(actor, dict) else ""
            if an and WeakSemanticMatcher.weak_match(rn, an):
                _add_group([rn, an])

    return index


def analyze_cross_language_context(
    diagram: Dict[str, Any],
    requirements: Optional[Dict[str, Any]],
) -> CrossLanguageContext:
    if not diagram or not requirements or not isinstance(requirements, dict):
        return CrossLanguageContext(False, "mixed", "mixed")

    req_lang = detect_language_profile(_collect_requirements_texts(requirements))
    dia_lang = detect_language_profile(_collect_diagram_texts(diagram))

    dia_names: List[str] = []
    for a in diagram.get("actors") or []:
        if isinstance(a, dict) and a.get("name"):
            dia_names.append(str(a["name"]))
    for u in diagram.get("use_cases") or []:
        if isinstance(u, dict) and u.get("name"):
            dia_names.append(str(u["name"]))
    dia_has_cjk = any(_contains_cjk(n) for n in dia_names)
    dia_has_latin = any(_contains_latin_word(n) for n in dia_names)

    cross = (req_lang == "en" and dia_lang == "zh") or (req_lang == "zh" and dia_lang == "en")
    if not cross and req_lang == "en" and dia_has_cjk:
        cross = True
    if not cross and req_lang == "zh" and dia_has_latin:
        cross = True
    if not cross and req_lang == "en" and dia_lang == "mixed" and dia_has_cjk:
        cross = True
    if not cross and req_lang == "zh" and dia_lang == "mixed" and dia_has_latin:
        cross = True

    alias_index = build_alias_index(diagram, requirements) if cross else {}
    note = ""
    if cross:
        note = (
            f"需求主体为{'英文' if req_lang == 'en' else '中文'}，"
            f"用例图名称为{'中文' if dia_lang == 'zh' else '英文'}，已启用跨语言语义对齐；"
            f"勿因字面语言不同而将 Customer-取款 等合理关联判为语义错误。"
        )

    ctx = CrossLanguageContext(
        cross_language=cross,
        requirements_lang=req_lang,
        diagram_lang=dia_lang,
        alias_index=alias_index,
        alignment_note=note,
    )
    ctx._corpus = _requirements_corpus(requirements)  # type: ignore[attr-defined]
    return ctx


def relationship_plausible_under_cross_language(
    diagram: Dict[str, Any],
    rel: Dict[str, Any],
    ctx: CrossLanguageContext,
) -> bool:
    """跨语言场景下，判断关系是否在需求语义上合理（从宽）。"""
    if not ctx.cross_language:
        return False

    id_to_elem: Dict[str, Dict[str, Any]] = {}
    for a in diagram.get("actors") or []:
        if isinstance(a, dict) and a.get("id"):
            id_to_elem[str(a["id"])] = a
    for u in diagram.get("use_cases") or []:
        if isinstance(u, dict) and u.get("id"):
            id_to_elem[str(u["id"])] = u

    fr_id = str(rel.get("from") or rel.get("source") or "").strip()
    to_id = str(rel.get("to") or rel.get("target") or "").strip()
    src = id_to_elem.get(fr_id, {})
    tgt = id_to_elem.get(to_id, {})
    src_name = (src.get("name") or "").strip()
    tgt_name = (tgt.get("name") or "").strip()
    rel_type = (rel.get("type") or "association").strip().lower()

    if not src_name or not tgt_name:
        return False

    if rel_type == "association":
        return ctx.text_supported_by_requirements(src_name, tgt_name)

    if rel_type == "include":
        pin_like = {"validate pin", "pin", "验证", "驗證", "校验", "校驗", "authenticate"}
        tgt_l = tgt_name.lower()
        if any(p in tgt_l or p in _norm_label(tgt_name) for p in pin_like):
            return ctx.text_supported_by_requirements(src_name, "pin", "authenticate", "password")
        return ctx.text_supported_by_requirements(src_name, tgt_name)

    if rel_type == "extend":
        err_like = {"error", "display", "错误", "錯誤", "消息", "message"}
        if any(e in src_name.lower() for e in err_like):
            return ctx.text_supported_by_requirements(tgt_name, "error", "fail", "transaction")
        return ctx.text_supported_by_requirements(src_name, tgt_name)

    return ctx.text_supported_by_requirements(src_name, tgt_name)


def language_mismatch_consistency_issue(ctx: CrossLanguageContext) -> Optional[Dict[str, Any]]:
    if not ctx.cross_language:
        return None
    return {
        "issue_type": "language_alignment",
        "description": f"【用例图·一致性】{ctx.alignment_note}建议在交付前统一需求与用例图的表述语言。",
        "severity": 0.25,
    }


def should_suppress_heuristic_semantic_issue(
    diagram: Dict[str, Any],
    element_id: str,
    requirements: Optional[Dict[str, Any]],
    ctx: CrossLanguageContext,
) -> bool:
    if not ctx.cross_language or not requirements:
        return False
    for rel in diagram.get("relationships") or []:
        if not isinstance(rel, dict):
            continue
        rid = str(rel.get("id") or "").strip()
        if rid and rid == str(element_id or "").strip():
            return relationship_plausible_under_cross_language(diagram, rel, ctx)
        fr = str(rel.get("from") or rel.get("source") or "")
        to = str(rel.get("to") or rel.get("target") or "")
        if element_id and element_id in (fr, to, f"{fr}→{to}"):
            return relationship_plausible_under_cross_language(diagram, rel, ctx)
    return True
