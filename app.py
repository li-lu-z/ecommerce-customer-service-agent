# app.py
# FastAPI 服务：提供多轮对话接口（含流式）+ 网页聊天界面。
# 启动：uvicorn app:app --host 127.0.0.1 --port 8000

import json
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import LLMClient, MockLLM, detect_escalation
from channels import normalize
from memory import create_store

BASE_DIR = Path(__file__).parent

app = FastAPI(title="电商AI客服")

# 有 Key 用真实 LLM（默认 DeepSeek），否则用本地 Mock，保证服务随时可启动
bot = (
    LLMClient()
    if (os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"))
    else MockLLM()
)
store = create_store()

ESCALATION_TIP = "\n\n（检测到您可能需要人工协助，可联系在线人工客服进一步处理）"


class ChatIn(BaseModel):
    session_id: str
    message: str


class ChatOut(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatOut)
def chat(body: ChatIn):
    history = store.get(body.session_id)
    reply = bot.reply(body.message, history=history)
    if detect_escalation(body.message):
        reply += ESCALATION_TIP
    store.append(body.session_id, "user", body.message)
    store.append(body.session_id, "assistant", reply)
    return ChatOut(reply=reply)


@app.post("/chat/stream")
def chat_stream(body: ChatIn):
    """流式返回：NDJSON，每行 {"delta": "..."}，最后一行 {"done": true}。"""

    def generate():
        history = store.get(body.session_id)
        full = ""
        escalated = detect_escalation(body.message)
        for chunk in bot.reply_stream(body.message, history=history):
            full += chunk
            yield json.dumps({"delta": chunk}, ensure_ascii=False) + "\n"
        if escalated:
            full += ESCALATION_TIP
            yield json.dumps({"delta": ESCALATION_TIP}, ensure_ascii=False) + "\n"
        store.append(body.session_id, "user", body.message)
        store.append(body.session_id, "assistant", full)
        yield json.dumps({"done": True}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.post("/webhook/{platform}")
async def webhook(platform: str, request: Request):
    """平台消息回调入口：验签 -> 归一化 -> 交给 Agent -> 返回回复。

    真实接入时，各平台会主动推送消息到这里，需按其签名算法验证请求来源。
    """
    payload = await request.json()
    # TODO: 按平台验签，例如 verify_signature(platform, request.headers, payload)
    msg = normalize(platform, payload)
    if not msg["message"]:
        return {"error": "empty message"}

    history = store.get(msg["session_id"])
    reply = bot.reply(msg["message"], history=history)
    if detect_escalation(msg["message"]):
        reply += ESCALATION_TIP
    store.append(msg["session_id"], "user", msg["message"])
    store.append(msg["session_id"], "assistant", reply)

    # 真实平台通常需要主动推送回复（而非同步返回），这里先返回统一结构
    return {"session_id": msg["session_id"], "reply": reply}


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
