@echo off
chcp 65001 >nul
cd /d "%~dp0"

if "%DEEPSEEK_API_KEY%"=="" (
    echo 未检测到 DEEPSEEK_API_KEY 环境变量。
    set /p DEEPSEEK_API_KEY=请输入你的 DeepSeek API Key: 
)

echo.
echo 正在启动网页版客服，启动后请在浏览器打开 http://127.0.0.1:8000
.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8000

pause
