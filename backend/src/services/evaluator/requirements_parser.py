# backend/src/services/evaluator/requirements_parser.py
"""
需求抽取器（规则+启发式版本）
将原始需求文本（可能半结构化、口语化）转换为评估引擎所需的结构化字典。
支持基于规则的抽取（默认）和可选的LLM增强。
"""
import re
from typing import Dict, Any, List, Optional


def _contains_chinese(text: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', text or ""))

# ---------- 可选LLM导入 ----------
try:
    from .llm_integration import LLMManager
    from .llm_prompts import LLMPromptTemplates
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    # 定义占位符，避免导入错误
    class LLMManager:
        def __init__(self, *args, **kwargs): pass
    class LLMPromptTemplates:
        @staticmethod
        def extract_requirements_prompt(text): return ("", "")

# ---------- 公共接口 ----------
def extract_structured_requirements(
    raw_text: str,
    use_llm: bool = True,          # 默认使用LLM（需配置密钥）
    llm_provider: str = "deepseek",
    fallback_to_rules: bool = True
) -> Dict[str, Any]:
    """
    将原始需求文本抽取为结构化字典。

    Args:
        raw_text: 原始需求文本
        use_llm: 是否使用LLM进行抽取（需配置API密钥）
        llm_provider: LLM提供商
        fallback_to_rules: LLM失败时是否回退到规则抽取

    Returns:
        符合评估引擎要求的结构化需求字典
    """
    if not raw_text.strip():
        raise ValueError("需求文本不能为空")

    if use_llm and LLM_AVAILABLE:
        try:
            result = _extract_with_llm(raw_text, llm_provider)
            return result
        except Exception:
            if fallback_to_rules:
                return _extract_with_rules(raw_text)
            else:
                raise
    else:
        return _extract_with_rules(raw_text)


# ---------- LLM抽取（封装）----------
def _extract_with_llm(raw_text: str, provider: str) -> Dict[str, Any]:
    """使用LLM抽取（要求LLM_AVAILABLE为True）"""
    if not LLM_AVAILABLE:
        raise ImportError("LLM模块不可用，无法使用LLM抽取")
    llm_manager = LLMManager(provider=provider)
    system_prompt, user_prompt = LLMPromptTemplates.extract_requirements_prompt(raw_text)
    response = llm_manager.call_with_retry(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.1,
        max_tokens=4000
    )
    result = llm_manager.parse_json_response(response)
    if result.get("error"):
        raise ValueError(f"LLM 抽取 JSON 解析失败: {result.get('error')}，将回退到规则抽取")
    return _postprocess_result(result)


# ---------- 规则抽取（核心，改进版）----------
def _extract_with_rules(raw_text: str) -> Dict[str, Any]:
    """
    改进的规则抽取器：
    - 先分割章节，只在对应章节提取内容。
    - 角色提取严格限定在“角色”章节。
    - 功能需求过滤小标题，合并描述更精准。
    - 预期关系基于角色和功能语义生成。
    """
    result = {
        "project_name": "",
        "roles": [],
        "functional_requirements": [],
        "expected_relationships": [],
        "terms": [],
        "glossary": {}
    }

    # 1. 分割章节
    sections = _split_sections(raw_text)

    # 2. 提取项目名称（取第一段或章节外的第一行）
    result["project_name"] = _extract_project_name(raw_text)

    # 3. 提取角色（从角色章节）
    role_section = sections.get("roles") or sections.get("角色") or ""
    if role_section:
        result["roles"] = _extract_roles(role_section)
    else:
        # 如果没有找到角色章节，尝试从全局提取（但不推荐）
        result["roles"] = _extract_roles_global(raw_text)

    # 4. 提取功能需求（从功能需求章节）
    func_section = sections.get("functional") or sections.get("功能需求") or sections.get("需求") or ""
    if func_section:
        result["functional_requirements"] = _extract_functional_requirements(func_section)
    else:
        # 如果没有找到功能章节，尝试从全局提取
        result["functional_requirements"] = _extract_functional_requirements_global(raw_text)

    # 5. 提取术语
    result["terms"] = _extract_terms(result["roles"], result["functional_requirements"])

    # 6. 提取同义词（从约束章节或全文）
    constraint_section = sections.get("constraints") or sections.get("约束") or sections.get("说明") or ""
    if constraint_section:
        result["glossary"] = _extract_glossary(constraint_section)
    else:
        result["glossary"] = _extract_glossary(raw_text)

    # 7. 生成预期关系（基于角色和功能描述）
    result["expected_relationships"] = _generate_expected_relationships(
        result["roles"], result["functional_requirements"]
    )

    return _postprocess_result(result)


# ---------- 辅助函数 ----------
def _split_sections(text: str) -> Dict[str, str]:
    """将文本按章节分割，返回章节名到内容的映射。"""
    sections = {}
    # 匹配Markdown标题（# 开头）或数字章节（如“2. 角色”）
    lines = text.split('\n')
    current_title = None
    current_content = []
    # 常见章节关键词（中英）
    section_aliases = {
        "roles": ["角色", "roles", "actors", "stakeholders", "participants"],
        "functional": ["功能需求", "功能", "需求", "functional requirements", "requirements", "features", "use cases"],
        "constraints": ["约束", "说明", "constraints", "notes", "assumptions"],
    }

    for line in lines:
        line = line.strip()
        # 检查是否为章节标题（支持多种格式）
        title_match = re.match(r'^(#{1,3})\s+(.*)', line)  # Markdown
        if not title_match:
            title_match = re.match(r'^[一二三四五六七八九十]+\s*[、.]\s*(.*)', line)  # 中文数字
        if not title_match:
            title_match = re.match(r'^\d+\.\s*(.*)', line)  # 英文数字
        if title_match:
            title = title_match.group(2) if len(title_match.groups()) > 1 else title_match.group(1)
            title = title.strip()
            # 统一章节名，便于后续中英兼容读取
            t_lower = title.lower()
            normalized_title = title
            if any(k in title for k in section_aliases["roles"]) or any(k in t_lower for k in section_aliases["roles"]):
                normalized_title = "roles"
            elif any(k in title for k in section_aliases["functional"]) or any(k in t_lower for k in section_aliases["functional"]):
                normalized_title = "functional"
            elif any(k in title for k in section_aliases["constraints"]) or any(k in t_lower for k in section_aliases["constraints"]):
                normalized_title = "constraints"

            # 保存上一个章节
            if current_title and current_content:
                sections[current_title] = '\n'.join(current_content).strip()
            # 新章节开始
            current_title = normalized_title
            current_content = []
        else:
            if current_title is not None:
                current_content.append(line)

    # 保存最后一个章节
    if current_title and current_content:
        sections[current_title] = '\n'.join(current_content).strip()

    # 如果没有找到任何章节，返回空字典
    return sections


def _extract_project_name(text: str) -> str:
    """从文本开头或第一行提取项目名称"""
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            # 取第一句或截断
            return line[:50]
    return ""


def _extract_roles(section_text: str) -> List[Dict[str, str]]:
    """从角色章节提取角色，每行格式如 "- 学员：购买课程的人" """
    roles = []
    lines = section_text.split('\n')
    for line in lines:
        line = line.strip()
        # 匹配列表项：以 - 或 • 开头
        if line.startswith('-') or line.startswith('•') or line.startswith('*'):
            content = line[1:].strip()
            # 尝试用中文冒号或英文冒号分割
            parts = re.split(r'[：:]', content, maxsplit=1)
            if len(parts) == 2:
                name = parts[0].strip()
                desc = parts[1].strip()
                if re.match(r'^(role|actor|stakeholder)s?$', name.lower()):
                    continue
                roles.append({"name": name, "description": desc})
            else:
                # 如果没有冒号，可能是纯名称，描述置空
                name_only = content.strip()
                if re.match(r'^(role|actor|stakeholder)s?$', name_only.lower()):
                    continue
                roles.append({"name": name_only, "description": ""})
    return roles


def _extract_roles_global(text: str) -> List[Dict[str, str]]:
    """全局提取角色（当没有明确角色章节时）"""
    roles = []
    # 常见角色名称模式
    role_pattern = re.compile(r'[-\*•]\s*([^：:]+)[：:]\s*(.+)')
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('-') or line.startswith('•') or line.startswith('*'):
            m = role_pattern.match(line)
            if m:
                name = m.group(1).strip()
                desc = m.group(2).strip()
                roles.append({"name": name, "description": desc})
    return roles


def _extract_functional_requirements(section_text: str) -> List[Dict[str, str]]:
    """从功能需求章节提取功能需求，过滤小标题，合并多行描述"""
    reqs = []
    lines = section_text.split('\n')
    i = 0
    fr_id = 1

    # 小标题关键词（如果一行包含这些词且较短，视为小标题，跳过）
    heading_keywords = ["相关", "部分", "方面", "管理", "模块", "功能", "流程", "场景",
                        "overview", "module", "feature", "flow", "scenario", "section"]

    def is_heading(line):
        # 判断是否为小标题：长度小于15且不含数字编号且包含关键词
        if len(line) < 15 and not re.match(r'^\d+', line):
            if any(kw in line for kw in heading_keywords):
                return True
        return False

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # 检查是否为需求开始：数字编号或列表项
        is_num_start = re.match(r'^\d+[).、]', line)
        is_dash_start = line.startswith('-') or line.startswith('•') or line.startswith('*')

        if is_num_start or is_dash_start:
            # 跳过小标题
            if is_heading(line):
                i += 1
                continue

            # 收集多行描述
            desc_lines = [line]
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line:
                    break  # 空行结束当前需求
                # 如果下一行是新的编号或列表项，停止
                if re.match(r'^\d+[).、]', next_line) or next_line.startswith('-') or next_line.startswith('•') or next_line.startswith('*'):
                    break
                desc_lines.append(next_line)
                i += 1

            # 合并描述，清理开头编号/列表标记
            full_desc = ' '.join(desc_lines)
            clean_desc = re.sub(r'^\d+[).、]\s*', '', full_desc)
            clean_desc = re.sub(r'^[-•*]\s*', '', clean_desc)
            # 优先级判断
            priority = _extract_priority(clean_desc)
            reqs.append({
                "id": f"FR-{fr_id:03d}",
                "text": clean_desc,
                "priority": priority
            })
            fr_id += 1
        else:
            i += 1

    return reqs


def _extract_functional_requirements_global(text: str) -> List[Dict[str, str]]:
    """全局提取功能需求（当没有明确功能章节时）"""
    # 简化版：提取所有以数字编号或列表项开头的行
    reqs = []
    lines = text.split('\n')
    fr_id = 1
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'^\d+[).、]', line) or line.startswith('-') or line.startswith('•') or line.startswith('*'):
            clean_desc = re.sub(r'^\d+[).、]\s*', '', line)
            clean_desc = re.sub(r'^[-•*]\s*', '', clean_desc)
            priority = _extract_priority(clean_desc)
            reqs.append({
                "id": f"FR-{fr_id:03d}",
                "text": clean_desc,
                "priority": priority
            })
            fr_id += 1
    return reqs


def _extract_priority(text: str) -> str:
    """根据文本中的关键词判断优先级"""
    text_lower = text.lower()
    if re.search(r'优先|必须|核心|强制|high|critical|must|mandatory|required', text_lower):
        return "high"
    elif re.search(r'可选|可能|如果|when|if|optional|low|nice to have|could|may', text_lower):
        return "low"
    else:
        return "medium"


def _extract_terms(roles: List[Dict], func_reqs: List[Dict]) -> List[Dict[str, str]]:
    """从角色和功能描述中提取候选术语（去重、过滤停用词）"""
    stopwords_zh = {"系统", "用户", "功能", "可以", "能够", "需要", "进行", "一个", "这个", "这些",
                    "如果", "没有", "还是", "就是", "什么", "我们", "他们", "它", "其", "该"}
    stopwords_en = {
        "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "by",
        "is", "are", "be", "as", "at", "that", "this", "these", "those", "system", "user",
        "users", "function", "feature", "can", "should", "must", "need"
    }
    term_set = set()

    # 添加角色名称
    for r in roles:
        name = r.get("name", "").strip()
        if name and len(name) >= 2:
            term_set.add(name)

    # 从功能描述中提取术语（中文短语 + 英文词组）
    for fr in func_reqs:
        text = fr.get("text", "")
        zh_words = re.findall(r'[\u4e00-\u9fa5]{2,}', text)
        for w in zh_words:
            if w not in stopwords_zh:
                term_set.add(w)
        en_words = re.findall(r'[A-Za-z][A-Za-z0-9_-]{2,}', text)
        for w in en_words:
            lw = w.lower()
            if lw not in stopwords_en:
                term_set.add(lw)

    # 转为列表，并附上空描述（实际应后续完善）
    terms = [{"term": t, "description": ""} for t in term_set]
    return terms


def _extract_glossary(text: str) -> Dict[str, List[str]]:
    """提取同义词，如 '学员/用户' 或 '购买/下单' """
    glossary = {}
    # 匹配 A/B（中英文）与 A又称B / A aka B
    syn_pattern = re.compile(r'([\u4e00-\u9fa5A-Za-z][\u4e00-\u9fa5A-Za-z0-9_\-]*)\s*/\s*([\u4e00-\u9fa5A-Za-z][\u4e00-\u9fa5A-Za-z0-9_\-]*)')
    for match in syn_pattern.finditer(text):
        a, b = match.groups()
        if a not in glossary:
            glossary[a] = []
        if b not in glossary[a]:
            glossary[a].append(b)
    aka_pattern = re.compile(r'([\u4e00-\u9fa5A-Za-z][\u4e00-\u9fa5A-Za-z0-9_\-]*)\s*(?:又称|也叫|aka|AKA|a\.k\.a\.)\s*([\u4e00-\u9fa5A-Za-z][\u4e00-\u9fa5A-Za-z0-9_\-]*)')
    for match in aka_pattern.finditer(text):
        a, b = match.groups()
        if a not in glossary:
            glossary[a] = []
        if b not in glossary[a]:
            glossary[a].append(b)
    return glossary


def _generate_expected_relationships(roles: List[Dict], func_reqs: List[Dict]) -> List[Dict]:
    """
    启发式生成预期关系：
    如果一个功能需求的文本以某个角色的名称开头（如“学员可以...”），则认为该角色与该功能有关联。
    功能名称取需求文本中第一个动作短语（动词+名词）的前几个字。
    如果没有以角色开头，尝试在描述中查找角色名。
    """
    relationships = []
    role_names = [r["name"] for r in roles]

    for fr in func_reqs:
        text = fr["text"]
        matched_role = None
        # 检查是否以某个角色名称开头
        for role in role_names:
            if text.startswith(role):
                matched_role = role
                break
        if not matched_role:
            # 尝试在文本中查找角色名（简单包含）
            for role in role_names:
                if role in text:
                    matched_role = role
                    break
        if matched_role:
            # 提取功能名称：去掉角色前缀和可能的助词
            func_text = text
            if text.startswith(matched_role):
                func_text = text[len(matched_role):].strip()
            func_text = re.sub(r'^(可以|能够|需要|能|会|将|can|should|must|need to|will)', '', func_text, flags=re.IGNORECASE).strip()
            if _contains_chinese(func_text):
                m = re.search(r'([\u4e00-\u9fa5]{2,})', func_text)
                if m:
                    func_name = m.group(1)
                else:
                    func_name = func_text[:8] if func_text else "功能"
            else:
                m = re.search(r'([A-Za-z][A-Za-z0-9_-]*(?:\s+[A-Za-z][A-Za-z0-9_-]*){0,3})', func_text)
                if m:
                    func_name = m.group(1).strip()
                else:
                    func_name = func_text[:24] if func_text else "feature"
            relationships.append({
                "role": matched_role,
                "function": func_name,
                "type": "association"
            })

    # 2. include/extend：從功能需求推斷用例間關係
    for fr in func_reqs:
        text = fr["text"]
        text_l = text.lower()
        if "结算" in text or "购买" in text or "checkout" in text_l or "purchase" in text_l:
            if "创建订单" in text or "创建 订单" in text:
                relationships.append({"role": "购买课程", "function": "创建订单", "type": "include"})
            if ("支付" in text and "调用" in text) or "支付平台" in text:
                relationships.append({"role": "购买课程", "function": "支付订单", "type": "include"})
            if "开通" in text and ("权限" in text or "学习" in text):
                relationships.append({"role": "购买课程", "function": "开通学习权限", "type": "include"})
            if "优惠券" in text or "抵扣" in text:
                relationships.append({"role": "购买课程", "function": "使用优惠券", "type": "extend"})
            if "create order" in text_l:
                relationships.append({"role": "purchase", "function": "create order", "type": "include"})
            if "payment" in text_l or "pay" in text_l:
                relationships.append({"role": "purchase", "function": "make payment", "type": "include"})
            if "coupon" in text_l or "discount" in text_l:
                relationships.append({"role": "purchase", "function": "apply coupon", "type": "extend"})
        if "退款" in text and ("原路" in text or "支付平台" in text):
            relationships.append({"role": "申请退款", "function": "原路退款", "type": "include"})
        if "refund" in text_l and ("payment" in text_l or "original" in text_l):
            relationships.append({"role": "request refund", "function": "refund payment", "type": "include"})
        # 通用模式：X时需要Y、X包含Y
        for m in re.finditer(r'([\u4e00-\u9fa5]{2,})[时際]?(?:系统)?需要(?:创建|调用|完成)?([\u4e00-\u9fa5]{2,})', text):
            base, sub = m.group(1), m.group(2)
            if base != sub and len(base) >= 2 and len(sub) >= 2:
                relationships.append({"role": base, "function": sub, "type": "include"})
        for m in re.finditer(r'([A-Za-z][A-Za-z0-9_\- ]{1,40})\s+(?:needs|need to|includes|include|must)\s+([A-Za-z][A-Za-z0-9_\- ]{1,40})', text, flags=re.IGNORECASE):
            base = m.group(1).strip()
            sub = m.group(2).strip()
            if base.lower() != sub.lower():
                relationships.append({"role": base, "function": sub, "type": "include"})

    # 去重（含 type，因同一對可能有 association 與 include）
    seen = set()
    unique_rels = []
    for rel in relationships:
        key = f"{rel['role']}::{rel['function']}::{rel.get('type','association')}"
        if key not in seen:
            seen.add(key)
            unique_rels.append(rel)
    return unique_rels


def _postprocess_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """确保所有必需字段存在"""
    defaults = {
        "project_name": "",
        "roles": [],
        "functional_requirements": [],
        "expected_relationships": [],
        "terms": [],
        "glossary": {}
    }
    for key, default_value in defaults.items():
        if key not in result or result[key] is None:
            result[key] = default_value
    return result