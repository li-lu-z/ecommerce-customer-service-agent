@echo off
chcp 65001 >nul
cd /d "%~dp0"

if "%DEEPSEEK_API_KEY%"=="" (
    echo 未检测到 DEEPSEEK_API_KEY 环境变量。
    set /p DEEPSEEK_API_KEY=请输入你的 DeepSeek API Key: 
)

echo.
echo 正在启动电商 AI 客服...
.venv\Scripts\python demo.py

echo.
pause
