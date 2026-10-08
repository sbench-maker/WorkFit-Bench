# 本地模拟盘说明

本目录是一份完全离线、实体与行情均为虚构的 2026-09-10 上午交易窗口。`trade_ticket.json` 是待执行工单；其余 JSON 是三个账户的初始资金、持仓批次、历史订单、成交与冻结行情，关联键为 `account_id`、`order_id` 和 `symbol`。

启动与技能 CLI 兼容的本地服务：

```bash
python3 /root/data/mock_paper_trading_service.py --state /root/results/broker_state.json
```

服务固定时钟为 `2026-09-10 10:05:00`，地址为 `http://127.0.0.1:18765`，支持本工单所需的账户、持仓、订单、成交、下单、撤单和撮合路由。首次启动会从本目录 JSON 建立 `/root/results/broker_state.json`，之后重启保留已执行状态；不要修改 `/root/data` 中的初始文件。HTTP 错误仍返回 JSON，例如 `{"status":"error","message":"..."}`。所有操作均不得联网。
