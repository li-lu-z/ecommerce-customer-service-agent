# 电商智能客服 Agent

基于大模型 Function Calling 的电商智能客服系统。让 LLM 从「只会聊天」变成「能查订单、查物流、办售后、答政策」的 Agent，支持多轮记忆、流式输出、转人工，并完成从本地演示到 Docker 生产的落地。

## 功能特性

- **商品 / 订单 / 物流查询**：通过 Function Calling 让模型自主调用工具查询结构化数据
- **FAQ 政策问答**：轻量 RAG（关键词检索 + 提示词注入），回答退换货、运费、保修等规则问题
- **售后写操作**：退款、取消订单，含「先确认再执行」的服务端校验
- **多轮会话记忆**：指代消解（「查订单 xxx」「那到哪了」），SQLite / Redis 双实现自动切换
- **流式输出**：NDJSON 流式协议，回复逐字渲染
- **转人工策略**：提示词 + 本地敏感词双层触发
- **可插拔 LLM**：OpenAI 兼容协议接入，默认 DeepSeek，换模型只改环境变量
- **数据源抽象**：`DataSource` 接口，JSON 演示数据与真实业务 API 无缝切换
- **双入口**：网页聊天界面（流式渲染）+ 命令行交互

## 架构

```
各电商平台 / 网页 / 命令行
            │
            ▼
     渠道适配层（消息归一化）
            │
            ▼
      Agent 核心（LLM）
        │   Function Calling
        ▼
     工具层（订单/物流/商品/FAQ/售后）
        │
        ▼
     数据源 DataSource（JSON / 真实 API）
```

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. 配置 Key 并启动

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "你的key"
# macOS/Linux
export DEEPSEEK_API_KEY="你的key"

# 启动网页版
uvicorn app:app --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000` 即可对话。

> 未配置 Key 时会自动切换到本地 Mock 后端（基于规则的演示模式），无需网络也能跑通流程。

### 3. 导入店铺数据

把店铺后台数据整理成 CSV，用脚本导入：

```bash
python import_data.py 商品表.csv products
python import_data.py 订单表.csv orders
python import_data.py 物流表.csv logistics
python import_data.py FAQ表.csv faq
```

CSV 列名要求见 `import_data.py` 中的 `SCHEMAS`，或直接编辑 `data/` 下的 JSON 文件。

## 目录结构

```
.
├── agent.py            # Agent 核心：函数调用循环、工具 schema、转人工检测
├── tools.py            # 工具层：委托给数据源
├── datasource.py       # 数据源抽象：JsonDataSource / ApiDataSource
├── channels.py         # 渠道适配层：多平台消息归一化
├── memory.py           # 会话记忆：SQLite / Redis 双实现
├── app.py              # FastAPI 入口：/chat、/chat/stream、/webhook/{platform}
├── demo.py             # 命令行交互入口
├── import_data.py      # CSV 数据导入脚本
├── static/index.html   # 网页聊天界面（流式渲染）
├── data/               # 示例数据（商品/订单/物流/FAQ）
├── Dockerfile          # 生产镜像
├── docker-compose.yml  # 应用 + Redis 编排
├── deploy/nginx.conf   # Nginx HTTPS 反向代理配置
└── .env.example        # 环境变量模板
```

## 技术栈

- **后端**：Python 3.13 / FastAPI / uvicorn
- **LLM**：DeepSeek（OpenAI 兼容协议，可换 OpenAI / 通义等）
- **存储**：SQLite（本地）/ Redis（生产）
- **部署**：Docker / docker-compose / Nginx

## 部署

生产部署详见部署文档，核心命令：

```bash
cp .env.example .env   # 填入密钥
docker compose up -d --build
```

## 关键设计

- **Function Calling 循环**：模型返回工具调用 → 本地执行 → 结果回传 → 生成最终回复，最多 5 轮防死循环
- **敏感操作服务端校验**：退款/取消不信任模型，工具内部校验订单状态
- **流式输出**：工具调用阶段非流式，最终回复流式生成；Nginx 需关闭缓冲

## License

MIT
