# import_data.py
# 数据导入脚本：把店铺后台导出的 CSV 文件转成 data/ 目录下的 JSON。
# 用法：
#   python import_data.py products.csv products
#   python import_data.py orders.csv orders
#   python import_data.py logistics.csv logistics

import csv
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# 各类型对应的 CSV 列名 -> JSON 字段（多值字段用 | 分隔）
SCHEMAS = {
    "products": {
        "商品名称": "name",
        "关键词": "keywords",
        "价格": "price",
        "库存": "stock",
        "描述": "desc",
    },
    "orders": {
        "订单号": "order_id",
        "状态": "status",
        "收货人": "receiver",
        "金额": "amount",
        "快递公司": "logistics_company",
        "快递单号": "tracking_no",
    },
    "logistics": {
        "快递单号": "tracking_no",
        "轨迹": "steps",
    },
    "faq": {
        "问题": "question",
        "关键词": "keywords",
        "回答": "answer",
    },
}


def convert(csv_path: str, kind: str) -> None:
    schema = SCHEMAS[kind]
    rows = []
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item = {}
            for col, key in schema.items():
                raw = (row.get(col) or "").strip()
                if key in ("price", "stock", "amount"):
                    val = float(raw) if raw else 0.0
                    # 整数金额/库存/价格存为 int，避免显示成 129.0
                    item[key] = int(val) if val.is_integer() else val
                elif key in ("keywords", "steps"):
                    item[key] = [x.strip() for x in raw.split("|") if x.strip()]
                else:
                    item[key] = raw
            rows.append(item)

    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"{kind}.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已导入 {len(rows)} 条数据到 {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[2] not in SCHEMAS:
        print("用法：python import_data.py <csv文件> <products|orders|logistics|faq>")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
