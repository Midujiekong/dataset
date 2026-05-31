"""
弱语义匹配器
提供中文文本的弱语义匹配功能，用于用例名称、功能需求等的模糊匹配
"""

class WeakSemanticMatcher:
    """弱语义匹配器类"""

    @staticmethod
    def normalize(text: str) -> str:
        """
        文本规范化
        
        去除中文文本中的辅助词和常见修饰词，保留核心语义
        
        Args:
            text: 原始文本
            
        Returns:
            str: 规范化后的文本
        """
        if not isinstance(text, str):
            return ""
        s = text.lower().strip()
        # 中文常见虚词
        for t in ("应", "能够", "可以", "用户", "系统", "需要", "进行"):
            s = s.replace(t, "")
        # 英文功能词
        for t in (" the ", " a ", " an ", " to ", " of ", " in ", " on ", " and ", " or ", " can ", " should ", " must "):
            s = s.replace(t, " ")
        return " ".join(s.split())

    @staticmethod
    def weak_match(a: str, b: str) -> bool:
        """
        弱语义匹配
        
        比较两个文本是否在语义上相似，基于规范化后的文本和字符重叠
        
        Args:
            a: 文本a
            b: 文本b
            
        Returns:
            bool: 如果语义相似则返回True
        """
        if not a or not b:
            return False

        a_n = WeakSemanticMatcher.normalize(a)
        b_n = WeakSemanticMatcher.normalize(b)

        if not a_n or not b_n:
            return False

        # 英文词级匹配（Jaccard）
        a_tokens = set(x for x in a_n.replace("-", " ").replace("_", " ").split(" ") if x)
        b_tokens = set(x for x in b_n.replace("-", " ").replace("_", " ").split(" ") if x)
        if a_tokens and b_tokens:
            inter = len(a_tokens & b_tokens)
            union = len(a_tokens | b_tokens)
            if union > 0 and (inter / union) >= 0.34:
                return True

        # 中文按字符重叠兜底
        for token in a_n:
            if token in b_n:
                return True

        return a_n in b_n or b_n in a_n