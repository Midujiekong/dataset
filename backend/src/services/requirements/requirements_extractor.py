"""
需求抽取统一入口（面向“原始需求文本”）。

注意：真正的抽取逻辑已经实现于
`src.services.evaluator.requirements_parser.extract_structured_requirements`。
本模块只是提供一个更语义化、位置更直观的包装，方便调用方按
“services.requirements” 这个命名空间来使用。
"""

from typing import Any, Dict

from src.services.evaluator.requirements_parser import extract_structured_requirements as _core_extract


def extract_structured_requirements(
    requirements_text: str,
    use_llm: bool = False,
    llm_provider: str = "deepseek",
    fallback_to_rules: bool = True,
) -> Dict[str, Any]:
    """
    将非/半结构化的需求文本抽取为评估引擎需要的结构化 requirements 字典。

    这只是对 evaluator.requirements_parser.extract_structured_requirements 的薄封装：
    - 默认关闭 LLM（use_llm=False），保证在本地无 API Key 时也能正常跑通。
    - 其余参数直接透传。
    """
    text = (requirements_text or "").strip()
    if not text:
        raise ValueError("requirements_text 不能为空")

    return _core_extract(
        raw_text=text,
        use_llm=use_llm,
        llm_provider=llm_provider,
        fallback_to_rules=fallback_to_rules,
    )

