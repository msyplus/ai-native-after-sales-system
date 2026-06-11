"""生产感样例数据 — 用于各模块演示统一 case_context 的输入输出.

提供至少 3 条样例 case，覆盖：
1. 航班延误退票赔付 + 民航局投诉风险（高风险转人工）。
2. 商品售后 RMA/换货 + 证据缺失（需追问后人工判断）。
3. 重复咨询物流进度（标准咨询可自动答复）。
"""

from .case_schema import build_case_context

SAMPLE_CASES: list[dict] = [
    # --- Case 1: 高风险转人工 ---
    build_case_context(
        customer_message="航班延误后我要求退票赔付，如果今天不给方案我就投诉到民航局。",
        conversation=[
            {"role": "customer", "content": "航班延误后我要求退票赔付，如果今天不给方案我就投诉到民航局。"},
            {"role": "agent", "content": "我已了解您的情况。为帮您尽快处理，请提供订单号和航班日期。"},
        ],
        required_slots={
            "order_id": {"status": "missing", "value": ""},
            "event_time": {"status": "missing", "value": ""},
            "customer_request": {"status": "provided", "value": "退票赔付"},
            "evidence": {"status": "missing", "value": ""},
        },
        risk_tags=["regulatory_or_public_risk", "compensation_or_refund"],
        knowledge_refs=[
            {"source": "退改签 SOP", "chunk_id": "KB-001", "text": "航班延误导致非自愿退票时，应先核实航司政策和订单状态。"},
            {"source": "升级投诉处理规范", "chunk_id": "KB-015", "text": "客户明确表示向民航局投诉时，应立即标记为监管投诉风险（P0/P1）。"},
        ],
        next_action="human_handoff",
        handoff_summary="客户因航班延误要求退票和赔付，并提到民航局投诉。当前缺少订单号、航班日期和证明材料，建议人工确认非自愿退票政策适用性。风险标签：监管投诉风险 + 赔付风险。",
        customer_intent="refund_compensation_complaint",
    ),
    # --- Case 2: RMA 换货 + 证据缺失 ---
    build_case_context(
        customer_message="我在你们平台买的蓝牙耳机用了三天就充不进电了，要求换货。",
        conversation=[
            {"role": "customer", "content": "我在你们平台买的蓝牙耳机用了三天就充不进电了，要求换货。"},
            {"role": "agent", "content": "收到。请提供订单号、购买时间和问题发生的具体情况，同时如能提供充电异常的视频或照片会加快处理。"},
        ],
        required_slots={
            "order_id": {"status": "missing", "value": ""},
            "event_time": {"status": "missing", "value": ""},
            "customer_request": {"status": "provided", "value": "换货"},
            "evidence": {"status": "missing", "value": ""},
        },
        risk_tags=["compensation_or_refund"],
        knowledge_refs=[
            {"source": "物流RMA", "chunk_id": "KB-013", "text": "客户提出质量问题要求退换货时，需确认订单号、购买时间、商品状态和相关证据。"},
        ],
        next_action="continue_inquiry",
        handoff_summary="",
        customer_intent="rma_exchange",
    ),
    # --- Case 3: 标准咨询（可自动答复）---
    build_case_context(
        customer_message="我三天前买的快递怎么还没到？能帮我查一下物流进度吗？",
        conversation=[
            {"role": "customer", "content": "我三天前买的快递怎么还没到？能帮我查一下物流进度吗？"},
            {"role": "agent", "content": "好的，请提供订单号，我帮您查一下最新物流节点。"},
        ],
        required_slots={
            "order_id": {"status": "missing", "value": ""},
            "event_time": {"status": "provided", "value": "三天前"},
            "customer_request": {"status": "provided", "value": "查询物流进度"},
            "evidence": {"status": "missing", "value": ""},
        },
        risk_tags=[],
        knowledge_refs=[
            {"source": "物流RMA", "chunk_id": "KB-014", "text": "当客户反馈物流长时间无更新或包裹丢失时，需确认订单号、物流单号和最后更新节点。"},
        ],
        next_action="continue_inquiry",
        handoff_summary="",
        customer_intent="logistics_inquiry",
    ),
]

# 额外：提供一些 raw 客户输入用于快速测试
RAW_TEST_INPUTS = [
    "航班延误后我要求退票赔付，如果今天不给方案我就投诉到民航局。",
    "我在你们平台买的蓝牙耳机用了三天就充不进电了，要求换货。",
    "我三天前买的快递怎么还没到？能帮我查一下物流进度吗？",
    "你们这是在欺骗消费者！我要求全额退款并赔偿我的时间损失。",
    "帮我查一下 CA1234 航班今天有没有延误。",
]
