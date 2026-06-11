# AI native 售后服务系统控制台/门户

这是一个基于真实服务运营经验构建的 AI native 售后服务系统控制台/门户，聚合对客沟通机器人、VOC 智能分类、批量异常预警、客服对话质检、客服 SOP 知识库问答和服务事件智能摘要等模块。

系统的核心不是展示单点工具，而是展示一条 AI native 售后服务工作流：

```text
对客输入 → 统一 case → 知识引用 → 风险判断 → 摘要/质检 → 反馈优化
```

## 在线演示

系统总入口：

https://ai-native-system-msydemo.streamlit.app

对客沟通机器人：

https://customer-agent-demo.streamlit.app

## 模块清单

| 模块 | 业务价值 | Demo |
|---|---|---|
| 对客沟通机器人 | 承接客户自然语言输入，生成统一 case，识别风险并转人工 | https://customer-agent-demo.streamlit.app |
| VOC 智能分类与优先级评估 | 将客诉文本转化为类别、情绪、优先级和处理建议 | https://complaint-classifier-demo.streamlit.app |
| 批量异常识别与服务风险预警 | 识别 VOC 聚集、敏感风险和时间异常 | https://voc-risk-detector-demo.streamlit.app |
| 客服对话质量评估 | 从四个维度评估客服对话质量 | https://cs-quality-evaluator-demo.streamlit.app |
| 客服 SOP 知识库问答 | 检索 SOP、质检标准和风险规则，并输出带引用依据的处理建议 | https://service-rag-msydemo.streamlit.app |
| 服务事件智能摘要 | 将对话、日志和备注压缩为结构化摘要 | https://summary-system-demo.streamlit.app |

## 项目定位

这组 Demo 对应过往经历中的真实服务 AI 能力：

- 对客沟通机器人：把客户原始表达转成 case、槽位、风险标签、知识依据和下一步动作。
- AI 智能客服落地：将服务 SOP、评估标准和 Prompt 约束转为系统能力。
- 智慧预警平台：把潜在舆情和批量问题前置识别。
- AI 质检：把服务质量从主观判断拆成可评估维度。
- RAG 知识库：把 SOP、规则和标准转化为可检索、可引用的问答能力。
- 自动总结：降低工单录入、复盘分析和交接协同成本。

## 设计原则

- 默认可演示：规则/统计引擎无需 API Key。
- AI 可增强：接入 DeepSeek、Gemini、Groq 或本地 Ollama 后可切换 LLM 模式。
- 数据可脱敏：样例数据均为模拟数据，不包含真实用户隐私。
- 结果可解释：每个系统都尽量输出规则依据、风险证据或评分理由。

## 技术栈

- Python
- Streamlit
- pandas
- Plotly
- scikit-learn
- Multi-LLM API

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 面试展示话术

这组 Demo 不是随机练手项目，而是我把过去做过的服务 AI 系统重新组织成一个 AI native 售后服务闭环：从对客输入开始，生成统一 case，再进入知识引用、风险判断、分类分流、摘要质检和反馈优化。它对应我对 AI 服务系统的核心理解：AI 不应该只是把人工脚本自动化，而应该重组服务信息流、判断流、人机分工和质量反馈闭环。

