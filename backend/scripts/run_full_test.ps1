# 完整质量评估测试 - PowerShell
# 用法: .\run_full_test.ps1
# 或先设置密钥: $env:DEEPSEEK_API_KEY = "sk-xxx"; .\run_full_test.ps1
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $ScriptDir "..")

if (-not $env:DEEPSEEK_API_KEY) {
    Write-Host "[错误] 请先设置环境变量 DEEPSEEK_API_KEY" -ForegroundColor Red
    Write-Host "例如: `$env:DEEPSEEK_API_KEY = `"sk-你的密钥`""
    Write-Host "然后再运行: python scripts\test_full_quality_evaluation.py"
    exit 1
}

Write-Host "使用 DEEPSEEK_API_KEY 运行完整质量评估测试..."
python scripts\test_full_quality_evaluation.py
exit $LASTEXITCODE
