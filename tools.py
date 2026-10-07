# tools.py
# 业务工具层：对外暴露给 Agent 的函数，内部委托给数据源。
# 默认用 JsonDataSource（本地文件）；设置 API_BASE_URL 与 API_TOKEN 后自动切换 ApiDataSource。

import os

from datasource import ApiDataSource, DataSource, JsonDataSource


def _get_source() -> DataSource:
    """根据环境变量选择数据源：有 API 配置则用真实接口，否则用本地 JSON。"""
    base_url = os.getenv("API_BASE_URL")
    token = os.getenv("API_TOKEN")
    if base_url and token:
        return ApiDataSource(base_url, token)
    return JsonDataSource()


_source = _get_source()


def query_product(name: str) -> dict:
    return _source.query_product(name)


def query_order(order_id: str) -> dict:
    return _source.query_order(order_id)


def query_logistics(tracking_no: str) -> dict:
    return _source.query_logistics(tracking_no)


def search_faq(question: str) -> dict:
    return _source.search_faq(question)


def apply_refund(order_id: str, reason: str) -> dict:
    return _source.apply_refund(order_id, reason)


def cancel_order(order_id: str) -> dict:
    return _source.cancel_order(order_id)


def list_product_keywords() -> list:
    return _source.list_product_keywords()
