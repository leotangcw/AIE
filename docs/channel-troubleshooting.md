# 渠道故障排查

> 常见渠道连接问题的排查方法。

## Telegram

### 测试连接提示 "Flood control exceeded"

Telegram API 有速率限制，短时间内多次调用 `getMe()` 会触发 flood control。等待提示的秒数后自动恢复，不影响正常聊天收发消息。

### 连接失败 / 超时

- 中国大陆网络无法直接访问 `api.telegram.org`，需要配置代理
- 在 Web UI → 设置 → 渠道 → Telegram 中填写代理地址（如 `http://127.0.0.1:7890`）
- 支持 HTTP 和 SOCKS5 代理

### Bot Token 无效

- 确认 Token 来自 [@BotFather](https://t.me/BotFather)
- Token 格式：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
- 如果 Token 泄露，在 BotFather 中使用 `/revoke` 重新生成

## 飞书

### WebSocket 断开重连

飞书 SDK 内置自动重连机制，短暂网络中断（几分钟内）会自动恢复。如果长时间无法重连，检查：
- App ID 和 App Secret 是否正确
- 飞书开放平台中机器人是否已发布
- 网络连接是否正常

### 收不到消息

- 确认在飞书开放平台 → 事件订阅中启用了 `im.message.receive_v1`
- 确认机器人已添加到目标群组或已被用户添加

## 钉钉

### Stream 连接失败

- 确认 Client ID 和 Client Secret 正确
- 确认在钉钉开放平台中启用了 Stream 模式
- 钉钉 SDK 内置重连，短暂断开会自动恢复

## QQ

### 凭据验证失败

- QQ App ID 必须是纯数字
- 确认在 [q.qq.com](https://q.qq.com) 中机器人已审核通过
- Secret 只能包含字母和数字

### 群消息收不到

- 确认机器人已被添加到目标群组
- 检查 `allow_from` 白名单配置

## 通用排查

### 渠道显示"已启用"但不是"运行中"

- 查看日志文件 `data/logs/` 中的错误信息
- 确认凭据配置正确
- 修改配置后需要重启应用才能生效

### 白名单配置

- `allow_from` 为空 = 允许所有人
- 各渠道用户 ID 格式不同：
  - Telegram：数字 ID（如 `123456789`），可通过 @userinfobot 获取
  - 飞书：Open ID（如 `ou_xxxxxxxxxx`）
  - 钉钉：staffId
  - QQ：用户 ID
