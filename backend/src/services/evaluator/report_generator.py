from typing import Dict, Any, List

class ReportGenerator:
    """评估报告生成器类（IEEE 830 体系）"""
    
    def generate(self, evaluation_results: Dict[str, Any], input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        生成评估报告
        """
        # 复制原始结果，保留所有字段
        report = evaluation_results.copy()
        
        # 添加 LLM 验证部分的格式化（可选）
        llm_results = evaluation_results.get('llm_validation_results', {})
        report['llm_semantic_validation'] = self._format_llm_results(llm_results)
        
        return report
    
    def _format_llm_results(self, llm_results: Dict[str, Any]) -> Dict[str, Any]:
        """格式化LLM验证结果"""
        validated = llm_results.get("validated_relationships", [])
        summary = llm_results.get("summary", {})
        
        return {
            "summary": summary,
            "detailed_results": validated,
            "recommendations": self._generate_llm_recommendations(validated)
        }
    
    def _generate_llm_recommendations(self, validated_results: List[Dict[str, Any]]) -> List[str]:
        """基于LLM验证结果生成建议"""
        recommendations = []
        invalid_results = [r for r in validated_results if not r.get("is_valid", True)]
        if invalid_results:
            recommendations.append("LLM语义验证发现以下关系存在问题：")
            for i, result in enumerate(invalid_results[:3], 1):
                rel_id = result.get("relationship_id", "未知关系")
                reason = result.get("reason", "")
                recommendations.append(f"  {i}. 关系 {rel_id}: {reason}")
        return recommendations