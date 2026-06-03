<template>
  <el-container class="app-root">
    <el-header class="app-header" height="64px">
      <div class="header-inner">
        <div class="brand">
          <span class="brand-mark" aria-hidden="true" />
          <div class="brand-text">
            <span class="brand-title">用例模型质量评估系统</span>
            <span class="brand-sub">规则 + LLM 混合评估 · 原型工具</span>
          </div>
        </div>
      </div>
    </el-header>
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
</script>

<style scoped>
.app-root {
  min-height: 100vh;
  background: #eef2f7;
}

.app-header {
  padding: 0 24px;
  background: #ffffff;
  border-bottom: 1px solid rgba(148, 163, 184, 0.35);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.8) inset;
}

.header-inner {
  max-width: 1180px;
  margin: 0 auto;
  height: 100%;
  display: flex;
  align-items: center;
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #3b82f6, #6366f1);
  box-shadow: 0 4px 14px rgba(59, 130, 246, 0.4);
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.brand-title {
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #0f172a;
}

.brand-sub {
  font-size: 12px;
  color: #64748b;
}

.app-main {
  padding: 0 0 32px;
  background: transparent;
}
</style>
