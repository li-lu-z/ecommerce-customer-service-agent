# datasource.py
# 数据源抽象层：把「数据从哪来」与「Agent 怎么用数据」解耦。
# 当前提供 JSON 文件实现；接真实业务时新增 ApiDataSource 即可，Agent 核心无需改动。

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


class DataSource:
    """数据源抽象接口：定义 Agent 需要的所有数据读写方法。"""

    def query_product(self, name: str) -> dict:
        raise NotImplementedError

    def query_order(self, order_id: str) -> dict:
        raise NotImplementedError

    def query_logistics(self, tracking_no: str) -> dict:
        raise NotImplementedError

    def search_faq(self, question: str) -> dict:
        raise NotImplementedError

    def apply_refund(self, order_id: str, reason: str) -> dict:
        raise NotImplementedError

    def cancel_order(self, order_id: str) -> dict:
        raise NotImplementedError

    def list_product_keywords(self) -> list:
        raise NotImplementedError


class JsonDataSource(DataSource):
    """本地 JSON 文件实现（当前演示用，数据放在 data/ 目录）。"""

    def _load(self, filename: str) -> list:
        path = DATA_DIR / filename
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, filename: str, data: list) -> None:
        (DATA_DIR / filename).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def query_product(self, name: str) -> dict:
        for item in self._load("products.json"):
            keys = [item.get("name", "")] + item.get("keywords", [])
            if any(k and k in name for k in keys):
                return {"found": True, **item}
        return {"found": False}

    def query_order(self, order_id: str) -> dict:
        for item in self._load("orders.json"):
            if str(item.get("order_id", "")) == str(order_id):
                return {"found": True, **item}
        return {"found": False}

    def query_logistics(self, tracking_no: str) -> dict:
        for item in self._load("logistics.json"):
            if str(item.get("tracking_no", "")) == str(tracking_no):
                return {"found": True, **item}
        return {"found": False}

    def search_faq(self, question: str) -> dict:
        faqs = self._load("faq.json")
        scored = []
        for faq in faqs:
            score = 0
            for kw in faq.get("keywords", []):
                if kw and kw in question:
                    score += 3
            score += len(set(question) & set(faq.get("question", "")))
            if score > 0:
                scored.append((score, faq))
        scored.sort(key=lambda x: -x[0])
        results = [f for _, f in scored[:3]]
        return {"found": len(results) > 0, "results": results}

    def apply_refund(self, order_id: str, reason: str) -> dict:
        orders = self._load("orders.json")
        for i, o in enumerate(orders):
            if str(o.get("order_id", "")) == str(order_id):
                if o.get("status") in ("退款中", "已取消"):
                    return {
                        "found": True,
                        "success": False,
                        "message": f"订单当前状态为「{o['status']}」，无法重复申请退款",
                    }
                orders[i]["status"] = "退款中"
                self._save("orders.json", orders)
                return {
                    "found": True,
                    "success": True,
                    "message": f"订单 {order_id} 已提交退款申请（原因：{reason}）",
                }
        return {"found": False, "success": False, "message": "未找到该订单，请核对订单号"}

    def cancel_order(self, order_id: str) -> dict:
        orders = self._load("orders.json")
        for i, o in enumerate(orders):
            if str(o.get("order_id", "")) == str(order_id):
                if o.get("status") != "待支付":
                    return {
                        "found": True,
                        "success": False,
                        "message": f"订单当前状态为「{o['status']}」，无法取消",
                    }
                orders[i]["status"] = "已取消"
                self._save("orders.json", orders)
                return {"found": True, "success": True, "message": f"订单 {order_id} 已取消"}
        return {"found": False, "success": False, "message": "未找到该订单，请核对订单号"}

    def list_product_keywords(self) -> list:
        keys = []
        for item in self._load("products.json"):
            keys.append(item.get("name", ""))
            keys.extend(item.get("keywords", []))
        return [k for k in keys if k]


class ApiDataSource(DataSource):
    """真实业务 API 实现（骨架）：接订单中心/商品中心/物流平台时按你的接口调整。"""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _get(self, path: str, params: dict | None = None) -> dict:
        import requests  # 延迟导入，只有切到 API 数据源时才需要

        resp = requests.get(
            f"{self.base_url}{path}",
            params=params,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict | None = None) -> dict:
        import requests

        resp = requests.post(
            f"{self.base_url}{path}",
            json=body,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()

    def query_product(self, name: str) -> dict:
        data = self._get("/products", {"name": name})
        return data if isinstance(data, dict) else {"found": False}

    def query_order(self, order_id: str) -> dict:
        data = self._get(f"/orders/{order_id}")
        return data if isinstance(data, dict) else {"found": False}

    def query_logistics(self, tracking_no: str) -> dict:
        data = self._get(f"/logistics/{tracking_no}")
        return data if isinstance(data, dict) else {"found": False}

    def search_faq(self, question: str) -> dict:
        data = self._get("/faq/search", {"question": question})
        return data if isinstance(data, dict) else {"found": False}

    def apply_refund(self, order_id: str, reason: str) -> dict:
        return self._post(f"/orders/{order_id}/refund", {"reason": reason})

    def cancel_order(self, order_id: str) -> dict:
        return self._post(f"/orders/{order_id}/cancel")

    def list_product_keywords(self) -> list:
        return []
