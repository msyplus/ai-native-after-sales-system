# 对客沟通机器人 v1.1

AI native 售后服务系统的信息输入端。客户自然语言问题从这里进入系统。

## 1.1 能力

| 能力 | 说明 |
|------|------|
| 多轮槽位继承 | 同一会话内 `required_slots` 跨轮累积，已收集字段不重复追问 |
| 同一 case_id | 整个会话只生成一个 `case_id`，后续轮次沿用 |
| 高风险转人工 | 监管投诉/赔付/高情绪场景优先 `human_handoff`，即使缺字段也生成 `handoff_summary` |
| 低风险标准答复 | 无风险、字段完整、知识充足时输出 `standard_answer`，不承诺具体退款/赔付金额 |
| 状态可回放 | 每轮记录 `state_history`（槽位、风险、知识命中、下一步动作的 diff） |
| LLM 驱动 | 默认 DeepSeek LLM 生成对话，无 Key 时规则兜底 |
| API Key 安全 | 从 `st.secrets` 或环境变量 `DEEPSEEK_API_KEY` 读取，不硬编码 |

## 2. 测试样例

### Case A：高风险投诉首轮转人工

输入：
```
航班延误后我要求退票赔付，如果今天不给方案我就投诉到民航局。
```

预期输出：
- `case_id` 非空
- `risk_tags` 包含 `regulatory_or_public_risk`、`compensation_or_refund`
- `next_action = human_handoff`
- `handoff_summary` 非空
- `knowledge_refs` 至少 1 条

### Case B：低风险物流咨询多轮补槽

第一轮输入：
```
我买的耳机三天了还没收到，帮我查一下物流。
```

第二轮输入：
```
订单号是 A123456789，昨天晚上物流就没更新了。
```

预期输出：
- 两轮 `case_id` 相同
- 首轮 `order_id=missing`，次轮 `order_id=provided`
- `state_history >= 2`

### Case C：低风险标准答复

输入：
```
自愿退票手续费怎么收？订单号 A123456789，今天想退票。
```

预期输出：
- `next_action = standard_answer`
- `knowledge_refs` 命中退票规则
- 回复说明以票规/系统为准，不承诺具体金额

## 3. 边界说明

本原型不代表已有生产上线经验，不接真实用户数据，不自动承诺退款、赔付或监管处理结果。

## 4. 运行

```powershell
streamlit run app.py --server.port 8507
```

或运行 `start-local-demos.bat` 一键启动全部 7 个模块。
