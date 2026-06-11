"""
客服 SOP 知识库问答 Demo

一个轻量级 RAG 原型：默认使用本地 TF-IDF 检索 + 模板生成答案，
不依赖外部 API Key，适合面试现场稳定演示。
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# 接入共享数据结构：RAG 作为对客机器人的统一知识服务（本地和云上通用）
import os as _os2
_SHARED_PATH = _os2.path.abspath(_os2.path.join(_os2.path.dirname(__file__), "..", ".."))
if _SHARED_PATH not in sys.path:
    sys.path.insert(0, _SHARED_PATH)

from ai_native_shared.case_schema import generate_case_id
from ai_native_shared.knowledge_base import retrieve_knowledge as shared_retrieve, has_sufficient_evidence as shared_has_evidence


st.set_page_config(
    page_title="客服 SOP 知识库问答",
    page_icon="KB",
    layout="wide",
    initial_sidebar_state="expanded",
)


@dataclass
class KnowledgeChunk:
    source: str
    title: str
    text: str


DEFAULT_KNOWLEDGE = [
    KnowledgeChunk(
        "退改签 SOP",
        "退票诉求处理原则",
        "当用户提出退票诉求时，客服需先确认订单状态、航班状态、票规类型和是否涉及航变。若为自愿退票，需按票规说明手续费；若为非自愿退票，需核实航变、取消、延误等证据，并优先引导用户提交相关材料。",
    ),
    KnowledgeChunk(
        "退改签 SOP",
        "改签诉求处理原则",
        "当用户提出改签诉求时，客服需确认原航班信息、目标航班、舱位价格差、航司改签规则和用户可接受时间。若目标航班无票或价格变动，应明确告知限制并提供替代方案。",
    ),
    KnowledgeChunk(
        "风险预警 SOP",
        "舆情风险识别",
        "出现民航局、12315、媒体曝光、微博投诉、集体维权、律师函等关键词时，应将事件标记为高风险。客服需避免情绪化表达，优先安抚用户，并同步主管介入评估是否升级处理。",
    ),
    KnowledgeChunk(
        "风险预警 SOP",
        "批量异常识别",
        "短时间内多个用户反馈相同航班、相同商家、相同物流节点或相同错误提示时，需判断是否为批量异常。处理动作包括聚合样本、定位共同特征、评估影响面、建立临时处理规则并同步一线话术。",
    ),
    KnowledgeChunk(
        "质检标准",
        "识别需求",
        "客服首先需要复述并确认用户核心诉求，避免直接给方案但没有确认问题。高质量表达应包含用户问题、订单或服务对象、用户希望达成的结果。",
    ),
    KnowledgeChunk(
        "质检标准",
        "有效共情",
        "有效共情不是简单说抱歉，而是结合用户处境表达理解。例如用户因航班取消影响行程，应回应其时间损失、情绪压力和后续安排不确定性。",
    ),
    KnowledgeChunk(
        "质检标准",
        "达成一致",
        "服务过程需要和用户就处理方案达成明确一致，包括退款、补偿、改签、等待回电或升级处理等。若用户未确认接受方案，应继续解释并记录分歧点。",
    ),
    KnowledgeChunk(
        "质检标准",
        "承诺回复",
        "需要后续跟进的服务场景，客服应给出明确的回复时间、处理节点和联系方式。只说稍后处理但没有时间承诺，属于闭环不完整。",
    ),
    KnowledgeChunk(
        "摘要规范",
        "服务事件摘要字段",
        "结构化摘要应包含事件类型、用户诉求、关键事实、已处理动作、当前状态、待跟进事项和风险等级。摘要应避免冗余聊天内容，保留可供复盘和交接的信息。",
    ),
    KnowledgeChunk(
        "摘要规范",
        "高风险摘要要求",
        "高风险事件摘要必须写明风险触发原因，例如监管投诉、媒体曝光、批量反馈、特殊身份或金额争议，并标注建议升级处理的对象和时限。",
    ),
]


SAMPLE_QUESTIONS = [
    "用户说要投诉到民航局，客服应该怎么处理？",
    "怎么判断一个客诉是不是批量异常？",
    "客服对话质检里，承诺回复应该怎么判断？",
    "服务事件摘要应该包含哪些字段？",
    "用户要退票，客服第一步应该确认什么？",
]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def split_uploaded_text(raw_text: str, source: str) -> list[KnowledgeChunk]:
    paragraphs = [normalize_text(p) for p in re.split(r"\n\s*\n|(?<=。)", raw_text) if normalize_text(p)]
    chunks: list[KnowledgeChunk] = []
    for index, paragraph in enumerate(paragraphs, start=1):
        if len(paragraph) < 12:
            continue
        chunks.append(KnowledgeChunk(source, f"上传片段 {index}", paragraph))
    return chunks


def build_dataframe(chunks: Iterable[KnowledgeChunk]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source": chunk.source,
                "title": chunk.title,
                "text": chunk.text,
                "display": f"{chunk.source}｜{chunk.title}：{chunk.text}",
            }
            for chunk in chunks
        ]
    )


def retrieve(query: str, df: pd.DataFrame, top_k: int = 3) -> pd.DataFrame:
    corpus = df["display"].tolist()
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 4))
    matrix = vectorizer.fit_transform(corpus + [query])
    scores = cosine_similarity(matrix[-1], matrix[:-1]).flatten()
    result = df.copy()
    result["score"] = scores
    return result.sort_values("score", ascending=False).head(top_k)


def generate_answer(query: str, hits: pd.DataFrame) -> str:
    if hits.empty or hits["score"].max() <= 0:
        return (
            "🔴 **证据不足，不强答**\n\n"
            "知识库中没有检索到足够相关的内容（最高相似度为 0）。\n\n"
            "**原因分析**：当前问题超出内置知识覆盖范围，或表达方式与知识源差异较大。\n\n"
            "**建议处理路径**：\n"
            "1. 补充知识源：上传相关 SOP 或规则文档到知识库\n"
            "2. 转人工确认：将问题升级给业务专家或主管判断\n"
            "3. 记录盲区：将此问题标记为知识盲区，推动知识库补充\n\n"
            "人工确认边界：当前问题缺少可引用依据，不建议直接生成处理结论。"
        )

    best_titles = "、".join(hits["title"].head(3).tolist())
    evidence = "\n".join(
        f"- {row.title}：{row.text}" for row in hits.itertuples(index=False)
    )

    # Check for potential rule conflicts
    max_score = hits["score"].max()
    min_score = hits["score"].min()
    conflict_warning = ""
    if len(hits) >= 2 and max_score - min_score < 0.1 and max_score > 0:
        conflict_warning = (
            "\n\n⚠️ **规则冲突提示**：多个召回片段相似度接近且处理方向可能不一致，"
            "建议人工确认适用规则后再做判断。"
        )

    evidence_quality = "较高" if max_score > 0.5 else "中等" if max_score > 0.2 else "较低"
    return (
        f"根据知识库中与“{query}”最相关的内容，建议优先参考：{best_titles}。\n\n"
        f"引用依据：\n{evidence}\n\n"
        f"判断逻辑：\n"
        f"1. 先确认用户问题的事件类型、影响范围和风险等级。\n"
        f"2. 如果涉及监管投诉、媒体曝光、批量异常或明确时限承诺，应按高风险/需升级场景处理。\n"
        f"3. 输出方案时需要说明依据、下一步动作和回复时限，保证服务闭环。\n\n"
        f"建议动作：\n"
        f"- 使用召回到的 SOP 或风险规则作为回复依据。\n"
        f"- 明确下一步处理动作、责任角色和回复时间。\n"
        f"- 如果存在规则冲突、证据不足或高风险升级，应转人工确认。\n\n"
        f"证据质量评估：召回相似度 **{max_score:.3f}**（{evidence_quality}）\n"
        f"人工确认边界：RAG 只提供依据检索和处理建议，不替代人工最终判断；涉及赔付、监管、舆情、隐私或高风险争议时，应保留人工复核。"
        f"{conflict_warning}"
    )


def render_header():
    st.title("客服 SOP 知识库问答")
    st.caption("轻量 RAG 原型 | 默认无需 API Key | 文档切分 → 检索 → 引用依据 → 结构化回答")
    st.info(
        "业务定位：本模块是对客沟通机器人和人工接管的统一知识服务。"
        " RAG 提供依据检索和处理建议，不替代人工做赔付承诺；证据不足时不强答，输出 human_handoff 信号。"
        " 本 Demo 是轻量 RAG 原型，不包装成企业级 RAG 系统。"
    )

    # 知识源治理说明
    with st.expander("📚 知识源治理说明", expanded=False):
        st.markdown("""
        | 维度 | 说明 |
        |------|------|
        | 知识源版本 | 当前内置 10 条知识片段（退改签 SOP / 风险预警 SOP / 质检标准 / 摘要规范） |
        | 更新时间 | 内置知识初始版本 2026-05 |
        | 适用范围 | 模拟服务运营场景中的标准处理流程，覆盖退改签、风险预警、质检评估和事件摘要 |
        | 过期风险 | 内置知识为静态演示版本，实际部署需对接业务系统定期同步和审核 |

        **治理要求：** 生产环境知识库需建立版本管理、变更审批、过期提醒和来源追溯机制。
        """)

    # 证据不足 + 规则冲突处理
    with st.expander("🔍 证据不足与规则冲突处理", expanded=False):
        st.markdown("""
        **证据不足不强答原则**

        当检索到的知识片段最高相似度低于阈值时（当前系统阈值：相似度 ≤ 0），系统不生成处理结论，而是输出：

        > "知识库中没有检索到足够相关的内容。当前问题缺少可引用依据，不建议直接生成处理结论。建议先补充 SOP、规则说明、历史案例或升级给业务专家确认。"

        **规则冲突处理**

        当召回的知识片段中存在相互矛盾的规则时（例如：同一场景不同 SOP 给出不同处理建议）：

        1. **冲突识别**：对比召回片段中的处理方向是否一致
        2. **提示人工确认**：不自动选择其中一条，而是将冲突内容一起展示给用户
        3. **升级路径**：标记为"需人工确认"，由业务专家或主管判断适用规则
        4. **冲突回溯**：定期梳理冲突规则，推动上游 SOP 统一

        **核心原则：** RAG 只提供依据检索和处理建议，不替代人工最终判断；涉及赔付、监管、舆情、隐私或高风险争议时，应保留人工复核。
        """)


def render_business_frame():
    with st.expander("产品思维：业务需求如何拆成 RAG 功能", expanded=True):
        st.markdown(
            """
            | 产品拆解层 | 设计说明 |
            |---|---|
            | 业务场景 | 一线员工和主管需要快速找到 SOP、风险规则、质检标准中的依据 |
            | 功能需求 | 不只回答问题，还要展示引用来源、判断逻辑、建议动作和人工确认边界 |
            | AI/工具调配 | TF-IDF 检索负责稳定召回依据；模板生成负责结构化回答；人工负责高风险或证据不足场景 |
            | 输出设计 | 回答正文、检索依据表、JSON 问答记录下载 |
            | 验证指标 | 看召回片段是否相关、回答是否引用依据、是否明确人工复核边界 |
            """
        )


def render_knowledge_service_output():
    """展示 RAG 作为系统知识服务的输出结构."""
    with st.expander("📦 作为系统知识服务的输出结构（供对客机器人/人工接管）", expanded=True):
        st.markdown("""
        **知识服务输出格式：**

        对客沟通机器人或人工接管模块调用 RAG 时，得到以下统一结构：

        ```json
        {
          "knowledge_refs": [
            {
              "source": "退改签SOP",
              "chunk_id": "KB-001",
              "text": "航班延误导致非自愿退票时，应先核实航司政策和订单状态。",
              "score": 0.85
            }
          ],
          "evidence_status": "sufficient",
          "human_confirm_required": true
        }
        ```

        **字段说明：**

        | 字段 | 说明 |
        |------|------|
        | `knowledge_refs` | 命中的知识片段列表，包含来源、片段ID、文本和相似度分数 |
        | `evidence_status` | 证据是否充足（"sufficient" / "insufficient"） |
        | `human_confirm_required` | 是否需要人工确认（高风险场景、证据不足或规则冲突时强制为 true） |

        **调用约定：**

        - RAG 给依据，不替代人工做赔付承诺。
        - `evidence_status = "insufficient"` 时，对客机器人应输出 `human_handoff`。
        - 规则冲突或证据不足时，`human_confirm_required` 强制为 `true`。
        - 对客机器人和人工接管包使用同一条 `knowledge_refs`，确保口径一致。
        """)

        # 实时演示：用共享知识库检索示例查询
        test_query = st.text_input("快速测试共享知识库检索", value="航班延误退票赔付投诉民航局")
        if st.button("检索共享知识库", key="shared_kb_test"):
            hits = shared_retrieve(test_query, top_k=3)
            evidence_ok = shared_has_evidence(hits)
            risk_terms = ("民航局", "12315", "消协", "监管", "投诉", "赔付", "赔偿", "退款", "退票", "舆情", "媒体")
            risk_text = test_query + " " + " ".join(
                f"{h.get('source', '')} {h.get('title', '')} {h.get('text', '')}" for h in hits
            )
            human_confirm_required = (not evidence_ok) or any(term in risk_text for term in risk_terms)
            st.markdown("**检索结果**")
            st.json({
                "knowledge_refs": hits,
                "evidence_status": "sufficient" if evidence_ok else "insufficient",
                "human_confirm_required": human_confirm_required,
            })


def render_sidebar() -> list[KnowledgeChunk]:
    st.sidebar.header("知识库")
    st.sidebar.caption("默认内置模拟 SOP，可上传补充知识文本。")

    chunks = list(DEFAULT_KNOWLEDGE)
    uploaded = st.sidebar.file_uploader("上传 SOP / 规则文本", type=["txt", "md"])
    if uploaded is not None:
        raw = uploaded.read().decode("utf-8", errors="ignore")
        extra_chunks = split_uploaded_text(raw, uploaded.name)
        chunks.extend(extra_chunks)
        st.sidebar.success(f"已添加 {len(extra_chunks)} 个上传片段")

    st.sidebar.metric("知识片段", len(chunks))
    st.sidebar.markdown("**内置来源**")
    for source in sorted({chunk.source for chunk in chunks}):
        st.sidebar.write(f"- {source}")
    return chunks


def main():
    render_header()
    render_business_frame()
    render_knowledge_service_output()
    chunks = render_sidebar()
    df = build_dataframe(chunks)

    left, right = st.columns([2, 1])
    with left:
        st.subheader("提问")
        sample = st.selectbox("选择示例问题", ["自定义输入"] + SAMPLE_QUESTIONS)
        default_query = "" if sample == "自定义输入" else sample
        query = st.text_area("输入你想查询的服务规则问题", value=default_query, height=100)
        top_k = st.slider("检索片段数", min_value=1, max_value=5, value=3)

        if st.button("检索并生成回答", type="primary", disabled=not query.strip()):
            hits = retrieve(query, df, top_k=top_k)
            answer = generate_answer(query, hits)
            st.session_state["last_hits"] = hits
            st.session_state["last_answer"] = answer
            st.session_state["last_query"] = query

    with right:
        st.subheader("RAG 流程")
        st.markdown(
            """
            1. 文档切分：把 SOP 拆成可检索片段  
            2. 检索召回：用 TF-IDF 找相关规则  
            3. 引用依据：展示来源、标题和相似度  
            4. 生成回答：按服务处理逻辑组织答案  
            """
        )
        st.caption("当前版本用 TF-IDF 做稳定兜底，后续可替换为 Embedding + 向量数据库 + LLM。")

    if "last_answer" in st.session_state:
        st.divider()
        st.subheader("回答")
        st.markdown(st.session_state["last_answer"])

        st.subheader("检索依据")
        hits = st.session_state["last_hits"].copy()
        hits["score"] = hits["score"].map(lambda value: f"{value:.3f}")
        st.dataframe(hits[["source", "title", "score", "text"]], width='stretch', height=280)

        export = {
            "question": st.session_state["last_query"],
            "answer": st.session_state["last_answer"],
            "references": hits[["source", "title", "score", "text"]].to_dict("records"),
        }
        st.download_button(
            "下载问答记录 JSON",
            data=pd.Series(export).to_json(force_ascii=False, indent=2),
            file_name="rag_qa_record.json",
            mime="application/json",
        )

    st.divider()
    st.subheader("知识库预览")
    st.dataframe(df[["source", "title", "text"]], width='stretch', height=260)


if __name__ == "__main__":
    main()
