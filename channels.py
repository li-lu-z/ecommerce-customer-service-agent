# channels.py
# 渠道适配层：把不同电商平台的消息回调，统一成内部格式。
# 内部统一格式：{"session_id": str, "message": str, "user": str}


def normalize(platform: str, payload: dict) -> dict:
    """把平台原始回调转成统一的内部消息格式。"""
    platform = (platform or "").lower()

    if platform == "taobao":
        return {
            "session_id": str(payload.get("buyer_nick", "")),
            "message": payload.get("content", ""),
            "user": payload.get("buyer_nick", ""),
        }
    if platform == "douyin":
        return {
            "session_id": str(payload.get("conversation_id", "")),
            "message": payload.get("text", ""),
            "user": payload.get("user_id", ""),
        }
    if platform == "wechat":
        return {
            "session_id": str(payload.get("FromUserName", "")),
            "message": payload.get("Content", ""),
            "user": payload.get("FromUserName", ""),
        }

    # 通用/自有渠道：尽量兼容常见字段
    session_id = (
        payload.get("session_id")
        or payload.get("conversation_id")
        or payload.get("user_id")
        or ""
    )
    message = payload.get("message") or payload.get("text") or payload.get("content") or ""
    user = payload.get("user") or payload.get("user_id") or payload.get("FromUserName") or ""
    return {"session_id": str(session_id), "message": str(message), "user": str(user)}
