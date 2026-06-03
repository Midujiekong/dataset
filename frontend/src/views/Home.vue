<template>
  <div class="home">
    <header class="hero">
      <div class="hero-inner">
        <div class="hero-badge">用例模型质量评估</div>
        <h1 class="hero-title">自动化混合评估工作台</h1>
        <p class="hero-desc">
          上传需求（Markdown / 纯文本 或 结构化需求 JSON）、用例图与用例描述 JSON，一键生成多维度得分、问题定位与改进建议。
        </p>
      </div>
    </header>

    <section class="panel">
      <div class="panel-head">
        <span class="panel-step">1</span>
        <div>
          <h2 class="panel-title">数据准备</h2>
          <p class="panel-sub">支持拖拽上传，三项就绪后可开始评估</p>
        </div>
      </div>
      <el-row :gutter="20" class="upload-row">
        <el-col :xs="24" :md="8">
          <div class="upload-card-wrap">
            <div class="upload-card-label">需求</div>
            <el-card shadow="hover" class="upload-card">
              <template #header>
                <span class="card-header-inner">
                  <el-icon class="header-icon"><Document /></el-icon>
                  需求文档
                </span>
              </template>
              <el-upload
                drag
                :auto-upload="false"
                :show-file-list="false"
                accept=".md,.txt,.markdown,.json"
                class="upload-inner"
                :on-change="(f) => onRequirementChange(f)"
              >
                <el-icon class="upload-icon"><UploadFilled /></el-icon>
                <div class="upload-text">拖拽到此处或<em>点击上传</em></div>
                <div class="upload-tip">.md / .txt / 结构化需求 JSON（goal_level_requirements）</div>
              </el-upload>
              <div v-if="requirementError" class="error-tip">{{ requirementError }}</div>
              <div v-else-if="requirementText || requirementStructured" class="success-tip">
                <el-icon><CircleCheck /></el-icon> 已加载 {{ requirementFileName }}
              </div>
            </el-card>
          </div>
        </el-col>
        <el-col :xs="24" :md="8">
          <div class="upload-card-wrap">
            <div class="upload-card-label">模型</div>
            <el-card shadow="hover" class="upload-card">
              <template #header>
                <span class="card-header-inner">
                  <el-icon class="header-icon"><Picture /></el-icon>
                  用例图
                </span>
              </template>
              <el-upload
                drag
                :auto-upload="false"
                :show-file-list="false"
                accept=".json"
                class="upload-inner"
                :on-change="(f) => onDiagramChange(f)"
              >
                <el-icon class="upload-icon"><UploadFilled /></el-icon>
                <div class="upload-text">拖拽到此处或<em>点击上传</em></div>
                <div class="upload-tip">JSON · actors / use_cases / relationships（可含 diagram_type、title）</div>
              </el-upload>
              <div v-if="diagramError" class="error-tip">{{ diagramError }}</div>
              <div v-else-if="useCaseDiagram" class="success-tip">
                <el-icon><CircleCheck /></el-icon> 已加载 {{ diagramFileName }}
              </div>
            </el-card>
          </div>
        </el-col>
        <el-col :xs="24" :md="8">
          <div class="upload-card-wrap">
            <div class="upload-card-label">描述</div>
            <el-card shadow="hover" class="upload-card">
              <template #header>
                <span class="card-header-inner">
                  <el-icon class="header-icon"><List /></el-icon>
                  用例描述
                </span>
              </template>
              <el-upload
                drag
                :auto-upload="false"
                :show-file-list="false"
                accept=".json"
                class="upload-inner"
                :on-change="(f) => onDescriptionsChange(f)"
              >
                <el-icon class="upload-icon"><UploadFilled /></el-icon>
                <div class="upload-text">拖拽到此处或<em>点击上传</em></div>
                <div class="upload-tip">JSON 数组或含 useCases / use_cases / use_case_descriptions / descriptions 的对象</div>
              </el-upload>
              <div v-if="descriptionsError" class="error-tip">{{ descriptionsError }}</div>
              <div v-else-if="useCaseDescriptions" class="success-tip">
                <el-icon><CircleCheck /></el-icon> 已加载 {{ descriptionsFileName }}
              </div>
            </el-card>
          </div>
        </el-col>
      </el-row>
    </section>

    <section class="panel action-panel">
      <div class="panel-head">
        <span class="panel-step">2</span>
        <div>
          <h2 class="panel-title">触发评估</h2>
          <p class="panel-sub">快速模式耗时更短；详细模式多模型协作，结果更稳</p>
        </div>
      </div>
      <div class="action-inner">
        <div class="action-btns">
          <el-button
            type="primary"
            size="large"
            round
            :loading="loading"
            :disabled="!canEvaluate"
            class="action-btn action-btn-primary"
            @click="() => runEvaluate('quick')"
          >
            <el-icon><Lightning /></el-icon>
            快速评估
          </el-button>
          <el-button
            type="success"
            size="large"
            round
            plain
            :loading="loading"
            :disabled="!canEvaluate"
            class="action-btn"
            @click="() => runEvaluate('detailed')"
          >
            <el-icon><DataAnalysis /></el-icon>
            详细评估
          </el-button>
        </div>
        <div v-if="!canEvaluate" class="action-hint muted">请先完成三份文件上传</div>
        <div v-else class="action-hint tags">
          <el-tag effect="dark" type="info" size="small">快速</el-tag>
          <span>单模型</span>
          <span class="dot">·</span>
          <el-tag effect="dark" type="success" size="small">详细</el-tag>
          <span>多智能体协作</span>
        </div>
      </div>
    </section>

    <transition name="fade-slide">
      <section v-if="report" class="report-shell">
        <div class="report-top">
          <div>
            <h2 class="report-title">评估报告</h2>
            <p class="report-sub">综合用例图与用例描述加权结果</p>
          </div>
          <div class="report-tags">
            <el-tag v-if="report.evaluation_mode === 'detailed'" type="success" effect="plain" round>
              详细 · 多智能体
            </el-tag>
            <el-tag v-else type="info" effect="plain" round>快速</el-tag>
            <el-tag type="warning" effect="plain" round>用时 {{ evaluationDurationText }}</el-tag>
          </div>
        </div>

        <el-row :gutter="16" class="stat-row">
          <el-col :xs="24" :sm="8">
            <div class="stat-card stat-card-main">
              <div class="stat-label">综合得分</div>
              <div class="stat-value" :class="'tone-' + overallScoreType">{{ overallScoreText }}</div>
              <el-progress
                :percentage="overallPercent"
                :stroke-width="10"
                :color="progressColor"
                :show-text="false"
                class="stat-progress"
              />
            </div>
          </el-col>
          <el-col :xs="24" :sm="8">
            <div class="stat-card">
              <div class="stat-label">用例图</div>
              <div class="stat-value secondary">{{ diagramOverallText }}</div>
              <el-progress
                :percentage="diagramOverallPercent"
                :stroke-width="8"
                :color="progressColorSoft"
                :show-text="false"
              />
            </div>
          </el-col>
          <el-col :xs="24" :sm="8">
            <div class="stat-card">
              <div class="stat-label">用例描述</div>
              <div class="stat-value secondary">{{ descriptionOverallText }}</div>
              <el-progress
                :percentage="descriptionOverallPercent"
                :stroke-width="8"
                :color="progressColorSoft"
                :show-text="false"
              />
            </div>
          </el-col>
        </el-row>

        <div class="report-section">
          <div class="section-title-row">
            <el-icon class="section-icon"><Picture /></el-icon>
            <h3>用例图 · 质量维度</h3>
          </div>
          <el-collapse v-model="activeDiagram" class="dim-collapse">
            <el-collapse-item
              v-for="dim in diagramDimensions"
              :key="'d-' + dim.key"
              :name="dim.key"
            >
              <template #title>
                <span class="collapse-title">
                  {{ dim.label }}
                  <el-tag :type="scoreTagType(dim.score)" size="small" effect="plain" round>
                    {{ dim.scoreText }}
                  </el-tag>
                </span>
              </template>
              <div v-if="dim.attributes?.length" class="attr-grid">
                <div v-for="attr in dim.attributes" :key="attr.key" class="attr-card">
                  <div class="attr-card-head">
                    <span>{{ attr.label }}</span>
                    <el-tag :type="scoreTagType(attr.score)" size="small">{{ (attr.score * 100).toFixed(0) }}%</el-tag>
                  </div>
                  <ul v-if="attr.score < 1.0 && attr.issues?.length" class="issue-chips">
                    <li v-for="(issue, i) in attr.issues" :key="i">{{ issueText(issue) }}</li>
                  </ul>
                  <p v-else-if="attr.score >= 1.0" class="no-issues">该项无扣分问题</p>
                </div>
              </div>
              <ul v-else-if="dim.issues?.length" class="issue-list">
                <li v-for="(issue, i) in dim.issues" :key="i">{{ issueText(issue) }}</li>
              </ul>
              <p v-else class="no-issues">无问题</p>
            </el-collapse-item>
          </el-collapse>
        </div>

        <div class="report-section">
          <div class="section-title-row">
            <el-icon class="section-icon"><List /></el-icon>
            <h3>用例描述 · 质量维度</h3>
          </div>
          <el-collapse v-model="activeDescription" class="dim-collapse">
            <el-collapse-item
              v-for="dim in descriptionDimensions"
              :key="'desc-' + dim.key"
              :name="dim.key"
            >
              <template #title>
                <span class="collapse-title">
                  {{ dim.label }}
                  <el-tag :type="scoreTagType(dim.score)" size="small" effect="plain" round>
                    {{ dim.scoreText }}
                  </el-tag>
                </span>
              </template>
              <div v-if="dim.attributes?.length" class="attr-grid">
                <div v-for="attr in dim.attributes" :key="attr.key" class="attr-card">
                  <div class="attr-card-head">
                    <span>{{ attr.label }}</span>
                    <el-tag :type="scoreTagType(attr.score)" size="small">{{ (attr.score * 100).toFixed(0) }}%</el-tag>
                  </div>
                  <ul v-if="attr.score < 1.0 && attr.issues?.length" class="issue-chips">
                    <li v-for="(issue, i) in attr.issues" :key="i">{{ issueText(issue) }}</li>
                  </ul>
                  <p v-else-if="attr.score >= 1.0" class="no-issues">该项无扣分问题</p>
                </div>
              </div>
              <ul v-else-if="dim.issues?.length" class="issue-list">
                <li v-for="(issue, i) in dim.issues" :key="i">{{ issueText(issue) }}</li>
              </ul>
              <p v-else class="no-issues">无问题</p>
            </el-collapse-item>
          </el-collapse>
        </div>

        <div class="report-section rec-section">
          <div class="section-title-row">
            <el-icon class="section-icon"><ChatDotRound /></el-icon>
            <h3>改进建议</h3>
          </div>
          <div v-if="recommendationsList.length" class="rec-box">
            <div v-for="(rec, i) in recommendationsList" :key="i" class="rec-line">{{ rec }}</div>
          </div>
          <el-empty v-else description="暂无改进建议" :image-size="80" />
        </div>
      </section>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  UploadFilled,
  Document,
  Picture,
  List,
  DataAnalysis,
  Lightning,
  CircleCheck,
  ChatDotRound
} from '@element-plus/icons-vue'
import { evaluate as evaluateApi } from '@/api/evaluation'

const QUALITY_LABELS = {
  consistency_and_normativity: '一致性与规范性',
  completeness: '完整性',
  necessity_traceability: '必要性（可追溯性）',
  modifiability: '可修改性'
}

const requirementText = ref('')
const requirementStructured = ref(null)
const requirementFileName = ref('')
const requirementError = ref('')

const useCaseDiagram = ref(null)
const diagramFileName = ref('')
const diagramError = ref('')

const useCaseDescriptions = ref(null)
const descriptionsFileName = ref('')
const descriptionsError = ref('')

const loading = ref(false)
const report = ref(null)

const activeDiagram = ref([])
const activeDescription = ref([])

const canEvaluate = computed(() => {
  const hasReq = Boolean(requirementText.value || requirementStructured.value)
  return (
    hasReq &&
    useCaseDiagram.value &&
    useCaseDescriptions.value &&
    !requirementError.value &&
    !diagramError.value &&
    !descriptionsError.value
  )
})

function onRequirementChange(file) {
  requirementError.value = ''
  requirementFileName.value = file?.name || ''
  if (!file?.raw) return
  const reader = new FileReader()
  reader.onload = (e) => {
    const raw = e.target.result
    const trimmed = typeof raw === 'string' ? raw.trim() : ''
    if (trimmed.startsWith('{')) {
      try {
        const data = JSON.parse(trimmed)
        const gl = data.goal_level_requirements
        const fr = data.functional_requirements
        const hasUnified = Array.isArray(gl) && gl.length > 0
        const hasLegacy = Array.isArray(fr) && fr.length > 0
        const ok =
          data &&
          typeof data === 'object' &&
          !Array.isArray(data) &&
          (hasUnified || hasLegacy)
        if (ok) {
          requirementStructured.value = data
          requirementText.value = ''
          ElMessage.success('结构化需求 JSON 已加载')
          return
        }
      } catch {
        /* 按纯文本处理 */
      }
    }
    requirementStructured.value = null
    requirementText.value = raw
    ElMessage.success('需求文档已加载')
  }
  reader.onerror = () => {
    requirementError.value = '文件读取失败'
    requirementText.value = ''
    requirementStructured.value = null
  }
  reader.readAsText(file.raw, 'UTF-8')
}

/** 与后端 input_normalizer 一致：数组或 useCases / use_cases / use_case_descriptions / descriptions / 单条用例对象 */
function extractUseCaseDescriptionsList(data) {
  if (Array.isArray(data)) return data
  if (data && typeof data === 'object') {
    if (Array.isArray(data.useCases)) return data.useCases
    if (Array.isArray(data.use_cases)) return data.use_cases
    if (Array.isArray(data.use_case_descriptions)) return data.use_case_descriptions
    if (Array.isArray(data.descriptions)) return data.descriptions
    if ('main_flow' in data || ('name' in data && 'id' in data)) return [data]
  }
  return null
}

function parseJsonFile(file, onSuccess, onError) {
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const raw = e.target.result
      const data = JSON.parse(raw)
      onSuccess(data)
    } catch (err) {
      onError('不是有效的 JSON 格式：' + (err.message || '解析错误'))
    }
  }
  reader.onerror = () => onError('文件读取失败')
  reader.readAsText(file.raw, 'UTF-8')
}

function onDiagramChange(file) {
  diagramError.value = ''
  diagramFileName.value = file?.name || ''
  if (!file?.raw) return
  parseJsonFile(
    file,
    (data) => {
      const obj = typeof data === 'object' && data !== null && !Array.isArray(data)
      if (!obj) {
        diagramError.value = '用例图应为 JSON 对象（包含 actors / use_cases / relationships）'
        useCaseDiagram.value = null
        return
      }
      useCaseDiagram.value = data
      ElMessage.success('用例图已加载')
    },
    (msg) => {
      diagramError.value = msg
      useCaseDiagram.value = null
    }
  )
}

function onDescriptionsChange(file) {
  descriptionsError.value = ''
  descriptionsFileName.value = file?.name || ''
  if (!file?.raw) return
  parseJsonFile(
    file,
    (data) => {
      const list = extractUseCaseDescriptionsList(data)
      if (!list || !list.length) {
        descriptionsError.value =
          '用例描述应为 JSON 数组，或含 useCases / use_cases / use_case_descriptions / descriptions 的对象（或单条用例对象）'
        useCaseDescriptions.value = null
        return
      }
      useCaseDescriptions.value = list
      ElMessage.success('用例描述已加载')
    },
    (msg) => {
      descriptionsError.value = msg
      useCaseDescriptions.value = null
    }
  )
}

async function runEvaluate(mode = 'quick') {
  if (!canEvaluate.value) return
  loading.value = true
  report.value = null
  try {
    const payload = {
      use_case_diagram: useCaseDiagram.value,
      use_case_descriptions: useCaseDescriptions.value,
      evaluation_mode: mode
    }
    if (requirementStructured.value) {
      payload.requirements = requirementStructured.value
    } else {
      payload.requirements_text = requirementText.value
    }
    const res = await evaluateApi(payload)
    if (res.success && res.data) {
      report.value = res.data
      ElMessage.success('评估完成')
    } else {
      ElMessage.error(res.error || '评估失败')
    }
  } catch (e) {
    const msg = e.message || String(e)
    ElMessage.error('评估失败：' + msg)
    if (e.response?.data?.traceback) {
      console.error('后端错误详情：', e.response.data.traceback)
    }
  } finally {
    loading.value = false
  }
}

const overallPercent = computed(() => {
  if (!report.value || report.value.overall_score == null) return 0
  return Math.round(Number(report.value.overall_score) * 100)
})

const overallScoreText = computed(() => {
  if (!report.value || report.value.overall_score == null) return '—'
  return (Number(report.value.overall_score) * 100).toFixed(2) + '%'
})

const overallScoreType = computed(() => {
  const s = report.value?.overall_score
  if (s == null) return 'info'
  if (s >= 0.8) return 'success'
  if (s >= 0.6) return 'warning'
  return 'danger'
})

const diagramOverallPercent = computed(() => {
  const s = report.value?.diagram_metrics?.overall_score
  if (s == null) return 0
  return Math.round(Number(s) * 100)
})

const diagramOverallText = computed(() => {
  const s = report.value?.diagram_metrics?.overall_score
  if (s == null) return '—'
  return (Number(s) * 100).toFixed(2) + '%'
})

const descriptionOverallPercent = computed(() => {
  const s = report.value?.description_metrics?.overall_score
  if (s == null) return 0
  return Math.round(Number(s) * 100)
})

const descriptionOverallText = computed(() => {
  const s = report.value?.description_metrics?.overall_score
  if (s == null) return '—'
  return (Number(s) * 100).toFixed(2) + '%'
})

const evaluationDurationText = computed(() => {
  const s = report.value?.evaluation_duration_seconds
  if (s == null || Number.isNaN(Number(s))) return '—'
  const n = Number(s)
  if (n < 60) return `${n.toFixed(2)}s`
  const m = Math.floor(n / 60)
  const sec = (n % 60).toFixed(2)
  return `${m}m ${sec}s`
})

const progressColor = computed(() => {
  const t = overallScoreType.value
  if (t === 'success') return '#67c23a'
  if (t === 'warning') return '#e6a23c'
  if (t === 'danger') return '#f56c6c'
  return '#409eff'
})

const progressColorSoft = '#94a3b8'

function scoreTagType(score) {
  if (score >= 0.8) return 'success'
  if (score >= 0.6) return 'warning'
  return 'danger'
}

function issueText(issue) {
  if (issue == null) return ''
  if (typeof issue === 'string') return issue
  return issue.description || issue.reason || issue.message || issue.detail || JSON.stringify(issue)
}

function buildQualityDimensions(metrics) {
  if (!metrics) return []
  const skip = ['overall_score', 'individual_scores']
  const result = []
  for (const [key, val] of Object.entries(metrics)) {
    if (skip.includes(key) || !val || typeof val !== 'object') continue
    const overall = val.overall
    const score = overall != null ? Number(overall) : 0
    const attributes = val.attributes || {}
    const attrList = Object.entries(attributes).map(([ak, av]) => ({
      key: ak,
      label: av?.label || ak,
      score: av?.score != null ? Number(av.score) : 0,
      issues: Array.isArray(av?.issues) ? av.issues : []
    }))
    const dimIssues = Array.isArray(val.issues) ? val.issues : []
    result.push({
      key,
      label: val.label || QUALITY_LABELS[key] || key,
      score,
      scoreText: (score * 100).toFixed(2) + '%',
      issues: dimIssues,
      attributes: attrList
    })
  }
  return result
}

const diagramDimensions = computed(() => buildQualityDimensions(report.value?.diagram_metrics))
const descriptionDimensions = computed(() => buildQualityDimensions(report.value?.description_metrics))

const recommendationsList = computed(() => {
  const rec = report.value?.recommendations
  if (!Array.isArray(rec)) return []
  return rec.filter(Boolean).map((r) => (typeof r === 'string' ? r : String(r)).trim()).filter(Boolean)
})

watch(
  diagramDimensions,
  (dims) => {
    activeDiagram.value = dims.map((d) => d.key)
  },
  { immediate: true }
)

watch(
  descriptionDimensions,
  (dims) => {
    activeDescription.value = dims.map((d) => d.key)
  },
  { immediate: true }
)
</script>

<style scoped>
.home {
  --home-max: 1180px;
  --radius-lg: 16px;
  --radius-md: 12px;
  --shadow-soft: 0 4px 24px rgba(15, 23, 42, 0.06);
  --shadow-card: 0 8px 32px rgba(15, 23, 42, 0.08);
  --border: 1px solid rgba(148, 163, 184, 0.25);
  max-width: var(--home-max);
  margin: 0 auto;
  padding: 28px 20px 48px;
}

.hero {
  margin-bottom: 28px;
  padding: 28px 32px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 45%, #eef2ff 100%);
  border: var(--border);
  box-shadow: var(--shadow-soft);
}

.hero-inner {
  max-width: 720px;
}

.hero-badge {
  display: inline-block;
  padding: 4px 12px;
  margin-bottom: 12px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: #3b82f6;
  background: rgba(59, 130, 246, 0.12);
  border-radius: 999px;
}

.hero-title {
  margin: 0 0 10px;
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #0f172a;
  line-height: 1.25;
}

.hero-desc {
  margin: 0;
  font-size: 15px;
  line-height: 1.65;
  color: #64748b;
}

.panel {
  margin-bottom: 20px;
  padding: 22px 24px 8px;
  background: #ffffff;
  border-radius: var(--radius-lg);
  border: var(--border);
  box-shadow: var(--shadow-soft);
}

.panel-head {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 20px;
}

.panel-step {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 15px;
  color: #fff;
  background: linear-gradient(135deg, #3b82f6, #6366f1);
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35);
}

.panel-title {
  margin: 0 0 4px;
  font-size: 1.1rem;
  font-weight: 600;
  color: #0f172a;
}

.panel-sub {
  margin: 0;
  font-size: 13px;
  color: #94a3b8;
}

.upload-row {
  margin-bottom: 8px;
}

.upload-card-wrap {
  position: relative;
  margin-bottom: 16px;
}

.upload-card-label {
  position: absolute;
  top: -8px;
  left: 16px;
  z-index: 1;
  padding: 2px 10px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #64748b;
  background: #fff;
  border: var(--border);
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}

.upload-card {
  border-radius: var(--radius-md) !important;
  overflow: hidden;
  border: none !important;
  box-shadow: var(--shadow-card) !important;
}

.upload-card :deep(.el-card__header) {
  padding: 14px 18px;
  background: linear-gradient(to bottom, #fafbfc, #fff);
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
}

.card-header-inner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
  color: #334155;
}

.header-icon {
  font-size: 18px;
  color: #3b82f6;
}

.upload-card :deep(.el-card__body) {
  padding: 16px 18px 18px;
}

.upload-inner :deep(.el-upload-dragger) {
  padding: 28px 16px;
  border-radius: var(--radius-md);
  border: 1px dashed #cbd5e1;
  background: #f8fafc;
  transition: border-color 0.2s, background 0.2s;
}

.upload-inner :deep(.el-upload-dragger:hover) {
  border-color: #3b82f6;
  background: #f0f9ff;
}

.upload-icon {
  font-size: 44px;
  color: #94a3b8;
  margin-bottom: 10px;
}

.upload-text {
  font-size: 14px;
  color: #475569;
}

.upload-text em {
  color: #2563eb;
  font-style: normal;
  font-weight: 600;
}

.upload-tip {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 8px;
}

.error-tip {
  margin-top: 10px;
  font-size: 12px;
  color: #dc2626;
}

.success-tip {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #16a34a;
  font-weight: 500;
}

.action-panel {
  padding-bottom: 20px;
}

.action-inner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px 24px;
  padding: 4px 0 8px;
}

.action-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.action-btn {
  min-width: 140px;
  font-weight: 600;
}

.action-btn-primary {
  box-shadow: 0 6px 20px rgba(59, 130, 246, 0.35);
}

.action-hint.muted {
  font-size: 14px;
  color: #94a3b8;
}

.action-hint.tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 13px;
  color: #64748b;
}

.action-hint.tags .dot {
  color: #cbd5e1;
}

.report-shell {
  margin-top: 8px;
  padding: 26px 28px 32px;
  background: #ffffff;
  border-radius: var(--radius-lg);
  border: var(--border);
  box-shadow: var(--shadow-card);
}

.report-top {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.95);
}

.report-title {
  margin: 0 0 6px;
  font-size: 1.35rem;
  font-weight: 700;
  color: #0f172a;
}

.report-sub {
  margin: 0;
  font-size: 13px;
  color: #94a3b8;
}

.report-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.stat-row {
  margin-bottom: 32px;
  padding-bottom: 12px;
}

/* 與 el-row gutter 負邊距區隔，避免三卡區塊與下方標題視覺重疊 */
.stat-row + .report-section {
  margin-top: 12px;
  padding-top: 8px;
}

.stat-card {
  height: auto;
  min-height: 0;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  background: #f8fafc;
  border: 1px solid rgba(226, 232, 240, 0.9);
  transition: transform 0.2s, box-shadow 0.2s;
}

.stat-card:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-soft);
}

.stat-card-main {
  background: linear-gradient(145deg, #ffffff 0%, #f0f9ff 100%);
  border-color: rgba(59, 130, 246, 0.2);
}

.stat-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8;
  margin-bottom: 6px;
}

.stat-value {
  font-size: 1.65rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.15;
  margin-bottom: 10px;
}

.stat-value.secondary {
  font-size: 1.2rem;
  font-weight: 700;
  color: #334155;
}

.stat-value.tone-success {
  color: #16a34a;
}
.stat-value.tone-warning {
  color: #d97706;
}
.stat-value.tone-danger {
  color: #dc2626;
}
.stat-value.tone-info {
  color: #3b82f6;
}

.stat-progress {
  margin-top: 2px;
}

.report-section {
  margin-bottom: 28px;
  position: relative;
  z-index: 0;
}

.report-section:last-child {
  margin-bottom: 0;
}

.section-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.section-title-row h3 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: #1e293b;
}

.section-icon {
  font-size: 20px;
  color: #3b82f6;
}

.dim-collapse {
  border: none !important;
  --el-collapse-border-color: transparent;
}

.dim-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 48px;
  padding: 12px 4px;
  font-size: 14px;
  font-weight: 500;
  color: #334155;
  background: transparent;
  border-bottom: 1px solid #e2e8f0;
}

.dim-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
  background: transparent;
}

.dim-collapse :deep(.el-collapse-item__content) {
  padding: 16px 4px 20px;
}

.collapse-title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.attr-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.attr-card {
  padding: 14px 16px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.attr-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.issue-chips {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.55;
}

.issue-chips li {
  margin-bottom: 6px;
}

.issue-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: #475569;
  line-height: 1.55;
}

.no-issues {
  margin: 0;
  font-size: 12px;
  color: #94a3b8;
}

.rec-section .rec-box {
  padding: 16px 18px;
  border-radius: var(--radius-md);
  background: linear-gradient(to bottom, #fffbeb, #fff);
  border: 1px solid rgba(251, 191, 36, 0.35);
}

.rec-line {
  font-size: 13px;
  line-height: 1.75;
  color: #78350f;
  white-space: pre-wrap;
  margin-bottom: 8px;
}

.rec-line:last-child {
  margin-bottom: 0;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.35s ease, transform 0.35s ease;
}
.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
</style>
