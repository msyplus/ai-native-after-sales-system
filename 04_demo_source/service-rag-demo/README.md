# 客服 SOP 知识库问答

轻量级 RAG 原型 Demo，面向客服 SOP、服务规则、质检标准和风险预警规则的知识库问答场景。默认使用本地 TF-IDF 检索和模板化回答，不依赖外部 API Key，适合面试现场稳定演示。

## 生产链路位置

本模块是 AI native 售后服务系统中对客沟通机器人和人工接管的**统一知识服务**。它接收查询后输出带引用依据的 `knowledge_refs`、`evidence_status` 和 `human_confirm_required`，供对客机器人决定是否标准回答或转人工。

```
对客机器人/人工接管 → RAG 知识检索 → knowledge_refs + evidence_status + human_confirm_required
```

- RAG 给依据，不替代人工做赔付承诺。
- 证据不足时输出 `evidence_status: "insufficient"`，对客机器人触发 `human_handoff`。
- 输出结构与 `ai_native_shared/knowledge_base.py` 保持一致。

## 本地演示

```powershell
streamlit run app.py --server.port 8505
```

## 业务背景

在服务运营和智能客服场景中，很多问题并不是没有答案，而是答案分散在 SOP、质检标准、风险规则和历史案例中。一线人员需要快速定位规则依据，并输出可执行处理建议。这个 Demo 用 RAG 思路模拟“文档切分 → 检索召回 → 引用依据 → 结构化回答”的最小闭环。

## 核心功能

- 内置模拟 SOP：退改签、风险预警、质检标准、摘要规范。
- 上传补充知识：支持上传 `.txt` / `.md` 文档并自动切分。
- 本地检索：使用 TF-IDF 字符 n-gram 做稳定检索兜底。
- 引用依据：展示来源、标题、相似度和原始片段。
- 结构化回答：按服务处理逻辑输出建议和下一步动作。
- 导出记录：支持下载问答结果 JSON。

## 为什么这是 RAG 原型

当前版本没有直接接入外部大模型，而是保留了 RAG 的核心产品链路：

```text
知识文档 → 文档切分 → 检索召回 → 引用依据 → 组织回答
```

后续可以将 TF-IDF 检索替换为 Embedding + 向量数据库，将模板回答替换为 LLM 生成。

## 技术栈

- Python
- Streamlit
- pandas
- scikit-learn

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 面试展示重点

这个项目用于补充 AI 产品运营面试中的 RAG/知识库证据：

- 能讲清 RAG 的基本链路，而不是只停留在概念层。
- 知道企业知识库落地时需要保留引用依据，方便复核。
- 用规则/检索引擎兜底，保证没有 API Key 时仍可演示。
- 后续可自然升级为 Embedding、向量数据库和 LLM-as-Answer。

> 这是轻量 RAG 原型，不包装成企业级 RAG 系统。它展示的是知识依据、引用追溯和人工确认边界。
