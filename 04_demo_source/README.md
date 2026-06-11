# Demo 源文件目录

本目录用于集中存放 AI native 售后服务系统相关 demo 源文件，避免继续分散在 C 盘用户目录。

## 当前模块

| 模块 | 本地路径 | 端口 |
| --- | --- | --- |
| 客诉智能分类 | `D:\job3.0\04_demo_source\complaint-classifier` | 8501 |
| VOC 风险识别 | `D:\job3.0\04_demo_source\voc-risk-detector` | 8502 |
| 客服对话质检 | `D:\job3.0\04_demo_source\cs-quality-evaluator` | 8503 |
| 智能总结概要 | `D:\job3.0\04_demo_source\summary-system` | 8504 |
| RAG 知识库问答 | `D:\job3.0\04_demo_source\service-rag-demo` | 8505 |
| AI native 售后服务系统控制台/门户 | `D:\job3.0\04_demo_source\ai-assistant-portal` | 8506 |

## 规划模块

| 模块 | 目标路径 | 建议端口 | 说明 |
| --- | --- | --- | --- |
| 对客沟通智能体 | `D:\job3.0\04_demo_source\customer-agent-demo` | 8507 | 作为售后服务系统的信息输入端，承接真实对客沟通、多轮补槽、风险识别和人工交接。线上入口当前使用 `https://customer-agent-demo.streamlit.app`。 |

## 线上入口

| 模块 | 线上地址 |
| --- | --- |
| 系统总入口：AI native 售后服务系统控制台/门户 | `https://ai-native-system-msydemo.streamlit.app` |
| 对客沟通机器人 | `https://customer-agent-demo.streamlit.app` |

## 启动方式

统一从以下脚本启动本地 demo：

```bat
D:\job3.0\00_流程SOP\start-local-demos.bat
```

当前迁移为复制迁移：D 盘目录已作为后续开发和交接的主路径；旧目录暂时保留，避免误删历史文件。确认 D 盘版本运行稳定后，再单独清理旧目录。

