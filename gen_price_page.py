#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tibo-price 价目页生成器（价格唯一真源 = 店铺页面接口）

⚠️ 价格铁律：只读 `/shopApi/goods/list` 返回的 `price` 字段。
   - 页面售价 = shopApi `price`
   - **不是** 开放 API 的 `unit_price`（那是拿货价，约为售价 × 0.8）
   - 交叉验证：订单 `unit_price` == shopApi `price`；订单 `cost_amount` == openApi `unit_price`
   2026-11-24 实测：FB账号 页面¥0.5 / 拿货¥0.4；Gemini 页面¥8.6 / 拿货¥6.88。

用法：
  python3 gen_price_page.py            # 拉实时价并生成 index.html
  python3 gen_price_page.py --check    # 只比对，不写文件
"""

import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

SHOP_NO = "S471063"
SHOP_URL = "https://www.16688.com.cn/shop/COCOS"
API = "https://www.16688.com.cn/shopApi/goods/list"
REPO = Path(__file__).resolve().parent


def fetch_goods() -> list[dict]:
    body = json.dumps({"shop_no": SHOP_NO, "goods_category_no": "",
                       "keywords": "", "sort": "default"}).encode()
    req = urllib.request.Request(API, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    if d.get("code") != 1:
        raise RuntimeError(f"shopApi 返回异常: {d.get('msg')}")
    data = d["data"]
    return data if isinstance(data, list) else (data.get("list") or [])


def in_stock(g: dict) -> bool:
    """页面能买才算在售：库存 > 0 或 无限库存(-1)。"""
    q = g.get("stock_available_quantity")
    try:
        return int(q) != 0
    except (TypeError, ValueError):
        return True


def fmt_price(p) -> str:
    try:
        f = float(p)
    except (TypeError, ValueError):
        return str(p)
    return f"{f:.2f}".rstrip("0").rstrip(".")


def clean_name(n: str) -> str:
    """去掉商品名里的营销前缀 emoji/【】堆叠，保留可读部分。"""
    s = str(n or "").strip()
    s = re.sub(r"^[🔥🐔\s]+", "", s)
    return s


def main() -> int:
    check_only = "--check" in sys.argv
    goods = fetch_goods()
    on_sale = [g for g in goods if in_stock(g)]
    on_sale.sort(key=lambda x: (float(x.get("price") or 0)))

    if check_only:
        print(f"在售 {len(on_sale)} / 共 {len(goods)}")
        for g in on_sale:
            print(f"  ¥{fmt_price(g.get('price')):<10} {clean_name(g.get('name'))[:40]}")
        return 0

    today = date.today().isoformat()
    rows = []
    for g in on_sale:
        name = clean_name(g.get("name"))
        price = fmt_price(g.get("price"))
        qty = g.get("stock_available_quantity")
        try:
            qn = int(qty)
            stock = "充足" if qn < 0 or qn > 20 else f"余 {qn}"
        except (TypeError, ValueError):
            stock = "在售"
        link = f"{SHOP_URL}"
        rows.append(
            f'<tr><td>{name}</td><td>¥{price}</td><td>{stock}</td>'
            f'<td><a href="{link}" rel="nofollow noopener">进店购买</a></td></tr>')

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cocos AI订阅源头 · 公开价目页</title>
<meta name="description" content="Cocos AI订阅源头店铺公开价目页：{len(on_sale)} 个在售商品的名称、价格（人民币 CNY）与库存状态。价格直接采自店铺实时页面，每日核对。">
<meta name="msvalidate.01" content="5F878F0B445E408788BEBF490289C2BA" />
<style>
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;margin:24px;line-height:1.6;color:#222;max-width:900px}}
table{{border-collapse:collapse;margin:16px 0;width:100%;font-size:15px;table-layout:fixed}}
th,td{{border:1px solid #ccc;padding:8px 12px;text-align:left;vertical-align:top}}
th{{background:#f5f5f5;font-weight:600}}
th:nth-child(1),td:nth-child(1){{width:auto;word-break:break-word}}
th:nth-child(2),td:nth-child(2){{width:110px;white-space:nowrap;font-variant-numeric:tabular-nums}}
th:nth-child(3),td:nth-child(3){{width:80px;white-space:nowrap;text-align:center}}
th:nth-child(4),td:nth-child(4){{width:96px;white-space:nowrap}}
.note{{background:#fff8e6;border-left:3px solid #e8a33d;padding:10px 14px;margin:16px 0;font-size:14px}}
footer{{margin-top:32px;color:#666;font-size:13px}}
</style>
</head>
<body>
<h1>Cocos AI订阅源头 · 公开价目页</h1>
<p>店铺名称：Cocos AI订阅源头（AI订阅源头-Cocos）<br>
店铺地址：<a href="{SHOP_URL}">{SHOP_URL}</a></p>
<div class="note">本页价格<b>直接采自店铺实时页面</b>，每日核对；如需最终确认以下单页为准。币种人民币（CNY）。</div>
<table>
<thead>
<tr><th>商品名称和规格</th><th>价格（CNY）</th><th>库存</th><th>购买</th></tr>
</thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
<footer>
<p>本页由店主维护，用于公开报价核验。价格与在售状态以店铺实时页面为准。<br>
更新日期：{today} ｜ 在售商品 {len(on_sale)} 个</p>
</footer>
</body>
</html>
'''
    (REPO / "index.html").write_text(html, encoding="utf-8")
    print(f"已生成 index.html：{len(on_sale)} 个在售商品，日期 {today}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
