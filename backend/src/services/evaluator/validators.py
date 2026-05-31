"""
数据验证工具
"""
from typing import Dict, Any, List, Tuple

def validate_use_case_diagram(diagram: Dict[str, Any]) -> Tuple[bool, str]:
    """
    验证用例图数据格式
    
    Returns:
        (是否有效, 错误信息)
    """
    if not isinstance(diagram, dict):
        return False, "用例图必须是字典格式"
    
    # TODO: 添加更多验证规则
    return True, ""

def validate_use_case_descriptions(descriptions: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    验证用例描述数据格式
    
    Returns:
        (是否有效, 错误信息)
    """
    if not isinstance(descriptions, list):
        return False, "用例描述必须是列表格式"
    
    # TODO: 添加更多验证规则
    return True, ""
