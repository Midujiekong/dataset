"""
LLM Prompt模板库
包含所有评估任务的标准Prompt模板
"""
import json
from typing import Any, Dict, List, Optional, Tuple

# 需求 JSON 送入 LLM 時的總字元上限（僅在極長文檔時按條目截斷，不對單條 text 做 [:20] 類截斷）
_REQUIREMENTS_LLM_MAX_CHARS = 24_000


def build_requirements_context_for_llm(
    diagram: Optional[Dict[str, Any]],
    requirements: Optional[Dict[str, Any]],
) -> str:
    """
    構造供 LLM 評估用的完整需求上下文（保留每條功能的完整 text/description）。
    禁止在送入模型前對單條需求做固定字元截斷，避免「The system shall all」類誤判。
    """
    if not requirements or not isinstance(requirements, dict):
        return ""

    from .input_normalizer import should_exclude_from_external_actor_role

    diagram_for_roles = diagram if isinstance(diagram, dict) else None
    pn = (requirements.get("project_name") or "").strip() or None
    if not pn and diagram_for_roles:
        pn = (diagram_for_roles.get("title") or "").strip() or None

    ext_roles: List[Dict[str, str]] = []
    for r in requirements.get("roles") or []:
        if not isinstance(r, dict):
            continue
        rn = (r.get("name") or "").strip()
        if not rn:
            continue
        if should_exclude_from_external_actor_role(
            rn, diagram_for_roles, pn, type_hint=r.get("type")
        ):
            continue
        ext_roles.append(
            {
                "name": rn,
                "description": (r.get("description") or "").strip(),
            }
        )

    def _fr_entry(fr: Any) -> Dict[str, Any]:
        if not isinstance(fr, dict):
            return {"text": str(fr).strip()}
        text = (fr.get("text") or "").strip()
        title = (fr.get("title") or "").strip()
        return {
            "id": (fr.get("id") or "").strip(),
            "title": title,
            "text": text or title,
            "priority": fr.get("priority"),
            "source": fr.get("source"),
        }

    funcs = [_fr_entry(fr) for fr in (requirements.get("functional_requirements") or [])]

    goals: List[Dict[str, Any]] = []
    for g in requirements.get("goal_level_requirements") or []:
        if not isinstance(g, dict):
            continue
        desc = (g.get("description") or "").strip()
        title = (g.get("title") or "").strip()
        goals.append(
            {
                "id": (g.get("id") or "").strip(),
                "title": title,
                "description": desc or title,
                "priority": g.get("priority"),
                "source": g.get("source"),
            }
        )

    payload: Dict[str, Any] = {
        "project_name": pn or requirements.get("project_name"),
        "roles": ext_roles,
        "functional_requirements": funcs,
    }
    if goals:
        payload["goal_level_requirements"] = goals

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(body) <= _REQUIREMENTS_LLM_MAX_CHARS:
        return body

    # 極長需求：保留每條完整 text，僅減少條目數量並註明
    trimmed_funcs = list(funcs)
    while trimmed_funcs and len(json.dumps({**payload, "functional_requirements": trimmed_funcs}, ensure_ascii=False)) > _REQUIREMENTS_LLM_MAX_CHARS:
        trimmed_funcs.pop()
    payload["functional_requirements"] = trimmed_funcs
    payload["_note"] = (
        f"需求條目過多，已省略尾部 {len(funcs) - len(trimmed_funcs)} 條；"
        "所列條目均為完整描述，勿將省略誤判為單條描述不完整。"
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


# 多語言輸入（中文 / 英文）時統一要求模型跟隨輸入語言撰寫理由與建議
_PROMPT_LANGUAGE_RULE = """【語言】請先判斷用例圖、需求與用例描述的主體語言。若主體為英文，則本輸出中所有自然語言欄位（reason、suggestion、issues 字串、歧義說明等）必須使用英文；若主體為中文，則使用簡體中文。不得混用，也不得輸出「無效的占位」或空泛的「請檢查」。"""


class LLMPromptTemplates:
    """LLM Prompt模板"""
    
    @staticmethod
    def extract_requirements_prompt(raw_text: str) -> tuple[str, str]:
        system_prompt = """你是一个需求分析专家。请将用户提供的原始需求文本（可能包含口语化描述、半结构化列表）转换为严格的结构化JSON格式。
    输出必须符合以下JSON Schema：

    {
      "project_name": "项目名称（可从文本中推断，若无则置空）",
      "roles": [
        {"name": "角色名", "description": "角色描述"}
      ],
      "functional_requirements": [
        {"id": "FR-001", "text": "需求描述", "priority": "high/medium/low"}
      ],
      "expected_relationships": [
        {"role": "角色名或基础用例名", "function": "功能名或被包含/扩展用例名", "type": "association|include|extend"}
      ],
      "terms": [
        {"term": "术语", "description": "术语解释"}
      ],
      "glossary": {
        "同义词组": ["词1", "词2"]
      }
    }

    抽取规则：
    1. roles：仅识别与待建系统交互的**外部**角色（人、组织、外部业务系统等）。**不要**将系统边界内的技术组件写入 roles，例如：数据库、银行数据库、仓储、消息队列、持久化服务、文件系统、内部后台服务等——这些属于系统实现，在用例图中不应画成 Actor；若需求提到「访问银行数据库」，应体现在用例描述或系统内部行为中，而非单独列为角色。
    2. functional_requirements：识别系统应提供的功能，每个需求应包含完整的描述，优先级可根据“优先”“必须”等关键词推断，否则默认为medium。需求ID按FR-001、FR-002…顺序生成。
    3. expected_relationships：根据角色和功能，推断哪些角色需要与哪些功能关联（association、include、extend 三种：association=角色-用例；include=用例包含用例；extend=用例可选扩展用例）。注意：function名称应与functional_requirements中的text提炼出的核心动作一致（如“登录”“购买课程”）。每个关联关系生成一条记录。
    4. terms：提取文本中的关键业务术语，并给出简要解释。可从角色、功能、约束中提炼。
    5. glossary：识别文本中出现的同义词或别名，例如“学员/用户”表示“学员”和“用户”同义，应记录为{"学员": ["用户"]}。

    只输出JSON，不要添加任何解释或额外文本。
""" + _PROMPT_LANGUAGE_RULE

        user_prompt = f"""请从以下原始需求文本中抽取结构化信息：

    {raw_text}

    输出JSON："""
        return system_prompt, user_prompt
    # ============ 语义正确性评估 ============
    
    @staticmethod
    def semantic_correctness_prompt(
        diagram_context: dict[str, any],
        relationships: list[dict[str, any]],
        requirements: Optional[dict[str, any]] = None,
        *,
        cross_language: bool = False,
    ) -> tuple[str, str]:
        """
        语义正确性评估Prompt
        
        Args:
            diagram_context: 用例图上下文
            relationships: 需要评估的关系列表
            
        Returns:
            (system_prompt, user_prompt) 元组
        """
        req_block = ""
        if requirements:
            req_json = build_requirements_context_for_llm(diagram_context, requirements)
            if req_json:
                req_block = f"""
需求全文（可能与用例图名称语言不同，请按业务语义对齐后判断，勿因中英混用判错）：
{req_json}
"""
        cross_note = ""
        if cross_language:
            cross_note = """
【跨语言】需求与用例图可能分别为英文/中文。Customer 与 取款、Validate PIN 与 authenticate PIN、Display Error Message 与错误处理等，若业务一致则 is_valid 应为 true。
"""

        system_prompt = """你是一个UML建模专家，专门评估用例图的语义正确性。
请根据UML 2.5规范，对照需求全文（若有）评估关系语义；跨语言时按业务含义对齐，禁止仅因字面语言不同判 invalid。"""

        user_prompt = f"""
请评估以下用例图关系的语义正确性：
{cross_note}
用例图上下文：
{json.dumps(diagram_context, ensure_ascii=False, indent=2)}
{req_block}
需要评估的关系列表：
{json.dumps(relationships, ensure_ascii=False, indent=2)}

评估标准（UML 2.5规范）：
1. include关系：表示基础用例"必须"包含被包含用例的行为，只能在用例之间
2. extend关系：表示扩展用例"可选地"在特定条件下扩展基础用例，只能在用例之间；输入关系中应包含extension_point字段，用于描述扩展插入点（扩展发生在基础用例的哪个位置/步骤）
3. generalization关系：表示特殊用例继承一般用例的行为，只能在同类型元素之间
4. association关系：表示参与者与用例之间的通信，只能在参与者和用例之间

请对每个关系进行评估，输出JSON格式的结果：
{{
  "evaluations": [
    {{
      "relationship_id": "关系ID",
      "is_valid": true/false,
      "reason": "评估理由",
      "suggestion": "改进建议（如果不有效）"
    }}
  ],
  "summary": {{
    "total_relationships": 总数,
    "valid_count": 有效数量,
    "invalid_count": 无效数量,
    "overall_validity": 总体有效性百分比
  }}
}}

【重要】reason 和 suggestion 必须直接指出：具体哪个关系（写出源用例-目标用例名）、什么问题、为何不符合UML规范。禁止"建议检查"等模糊表述。
正确示例：reason="关系「购买课程」-「支付订单」使用 include 不当：支付是可选步骤，应改为 extend"；suggestion="将 include 改为 extend，或明确支付为必选流程"。
错误示例：reason="语义可能不符，建议检查"。
【relationship_id】必须与输入「需要评估的关系列表」中每条关系的 id 字段完全一致（逐字相同）。若某条关系缺少 id，则使用该条 JSON 中的 from 与 to 的字符串值用「from→to」拼接作为 relationship_id。
只输出JSON，不要添加其他解释。
""" + _PROMPT_LANGUAGE_RULE
        
        return system_prompt, user_prompt
    
    # ============ 元素无歧义性评估 ============
    
    @staticmethod
    def element_ambiguity_prompt(elements: list[dict[str, any]], 
                                diagram_context: dict[str, any]) -> tuple[str, str]:
        """
        元素无歧义性评估Prompt
        """
        system_prompt = """你是一个UML建模与术语管理专家，擅长识别模型元素名称的歧义性。
    歧义是指一个名称在给定的业务上下文中可能被解释为两种或更多种**截然不同的业务含义**，且无法通过上下文推断。
    【原则】从宽认定无歧义，从严认定歧义。只有在业务上确实存在两种以上不可调和解释时，才判为歧义。
    请严格区分“歧义”与“不够具体”“多角色共用”“常见通用词”：
    - **歧义**：同一名称在业务上可指多种截然不同概念，且图中/上下文无法区分（例如孤立裸词“处理”且无任何关联用例时可指多种处理）。
    - **不够具体**：含义单一，只是未加修饰（如“管理员”“管理课程”“查看订单”）。不算歧义。
    - **多角色共用**：同一动词用于不同参与者（如“注册”“登录”），图中已有参与者区分时，**不算歧义**。
    - **常见用例词**：“管理”“查询”“查看”“浏览”“维护”“配置”等若能与参与者或领域语境搭配理解，**不算歧义**。"""

        user_prompt = f"""
    请评估以下用例图元素的名称是否存在**真正的歧义**。宁可判为无歧义，不要过度报歧义。

    用例图上下文（提供所有元素，便于理解业务领域）：
    {json.dumps(diagram_context, ensure_ascii=False, indent=2)}

    需要评估的元素列表：
    {json.dumps(elements, ensure_ascii=False, indent=2)}

    评估标准（整体放宽）：
    1. **一词多义**：仅当名称在业务上对应多种截然不同概念且上下文无法区分时判歧义。如“登录”“注册”“管理课程”“查看订单”等常见用例名**不算歧义**。
    2. **模糊动作**：仅当完全无对象且业务完全无法推断时判歧义。如“管理”“查询”配合参与者或系统边界可理解时**不算歧义**。
    3. **缩写**：行业通用缩写（CRM、API 等）或图中可推断的缩写**不算歧义**。
    4. **默认无歧义**：只要能在业务上下文中推断出合理单一含义，即判为**无歧义**。

    请对每个元素进行判断，输出JSON格式结果：
    {{
      "evaluations": [
        {{
          "element_id": "元素ID",
          "element_name": "元素名称",
          "element_type": "actor/use_case",
          "is_ambiguous": true/false,
          "ambiguity_reasons": ["具体歧义说明：如「处理」可指处理订单/退款/投诉，未限定对象"],  // 只有is_ambiguous为true时提供，必须直接指出多种解释
          "suggested_names": ["建议名称1", "建议名称2"]  // 可选，用于消除歧义
        }}
      ],
      "summary": {{
        "total_elements": 总数,
        "ambiguous_count": 歧义元素数量,
        "clear_count": 清晰元素数量,
        "note": "仅将真正有多个解释的名称记为歧义，不够具体但含义单一的记为清晰。"
      }}
    }}

    【重要】仅当名称在业务上确实可对应多种截然不同含义且无法通过上下文区分时，才设 is_ambiguous=true。ambiguity_reasons 必须直接指出可对应的多种含义。宁可少报歧义。只输出JSON。
""" + _PROMPT_LANGUAGE_RULE
        return system_prompt, user_prompt
    
    # ============ 术语一致性评估 ============
    
    @staticmethod
    def terminology_consistency_prompt(
        terms: list[str],
        diagram_context: dict[str, any],
        requirements: Optional[dict[str, any]] = None,
    ) -> tuple[str, str]:
        """
        术语一致性评估（对照需求全文，不使用碎片化的「标准术语表」机械对齐）。
        """
        req_block = ""
        if requirements:
            req_json = build_requirements_context_for_llm(diagram_context, requirements)
            if req_json:
                req_block = f"""
需求全文（functional_requirements / goal_level 的完整 text、description）：
{req_json}
"""

        system_prompt = """你是用例建模与需求分析专家，评估用例图中参与者/用例名称与需求文档的用语是否一致。
【从宽原则】默认图中名称与需求一致；仅当会造成业务理解错误或同一图中自相矛盾时才判为不一致。
以下均视为一致，不得扣分或列入 inconsistent_terms：
- 用例名为需求功能的子步骤或实现级名称（如需求写 authenticate…PIN，用例名 Validate PIN；需求写 display balance，用例名 Display Error Message 表示流程中的显示步骤）
- 中英文对应或常见同义（修改密码 / change ATM PIN；取款 / Cash Withdrawal；打印小票 / print receipt，与 transaction history 等不同概念时不强行等同，但若需求未要求「交易历史」用例则不得因存在打印小票而判错）
- 粒度不同：需求为完整句子，用例为动宾短语
- 禁止依据从需求句子中机械切出的单词表、禁止「标准术语表中没有 XX 词」「部分匹配」类理由
""" + _PROMPT_LANGUAGE_RULE

        user_prompt = f"""
用例图：
{json.dumps(diagram_context, ensure_ascii=False, indent=2)}

待核对名称（参与者与用例 name）：
{json.dumps(terms, ensure_ascii=False, indent=2)}
{req_block}

请输出 JSON：
{{
  "term_evaluations": [
    {{
      "term": "图中名称",
      "is_consistent": true,
      "matched_requirement": "对应的需求 id 或需求标题/原文片段（一致时填写）",
      "match_type": "exact|synonym|sub_use_case|bilingual",
      "reason": "仅在不一致时简要说明真实业务冲突",
      "suggestion": "仅在不一致时给出"
    }}
  ],
  "inconsistent_terms": [],
  "undefined_terms": [],
  "summary": {{
    "total_terms": 0,
    "consistent_count": 0,
    "inconsistent_count": 0
  }}
}}

只将 is_consistent 为 false 的项填入 inconsistent_terms。若无真实冲突，inconsistent_terms 必须为空且 consistent_count 等于 total_terms。只输出 JSON。"""
        return system_prompt, user_prompt
    
    # ============ 用例可验收性评估 ============
    
    @staticmethod
    def use_case_verifiability_prompt(use_cases: list[dict[str, any]]) -> tuple[str, str]:
        """
        用例可验收性评估Prompt
        
        Args:
            use_cases: 用例列表
            
        Returns:
            (system_prompt, user_prompt) 元组
        """
        system_prompt = """你是一个软件测试专家，擅长评估用例的可验证性。
请评估以下用例是否具有明确的、可被客观检验的成功条件。"""

        user_prompt = f"""
请评估以下用例是否可验证（即是否具有明确的成功条件）：

用例列表：
{json.dumps(use_cases, ensure_ascii=False, indent=2)}

评估标准：
1. 用例名称是否描述明确的用户目标
2. 用例是否包含明确的成功条件（成功时系统状态）
3. 用例是否包含可观察的结果（结果可测量）
4. 用例是否避免主观形容词（如"快速"、"友好"）
5. 用例是否避免模糊术语（如"处理"、"操作"）

请对每个用例进行评估，输出JSON格式的结果：
{{
  "evaluations": [
    {{
      "use_case_id": "用例ID",
      "use_case_name": "用例名称",
      "is_verifiable": true/false,
      "verification_criteria": ["可验证条件1", "可验证条件2"],
      "unverifiable_reasons": ["不可验证原因1", "不可验证原因2"],
      "suggested_improvements": ["改进建议1", "改进建议2"]
    }}
  ],
  "summary": {{
    "total_use_cases": 总数,
    "verifiable_count": 可验证数量,
    "unverifiable_count": 不可验证数量,
    "verifiability_rate": 可验证率百分比
  }}
}}

【重要】unverifiable_reasons 和 suggested_improvements 必须直接指出：具体哪个用例、缺少什么可验证条件、应如何补充。禁止"建议检查"等模糊表述。
只输出JSON，不要添加其他解释。所有字段请使用简体中文。"""
        
        return system_prompt, user_prompt
    
    # ============ 表达无歧义性评估（用例描述） ============
    
    @staticmethod
    def expression_ambiguity_prompt(expressions: list[str], 
                                   context: dict[str, any]) -> tuple[str, str]:
        """
        表达无歧义性评估Prompt（用于用例描述）
        
        Args:
            expressions: 需要评估的表达列表
            context: 上下文信息
            
        Returns:
            (system_prompt, user_prompt) 元组
        """
        system_prompt = """你是一个技术写作专家，擅长评估技术文档的清晰度。
歧义是指在给定用例上下文中，表达可能被理解为两种及以上截然不同的业务含义，且无法推断。
【原则】从宽认定无歧义。用例描述允许一定程度的通用表述，只要上下文可推断合理含义即不算歧义。"""

        user_prompt = f"""
请评估以下用例描述中的表达是否存在**真正的歧义**。宁可判为无歧义，不要过度报歧义。

上下文信息：
{json.dumps(context, ensure_ascii=False, indent=2)}

需要评估的表达列表：
{json.dumps(expressions, ensure_ascii=False, indent=2)}

评估标准（整体放宽）：
1. **模糊量词**：如"快速""大量"等，若在用例流程中含义可推断（如"系统快速响应"指返回结果），**不算歧义**。
2. **主观词**：如"友好""高效"，仅在完全无法推断业务含义时才算歧义；若语境明确（如"用户友好的界面"在登录场景中）**不算歧义**。
3. **代词**：若前文指代明确（同段内刚提到的"订单""用户"等），**不算歧义**。
4. **通用术语**：行业常见词（如"提交""确认""保存"）**不算歧义**。
5. **默认无歧义**：只要在用例上下文中能推断出合理单一含义，即判为**无歧义**。

请对每个表达进行评估，输出JSON格式的结果：
{{
  "evaluations": [
    {{
      "expression": "原始表达",
      "is_unambiguous": true/false,
      "ambiguity_reasons": ["歧义原因1", "歧义原因2"],
      "clarified_version": "澄清后的版本"
    }}
  ],
  "summary": {{
    "total_expressions": 总数,
    "unambiguous_count": 无歧义数量,
    "ambiguous_count": 有歧义数量,
    "ambiguity_rate": 歧义率百分比
  }}
}}

【重要】仅当表达在用例上下文中确实可对应多种截然不同含义且无法推断时，才设 is_unambiguous=false。ambiguity_reasons 必须直接指出多种可能含义。宁可少报歧义。只输出JSON，简体中文。"""
        
        return system_prompt, user_prompt

    # ============ 用例图：用例独立性 ============

    @staticmethod
    def use_case_independence_prompt(use_cases: list, diagram_context: dict) -> tuple[str, str]:
        """用例独立性：每个用例是否代表独立、完整、单一职责的用户目标。仅当用例参与 3 个以上 include/extend 关系时才判为可能不独立。"""
        system_prompt = """你是UML用例建模专家。请评估图中每个用例是否具有单一职责、独立完整的用户目标。
仅当用例被 3 个及以上 include/extend 关系连接（或被包含/扩展达 3 次以上）且职责混杂、边界模糊时，才判为不独立。
若用例名称或依赖关系显示其混合了多个用户目标（如“用户登录和管理”），或过度依赖大量其他用例而边界模糊，应判为不独立；否则判为独立。"""
        user_prompt = f"""
用例图上下文：
{json.dumps(diagram_context, ensure_ascii=False, indent=2)}

需要评估的用例列表：
{json.dumps(use_cases, ensure_ascii=False, indent=2)}

请对每个用例判断是否具有单一职责、独立完整。输出JSON：
{{
  "evaluations": [
    {{
      "use_case_id": "用例ID",
      "use_case_name": "用例名称",
      "is_independent": true/false,
      "reasons": ["原因1"],
      "suggestion": "改进建议"
    }}
  ],
  "summary": {{ "total": 总数, "independent_count": 独立数量 }}
}}
【重要】reasons 和 suggestion 必须直接指出：具体哪个用例、与哪些用例耦合、为何边界模糊。禁止"建议检查"等模糊表述。示例：reasons=["用例「用户管理」混合了登录、权限、资料修改，应拆分为独立用例"]。
只输出JSON。所有字段请使用简体中文。"""
        return system_prompt, user_prompt

    @staticmethod
    def diagram_necessity_four_category_prompt(diagram: dict, requirements: dict) -> tuple[str, str]:
        """用例图必要性（可追溯性）四分类评估：用例/参与者/关系是否多余。"""
        system_prompt = """你是需求工程与UML评审专家。请根据需求与用例图，对图中元素做“必要性（可追溯性）”四分类评估。
四分类定义（必须四选一）：
1) 合理细化：需求范围内自然展开，不新增需求承诺；
2) 有依据的补充：可由需求文本/术语/约束推导；
3) 无依据且不合理：无法在需求中找到依据；
4) 与需求矛盾：与需求陈述或约束明显冲突。
判定规则：
- 前两类视为“必要”（necessary=true）；
- 后两类视为“可能冗余/不必要”（necessary=false）。"""
        user_prompt = f"""
需求（结构化）：
{json.dumps(requirements or {{}}, ensure_ascii=False, indent=2)}

用例图：
{json.dumps(diagram, ensure_ascii=False, indent=2)}

请输出 JSON：
{{
  "use_case_evaluations": [
    {{
      "id": "uc_xxx",
      "name": "用例名",
      "category": "合理细化|有依据的补充|无依据且不合理|与需求矛盾",
      "necessary": true/false,
      "reason": "判定理由",
      "evidence": "需求依据或冲突点"
    }}
  ],
  "actor_evaluations": [
    {{
      "id": "actor_xxx",
      "name": "参与者名",
      "category": "合理细化|有依据的补充|无依据且不合理|与需求矛盾",
      "necessary": true/false,
      "reason": "判定理由",
      "evidence": "需求依据或冲突点"
    }}
  ],
  "relationship_evaluations": [
    {{
      "id": "rel_xxx",
      "from": "源元素名",
      "to": "目标元素名",
      "type": "association|include|extend|generalization",
      "category": "合理细化|有依据的补充|无依据且不合理|与需求矛盾",
      "necessary": true/false,
      "reason": "判定理由",
      "evidence": "需求依据或冲突点"
    }}
  ],
  "summary": {{
    "use_case_unsupported_count": 0,
    "actor_unsupported_count": 0,
    "relationship_unsupported_count": 0
  }}
}}
【重要】每条评估都必须给 category（四选一）和 reason；禁止输出“建议检查”这类空泛语句。只输出 JSON，使用简体中文。"""
        return system_prompt, user_prompt

    # ============ 用例描述：语义正确性 ============

    @staticmethod
    def description_semantic_correctness_prompt(description: dict) -> tuple[str, str]:
        """用例描述语义正确性：步骤是否表示可执行行为、符合用例建模语义。"""
        system_prompt = """你是用例描述与业务分析专家。请评估该用例描述中每一步是否表示可执行行为（主语+谓语+宾语），而非纯状态或UI细节（如“用户点击”单独成步可接受，但前置条件中不应写“用户点击提交”）。"""
        user_prompt = f"""
用例描述：
{json.dumps(description, ensure_ascii=False, indent=2)}

请输出JSON：
{{
  "evaluations": [
    {{ "step_index": 1, "step_text": "步骤文本", "step_location": "主流程步骤1 或 备选流X步骤N", "is_executable": true/false, "reason": "理由" }}
  ],
  "score": 0.0-1.0,
  "summary": "简要说明"
}}
【重要】step_location 必须标明精確位置：主流程步骤用「主流程步骤N」，备选流用「备选流X步骤N」（X为备选流名称）。reason 必须直接指出为何不可执行。禁止"建议检查"等模糊表述。
只输出JSON。所有字段请使用简体中文。"""
        return system_prompt, user_prompt

    @staticmethod
    def description_internal_logical_consistency_prompt(description: dict) -> tuple[str, str]:
        """用例描述内部逻辑一致性：前置/后置/主流程/备选流之间是否矛盾。"""
        system_prompt = """你是需求与用例分析专家。请检查该用例描述中前置条件、后置条件、主事件流、备选流之间是否存在逻辑矛盾（例如前置说“已登录”而后置说“未登录”）。同时检查：所列举的失败后态或异常结果是否与扩展流中的相应描述保持一致（续表6-1 后态检查项）。"""
        user_prompt = f"""
用例描述：
{json.dumps(description, ensure_ascii=False, indent=2)}

请输出JSON：
{{
  "is_consistent": true/false,
  "conflicts": ["矛盾描述1", "矛盾描述2"],
  "score": 0.0-1.0
}}
【重要】conflicts 必须直接列出具体矛盾：如"前置条件写「已登录」，后置条件写「未登录」"或"主流程步骤5与备选流A步骤2描述冲突"。禁止"建议检查逻辑一致性"等模糊表述。
只输出JSON。所有字段请使用简体中文。"""
        return system_prompt, user_prompt

    @staticmethod
    def description_step_verifiability_prompt(description: dict) -> tuple[str, str]:
        """步骤可测试性：每个步骤是否可派生为可执行的验收测试。"""
        system_prompt = """你是测试专家。请评估用例描述中每个步骤是否可验证（无模糊量词如“快速”“大量”，无主观词如“友好”；有可观察结果）。"""
        user_prompt = f"""
用例描述：
{json.dumps(description, ensure_ascii=False, indent=2)}

请对主流程与备选流中的每一步评估是否可测试。输出JSON：
{{
  "evaluations": [
    {{ "step_text": "步骤文本", "step_location": "主流程步骤N 或 备选流X步骤N", "is_verifiable": true/false, "reason": "理由" }}
  ],
  "score": 0.0-1.0,
  "summary": {{ "total_steps": 总数, "verifiable_count": 可验证数 }}
}}
【重要】step_location 必须标明精確位置。reason 必须直接指出含什么模糊词（如"快速"）、为何不可测。禁止"建议检查"等模糊表述。
只输出JSON。所有字段请使用简体中文。"""
        return system_prompt, user_prompt

    @staticmethod
    def description_functional_cohesion_prompt(description: dict) -> tuple[str, str]:
        """功能内聚性：描述是否紧扣单一用户目标、未混杂其他用例功能。"""
        system_prompt = """你是用例建模专家。请判断该用例描述是否只描述一个用户目标，是否混杂了其他用例的核心功能（如“用户管理”里混入“订单查询”）。"""
        user_prompt = f"""
用例描述：
{json.dumps(description, ensure_ascii=False, indent=2)}

请输出JSON：
{{
  "has_single_goal": true/false,
  "cross_functionality": ["混杂的功能描述"],
  "score": 0.0-1.0
}}
【重要】cross_functionality 必须直接列出：具体哪些描述属于其他用例（如"步骤5「查询订单」属于订单管理用例，不应出现在购买课程中"）。禁止"建议检查"等模糊表述。
只输出JSON。所有字段请使用简体中文。"""
        return system_prompt, user_prompt

    @staticmethod
    def description_information_relevance_prompt(description: dict) -> tuple[str, str]:
        """信息相关性：描述内容是否与用例目标相关、无无关信息。"""
        system_prompt = """你是需求分析专家。请判断该用例描述中各步骤、前置/后置条件是否与用例目标和需求依据一致。
请将每个片段严格划分为以下四类之一：
1) 合理细化：在需求范围内的自然展开，不新增需求承诺；
2) 有依据的补充：虽未逐字出现在用例名，但可由需求文本、约束或术语推导；
3) 无依据且不合理：无法在需求中找到依据，且不应出现在该用例；
4) 与需求矛盾：与需求或前后逻辑明显冲突。"""
        user_prompt = f"""
用例描述：
{json.dumps(description, ensure_ascii=False, indent=2)}

请输出JSON：
{{
  "evaluations": [
    {{
      "fragment": "片段文本",
      "step_location": "主流程步骤N 或 备选流X步骤N 或 前置条件 或 后置条件",
      "category": "合理细化|有依据的补充|无依据且不合理|与需求矛盾",
      "is_relevant": true/false,
      "reason": "分类理由（需指出依据或冲突点）",
      "evidence": "可选，引用需求依据关键词或冲突对象"
    }}
  ],
  "score": 0.0-1.0,
  "irrelevant_count": 无关片段数,
  "summary": {{
    "reasonable_refinement_count": 0,
    "grounded_supplement_count": 0,
    "unsupported_count": 0,
    "contradiction_count": 0
  }}
}}
【打分建议】
- 合理细化、有依据的补充 视为 relevant；
- 无依据且不合理、与需求矛盾 视为 irrelevant（其中矛盾问题严重度更高）。
【重要】step_location 必须标明精確位置；category 必须四选一；reason 不能写“建议检查”这类空泛语句。只输出JSON。所有字段请使用简体中文。"""
        return system_prompt, user_prompt

    # ============ 多智能體協作：審核與再評估 ============

    @staticmethod
    def review_evaluation_prompt(task_name: str, original_input: dict, evaluation_result: dict) -> tuple[str, str]:
        """審核者 prompt：對初評結果做出評價與修改建議"""
        system_prompt = """你是用例模型質量評估的資深審核專家。你將收到一份由另一模型完成的評估結果，以及原始輸入。請從專業角度審核該評估是否合理、是否有遺漏或誤判，並給出具體修改建議。"""
        user_prompt = f"""
評估任務：{task_name}

原始輸入：
{json.dumps(original_input, ensure_ascii=False, indent=2)}

初評結果：
{json.dumps(evaluation_result, ensure_ascii=False, indent=2)}

請審核並輸出 JSON：
{{
  "overall_agreement": true/false,
  "agreement_summary": "對初評的整體評價（是否合理、有無明顯問題）",
  "corrections": [
    {{ "item": "具體項目（如關係ID、用例名等）", "issue": "初評的問題", "suggestion": "建議如何修正" }}
  ],
  "missed_issues": ["初評遺漏的問題1", "初評遺漏的問題2"],
  "false_positives": ["初評誤判為問題的項1"]
}}

若初評完全合理，corrections、missed_issues、false_positives 可為空數組。只輸出 JSON，使用簡體中文。"""
        return system_prompt, user_prompt

    @staticmethod
    def reevaluate_with_feedback_prompt(task_name: str, original_input: dict, initial_result: dict, feedbacks: list) -> tuple[str, str]:
        """初評者再評估 prompt：結合審核反饋重新評估"""
        feedback_str = "\n\n".join(
            f"審核意見 {i+1}：\n{json.dumps(f, ensure_ascii=False, indent=2)}" for i, f in enumerate(feedbacks)
        )
        system_prompt = """你是用例模型質量評估專家。你已完成初評，現收到其他專家的審核意見。請結合這些意見，修正初評中不合理之處，產出最終評估結果。若審核意見合理，應採納並修正；若你認為審核意見有誤，可保留原判斷但需簡要說明理由。"""
        user_prompt = f"""
評估任務：{task_name}

原始輸入：
{json.dumps(original_input, ensure_ascii=False, indent=2)}

你的初評結果：
{json.dumps(initial_result, ensure_ascii=False, indent=2)}

審核意見：
{feedback_str}

請輸出修正後的最終評估結果，格式與初評結果完全一致（保留 score、llm_evaluations、summary 等字段）。只輸出 JSON，使用簡體中文。"""
        return system_prompt, user_prompt

    # ============ 整合 Prompt（一次調用解決多指標） ============

    @staticmethod
    def diagram_quality_batch_prompt(diagram: dict, requirements: dict = None) -> tuple[str, str]:
        """用例圖質量整合評估：語義 + 歧義 + 獨立性 + 完整性 + 術語一致性，一次調用"""
        req_block = ""
        if requirements:
            req_json = build_requirements_context_for_llm(diagram, requirements)
            if req_json:
                req_block = f"""
需求（完整结构化 JSON，每条功能的 text/description 均为全文，勿当作截断摘要）：
{req_json}
"""
        system_prompt = """你是用例圖質量評估專家。請在一次評估中完成語義、歧義、獨立性、「完整性」與「術語一致性」五項，輸出統一 JSON。
完整性：通讀需求 JSON 全文與用例圖判断覆盖，禁止因需求看似截断而扣分。
术语一致性：对照需求完整句，从宽认定；子用例名、中英文同义、修改密码与 change PIN 等均视为一致；禁止用碎片化术语表或「标准术语表中没有某词」类理由挑刺。
""" + _PROMPT_LANGUAGE_RULE
        user_prompt = f"""
用例圖：
{json.dumps(diagram, ensure_ascii=False, indent=2)}
{req_block}

請完成並輸出 JSON：
{{
  "semantic_correctness": {{
    "evaluations": [{{"relationship_id":"","is_valid":true/false,"reason":"","suggestion":""}}],
    "score": 0.0-1.0,
    "summary": {{"valid_count":0,"total_relationships":0}}
  }},
  "element_ambiguity": {{
    "ambiguous_elements": [{{"id":"","name":"","type":"actor|use_case","reasons":[]}}],
    "score": 0.0-1.0,
    "summary": {{"total_elements":0,"ambiguous_count":0}}
  }},
  "use_case_independence": {{
    "dependent_cases": [{{"id":"","name":"","reasons":[]}}],
    "score": 0.0-1.0,
    "summary": {{"independent_count":0,"total_use_cases":0}}
  }},
  "diagram_completeness": {{
    "actor_completeness": {{
      "score": 0.0-1.0,
      "issues": ["外部参与者：需求正文出现 customers/客户 等则必须在图中有对应 Actor；若需求要求 Customer 而图中无任何 Customer/客户 参与者，必须扣分并写明缺失。禁止建议添加 Bank Database 等内部组件为参与者"]
    }},
    "use_case_completeness": {{
      "score": 0.0-1.0,
      "issues": ["僅當某條 functional_requirements/goal_level 的完整描述在圖中確無對應用例時列出；禁止抱怨需求摘要截断、禁止建议补充完整需求描述（输入已是全文）"]
    }},
    "relationship_completeness": {{
      "score": 0.0-1.0,
      "issues": ["具體說明：缺少某參與者與用例的關聯、缺少必要的 include/extend 等"]
    }},
    "system_boundary_completeness": {{
      "score": 0.0-1.0,
      "issues": ["具體說明：未標系統邊界、用例未置於邊界內、邊界語義不清等"]
    }}
  }},
  "terminology_consistency": {{
    "term_evaluations": [{{"term":"","is_consistent":true,"matched_requirement":"","match_type":"synonym","reason":"","suggestion":""}}],
    "score": 0.0-1.0,
    "inconsistent_terms": [],
    "summary": {{"total_terms":0,"consistent_count":0,"inconsistent_count":0}}
  }}
}}

評估要點：1) 語義：跨语言时 Customer-取款、include Validate PIN 等 ATM 常模合理则 is_valid=true；is_valid=false 须写明当前类型与建议类型。2) 歧義：從寬。3) 獨立性。4) 完整性。5) 術語：从宽。只輸出 JSON。"""
        return system_prompt, user_prompt

    @staticmethod
    def description_quality_batch_prompt(description: dict) -> tuple[str, str]:
        """用例描述質量整合評估：語義 + 無歧義 + 邏輯一致 + 可測試 + 內聚 + 相關性，一次調用"""
        system_prompt = """你是用例描述質量評估專家。請在一次評估中完成多項檢查，並增加「結構完整性」評分（不要用固定步數閾值機械扣分；從業務上判斷主流程、備選流、前置/後置是否足以支撐該用例目標）。
""" + _PROMPT_LANGUAGE_RULE
        user_prompt = f"""
用例描述：
{json.dumps(description, ensure_ascii=False, indent=2)}

請完成並輸出 JSON：
{{
  "semantic_correctness": {{"evaluations":[{{"step_index":1,"step_text":"","step_location":"主流程步驟N","is_executable":true/false,"reason":""}}],"score":0.0-1.0}},
  "expression_unambiguity": {{"evaluations":[{{"expression":"","is_unambiguous":true/false,"ambiguity_reasons":[]}}],"score":0.0-1.0}},
  "internal_logical_consistency": {{"is_consistent":true/false,"conflicts":[],"score":0.0-1.0}},
  "step_verifiability": {{"evaluations":[{{"step_text":"","step_location":"","is_verifiable":true/false,"reason":""}}],"score":0.0-1.0}},
  "functional_cohesion": {{"has_single_goal":true/false,"cross_functionality":[],"score":0.0-1.0}},
  "information_relevance": {{
    "evaluations":[{{"fragment":"","step_location":"","category":"合理细化|有依据的补充|无依据且不合理|与需求矛盾","is_relevant":true/false,"reason":"","evidence":""}}],
    "score":0.0-1.0
  }},
  "description_completeness": {{
    "main_flow": {{"score":0.0-1.0,"issues":["若主流程有问题，每条 issue 须写明本用例 name 或 id，如「用例 Withdraw Cash（UC-01）：…」"]}},
    "alternative_flows": {{"score":0.0-1.0,"issues":["若备选流有问题，每条 issue 须写明本用例 name 或 id"]}},
    "pre_post_conditions": {{"score":0.0-1.0,"issues":["若前置/后置为空或与主流程矛盾，每条 issue 须写明本用例 name 或 id，并说明缺什么或应补充什么"]}}
  }}
}}

檢查要點：步驟可執行、邏輯一致、可驗證、功能單一、與用例目標相關。表達無歧義從寬認定：僅當表述在用例上下文中可指多種截然不同含義且無法推斷時才記為有歧義；通用術語、可推斷的模糊詞不算歧義。完整性：對照**当前 JSON 中该用例**的 goal、主流程、备选流与 preconditions/postconditions；description_completeness 下每条 issues 字符串必须包含该用例的 name 或 id，便于报告定位。只輸出 JSON。"""
        return system_prompt, user_prompt