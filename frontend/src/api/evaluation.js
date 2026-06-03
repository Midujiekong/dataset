/**
 * 评估相关 API
 */
import axios from 'axios'

// 评估含多轮 LLM 调用（多智能体 × 多指标 × 多用例描述），整体耗时可达 30–60 分钟
const EVALUATION_TIMEOUT_MS = 60 * 60 * 1000

const api = axios.create({
  baseURL: '/api',
  timeout: EVALUATION_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json'
  }
})

/**
 * 提交评估
 * @param {Object} data
 * @param {string} [data.requirements_text] - 需求文本（与 requirements 二选一）
 * @param {Object} [data.requirements] - 结构化需求（goal_level_requirements 等）
 * @param {Object} data.use_case_diagram
 * @param {Array|Object} data.use_case_descriptions - 用例描述数组；对象时可含 useCases / use_cases
 * @param {string} [data.evaluation_mode]
 */
export const evaluate = (data) => {
  return api.post('/evaluate', data)
    .then(response => response.data)
    .catch(error => {
      const msg = error.response?.data?.error || error.message || '请求失败'
      const err = new Error(msg)
      err.response = error.response
      throw err
    })
}

/**
 * 健康检查
 */
export const healthCheck = () => {
  return api.get('/health')
    .then(response => response.data)
    .catch(() => {
      throw new Error('服务不可用')
    })
}
