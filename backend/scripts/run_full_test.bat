@echo off
chcp 65001 >nul
cd /d "%~dp0.."

if "%DEEPSEEK_API_KEY%"=="" (
    echo [错误] 请先设置环境变量 DEEPSEEK_API_KEY
    echo 例如: set DEEPSEEK_API_KEY=sk-你的密钥
    echo 然后再运行: python scripts\test_full_quality_evaluation.py
    exit /b 1
)

echo 使用 DEEPSEEK_API_KEY 运行完整质量评估测试...
python scripts\test_full_quality_evaluation.py
exit /b %ERRORLEVEL%
