# AI native After-Sales Service System

Streamlit deployment source for the AI native after-sales service system demos.

This repository is a clean deployment copy. It only includes demo source code and shared runtime helpers.

## Streamlit Cloud Apps

Use the same repository and branch for all apps. Configure different **Main file path** values:

| App | Main file path |
| --- | --- |
| System portal / control console | `04_demo_source/ai-assistant-portal/app.py` |
| Customer-facing agent | `04_demo_source/customer-agent-demo/app.py` |
| Complaint classifier | `04_demo_source/complaint-classifier/app.py` |
| VOC risk detector | `04_demo_source/voc-risk-detector/app.py` |
| CS quality evaluator | `04_demo_source/cs-quality-evaluator/app.py` |
| Summary system | `04_demo_source/summary-system/app.py` |
| Service RAG demo | `04_demo_source/service-rag-demo/app.py` |

## Secrets

For apps that need LLM mode, configure secrets in Streamlit Cloud:

```toml
DEEPSEEK_API_KEY = "your-key"
```

The demos keep rule-based fallback paths where available.

## Included Source

- `04_demo_source/`: seven Streamlit demos
- `ai_native_shared/`: shared case, knowledge, feedback, metrics, and insight helpers

## Not Included

Personal job-search documents, resumes, interview packages, local logs, and agent memory files are intentionally excluded.
