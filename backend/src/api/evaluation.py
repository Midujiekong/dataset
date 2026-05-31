"""
评估相关API路由
"""
import os
from flask import request, jsonify
from api import api_bp
from services.evaluator.evaluation_service import EvaluationService
from services.evaluator.external_evaluation_client import ExternalEvaluationError, use_external_evaluation

# 有 DEEPSEEK_API_KEY 时启用 LLM；可通過 USE_LLM=false 強制關閉（API 連不上時用規則評估）
def _use_llm():
    use_env = os.environ.get("USE_LLM", "").strip().lower()
    if use_env in ("false", "0", "no", "off"):
        return False
    if use_env in ("true", "1", "yes", "on"):
        return True
    try:
        from config import Config
        return bool(Config.DEEPSEEK_API_KEY)
    except Exception:
        return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())

evaluation_service = EvaluationService(use_llm=_use_llm())

@api_bp.route('/evaluate', methods=['POST'])
def evaluate():
    """
    评估用例模型质量
    接收JSON格式的用例图和用例描述，返回评估报告
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': '请求体不能为空'
            }), 400
        
        # 验证输入数据格式
        if 'use_case_diagram' not in data or 'use_case_descriptions' not in data:
            return jsonify({
                'success': False,
                'error': '缺少必要字段：use_case_diagram 或 use_case_descriptions'
            }), 400

        # 需求输入：允许两种形式
        # - requirements: 结构化需求。支援統一 schema（goal_level_requirements 等），服務內會轉為引擎格式
        # - requirements_text: 非/半结构化文本（需先抽取为 requirements）
        if data.get("requirements") is None and not data.get("requirements_text"):
            return jsonify({
                'success': False,
                'error': '缺少需求输入：请提供 requirements（结构化）或 requirements_text（文本）'
            }), 400

        # 使用文本需求时，若已配置 API Key 则自动用 LLM 抽取
        if data.get("requirements_text") and data.get("requirements") is None:
            data = dict(data)
            data["use_llm_for_extraction"] = _use_llm()
        
        # 执行评估（默认转发至外部 3 Agent 平台）
        report = evaluation_service.evaluate(data)
        
        return jsonify({
            'success': True,
            'data': report
        }), 200

    except ExternalEvaluationError as e:
        status = e.status_code or 502
        payload = {
            'success': False,
            'error': str(e),
        }
        if e.response_body is not None:
            payload['external_response'] = e.response_body
        return jsonify(payload), status
        
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': tb
        }), 500

@api_bp.route('/health', methods=['GET'])
def health():
    """健康檢查接口"""
    info = {
        'status': 'healthy',
        'service': '用例模型质量评估系统',
    }
    if use_external_evaluation():
        client = getattr(evaluation_service, 'external_client', None)
        info['evaluation_backend'] = 'external'
        info['external_evaluation_url'] = getattr(client, 'base_url', '')
        info['external_evaluation_mode'] = getattr(client, 'evaluation_mode', 'detailed')
        info['multi_agent_count'] = 3
    else:
        try:
            eng = getattr(evaluation_service, 'evaluation_engine', None)
            if eng and getattr(eng.metrics, 'llm_evaluator', None):
                ev = eng.metrics.llm_evaluator
                if hasattr(ev, 'evaluators'):
                    info['multi_agent_count'] = len(ev.evaluators)
                    info['multi_agent_models'] = [
                        e.llm_manager.provider.get_model_name()
                        for e in ev.evaluators
                    ]
        except Exception:
            pass
    return jsonify(info), 200
