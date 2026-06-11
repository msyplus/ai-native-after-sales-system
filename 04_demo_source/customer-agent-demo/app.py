"""
对客沟通机器人 v1.1 — AI native 售后服务系统信息输入端
=================================================================

多轮槽位继承 | 同一 case_id 跨轮更新 | 高风险转人工 | 低风险标准答复 | 状态可回放

默认使用 LLM 后端（DeepSeek / Ollama），无 Key 时规则兜底。
不接真实客服系统、CRM 或用户数据。
"""

from __future__ import annotations

import json
import os as _os
import re
import sys
from datetime import datetime

import streamlit as st

# ---------- path setup ----------
_SHARED = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)

# ---------- 导入共享模块，带调试保护 ----------
try:
    from ai_native_shared.case_schema import (
        generate_case_id,
        build_case_context,
        missing_slots,
        is_handoff_required,
    )
    from ai_native_shared.knowledge_base import (
        retrieve_knowledge,
        has_sufficient_evidence,
    )
    from ai_native_shared.feedback_schema import build_feedback_event
    from ai_native_shared.case_store import save_case
    from ai_native_shared.feedback_store import save_event
except ImportError as _e:
    st.error(f"导入 ai_native_shared 失败: {_e}")
    st.info(f"当前 sys.path: {sys.path}")
    st.info(f"__file__: {__file__}")
    st.info(f"_SHARED: {_SHARED}")
    st.stop()

# ---------- page config ----------
st.set_page_config(
    page_title="对客沟通机器人 v1.1 · AI native 售后",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- API Key 安全读取 (Task 1) ----------

def get_secret_value(name: str, default: str | None = None) -> str | None:
    """从 Streamlit secrets 优先，再 fallback 到环境变量."""
    try:
        value = st.secrets.get(name)  # type: ignore[attr-defined]
        if value:
            return str(value)
    except Exception:
        pass
    return _os.getenv(name, default)


# ---------- LLM provider configs ----------
LLM_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek V4",
        "icon": "🐋",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": get_secret_value("DEEPSEEK_API_KEY"),
        "description": "中文能力最强",
    },
    "ollama": {
        "name": "Ollama 本地",
        "icon": "💻",
        "model": "qwen2.5:3b",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "description": "本地运行，完全免费",
    },
    "rule-only": {
        "name": "纯规则引擎",
        "icon": "🔧",
        "model": None,
        "base_url": None,
        "api_key": None,
        "description": "无需网络/Key",
    },
}

# ---------- risk patterns ----------
RISK_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("regulatory_or_public_risk", re.compile(r"民航局|12315|消协|工商|媒体|微博|曝光|维权|举报|监管|律师函|起诉|投诉到")),
    ("compensation_or_refund", re.compile(r"赔[偿付]|退款|退票|退[货钱]|补偿|赔偿|换货")),
    ("high_emotion", re.compile(r"不承认|欺骗|欺诈|投诉到底|决不|没完|等着|走着瞧|曝光你们|报警")),
]

# ---------- slot patterns ----------
SLOT_PATTERNS: dict[str, re.Pattern] = {
    "order_id": re.compile(r"订单号[是为：:\s]*\s*([A-Za-z0-9]{5,30})|([A-Za-z0-9]{8,30})"),
    "event_time": re.compile(
        r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?|"
        r"(今天|昨天|前天|昨天晚上|刚才|刚刚|上午|下午|晚上|月初|月末|上周|这周|前几天|三天前|一天前|"
        r"\d{1,2}[月号]\d{1,2}[日号])"
    ),
    "evidence": re.compile(r"照片|截图|视频|凭证|票据|订单截图|支付截图|物流截图|有证据|拍了|拍照"),
}

# ---------- system prompt ----------
SYSTEM_PROMPT = """你是一个专业的售后服务客服Agent，名字叫"小助"，正在与客户进行文字对话。

## 职责
1. 理解客户问题，用自然友好的中文回复。
2. 根据知识库信息给客户准确解答。
3. 缺关键信息时自然引导补充，但不要机械地要订单号。
4. 涉及赔付、退款、监管投诉等敏感场景时表达理解但不要承诺结果。

## 原则
- 先共情再给信息，每次2-4句话。
- 知识库有依据时用自己的话转述，标注"根据政策"。
- 知识库无覆盖时诚实说"需要帮您进一步确认"。
- 不承诺具体退款/赔付金额，不代替公司承担责任。

## 禁止
- 不承诺具体赔付金额、退款金额或补偿方案。
- 不在客户投诉时反驳或激化。
- 不编造不存在于知识库的规则。
"""


def build_system_prompt(knowledge_text: str, slot_status: str, risk_info: str) -> str:
    parts = [SYSTEM_PROMPT]
    if knowledge_text:
        parts.append(f"\n\n## 可参考的知识库\n{knowledge_text}")
    if slot_status:
        parts.append(f"\n\n## 字段状态\n{slot_status}")
    if risk_info:
        parts.append(f"\n\n## 风险提醒\n{risk_info}\n注意：涉及高风险场景时保持克制，不承诺处理结果，但让客户感到被重视。")
    return "\n".join(parts)


# ---------- session init ----------
SESSION_DEFAULTS: dict = {
    "conversation": [],
    "slots": {
        "order_id": {"status": "missing", "value": ""},
        "event_time": {"status": "missing", "value": ""},
        "customer_request": {"status": "missing", "value": ""},
        "evidence": {"status": "missing", "value": ""},
    },
    "risk_tags": [],
    "current_case_id": "",
    "case_started_at": "",
    "case_context": None,
    "state_history": [],
    "feedback_events": [],
    "metrics": {
        "total_cases": 0,
        "handoff_count": 0,
        "auto_resolved": 0,
        "repeat_count": 0,
        "knowledge_hit_count": 0,
        "knowledge_miss_count": 0,
    },
    "last_customer_msg": "",
    "last_save_time": "",
}

for key, default in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ========== helpers ==========

def _similarity(a: str, b: str) -> float:
    set_a, set_b = set(a), set(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def detect_risks(text: str) -> list[str]:
    tags = [tag for tag, pattern in RISK_PATTERNS if pattern.search(text)]
    policy_inquiry = re.search(r"手续费|怎么收|如何收费|规则|票规|多久到账|流程", text)
    forceful_request = re.search(r"要求|必须|赔付|赔偿|补偿|投诉|举报|曝光|维权|起诉", text)
    if policy_inquiry and not forceful_request:
        tags = [tag for tag in tags if tag != "compensation_or_refund"]
    return tags


def extract_slots_from_text(text: str, current_slots: dict) -> dict:
    """跨轮增量提取——已有槽位不覆盖，新槽位仅当文本包含明确信息时才更新."""
    slots = {k: dict(v) for k, v in current_slots.items()}
    if "customer_request" not in slots:
        slots["customer_request"] = {"status": "missing", "value": ""}

    # customer_request：首轮设置，后续追加，不覆盖
    if slots["customer_request"]["status"] != "provided":
        slots["customer_request"] = {"status": "provided", "value": text[:150]}
    elif text.strip():
        old = slots["customer_request"]["value"]
        if text[:80] not in old:
            slots["customer_request"]["value"] = f"{old} / {text[:80]}"

    for name, pattern in SLOT_PATTERNS.items():
        if slots.get(name, {}).get("status") == "provided":
            continue
        m = pattern.search(text)
        if m:
            val = m.group(1) or m.group(2) or m.group(0)
            slots[name] = {"status": "provided", "value": val}
    return slots


def check_evidence_sufficient(slots: dict, risk_tags: list[str]) -> bool:
    provided = sum(1 for s in slots.values() if s.get("status") == "provided")
    has_refund = any("compensation" in t for t in risk_tags)
    if has_refund and slots.get("evidence", {}).get("status") != "provided":
        return False
    return provided >= 2


def get_or_create_case_id() -> str:
    """同一会话复用同一个 case_id."""
    if not st.session_state.get("current_case_id"):
        st.session_state["current_case_id"] = generate_case_id()
        st.session_state["case_started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return st.session_state["current_case_id"]


def snapshot_case_state(slots: dict, risks: list[str], hits: list[dict], next_action: str) -> dict:
    """每轮结束后拍快照，用于状态回放."""
    return {
        "turn": len(st.session_state.get("state_history", [])) + 1,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "case_id": st.session_state.get("current_case_id", ""),
        "provided_slots": [k for k, v in slots.items() if v.get("status") == "provided"],
        "missing_slots": [k for k, v in slots.items() if v.get("status") == "missing"],
        "risk_tags": list(risks),
        "knowledge_refs": [h.get("chunk_id", "") for h in hits],
        "next_action": next_action,
    }


def determine_next_action(slots: dict, risks: list[str], hits: list[dict]) -> str:
    """决策逻辑：高风险 → human_handoff，缺字段 → continue_inquiry，知识充足 → standard_answer."""
    is_high = any(t in risks for t in ("regulatory_or_public_risk", "compensation_or_refund", "high_emotion"))
    if is_high:
        return "human_handoff"
    miss = [k for k, v in slots.items() if v.get("status") == "missing"]
    if hits and has_sufficient_evidence(hits) and set(miss).issubset({"evidence"}):
        return "standard_answer"
    if miss:
        return "continue_inquiry"
    if hits and has_sufficient_evidence(hits):
        return "standard_answer"
    return "human_handoff"


def build_handoff_summary(user_msg: str, slots: dict, risks: list[str], hits: list[dict]) -> str:
    parts = [f"客户原话：{user_msg}"]
    provided = [f"{k}={v['value']}" for k, v in slots.items() if v.get("status") == "provided"]
    miss = [k for k, v in slots.items() if v.get("status") == "missing"]
    if provided:
        parts.append(f"已收集：{'；'.join(provided)}")
    if miss:
        parts.append(f"仍缺失：{'、'.join(miss)}")
    if risks:
        parts.append(f"风险标签：{'、'.join(risks)}")
    if hits:
        parts.append(f"命中知识源：{'、'.join({h['source'] for h in hits})}")
    else:
        parts.append("知识库：未命中足够依据")
    parts.append("建议动作：人工确认高风险事项的适用政策，补充缺失字段后给出最终处理方案并设定回复时限。")
    return "。".join(parts) + "。"


# ========== LLM call (Task 1: check api_key) ==========

def call_llm(provider_key: str, messages: list[dict]) -> str | None:
    cfg = LLM_PROVIDERS.get(provider_key)
    if not cfg or not cfg["model"] or not cfg.get("api_key"):
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=messages,
            temperature=0.7,
            max_tokens=600,
            timeout=20,
        )
        return response.choices[0].message.content
    except Exception:
        return None


# ========== rule-based fallback (Task 6: no amount promises) ==========

# 禁止承诺词检查
_PROMISE_BLACKLIST = re.compile(r"一定赔付|保证退款|肯定全额|必须赔偿|承诺退还|确保退[款票]|包退|绝对[可会]|百分百[退赔]")


def _sanitize_response(text: str) -> str:
    """确保回复不包含具体金额承诺用语."""
    if _PROMISE_BLACKLIST.search(text):
        text = _PROMISE_BLACKLIST.sub("具体结果以系统或人工确认为准", text)
    if "具体金额" not in text and "实际" not in text and "确认为准" not in text:
        if any(kw in text for kw in ("退", "赔", "补偿", "退款")):
            text += " 具体金额/结果以系统或人工确认为准。"
    return text


def rule_based_response(user_msg: str, slots: dict, risks: list[str], hits: list[dict], next_action: str) -> str:
    """规则兜底回复。对客话术与知识原文分离。"""
    miss = [k for k, v in slots.items() if v.get("status") == "missing"]
    is_high = any(t in risks for t in ("regulatory_or_public_risk", "compensation_or_refund", "high_emotion"))

    if next_action == "standard_answer":
        # 知识充足 → 自然语言话术，不包含知识原文
        if hits:
            return _sanitize_response(
                "根据系统知识库中的相关政策说明，您的情况适用相应处理标准。"
                "具体金额/结果以系统或人工确认为准。如需进一步了解详细信息，我们将转接人工专员为您处理。"
            )
        return _sanitize_response(
            "已记录您的需求，我需要帮您进一步确认相关政策和规则，请稍候。"
        )

    if miss:
        questions = {
            "order_id": "方便提供一下订单号吗？",
            "event_time": "请问具体是什么时候的事？",
            "evidence": "如有照片、截图或凭证可以发给我，加速处理。",
            "customer_request": "能详细说说您希望怎么解决吗？",
        }
        followups = [questions[n] for n in miss if n in questions]
        return f"{'收到，我来帮您处理。'} {' '.join(followups[:2])}"

    if is_high:
        return _sanitize_response(
            "我已详细记录您的情况，您的问题涉及需要人工专员进一步确认的事项。"
            "我已将对话记录和信息整理好，马上为您转接人工客服，请稍候。"
        )

    return "收到，我来帮您处理。已记录您的需求，我会尽快帮您跟进。"


# ========== main processing ==========

def _process_user_input(user_msg: str, provider_key: str):
    """处理一条客户消息——多轮增量更新."""
    conv = st.session_state["conversation"]
    conv.append({"role": "customer", "content": user_msg})

    # 重复检测
    last = st.session_state.get("last_customer_msg", "")
    if last and _similarity(last, user_msg) > 0.7:
        st.session_state["metrics"]["repeat_count"] += 1
    st.session_state["last_customer_msg"] = user_msg

    # Task 2: 跨轮复用同一个 case_id
    case_id = get_or_create_case_id()

    # 提取结构化信息（Task 3: 跨轮增量）
    risks = detect_risks(user_msg)
    slots = extract_slots_from_text(user_msg, st.session_state["slots"])
    st.session_state["slots"] = slots
    st.session_state["risk_tags"] = risks

    # 知识检索
    hits = retrieve_knowledge(user_msg, top_k=3)
    if hits and has_sufficient_evidence(hits):
        st.session_state["metrics"]["knowledge_hit_count"] += 1
    else:
        st.session_state["metrics"]["knowledge_miss_count"] += 1

    # Task 5: 决策
    next_action = determine_next_action(slots, risks, hits)

    # 高风险缺字段也生成 handoff_summary (Task 5 Step 3)
    handoff_summary = ""
    if next_action == "human_handoff":
        handoff_summary = build_handoff_summary(user_msg, slots, risks, hits)

    # 构建 LLM messages
    knowledge_text = "\n".join(f"【{h['source']}】{h['title']}：{h['text']}" for h in hits) if hits else "无匹配内容"
    provided_info = [f"{k}：{v['value']}" for k, v in slots.items() if v["status"] == "provided"]
    missing_info = [k for k, v in slots.items() if v["status"] == "missing"]
    slot_status = ""
    if provided_info:
        slot_status += f"已收集：{'；'.join(provided_info)}\n"
    if missing_info:
        slot_status += f"仍需：{'、'.join(missing_info)}"
    risk_labels = {
        "regulatory_or_public_risk": "客户提及监管投诉/媒体曝光",
        "compensation_or_refund": "客户要求赔付/退款",
        "high_emotion": "客户情绪激动",
    }
    risk_info = "\n".join(risk_labels.get(r, r) for r in risks) if risks else ""

    system_content = build_system_prompt(knowledge_text, slot_status, risk_info)
    messages = [{"role": "system", "content": system_content}]
    for m in conv[-8:]:
        role = "assistant" if m["role"] == "agent" else "user"
        messages.append({"role": role, "content": m["content"]})

    # LLM 优先
    agent_msg = None
    if provider_key != "rule-only":
        agent_msg = call_llm(provider_key, messages)

    if agent_msg is None:
        agent_msg = rule_based_response(user_msg, slots, risks, hits, next_action)

    conv.append({"role": "agent", "content": agent_msg})

    # Task 4: 快照状态
    snap = snapshot_case_state(slots, risks, hits, next_action)
    st.session_state["state_history"].append(snap)

    # 构建 case_context (Task 2: 外界传入 case_id)
    case_ctx = build_case_context(
        customer_message=user_msg,
        conversation=conv.copy(),
        required_slots=slots,
        risk_tags=risks,
        knowledge_refs=hits,
        next_action=next_action,
        handoff_summary=handoff_summary,
        customer_intent=_classify_intent(user_msg),
        case_id=case_id,
        state_history=st.session_state["state_history"],
    )

    st.session_state["case_context"] = case_ctx

    # ── 持久化到 case_store ─────────────────────────────
    try:
        save_case(case_ctx)
        st.session_state["last_save_time"] = datetime.now().strftime("%H:%M:%S")
    except Exception:
        # 持久化失败不阻塞主流程
        pass

    st.session_state["metrics"]["total_cases"] = max(st.session_state["metrics"]["total_cases"], 1)

    if next_action == "human_handoff":
        st.session_state["metrics"]["handoff_count"] += 1
    elif next_action == "standard_answer":
        st.session_state["metrics"]["auto_resolved"] += 1

    # ── 反馈事件（内存 + 持久化） ──
    if not hits or not has_sufficient_evidence(hits):
        ev = build_feedback_event(
            case_id=case_id, event_type="knowledge_miss", source_module="customer_agent",
            description=f"知识库未命中：{user_msg[:80]}",
            root_cause="knowledge_gap",
            suggested_action="补充该场景的知识片段。",
            priority="P1",
        )
        st.session_state["feedback_events"].append(ev)
        try:
            save_event(
                case_id=case_id, event_type="knowledge_miss", source_module="customer_agent",
                description=ev["description"], root_cause="knowledge_gap",
                suggested_action="补充该场景的知识片段。", priority="P1",
            )
        except Exception:
            pass  # 持久化失败不阻塞主流程

    if next_action == "human_handoff" and (risks or not hits or not has_sufficient_evidence(hits)):
        priority = "P0" if "regulatory_or_public_risk" in risks else "P1"
        ev = build_feedback_event(
            case_id=case_id, event_type="handoff_reason", source_module="customer_agent",
            description=f"转人工原因：风险标签{'、'.join(risks) if risks else '证据不足'}。",
            root_cause="policy_unclear",
            suggested_action="确认转人工规则阈值。",
            priority=priority,
        )
        st.session_state["feedback_events"].append(ev)
        try:
            save_event(
                case_id=case_id, event_type="handoff_reason", source_module="customer_agent",
                description=ev["description"], root_cause="policy_unclear",
                suggested_action="确认转人工规则阈值。", priority=priority,
            )
        except Exception:
            pass

    # 追问失败检测：超过 6 轮仍缺关键字段 → 生成 inquiry_failure 事件
    if next_action == "continue_inquiry" and len(conv) >= 12:  # 6 turn pairs
        ev = build_feedback_event(
            case_id=case_id, event_type="inquiry_failure", source_module="customer_agent",
            description=f"追问失败：{len(conv)//2} 轮后仍缺少必要字段",
            root_cause="inquiry_exhausted",
            suggested_action="优化追问策略或提前转人工兜底。",
            priority="P1",
        )
        st.session_state["feedback_events"].append(ev)
        try:
            save_event(
                case_id=case_id, event_type="inquiry_failure", source_module="customer_agent",
                description=ev["description"], root_cause="inquiry_exhausted",
                suggested_action="优化追问策略或提前转人工兜底。", priority="P1",
            )
        except Exception:
            pass


def _classify_intent(text: str) -> str:
    if re.search(r"退票|退款|赔付|赔偿|退钱|退货|换货|补偿", text):
        return "refund_compensation_complaint"
    if re.search(r"快递|物流|发货|到哪|查单|运输|揽收|派件|还没收到|没更新", text):
        return "logistics_inquiry"
    if re.search(r"民航局|12315|消协|工商|投诉|举报|维权|欺骗|监管|态度|曝光", text):
        return "regulatory_complaint"
    return "general_inquiry"


# ========== UI ==========

def inject_css():
    st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; }
    .case-id-badge {
        display:inline-block;padding:4px 12px;border-radius:6px;
        background:#0f766e;color:white;font-family:monospace;font-size:14px;font-weight:700;
    }
    .risk-high { color:#dc2626;font-weight:700; }
    .slot-provided { color:#059669; }
    .slot-missing { color:#94a3b8; }
    </style>
    """, unsafe_allow_html=True)


def render_sidebar():
    st.sidebar.title("⚙️ 设置")
    provider = st.sidebar.selectbox(
        "LLM 引擎",
        list(LLM_PROVIDERS.keys()),
        format_func=lambda k: f"{LLM_PROVIDERS[k]['icon']} {LLM_PROVIDERS[k]['name']}",
        index=0,
    )
    st.sidebar.caption(LLM_PROVIDERS[provider]["description"])

    # 显示 Key 状态
    if provider == "deepseek":
        key_status = "已配置" if LLM_PROVIDERS["deepseek"].get("api_key") else "未配置"
        st.sidebar.caption(f"DeepSeek API Key：{key_status}  |  配置方式：环境变量 DEEPSEEK_API_KEY 或 Streamlit secrets")

    if provider == "rule-only":
        st.sidebar.warning("纯规则模式，回复基础。建议选 DeepSeek 并配置 API Key。")

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 重置会话"):
        for key in SESSION_DEFAULTS:
            st.session_state[key] = SESSION_DEFAULTS[key]
        st.rerun()

    st.sidebar.metric("总 Case", st.session_state["metrics"]["total_cases"])
    st.sidebar.metric("转人工", st.session_state["metrics"]["handoff_count"])
    st.sidebar.metric("反馈事件", len(st.session_state["feedback_events"]))
    st.sidebar.caption(f"💾 最后同步时间：{st.session_state.get('last_save_time', '—')}")

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "**版本 v1.1** · AI native 售后服务系统\n\n"
        "不接真实用户数据，不承诺退款/赔付。\n"
        "展示多轮槽位继承、高风险转人工和低风险标准答复能力。"
    )

    st.sidebar.markdown("**快速测试**")
    samples = [
        "航班延误后我要求退票赔付，如果今天不给方案我就投诉到民航局。",
        "我买的耳机三天了还没收到，帮我查一下物流。",
        "自愿退票手续费怎么收？订单号 A123456789，今天想退票。",
    ]
    for s in samples:
        if st.sidebar.button(s[:42] + "…", key=f"sp_{abs(hash(s)) % 100000}"):
            _process_user_input(s, provider)
            st.rerun()

    return provider


def render_chat():
    st.subheader("💬 客户对话")
    for msg in st.session_state["conversation"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("输入售后问题…")
    if user_input:
        provider = st.session_state.get("_provider", "deepseek")
        _process_user_input(user_input, provider)
        st.rerun()


def render_right_panel():
    ctx = st.session_state.get("case_context")
    if ctx is None:
        st.subheader("📋 当前 Case")
        st.caption("等待客户输入…")
        return

    st.subheader("📋 当前 Case")
    st.markdown(f'<span class="case-id-badge">{ctx["case_id"]}</span>', unsafe_allow_html=True)
    if st.session_state.get("case_started_at"):
        st.caption(f"创建于 {st.session_state['case_started_at']}")

    st.markdown("**🎯 意图**")
    st.markdown(f"`{ctx['customer_intent']}`")

    st.markdown("**📝 字段收集**")
    for name, info in ctx["required_slots"].items():
        status = info.get("status", "missing")
        icon = "✅" if status == "provided" else "⬜"
        val = info.get("value", "")[:40] or "—"
        cls = "slot-provided" if status == "provided" else "slot-missing"
        st.markdown(f'{icon} **{name}**：<span class="{cls}">{val}</span>', unsafe_allow_html=True)

    st.markdown("**⚠️ 风险标签**")
    tags = ctx.get("risk_tags", [])
    if tags:
        for t in tags:
            st.markdown(f'- <span class="risk-high">{t}</span>' if "regulatory" in t or "high_emotion" in t else f"- {t}", unsafe_allow_html=True)
    else:
        st.caption("无风险标签")

    st.markdown("**📚 知识引用**")
    refs = ctx.get("knowledge_refs", [])
    if refs:
        for r in refs:
            st.caption(f"- {r['source']}｜{r['title']}")
        with st.expander("📖 知识原文（客服参考）", expanded=True):
            for r in refs:
                st.markdown(f"**{r['source']} — {r['title']}**")
                st.caption(f"匹配得分：{r.get('score', '—')}")
                st.markdown(f"```\n{r['text'][:500]}\n```")
    else:
        st.caption("未命中")

    action = ctx.get("next_action", "")
    labels = {"continue_inquiry": "🔍 继续对话", "standard_answer": "✅ 标准回答", "human_handoff": "🔄 转人工", "escalate": "🚨 升级"}
    st.markdown(f"**🔀 下一步**：{labels.get(action, action)}")

    if ctx.get("handoff_summary"):
        st.markdown("**📦 转人工包**")
        with st.container(border=True):
            st.markdown(ctx["handoff_summary"])

    # Task 4: 状态变化记录
    history = st.session_state.get("state_history", [])
    if history:
        with st.expander(f"📜 状态变化记录 ({len(history)} 轮)", expanded=False):
            st.json(history)


def render_bottom():
    m = st.session_state["metrics"]
    total = max(m["total_cases"], 1)
    knowledge_total = max(m["knowledge_hit_count"] + m["knowledge_miss_count"], 1)
    ctx = st.session_state.get("case_context")
    field_complete = 0
    if ctx:
        provided = sum(1 for s in ctx["required_slots"].values() if s.get("status") == "provided")
        field_complete = provided / max(len(ctx["required_slots"]), 1) * 100

    cols = st.columns(6)
    cols[0].metric("自动解决率", f"{m['auto_resolved'] / total * 100:.0f}%")
    cols[1].metric("转人工率", f"{m['handoff_count'] / total * 100:.0f}%")
    cols[2].metric("字段完整率", f"{field_complete:.0f}%")
    cols[3].metric("知识命中率", f"{m['knowledge_hit_count'] / knowledge_total * 100:.0f}%")
    cols[4].metric("人工接管时长", "≈ 0s")
    cols[5].metric("重复描述", m["repeat_count"])

    if ctx:
        with st.expander("🔍 case_context JSON"):
            st.json(ctx)
    events = st.session_state.get("feedback_events", [])
    if events:
        with st.expander(f"📋 反馈事件 ({len(events)} 条)"):
            for ev in reversed(events[-10:]):
                st.caption(f"[{ev['priority']}] {ev['event_type']} — {ev['description'][:100]}")


# ========== main ==========

def main():
    inject_css()
    provider = render_sidebar()
    st.session_state["_provider"] = provider

    st.title("🤖 对客沟通机器人 v1.1")
    st.caption("多轮槽位继承 | 同一 case_id | 高风险转人工 | 低风险标准答复 | DeepSeek LLM 驱动")
    st.info(
        "**系统定位**：AI native 售后服务系统的信息输入端。"
        "同一会话内 case_id 不变，字段跨轮累积，高风险场景优先转人工，"
        "低风险场景给标准答复且不承诺具体金额。"
        " 不接真实用户数据，不自动承诺退款/赔付/监管结果。"
    )

    left, right = st.columns([3, 2])
    with left:
        render_chat()
        st.divider()
        render_bottom()
    with right:
        render_right_panel()


if __name__ == "__main__":
    main()
