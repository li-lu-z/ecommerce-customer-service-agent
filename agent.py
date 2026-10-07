# agent.py
# AI 客服 Agent 核心：理解意图 -> 调用工具 -> 生成回复。
# 提供两种后端：
#   1. MockLLM：纯本地规则，无需 API Key，用于跑通闭环/演示。
#   2. LLMClient：真实调用 OpenAI 兼容接口（默认 DeepSeek），支持函数调用与流式输出。

import json
import os
import re

from tools import (
    apply_refund,
    cancel_order,
    list_product_keywords,
    query_logistics,
    query_order,
    query_product,
    search_faq,
)

# 系统提示词：定义角色、边界与平台规则（真实 LLM 模式使用）
SYSTEM_PROMPT = """你是「XX旗舰店」的智能客服，只回答商品、订单、物流、售后相关问题。
规则：
1. 涉及退款、取消订单等敏感操作，先向用户确认订单号无误，得到用户明确确认后再调用工具。
2. 无法处理时，礼貌引导转人工。
3. 不承诺平台之外的优惠或价格。
4. 回答退换货、发货时间、运费、保修、发票等政策类问题时，先调用 search_faq 工具查询店铺规则，再基于查询结果回答。
5. 遇到用户投诉、情绪激动、要求人工或问题无法解决时，主动引导转人工客服。
"""

# 转人工检测：命中敏感词或情绪激动时触发
ESCALATION_KEYWORDS = ["人工", "投诉", "差评", "举报", "曝光", "欺骗", "维权", "没人管"]


def detect_escalation(message: str) -> bool:
    """检测用户消息是否应转人工（命中敏感词或情绪激动）。"""
    if any(k in message for k in ESCALATION_KEYWORDS):
        return True
    if message.count("!") >= 3 or message.count("！") >= 3:
        return True
    return False


class MockLLM:
    """本地规则引擎：模拟「理解意图 -> 调用工具 -> 组织回复」的完整闭环。"""

    @staticmethod
    def _num(n):
        """把 129.0 这类整数浮点显示为 129，保留真正的小数。"""
        if isinstance(n, float) and n.is_integer():
            return int(n)
        return n

    def reply(self, message: str, history: list | None = None) -> str:
        # Mock 后端基于关键词规则，暂不使用历史上下文
        msg = message.strip()

        # 1. 优先识别快递单号（物流查询），支持顺丰/圆通/中通/韵达/申通/京东
        tracking_match = re.search(r"(?:SF|YT|ZT|YD|STO|JD)\d{8,}", msg)
        if tracking_match:
            return self._format_logistics(query_logistics(tracking_match.group()))

        # 2. 识别 11 位订单号（订单查询）
        order_match = re.search(r"\d{11}", msg)
        if order_match:
            return self._format_order(query_order(order_match.group()))

        # 3. 商品咨询（按导入数据里的商品名/关键词命中）
        for key in list_product_keywords():
            if key in msg:
                return self._format_product(query_product(key))

        # 4. 兜底回复
        return (
            "抱歉，我暂时没理解您的问题。您可以这样问我：\n"
            "· 商品：手机多少钱 / 耳机有货吗\n"
            "· 订单：查订单 20261006001\n"
            "· 物流：单号 SF123456789 到哪了"
        )

    def reply_stream(self, message: str, history: list | None = None):
        """Mock 后端不支持真正的流式，直接一次性返回完整回复。"""
        yield self.reply(message, history)

    def _format_product(self, data: dict) -> str:
        if not data["found"]:
            return "抱歉，没找到您要的商品，您可以换个关键词再试。"
        stock = "有货" if data["stock"] > 0 else "暂时缺货"
        return (
            f"{data['name']}：{data['desc']}\n"
            f"价格：¥{self._num(data['price'])}\n"
            f"库存：{stock}（剩余 {self._num(data['stock'])} 件）"
        )

    def _format_order(self, data: dict) -> str:
        if not data["found"]:
            return "抱歉，没有查到该订单，请核对订单号是否正确。"
        logistics = (
            f"{data['logistics_company']}（单号 {data['tracking_no']}）"
            if data["logistics_company"]
            else "尚未发货"
        )
        return (
            f"订单 {data['order_id']} 当前状态：{data['status']}\n"
            f"收货人：{data['receiver']}，金额：¥{self._num(data['amount'])}\n"
            f"物流：{logistics}"
        )

    def _format_logistics(self, data: dict) -> str:
        if not data["found"]:
            return "抱歉，没有查到该快递单号的物流信息。"
        steps = " → ".join(data["steps"])
        return f"快递单号 {data['tracking_no']} 物流轨迹：{steps}"


class LLMClient:
    """OpenAI 兼容 LLM 后端（默认 DeepSeek），支持函数调用与流式输出。"""

    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "query_product",
                "description": "根据商品名查询商品的价格、库存和描述",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "商品名称，如 手机、耳机"}
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_order",
                "description": "根据订单号查询订单状态、金额和物流信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "11 位订单号"}
                    },
                    "required": ["order_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_logistics",
                "description": "根据快递单号查询完整物流轨迹",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tracking_no": {"type": "string", "description": "快递单号，如 SF123456789"}
                    },
                    "required": ["tracking_no"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_faq",
                "description": "检索店铺 FAQ 知识库，回答退换货、发货、运费、保修、发票等政策类问题",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "用户提出的政策类问题"}
                    },
                    "required": ["question"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "apply_refund",
                "description": "为订单申请退款/退货，把订单状态更新为退款中（敏感操作，需先核对订单信息）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "订单号"},
                        "reason": {"type": "string", "description": "退款/退货原因"},
                    },
                    "required": ["order_id", "reason"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "cancel_order",
                "description": "取消订单，仅待支付订单可取消",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "订单号"}
                    },
                    "required": ["order_id"],
                },
            },
        },
    ]

    def __init__(self):
        from openai import OpenAI  # 延迟导入，避免未安装 openai 包时影响 Mock 模式

        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("未检测到 API Key，请先设置 DEEPSEEK_API_KEY 环境变量")

        base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("LLM_MODEL", "deepseek-chat")
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _call_tool(self, name: str, arguments: str) -> str:
        """把模型请求的工具名与参数，映射到本地业务函数并返回 JSON 结果。"""
        args = json.loads(arguments)
        functions = {
            "query_product": query_product,
            "query_order": query_order,
            "query_logistics": query_logistics,
            "search_faq": search_faq,
            "apply_refund": apply_refund,
            "cancel_order": cancel_order,
        }
        result = functions[name](**args)
        return json.dumps(result, ensure_ascii=False)

    def _build_messages(self, message: str, history: list | None) -> list:
        """组装消息：系统提示词 + 历史对话 + 当前用户输入。"""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in history or []:
            messages.append(h)
        messages.append({"role": "user", "content": message})
        return messages

    def _run_tool_loop(self, messages: list) -> list:
        """执行工具调用循环，返回已包含工具结果的 messages 列表。"""
        for _ in range(5):  # 最多 5 轮，防止死循环
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.TOOLS,
                tool_choice="auto",
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return messages  # 模型不再需要工具，准备生成最终回复
            messages.append(msg)
            for call in msg.tool_calls:
                result = self._call_tool(call.function.name, call.function.arguments)
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": result}
                )
        return messages

    def reply(self, message: str, history: list | None = None) -> str:
        """非流式：返回完整回复。"""
        messages = self._run_tool_loop(self._build_messages(message, history))
        resp = self.client.chat.completions.create(model=self.model, messages=messages)
        return resp.choices[0].message.content or ""

    def reply_stream(self, message: str, history: list | None = None):
        """流式：逐块产出最终回复文本。"""
        messages = self._run_tool_loop(self._build_messages(message, history))
        stream = self.client.chat.completions.create(
            model=self.model, messages=messages, stream=True
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
