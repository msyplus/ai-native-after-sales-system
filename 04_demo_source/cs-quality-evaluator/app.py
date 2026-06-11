"""
AI客服对话质检系统 v3.2
AI Customer Service Conversation Quality Evaluator

独立作品 — 多模型 AI 引擎架构
支持: Ollama(本地免费) | DeepSeek V4 | Gemini 2.0 Flash(免费) | Groq(免费)
技术栈: Python + Streamlit + Plotly + Multi-LLM
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import json
import os

st.set_page_config(
    page_title="AI客服质检系统",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════
# 模型定义
# ═══════════════════════════════════════════════════════════

MODELS = {
    "rule-only": {
        "name": "关键词规则引擎", "provider": "内置", "icon": "🔧",
        "model_id": None, "key_required": False, "key_name": None,
        "base_url": None, "sdk_type": "rule",
        "description": "纯关键词匹配，无需网络/Key，结果立即可见",
        "speed": "⚡ 即时", "cost": "免费",
    },
    "ollama-qwen": {
        "name": "Qwen2.5 3B (本地)", "provider": "Ollama", "icon": "💻",
        "model_id": "qwen2.5:3b", "key_required": False, "key_name": None,
        "base_url": "http://localhost:11434/v1", "sdk_type": "openai",
        "description": "本地运行，完全免费，无需网络",
        "speed": "🚀 快（本地）", "cost": "免费",
    },
    "deepseek": {
        "name": "DeepSeek V4", "provider": "DeepSeek", "icon": "🐋",
        "model_id": "deepseek-chat", "key_required": True, "key_name": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com", "sdk_type": "openai",
        "description": "中文能力最强", "speed": "⚡ 较快", "cost": "¥1/百万tokens",
    },
    "gemini": {
        "name": "Gemini 2.0 Flash", "provider": "Google", "icon": "🌐",
        "model_id": "gemini-2.0-flash", "key_required": True, "key_name": "GEMINI_API_KEY",
        "base_url": None, "sdk_type": "gemini",
        "description": "免费1500次/天", "speed": "⚡ 较快", "cost": "免费",
    },
    "groq": {
        "name": "Llama 3.3 70B (Groq)", "provider": "Groq", "icon": "⚡",
        "model_id": "llama-3.3-70b-versatile", "key_required": True, "key_name": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1", "sdk_type": "openai",
        "description": "免费30次/分钟", "speed": "🔥 极快", "cost": "免费",
    },
}

# ═══════════════════════════════════════════════════════════
# 评估标准 + 关键词库
# ═══════════════════════════════════════════════════════════

EVALUATION_DIMENSIONS = {
    "识别需求": {
        "weight": 0.25,
        "description": "客服是否准确理解消费者的问题和真实诉求",
        "rubric": {
            5: "不仅识别表面问题，还挖掘了深层需求，消费者感到'被理解'",
            4: "准确识别了主要问题，基本覆盖消费者诉求",
            3: "识别了主要问题但遗漏了部分细节",
            2: "部分理解错误，需要消费者重复说明",
            1: "完全理解错误或未尝试理解消费者问题",
        },
    },
    "有效共情": {
        "weight": 0.25,
        "description": "客服是否展现了恰当的同理心",
        "rubric": {
            5: "共情自然恰当、时机准确，有效缓解消费者负面情绪",
            4: "有共情表达，基本恰当但略显模板化",
            3: "有共情尝试但时机或方式不够好",
            2: "共情缺乏或过度夸张显得虚假",
            1: "完全冷漠、机械化，或态度恶劣",
        },
    },
    "达成一致": {
        "weight": 0.30,
        "description": "客服是否给出了消费者可接受的解决方案",
        "rubric": {
            5: "方案明确可行且消费者明确表示接受，有备选方案",
            4: "给出了可行方案，消费者基本接受",
            3: "有方案但不够明确，消费者态度模糊",
            2: "方案不合理或消费者明显不接受",
            1: "未提供任何有效解决方案或直接拒绝",
        },
    },
    "承诺回复": {
        "weight": 0.20,
        "description": "客服是否明确了后续步骤和时间节点",
        "rubric": {
            5: "清晰告知下一步动作、明确时间节点、对接人",
            4: "告知了下一步但不明确时间节点",
            3: "承诺了会处理但缺乏具体信息",
            2: "含糊其辞，消费者不确定是否会被跟进",
            1: "没有任何承诺或直接结束对话",
        },
    },
}

# 可编辑的关键词库
KW_POSITIVE = {
    "识别需求": ["您是说", "我理解您", "您的问题是", "您的意思是", "帮您确认", "核实一下",
                  "让我看看", "帮您查", "明白了", "了解了", "知道您的情况"],
    "有效共情": ["理解您的心情", "非常抱歉", "给您带来不便", "确实是我们不好", "让您久等了",
                  "我明白您的感受", "请您放心", "我会尽力", "感谢您的耐心", "辛苦您了"],
    "达成一致": ["帮您申请", "为您办理", "给您退款", "帮您协调", "已为您提交",
                  "补偿方案", "优惠券", "退差价", "换货处理", "加急处理",
                  "您看这样行吗", "您觉得可以吗", "这个方案您接受吗"],
    "承诺回复": ["X个工作日内", "明天", "今天", "稍后", "马上", "会尽快", "预计",
                  "我会跟进", "会有专人", "请注意查收", "会有通知", "会联系您", "后续您可以看到"],
}

KW_NEGATIVE = {
    "识别需求": ["没听懂", "再说一遍", "什么意思", "不知道您在说什么", "我没理解"],
    "有效共情": ["这是规定", "我也没办法", "不是我负责", "你去找", "不关我事", "你不满意我也没办法"],
    "达成一致": ["做不到", "不行", "不可能", "没有办法", "不能退", "我们没错", "你自己弄的", "跟我们没关系"],
    "承诺回复": ["等着吧", "不一定", "不敢保证", "说不准", "看情况", "到时候再说"],
}

NOISE_WORDS = {
    "嗯", "哦", "啊", "呢", "吧", "哈", "呀", "嘛", "哎", "唉", "喂",
    "嗯嗯", "哦哦", "啊啊", "哈哈", "呵呵", "嘿嘿",
    "收到", "好的", "好滴", "好哒", "好嘞", "行", "行吧", "好吧", "可以", "可以的", "没问题",
    "谢谢", "感谢", "不客气", "没事", "没关系",
    "您好", "你好", "在的", "在呢", "亲", "亲亲", "亲您好",
    "知道了", "收到啦", "明白了", "清楚", "清楚了", "晓得了", "了解了",
    "~", "~~", "~~~",
}

# ═══════════════════════════════════════════════════════════
# 多模型客户端
# ═══════════════════════════════════════════════════════════

def get_client(model_key):
    cfg = MODELS[model_key]
    if cfg["sdk_type"] == "rule":
        return None
    if cfg["sdk_type"] == "openai":
        from openai import OpenAI
        if not cfg["key_required"]:
            if not check_ollama_available() or not check_ollama_model(cfg["model_id"]):
                return None
            return OpenAI(
                base_url=cfg["base_url"],
                api_key="ollama",
                timeout=20.0,
                max_retries=0,
            )
        key = os.getenv(cfg["key_name"], "") or st.session_state.get(f"key_{model_key}", "")
        if not key:
            return None
        return OpenAI(base_url=cfg["base_url"], api_key=key, timeout=30.0, max_retries=0)
    elif cfg["sdk_type"] == "gemini":
        import google.generativeai as genai
        key = os.getenv("GEMINI_API_KEY", "") or st.session_state.get("key_gemini", "")
        if not key:
            return None
        genai.configure(api_key=key)
        return genai.GenerativeModel(cfg["model_id"])
    return None


@st.cache_data(ttl=30, show_spinner=False)
def check_ollama_available():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        r = s.connect_ex(("127.0.0.1", 11434))
        s.close()
        return r == 0
    except Exception:
        return False


@st.cache_data(ttl=30, show_spinner=False)
def check_ollama_model(model_id="qwen2.5:3b"):
    try:
        from openai import OpenAI
        c = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            timeout=2.0,
            max_retries=0,
        )
        return model_id in [m.id for m in c.models.list()]
    except Exception:
        return False

# ═══════════════════════════════════════════════════════════
# 规则引擎
# ═══════════════════════════════════════════════════════════

def _filter_noise(text):
    if not isinstance(text, str):
        return text
    clean = text
    for w in sorted(NOISE_WORDS, key=len, reverse=True):
        clean = clean.replace(w, " ")
    return clean


def rule_evaluate(conversation):
    if not isinstance(conversation, str) or not conversation.strip():
        return {d: {"score": 3, "reason": "对话内容不足", "pos_words": [], "neg_words": []} for d in EVALUATION_DIMENSIONS}

    text = _filter_noise(conversation.lower())
    result = {}

    for dim in EVALUATION_DIMENSIONS:
        pos_kw = KW_POSITIVE.get(dim, [])
        neg_kw = KW_NEGATIVE.get(dim, [])
        pos_hits = [kw for kw in pos_kw if kw in text]
        neg_hits = [kw for kw in neg_kw if kw in text]
        score = min(5, max(1, round(3 + len(pos_hits) * 0.3 - len(neg_hits) * 0.8)))
        result[dim] = {
            "score": score,
            "reason": f"命中{len(pos_hits)}正向/{len(neg_hits)}负向关键词",
            "pos_words": pos_hits,
            "neg_words": neg_hits,
        }
    return result


# ═══════════════════════════════════════════════════════════
# AI 引擎
# ═══════════════════════════════════════════════════════════

def llm_evaluate(conversation, model_key, client):
    if not client or not conversation.strip():
        return None

    cfg = MODELS[model_key]
    prompt = f"""你是资深客服质检专家。请评估以下客服对话，返回严格 JSON（不要 markdown 标记）。

对话内容：
{conversation[:3000]}

评分标准（1-5分）：
1. 识别需求(权重25%): 客服是否准确理解消费者问题？
2. 有效共情(权重25%): 客服是否展现恰当同理心？
3. 达成一致(权重30%): 客服是否给出可接受方案？
4. 承诺回复(权重20%): 客服是否明确后续步骤和时间节点？

返回 JSON：
{{
    "识别需求": {{"score": 4, "reason": "评分理由"}},
    "有效共情": {{"score": 3, "reason": "评分理由"}},
    "达成一致": {{"score": 5, "reason": "评分理由"}},
    "承诺回复": {{"score": 3, "reason": "评分理由"}},
    "overall_assessment": "整体评价（2-3句话）",
    "tone_analysis": "客服语气分析（1句话）",
    "risk_flags": ["风险标注1", "风险标注2"],
    "highlights": ["亮点1"],
    "improvement_rewrite": "将对话中客服最差的一句回复改写为合格版本"
}}

严格 JSON 格式，不要包含 ```json``` 标记"""

    try:
        if cfg["sdk_type"] == "openai":
            r = client.chat.completions.create(
                model=cfg["model_id"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2, max_tokens=1000,
            )
            raw = r.choices[0].message.content.strip()
        elif cfg["sdk_type"] == "gemini":
            r = client.generate_content(prompt)
            raw = r.text.strip()
        else:
            return None

        if raw.startswith("```"):
            lines = [l for l in raw.split("\n") if not l.startswith("```")]
            raw = "\n".join(lines)
        return json.loads(raw)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def calc_total(dim_scores):
    return round(sum(EVALUATION_DIMENSIONS[d]["weight"] * dim_scores[d]["score"] for d in EVALUATION_DIMENSIONS), 1)


# ═══════════════════════════════════════════════════════════
# 版本历史
# ═══════════════════════════════════════════════════════════

VERSION_HISTORY = [
    {
        "version": "v3.2", "date": "2026-05-20",
        "title": "对话洞察增强 — 高亮标注 + 客服对比 + AI Coaching",
        "changes": [
            "新增对话高亮标注视图：绿色/红色/黄色标注关键词命中位置",
            "新增客服能力雷达对比：多客服同图叠加4维得分+优劣势表",
            "新增AI Coaching要点：针对低分维度自动生成改进话术和培训建议",
        ],
        "advantage": "不仅打分，更深入对话细节，做团队管理和AI辅助培训",
        "icon": "🎯",
    },
    {
        "version": "v3.1", "date": "2026-05-20", "title": "多模型 AI 引擎架构",
        "changes": [
            "新增 4 引擎切换：Ollama Qwen2.5 / DeepSeek / Gemini / Groq",
            "AI 评估新增：整体评价、语调分析、风险标注、亮点、改进话术",
            "新增规则配置面板（关键词/噪声词可编辑）",
            "新增版本演进、问题反馈入口",
            "规则引擎作为默认 baseline",
        ],
        "advantage": "规则引擎秒级评分，AI 引擎提供深度分析和改进建议",
        "icon": "🔄",
    },
    {
        "version": "v2.0", "date": "2026-05-17", "title": "规则引擎版",
        "changes": [
            "4维度加权评估体系（识别需求/有效共情/达成一致/承诺回复）",
            "雷达图 + 柱状图可视化",
            "单条/批量双模式",
            "20段示例对话（高/中/Badcase）",
            "噪声词过滤、Badcase 标注",
        ],
        "advantage": "无外部依赖，关键词规则引擎快速评估",
        "icon": "📊",
    },
    {"version": "v1.0", "date": "2026-05-17", "title": "原型版", "changes": ["评估框架搭建", "示例数据"], "advantage": "验证质检方向", "icon": "🚀"},
]

# ═══════════════════════════════════════════════════════════
# 问题反馈
# ═══════════════════════════════════════════════════════════

ISSUE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "issue_reports.jsonl")

def save_issue(d):
    d["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ISSUE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")

# ═══════════════════════════════════════════════════════════
# 示例数据
# ═══════════════════════════════════════════════════════════

def generate_samples():
    return [
        # 高分 (5)
        {"id": "G001", "agent": "客服A", "text": "消费者：我买的手机收到之后屏幕有一道划痕，我要退货。\n客服：非常抱歉给您带来不好的体验！您是说收到的手机屏幕上有一道划痕对吗？我完全理解您的心情。您放心，我马上帮您核实一下。\n消费者：对，我刚拆开就看到了，太失望了。\n客服：确实是我们工作不到位。我帮您申请换货处理，新的手机会在2个工作日内发出。同时帮您申请一张50元优惠券作为补偿，您看这样可以吗？\n消费者：那行吧，快点换就行。\n客服：好的，已为您提交换货申请，订单号HC20260517001。稍后您会收到短信确认。预计后天发货，物流单号会同步推送。后续有任何问题可以随时联系我们，我会全程跟进。"},
        {"id": "G002", "agent": "客服B", "text": "消费者：物流显示已签收但我没收到包裹。\n客服：非常抱歉！您的意思是物流显示签收但实际没有收到对吧？我帮您查一下。\n消费者：对啊，都两天了。\n客服：理解您的着急。我现在就帮您核实物流情况。已联系物流商，同时先帮您申请补发，新包裹预计明天发出。如果原包裹找到的话您直接拒收就行。您觉得这样可以吗？\n消费者：那行尽快吧。\n客服：好的，补发已生成。明天上午我会跟进物流进度并主动联系您。感谢您的耐心！"},
        {"id": "G003", "agent": "客服A", "text": "消费者：买了两件只收到一件。\n客服：抱歉添麻烦了！您是说买了两件只收到一件对吗？帮您确认一下订单。\n消费者：对，白色的没发。\n客服：明白了，白色那件确实漏发了。非常抱歉是我们仓库的问题。马上帮您补发，预计明天发出。同时帮您申请20元优惠券补偿，您看可以吗？\n消费者：可以，赶紧发。\n客服：好的已提交。明天下午物流更新，请注意查收。我是客服A工号1001，有问题随时找我。"},
        {"id": "G004", "agent": "客服C", "text": "消费者：订单我要取消退款。\n客服：帮您查看一下。您的订单已经发货在路上了。您是确定要取消还是先了解预计到达时间？\n消费者：太慢了不想要了。\n客服：理解您的心情。包裹预计后天送达。如果现在取消退回去还需要3-5天才能退款。您看要不要再等两天？我帮您申请10元延迟补贴。\n消费者：那行吧再等等。\n客服：好的已申请补贴。包裹预计后天到，明天物流更新。如果后天还没收到再联系我优先处理。"},
        {"id": "G005", "agent": "客服B", "text": "消费者：奶粉罐子瘪了不敢给孩子喝。\n客服：非常抱歉！给宝宝的食品容不得任何问题。您请放心，我立即帮您处理。\n消费者：这种谁敢给孩子喝啊。\n客服：确实应该谨慎。我马上帮您申请退货退款并重新下单，新的一罐明天即可发出。瘪罐那罐您不需要退回。同时申请30元优惠券。您看可以吗？\n消费者：好，尽快。\n客服：退款预计1-3个工作日到账。新奶粉明天发出，物流实时更新。明天我会跟进确保万无一失。"},
        # Badcase (5)
        {"id": "B001", "agent": "客服X", "text": "消费者：鞋子穿了两次就开胶了。\n客服：这是你自己穿的问题吧，我们卖了这么多都没人反映。\n消费者：明明就是质量问题。\n客服：我们鞋子质量都没问题，是你自己穿法不对。退不了。\n消费者：我要投诉！\n客服：随便你。"},
        {"id": "B002", "agent": "客服Y", "text": "消费者：快递显示异常能不能帮我查一下？\n客服：你去问快递公司啊，问我干嘛。\n消费者：我在你们平台买的当然找你们。\n客服：我们只管卖，物流不归我们管。你自己打电话问。\n消费者：那丢件了怎么办？\n客服：等着吧，快递公司确认了再说。"},
        {"id": "B003", "agent": "客服X", "text": "消费者：收到的衣服颜色不对，我要换。\n客服：图片和实物有色差是正常的。\n消费者：这色差也太大了吧。\n客服：那是你显示器的问题。\n消费者：你这什么态度？\n客服：我就这态度。不满意去找平台。"},
        {"id": "B004", "agent": "客服Z", "text": "消费者：手机用了两天黑屏了，我要换一个。\n客服：有没有摔过？\n消费者：没有，正常用的。\n客服：那不会啊，我们从来不出这种问题。你是不是进水了？\n消费者：没有。\n客服：人为损坏我们不管。想换自己掏钱。"},
        {"id": "B005", "agent": "客服Y", "text": "消费者：退款怎么还没到？已经一周了。\n客服：系统在处理。\n消费者：什么时候能到？\n客服：不知道。\n消费者：那你能帮我查一下吗？\n客服：系统显示的你也看到了，等着就行。\n消费者：能不能给个时间？\n客服：看情况吧，说不准。"},
        # 中等 (10)
        {"id": "M001", "agent": "客服D", "text": "消费者：订单三天了还没发货。\n客服：我帮您查一下。这个订单仓库在备货，预计明天发出。\n消费者：太慢了，能不能快点。\n客服：好的帮您备注加急。\n消费者：好吧。"},
        {"id": "M002", "agent": "客服E", "text": "消费者：零食有一包破了。\n客服：抱歉。您拍个照片给我看一下。\n消费者：拍了你看。\n客服：好的帮您申请退款这个单品。大概3-5个工作日到账。\n消费者：好吧。"},
        {"id": "M003", "agent": "客服D", "text": "消费者：怎么退货？\n客服：订单详情里点申请退货就行。\n消费者：然后呢？\n客服：选择退货原因提交，快递上门取件。\n消费者：运费谁出？\n客服：质量问题我们出，非质量问题您出。\n消费者：好吧。"},
        {"id": "M004", "agent": "客服F", "text": "消费者：这个商品能优惠吗？\n客服：不好意思这款不参加活动。\n消费者：有没有类似的便宜点的？\n客服：您可以看下这个链接，类似款式。\n消费者：好的谢谢。\n客服：不客气。"},
        {"id": "M005", "agent": "客服E", "text": "消费者：物流能不能改地址？\n客服：已经发货了还是没发货？\n消费者：已经发了。\n客服：那需要联系快递公司改，我给您电话。\n消费者：你不能直接帮我改吗？\n客服：已发出的我们系统改不了，需要联系快递。\n消费者：好吧发给我。"},
        {"id": "M006", "agent": "客服F", "text": "消费者：发票怎么申请？\n客服：订单详情页有电子发票入口，填信息就行。\n消费者：多久能开好？\n客服：一般1-2个工作日。\n消费者：好的。"},
        {"id": "M007", "agent": "客服D", "text": "消费者：收到了但包装盒坏了。\n客服：东西有没有损坏？\n消费者：东西倒是好的。\n客服：那不影响使用就行，包装下次注意。\n消费者：嗯。"},
        {"id": "M008", "agent": "客服E", "text": "消费者：这个有没有保修。\n客服：有的，支持全国联保一年。\n消费者：怎么保修？\n客服：拿着购买凭证去任意售后网点就行。\n消费者：好的。"},
        {"id": "M009", "agent": "客服F", "text": "消费者：优惠券过期了能补发吗？\n客服：过期了系统补不了，不好意思。\n消费者：下次什么时候有活动？\n客服：您可以关注店铺首页，不定期有活动。\n消费者：好吧。"},
        {"id": "M010", "agent": "客服D", "text": "消费者：这个码数偏大还是偏小？\n客服：正常码，按平时尺码选。\n消费者：我平时穿L但评论说偏小。\n客服：那您选XL比较保险。\n消费者：好的谢谢。"},
    ]

# ═══════════════════════════════════════════════════════════
# UI
# ═══════════════════════════════════════════════════════════

def init_session():
    for k, v in {
        "cs_convos": None, "cs_results": None, "selected_model": "rule-only",
        "key_deepseek": "", "key_gemini": "", "key_groq": "",
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v


def show_model_selector():
    st.subheader("🤖 评估引擎选择")
    ollama_ok = check_ollama_available() and check_ollama_model()

    opts, status = {}, {}
    opts["rule-only"] = "🔧 关键词规则引擎（默认·即时可用）"
    status["rule-only"] = "✅ 已就绪"

    for k, c in MODELS.items():
        if k == "rule-only":
            continue
        elif k == "ollama-qwen":
            opts[k] = f"{c['icon']} {c['name']}" + (" (Ollama 未启动)" if not ollama_ok else "")
            status[k] = "✅ 已就绪" if ollama_ok else "❌ 未启动"
        else:
            has = bool(st.session_state.get(f"key_{k}"))
            opts[k] = f"{c['icon']} {c['name']} ({'已配' if has else '需'} Key)"
            status[k] = "✅ 已配置" if has else "🔑 需 Key"

    cur = st.session_state.get("selected_model", "rule-only")
    if cur not in opts:
        cur = "rule-only"
    sel = st.selectbox("选择评估引擎", list(opts.keys()), format_func=lambda k: opts[k],
                       index=list(opts.keys()).index(cur))
    st.session_state["selected_model"] = sel
    cfg = MODELS[sel]

    with st.container(border=True):
        st.caption(f"**{cfg['icon']} {cfg['name']}** | {cfg['provider']} | {cfg['speed']} | {cfg['cost']}")
        st.caption(cfg["description"])
        st.caption(f"状态: {status.get(sel, '')}")

    if cfg["key_required"]:
        kv = st.text_input(f"{cfg['provider']} API Key", type="password",
                           value=st.session_state.get(f"key_{sel}", ""),
                           placeholder=f"输入 {cfg['provider']} API Key...", key=f"api_key_{sel}")
        if kv:
            st.session_state[f"key_{sel}"] = kv

    if sel == "ollama-qwen" and not ollama_ok:
        st.warning("⚠️ 安装 Ollama: https://ollama.com/download/windows")
    return sel


def show_rules_config():
    with st.expander("📋 规则配置", expanded=False):
        st.caption("编辑评估关键词和噪声词")
        st.markdown("**正向关键词**")
        for dim in KW_POSITIVE:
            k = f"pos_{dim}"
            if k not in st.session_state:
                st.session_state[k] = "、".join(KW_POSITIVE[dim])
            with st.expander(dim, expanded=False):
                v = st.text_area(dim, value=st.session_state[k], key=f"in_{k}", height=50, label_visibility="collapsed")
                st.session_state[k] = v
                KW_POSITIVE[dim] = [x.strip() for x in v.replace(",", "、").split("、") if x.strip()]

        st.markdown("**负向关键词**")
        for dim in KW_NEGATIVE:
            k = f"neg_{dim}"
            if k not in st.session_state:
                st.session_state[k] = "、".join(KW_NEGATIVE[dim])
            with st.expander(dim, expanded=False):
                v = st.text_area(dim, value=st.session_state[k], key=f"in_{k}", height=40, label_visibility="collapsed")
                st.session_state[k] = v
                KW_NEGATIVE[dim] = [x.strip() for x in v.replace(",", "、").split("、") if x.strip()]

        st.markdown("**噪声词**（过滤不参与评分）")
        nk = "noise_words"
        if nk not in st.session_state:
            st.session_state[nk] = "、".join(sorted(NOISE_WORDS))
        nv = st.text_area("噪声词", value=st.session_state[nk], key="in_noise", height=68, label_visibility="collapsed")
        st.session_state[nk] = nv
        NOISE_WORDS.clear()
        NOISE_WORDS.update(x.strip() for x in nv.replace(",", "、").split("、") if x.strip())
        if st.button("🔄 恢复默认", width='stretch'):
            for key in list(st.session_state.keys()):
                if key.startswith(("pos_", "neg_", "noise")):
                    st.session_state.pop(key, None)
            st.rerun()


def show_issue_entry():
    with st.expander("🐛 问题反馈", expanded=False):
        t = st.text_input("标题", key="cs_issue_t", placeholder="一句话描述")
        d = st.text_area("描述", key="cs_issue_d", height=80)
        c1, c2 = st.columns(2)
        with c1:
            it = st.selectbox("类型", ["评分不准", "Bug", "建议", "数据问题", "界面", "其他"], key="cs_issue_ty")
        with c2:
            iu = st.selectbox("紧急度", ["一般", "重要", "紧急"], key="cs_issue_ur")
        if st.button("提交", key="cs_issue_sub", type="primary", width='stretch'):
            if not t.strip():
                st.error("请填写标题")
            else:
                save_issue({"title": t, "description": d, "type": it, "urgency": iu})
                st.success("已提交！")
                st.rerun()


def show_sidebar():
    with st.sidebar:
        st.header("⚙️ 控制面板")
        sel = show_model_selector()
        st.divider()
        st.subheader("📥 快速体验")
        if st.button("🎲 加载20段示例对话", type="primary", width='stretch'):
            st.session_state["cs_convos"] = generate_samples()
            st.rerun()
        if st.session_state.get("cs_convos") is not None:
            if st.button("🗑️ 清除数据", width='stretch'):
                st.session_state["cs_convos"] = None
                st.session_state["cs_results"] = None
                st.rerun()
        st.divider()
        show_rules_config()
        show_issue_entry()
        with st.expander("📜 版本演进", expanded=False):
            for e in VERSION_HISTORY:
                st.markdown(f"{e['icon']} **{e['version']}** — {e['title']}{' `当前`' if e == VERSION_HISTORY[0] else ''}")
                st.caption(f"{e['date']} | {e['advantage'][:40]}...")
                if e != VERSION_HISTORY[-1]:
                    st.markdown("│")
        return sel


def show_single(conv_text, model_key, client):
    st.subheader("📝 单条对话评估")
    is_rule = (MODELS[model_key]["sdk_type"] == "rule")

    # 规则引擎
    rule_res = rule_evaluate(conv_text)
    rule_total = calc_total(rule_res)

    # AI 引擎
    llm_res = None
    if not is_rule and client:
        with st.spinner(f"🤖 {MODELS[model_key]['name']} 评估中..."):
            llm_res = llm_evaluate(conv_text, model_key, client)

    # 展示
    if is_rule:
        st.success("🔧 关键词规则引擎评估完成")

    col1, col2 = st.columns([1, 2])
    with col1:
        total = calc_total(llm_res) if llm_res and all(d in llm_res for d in EVALUATION_DIMENSIONS) else rule_total
        color = "#66BB6A" if total >= 4 else "#FFA726" if total >= 3 else "#FF4444"
        st.markdown(f"### 加权总分")
        st.markdown(f"<h1 style='text-align:center;color:{color}'>{total}/5.0</h1>", unsafe_allow_html=True)

        # 雷达图
        cats = list(EVALUATION_DIMENSIONS.keys())
        vals_rule = [rule_res[d]["score"] for d in cats]
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=vals_rule, theta=cats, fill="toself", name="规则引擎",
                                      line=dict(color="#2196F3", width=2)))
        if llm_res and all(d in llm_res for d in EVALUATION_DIMENSIONS):
            vals_llm = [llm_res[d]["score"] for d in cats]
            fig.add_trace(go.Scatterpolar(r=vals_llm, theta=cats, fill="toself", name="AI引擎",
                                          line=dict(color="#FF5722", width=2)))
        fig.add_trace(go.Scatterpolar(r=[4, 4, 4, 4], theta=cats, fill="none", name="优秀线",
                                      line=dict(color="#90A4AE", width=1, dash="dash")))
        fig.update_layout(polar=dict(radialaxis=dict(range=[0, 5])), height=350, margin=dict(l=40, r=40, t=20, b=20))
        st.plotly_chart(fig, width='stretch')

    with col2:
        # 规则结果
        st.markdown("#### 🔧 规则引擎评分")
        for d in EVALUATION_DIMENSIONS:
            s = rule_res[d]
            color = "#66BB6A" if s["score"] >= 4 else "#FFA726" if s["score"] >= 3 else "#FF4444"
            st.markdown(f"**{d}**: :{color}[{s['score']}/5] — {s['reason']}")

        # AI 结果
        if llm_res:
            st.divider()
            st.markdown(f"#### 🤖 {MODELS[model_key]['name']} 深度评估")
            if all(d in llm_res for d in EVALUATION_DIMENSIONS):
                for d in EVALUATION_DIMENSIONS:
                    s = llm_res[d]["score"]
                    color = "#66BB6A" if s >= 4 else "#FFA726" if s >= 3 else "#FF4444"
                    st.markdown(f"**{d}**: :{color}[{s}/5] — {llm_res[d].get('reason', '')}")
            if llm_res.get("overall_assessment"):
                st.info(f"**整体评价**: {llm_res['overall_assessment']}")
            if llm_res.get("tone_analysis"):
                st.caption(f"**语调分析**: {llm_res['tone_analysis']}")
            if llm_res.get("risk_flags"):
                for rf in llm_res["risk_flags"]:
                    st.error(f"⚠️ {rf}")
            if llm_res.get("highlights"):
                for hl in llm_res["highlights"]:
                    st.success(f"✨ {hl}")
            if llm_res.get("improvement_rewrite"):
                with st.expander("✏️ AI 改进话术示例"):
                    st.info(llm_res["improvement_rewrite"])

        # 对话高亮标注
        st.divider()
        st.subheader("📝 对话高亮标注视图")
        st.caption("绿色=正向关键词命中 | 红色=负向关键词命中 | 黄色=噪声词过滤")
        lines = conv_text.split("\n")
        for line in lines:
            if not line.strip():
                continue
            clean = _filter_noise(line.lower())
            pos_hits = []
            neg_hits = []
            for dim in KW_POSITIVE:
                for kw in KW_POSITIVE[dim]:
                    if kw in clean and kw not in pos_hits:
                        pos_hits.append(kw)
            for dim in KW_NEGATIVE:
                for kw in KW_NEGATIVE[dim]:
                    if kw in clean and kw not in neg_hits:
                        neg_hits.append(kw)
            noised = any(w in line for w in NOISE_WORDS if len(w) >= 2)

            if pos_hits:
                st.markdown(f"🟢 {line}  `+{' +'.join(pos_hits[:3])}`")
            elif neg_hits:
                st.markdown(f"🔴 {line}  `-{' -'.join(neg_hits[:3])}`")
            elif noised:
                st.caption(f"🟡 {line}")
            else:
                st.markdown(line)


def show_batch(conversations, model_key, client):
    st.subheader("📊 批量对话评估")
    is_rule = (MODELS[model_key]["sdk_type"] == "rule")

    if st.button("🔍 开始批量评估", type="primary") or st.session_state.get("cs_results") is not None:
        if st.session_state.get("cs_results") is None:
            results = []
            pb = st.progress(0)
            for i, conv in enumerate(conversations):
                rule_res = rule_evaluate(conv["text"])
                total = calc_total(rule_res)
                row = {"id": conv["id"], "agent": conv["agent"], "总分": total}
                for d in EVALUATION_DIMENSIONS:
                    row[d] = rule_res[d]["score"]

                # AI 评估
                if not is_rule and client:
                    llm_res = llm_evaluate(conv["text"], model_key, client)
                    if llm_res and all(d in llm_res for d in EVALUATION_DIMENSIONS):
                        row["AI总分"] = calc_total(llm_res)
                        for d in EVALUATION_DIMENSIONS:
                            row[f"AI_{d}"] = llm_res[d]["score"]
                        row["AI评价"] = llm_res.get("overall_assessment", "")
                        row["风险标注"] = "；".join(llm_res.get("risk_flags", []))

                row["Badcase"] = "是" if total < 3.0 else "否"
                row["text"] = conv["text"]
                results.append(row)
                pb.progress((i + 1) / len(conversations))
            pb.empty()
            st.session_state["cs_results"] = results
        else:
            results = st.session_state["cs_results"]

        dr = pd.DataFrame(results)
        bc = len(dr[dr["Badcase"] == "是"])

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("总数", len(results))
        with c2:
            st.metric("平均总分", f"{dr['总分'].mean():.1f}/5.0")
        with c3:
            st.metric("Badcase", bc, delta="需关注" if bc > 0 else "正常")
        with c4:
            best = dr.groupby("agent")["总分"].mean().idxmax() if "agent" in dr.columns else "-"
            st.metric("最佳客服", best)

        st.divider()
        t1, t2, t3, t4 = st.tabs(["📋 评估结果", "📊 维度分析", "👥 客服对比", "⚠️ Badcase清单"])

        with t1:
            dc = [c for c in ["id", "agent", "总分", "识别需求", "有效共情", "达成一致", "承诺回复", "Badcase"] if c in dr.columns]
            st.dataframe(dr[dc], width='stretch', height=350)

        with t2:
            st.subheader("各维度平均分")
            davg = {d: round(dr[d].mean(), 1) for d in EVALUATION_DIMENSIONS if d in dr.columns}
            fig = px.bar(x=list(davg.keys()), y=list(davg.values()), title="维度平均分",
                         color=list(davg.values()), color_continuous_scale="RdYlGn", range_color=[1, 5])
            fig.update_layout(yaxis_range=[0, 5])
            st.plotly_chart(fig, width='stretch')

            if "agent" in dr.columns:
                ascores = dr.groupby("agent")["总分"].mean().sort_values(ascending=False)
                fig2 = px.bar(x=ascores.index, y=ascores.values, title="客服平均总分配对",
                              color=ascores.values, color_continuous_scale="RdYlGn", range_color=[1, 5])
                fig2.update_layout(yaxis_range=[0, 5])
                st.plotly_chart(fig2, width='stretch')

        with t3:
            st.subheader("客服能力雷达对比")
            if "agent" in dr.columns and len(dr["agent"].unique()) >= 2:
                agents = st.multiselect("选择对比客服", dr["agent"].unique().tolist(),
                                        default=list(dr["agent"].unique())[:min(4, len(dr["agent"].unique()))])
                if agents:
                    fig_r = go.Figure()
                    for ag in agents:
                        adf = dr[dr["agent"] == ag]
                        vals = [round(adf[d].mean(), 1) for d in EVALUATION_DIMENSIONS if d in adf.columns]
                        fig_r.add_trace(go.Scatterpolar(r=vals, theta=list(EVALUATION_DIMENSIONS.keys()),
                                                         fill="toself", name=ag))
                    fig_r.add_trace(go.Scatterpolar(r=[4, 4, 4, 4], theta=list(EVALUATION_DIMENSIONS.keys()),
                                                     fill="none", name="优秀线",
                                                     line=dict(color="#90A4AE", width=1, dash="dash")))
                    fig_r.update_layout(polar=dict(radialaxis=dict(range=[0, 5])), height=400)
                    st.plotly_chart(fig_r, width='stretch')
                    # 对比表
                    st.markdown("**各客服优劣势对比**")
                    comp_data = []
                    for ag in agents:
                        adf = dr[dr["agent"] == ag]
                        row_d = {"客服": ag, "平均总分": round(adf["总分"].mean(), 1)}
                        for d in EVALUATION_DIMENSIONS:
                            row_d[d] = round(adf[d].mean(), 1) if d in adf.columns else "-"
                        # 找最强和最弱维度
                        dim_means = {d: round(adf[d].mean(), 1) for d in EVALUATION_DIMENSIONS if d in adf.columns}
                        row_d["优势"] = max(dim_means, key=dim_means.get) if dim_means else "-"
                        row_d["短板"] = min(dim_means, key=dim_means.get) if dim_means else "-"
                        comp_data.append(row_d)
                    st.dataframe(pd.DataFrame(comp_data), width='stretch')
            else:
                st.info("需要多个客服数据才能对比")

        with t4:
            st.subheader("Badcase 清单与 AI Coaching")
            bdf = dr[dr["Badcase"] == "是"].sort_values("总分")
            if bdf.empty:
                st.success("✅ 无 Badcase")
            else:
                st.warning(f"共 {len(bdf)} 条 Badcase")
                for _, row in bdf.iterrows():
                    with st.expander(f"🔴 [{row['总分']}/5.0] {row.get('id', '')} — {row.get('agent', '')}"):
                        st.text(row.get("text", ""))
                        low = [f"{d}({row[d]}分)" for d in EVALUATION_DIMENSIONS if d in row and row[d] <= 2]
                        if low:
                            st.error(f"低分维度: {'、'.join(low)}")
                        # AI coaching 建议
                        st.markdown("**Coaching 要点**")
                        coaching_tips = []
                        for d in EVALUATION_DIMENSIONS:
                            if d in row and row[d] <= 2:
                                if d == "识别需求":
                                    coaching_tips.append("- 复述消费者问题后再回应，确保理解准确")
                                elif d == "有效共情":
                                    coaching_tips.append("- 先表达理解和歉意，再进入问题解决")
                                elif d == "达成一致":
                                    coaching_tips.append("- 提供至少一个具体方案并确认消费者是否接受")
                                elif d == "承诺回复":
                                    coaching_tips.append("- 明确告知下一步动作和时间节点，不要说模糊词")
                        for tip in coaching_tips:
                            st.info(tip)
                        if "AI评价" in row and pd.notna(row.get("AI评价")):
                            st.caption(f"AI: {row['AI评价']}")

        st.divider()
        ec = [c for c in dc + ["text"] if c in dr.columns]
        st.download_button("⬇️ 导出CSV", data=dr[ec].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                           file_name=f"质检评估_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv")


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def main():
    init_session()

    c1, c2 = st.columns([3, 1])
    with c1:
        st.title("🎧 客服对话质量评估")
        st.caption("默认规则引擎无需 API Key | 识别需求 · 有效共情 · 达成一致 · 承诺回复")
        # 业务定位
        st.info(
            '**业务定位：** AI 质检的难点不是让模型打分，而是让评分标准被业务认可。'
            "本 Demo 用四阶段服务质量标准，把主观服务体验拆成可解释、可复核的评估维度。"
        )
        st.info(
            "**生产链路位置**：本模块不是单独打分工具，而是把服务过程中的低分维度（`quality_feedback`）、"
            "争议样本和 badcase 回流到知识库、SOP、Prompt 和对客追问策略。质检结果按 `case_id` 绑定，"
            "输出 `root_cause` 和 `suggested_action`，统一进入 `feedback_events`。"
        )

        # 质检标准校准区
        with st.expander("📏 质检标准校准区", expanded=False):
            st.markdown("### 四维评分标准详解")
            st.caption("每个维度的 5 分 / 3 分 / 1 分含义，帮助业务对齐评分口径。")
            for dim_key, dim_cfg in EVALUATION_DIMENSIONS.items():
                st.markdown(f"**{dim_key}** — {dim_cfg['description']}")
                rubric = dim_cfg["rubric"]
                c5, c3, c1_col = st.columns(3)
                with c5:
                    st.success(f"**5 分（优秀）**\n{rubric[5]}")
                with c3:
                    st.warning(f"**3 分（及格）**\n{rubric[3]}")
                with c1_col:
                    st.error(f"**1 分（差）**\n{rubric[1]}")
            st.info(
                "💡 评分争议处理：规则引擎和 AI 引擎评分差异超过 1.5 分时，当前对话应标记为"
                '"需人工复核"，由质检专家最终判断。质检系统不是替代质检员，而是扩展覆盖率和统一初筛口径。'
            )

        # 争议样本处理说明
        with st.expander("⚠️ 争议样本处理", expanded=False):
            st.markdown("""
            **规则 vs AI 评分差异处理流程**

            当规则引擎和 AI 引擎对同一对话的评分出现较大分歧时：

            1. **差异阈值**：总分差异 > 1.5 分或任意维度差异 > 2 分 → 标记为"争议样本"
            2. **争议标记**：自动标识为"需人工复核"，进入人工质检队列
            3. **人工复核**：质检专家结合对话原文、评分依据和业务标准给出最终分
            4. **口径回溯**：定期分析争议样本，判断是规则漏报、AI 误判还是标准需要优化
            5. **标准迭代**：根据争议样本更新关键词库、评分规则和 Prompt 指令

            **核心原则**
            - AI 质检不是替代质检员，而是扩展覆盖率和统一初筛口径
            - 争议样本是系统改进的燃料，不是系统失败的证据
            - 人工质检团队保留最终判定权，AI 只提供建议和依据
            """)

    with c2:
        st.metric("版本", "v3.2", delta="对话洞察增强")
        st.metric("本地AI", "就绪" if (check_ollama_available() and check_ollama_model()) else "待启动")

    st.divider()
    sel = show_sidebar()
    cfg = MODELS[sel]

    mode_options = {"single": "📝 单条评估", "batch": "📊 批量评估"}
    if st.session_state.get("eval_mode") not in mode_options:
        st.session_state["eval_mode"] = "single"
    mode = st.radio(
        "评估模式",
        list(mode_options.keys()),
        format_func=lambda key: mode_options[key],
        horizontal=True,
        key="eval_mode",
    )

    if mode == "single":
        st.info("面试演示建议：先加载一段示例对话，展示四维评分和可解释改进建议；批量模式可展示客服表现对比。")
        if st.button("🎲 填入高分示例对话", width='stretch'):
            st.session_state["single_conv"] = generate_samples()[0]["text"]
            st.rerun()
        conv_text = st.text_area("粘贴客服对话文本", height=220, placeholder="消费者：......\n客服：......", key="single_conv")
        if st.button("🔍 开始评估", type="primary", disabled=not conv_text):
            client = None if cfg["sdk_type"] == "rule" else get_client(sel)
            show_single(conv_text, sel, client)
    else:
        # 数据源
        if st.session_state.get("cs_convos") is None:
            st.info("👈 请从左侧边栏点击「加载20段示例对话」")
            return
        convos = st.session_state["cs_convos"]

        client = None if cfg["sdk_type"] == "rule" else get_client(sel)
        if not cfg["key_required"] and cfg["sdk_type"] != "rule" and not client:
            st.warning("⚠️ Ollama 未就绪，使用规则引擎评估")
            client = None
        show_batch(convos, sel, client)


if __name__ == "__main__":
    main()
