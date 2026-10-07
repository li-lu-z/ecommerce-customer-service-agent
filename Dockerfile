# Dockerfile
# 电商 AI 客服生产镜像

FROM python:3.13-slim

WORKDIR /app

# 先复制依赖清单，充分利用 Docker 构建缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 复制应用代码（data/ 与 static/ 一起进入镜像）
COPY . .

EXPOSE 8000

# 多 worker 提高并发（会话走 Redis，多进程安全）
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
