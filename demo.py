# demo.py
# 命令行交互演示：支持多轮记忆与流式输出。
# 未配置 API Key 时自动使用本地 Mock 后端；配置后自动切换真实 DeepSeek 后端。

import os

from agent import LLMClient, MockLLM, detect_escalation
from memory import create_store

ESCALATION_TIP = "\n（检测到您可能需要人工协助，可联系在线人工客服进一步处理）"


def main():
    if os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"):
        print("检测到 API Key，使用真实 LLM 后端（默认 DeepSeek）。")
        bot = LLMClient()
    else:
        print("未检测到 API Key，使用本地模拟后端（Mock）。")
        bot = MockLLM()

    store = create_store()

    print("=" * 52)
    print("电商 AI 客服已启动，输入 exit 退出")
    print("示例：查订单 20261103001 / 怎么退换货 / 手机多少钱")
    print("=" * 52)

    while True:
        try:
            text = input("\n用户：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in ("exit", "quit", "退出"):
            break
        if not text:
            continue

        history = store.get("cli")
        print("客服：", end="", flush=True)
        full = ""
        for chunk in bot.reply_stream(text, history=history):
            full += chunk
            print(chunk, end="", flush=True)
        if detect_escalation(text):
            full += ESCALATION_TIP
            print(ESCALATION_TIP, end="", flush=True)
        print()
        store.append("cli", "user", text)
        store.append("cli", "assistant", full)


if __name__ == "__main__":
    main()
