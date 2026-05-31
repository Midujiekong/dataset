"""
质量特性配置 - 按最新评估表组织
评估对象 → 质量特性 → 子属性(attribute)
"""

# 用例图质量特性
DIAGRAM_QUALITY_CONFIG = {
    "consistency_and_normativity": {
        "label": "一致性与规范性",
        "description": "用例图在语法结构、语义表达及术语使用上符合 UML 2.5 规范和相关建模约定",
        "attributes": {
            "syntax_correctness": {
                "label": "语法规范性",
                "description": "用例图符合 UML 用例图语法规范的程度",
            },
            "semantic_correctness": {
                "label": "语义正确性",
                "description": "用例图中各元素及其关系所表达的含义符合UML规范或建模语义约定的程度",
            },
            "terminology_consistency": {
                "label": "术语一致性",
                "description": "用例图名称与需求全文用语是否在业务上一致（LLM 从宽评估，含子用例名与中英文同义；不用碎片化术语表机械对齐）",
            },
            "element_unambiguity": {
                "label": "元素无歧义性",
                "description": "用例图中每个元素的名称不存在多种可能解释的程度",
            },
        },
    },
    "completeness": {
        "label": "完整性",
        "description": "用例图中包含理解系统需求所必需的全部建模元素的程度",
        "attributes": {
            "actor_completeness": {"label": "参与者完整性", "description": "用例图中是否覆盖需求中的外部角色（人、外部业务系统）；不含待建系统本体及边界内的数据库、仓储等技术组件"},
            "use_case_completeness": {"label": "用例完整性", "description": "用例图覆盖系统需求中定义的功能点的程度"},
            "relationship_completeness": {"label": "关系完整性", "description": "用例图中参与者与用例之间、用例与用例之间的必要关系被建模的程度"},
            "system_boundary_completeness": {"label": "系统边界完整性", "description": "用例图清晰定义系统边界的程度"},
        },
    },
    "necessity_traceability": {
        "label": "必要性（可追溯性）",
        "description": "用例图中的元素能够通过唯一标识符与上游需求建立明确的对应关系",
        "attributes": {
            "use_case_redundancy": {"label": "用例冗余性", "description": "用例图中出现需求中未提及的功能的程度"},
            "actor_redundancy": {"label": "参与者冗余性", "description": "用例图中出现与系统无关的参与者的程度"},
            "relationship_redundancy": {"label": "关系冗余性", "description": "用例图中存在根据需求不应出现的关系的程度"},
        },
    },
    "modifiability": {
        "label": "可修改性",
        "description": "用例图的结构易于进行局部调整，且修改的影响范围可控的程度",
        "attributes": {
            "use_case_independence": {"label": "用例独立性", "description": "用例图中每个用例代表独立的用户目标"},
        },
    },
}

# 用例描述质量特性
DESCRIPTION_QUALITY_CONFIG = {
    "consistency_and_normativity": {
        "label": "一致性与规范性",
        "description": "用例描述的文档结构、步骤编号、字段完整性符合预定义模板要求",
        "attributes": {
            "syntax_correctness": {"label": "语法正确性", "description": "用例描述的文档结构、步骤编号、字段完整性符合预定义模板要求的程度"},
            "semantic_correctness": {"label": "语义正确性", "description": "用例描述中每个步骤的表达方式符合用例建模语义约定的程度"},
            "terminology_consistency": {"label": "术语一致性", "description": "用例描述全文对同一业务概念、对象或操作使用相同术语进行指称的程度"},
            "expression_unambiguity": {"label": "表达无歧义性", "description": "用例描述中不存在同一用词多重含义的情况的程度"},
            "internal_logical_consistency": {"label": "内部逻辑一致性", "description": "用例描述中不同部分所描述的事实、状态与约束互不矛盾的程度"},
        },
    },
    "completeness": {
        "label": "完整性",
        "description": "用例描述中包含了定义其完整行为所必需的全部信息要素的程度",
        "attributes": {
            "main_flow_completeness": {"label": "主事件流完整性", "description": "用例描述中的主事件流完整覆盖用例目标的核心业务过程的程度"},
            "alternative_flow_completeness": {"label": "备选流程/异常流程完整性", "description": "用例描述完整刻画可能出现的分支情形和异常情况的程度"},
            "pre_post_condition_completeness": {"label": "前置、后置条件完整性", "description": "用例描述明确给出了用例执行前必须满足的条件以及执行结束后系统应处于的状态"},
        },
    },
    "modifiability": {
        "label": "可修改性",
        "description": "用例描述对特定流程或规则的修改能够被快速定位和局部化实施的程度",
        "attributes": {
            "structure_clarity": {"label": "结构清晰性", "description": "用例描述的格式、布局和编号方式易于人类阅读和导航的程度"},
            "content_redundancy": {"label": "内容冗余度", "description": "用例描述中存在完全相同或语义重复的信息片段的程度"},
            "functional_cohesion": {"label": "功能内聚性", "description": "用例描述中的事件流紧密围绕单一用户目标展开的程度"},
        },
    },
    "necessity_traceability": {
        "label": "必要性（可追溯性）",
        "description": "用例描述中的信息能够清晰体现其需求来源，并为后续设计与测试提供唯一、明确的引用标识",
        "attributes": {
            "information_relevance": {"label": "信息相关性", "description": "用例描述中出现与需求无关的多余描述的程度"},
            "identifier_uniqueness": {"label": "标识唯一性", "description": "用例描述中的每个用例具有唯一标识的程度"},
        },
    },
}
