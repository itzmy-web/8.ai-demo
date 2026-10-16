"""知识意图表 + FAQ 知识库（移植自 itzmy knowledge/intents.py）。

provider：faq.default 走本地 FAQ；rag.default 走融合版 RAG 智库检索。
"""
from __future__ import annotations

KNOWLEDGE_INTENTS: dict[str, dict] = {
    "product_info": {
        "id": "product_info",
        "description": "商品信息咨询",
        "providers": ["api.product"],
        "keywords": ["商品", "产品", "多少钱", "价格", "库存", "有货"],
    },
    "order_info": {
        "id": "order_info",
        "description": "订单信息咨询",
        "providers": ["api.order"],
        "keywords": ["订单", "买的东西", "下单"],
    },
    "refund_policy": {
        "id": "refund_policy",
        "description": "退款政策咨询",
        "providers": ["faq.default", "rag.default"],
        "keywords": ["退款", "退钱", "退货", "怎么退"],
    },
    "return_policy": {
        "id": "return_policy",
        "description": "退货政策咨询",
        "providers": ["faq.default", "rag.default"],
        "keywords": ["退货", "换货", "退回"],
    },
    "shipping_policy": {
        "id": "shipping_policy",
        "description": "配送政策咨询",
        "providers": ["faq.default", "rag.default"],
        "keywords": ["配送", "运费", "快递", "发货", "多久到"],
    },
    "platform_rule": {
        "id": "platform_rule",
        "description": "平台规则咨询",
        "providers": ["rag.default"],
        "keywords": ["规则", "违规", "处罚", "保证金"],
    },
    "general_ecommerce_info": {
        "id": "general_ecommerce_info",
        "description": "电商通用信息咨询",
        "providers": ["faq.default", "rag.default"],
        "keywords": ["怎么", "如何", "请问"],
    },
}

FAQ = {
    "refund_policy": "退款政策：订单签收后 7 天内支持无理由退款（定制类商品除外）。退款将在收到退货并验收后 1-3 个工作日原路退回。生鲜及贴身衣物不支持无理由退货。",
    "return_policy": "退货政策：商品保持完好、配件齐全即可申请退货，退货运费由责任方承担——质量问题由商家承担，七天无理由由买家承担。",
    "shipping_policy": "配送政策：全场满 99 元包邮（偏远地区除外），默认中通/顺丰发货，工作日 16 点前付款当日发出，一般 2-4 天送达。",
    "platform_rule": "平台规则：商家需保持发货时效（48 小时内），严禁虚假交易与引导站外交易；违规将按层级扣分、限流或下架处理。",
    "general_ecommerce_info": "您好，我是电商小二，可以咨询订单、物流、退款退货、配送与商品信息，也可以直接说「转人工」。",
    "product_info": "您好，可以直接告诉我您想咨询的商品名称，我来帮您查价格和库存；也可以在工作台「商品池」页面浏览全部在售商品。",
    "order_info": "查询订单请直接说「查订单」并告诉我订单号；物流查询说「查物流」即可。",
}


def match_intents_by_keywords(text: str) -> list[str]:
    """无 LLM 时的关键词兜底路由。"""
    hits: list[str] = []
    for intent in KNOWLEDGE_INTENTS.values():
        if any(k in text for k in intent["keywords"]):
            hits.append(intent["id"])
    return hits


def faq_answer(intent_id: str) -> str:
    return FAQ.get(intent_id, "这个问题我还在学习中，您可以换个问法，或者说「转人工」联系人工客服。")
