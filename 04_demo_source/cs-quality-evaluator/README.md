# 客服对话质量评估

面向智能质检场景的客服对话评估 Demo。系统围绕识别需求、有效共情、达成一致、承诺回复四个维度，对客服与用户的对话进行结构化评分和问题定位。

## 在线演示

https://cs-quality-evaluator-kwkg6qntv2gwruquwijmgp.streamlit.app

## 业务背景

传统人工质检覆盖率低，且质检标准容易因人而异。这个 Demo 模拟将服务质量标准结构化、可解释化，并通过规则/AI 双引擎辅助完成对话评估。

## 核心功能

- 四维评分：识别需求、有效共情、达成一致、承诺回复。
- 单条质检：输入一段对话，输出分数、问题点和改进建议。
- 批量质检：对多段对话进行批量评估和对比。
- 可视化分析：雷达图、维度对比、客服表现分布。
- 问题记录：沉淀可追踪的 Badcase 和优化建议。

## 引擎设计

默认规则评价无需 API Key，可直接体验质检流程。接入 DeepSeek、Gemini、Groq 或本地 Ollama 后，可切换为 AI 语义评估。

## 技术栈

- Python
- Streamlit
- pandas
- Plotly
- OpenAI-compatible SDK

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 数据说明

演示对话均为模拟数据，不包含真实用户隐私。

## 面试展示重点

这个项目适合展示：

- 如何把“服务好不好”拆成可评估、可追问的维度。
- 如何用 Badcase 反推质检标准本身是否清晰。
- 如何从人工抽检思路升级到全量自动化质检思路。
