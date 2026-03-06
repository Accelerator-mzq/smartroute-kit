# SmartRoute 踩坑记录与排障指南

## 坑 1：CCM 中 MiniMax 配置为 anthropic 类型会报错

### 症状

```
502 {"error":{"message":"All 1 provider mappings failed","type":"error"}}
```

或者：

```
TOML parse error: missing field `provider_type`
TOML parse error: missing field `models`
```

### 原因

claude-code-mux (CCM) 内部对 `anthropic` 类型的 Provider 实现有限制。MiniMax 虽然提供了 Anthropic 兼容端点 (`/anthropic`)，但 CCM 的 anthropic 模块在处理时会出现兼容性问题。

### 解决方案：将 MiniMax 配置为 OpenAI 类型

MiniMax 完美兼容 OpenAI API 格式。在 CCM Web UI (`http://127.0.0.1:13456`) 中：

1. 进入 **Providers** 菜单，点击新建
2. 选择 **openai** 类型
3. 填写：
   - **Name**: `MiniMax-OpenAI-Mode`（随意命名）
   - **API Key**: 你的 MiniMax API Key
   - **Custom Endpoint**: `https://api.minimaxi.com/v1`
4. 保存后，进入 **Models** 菜单
5. 找到 `MiniMax-M2.5-highspeed` 模型，将 Provider 改为刚创建的 `MiniMax-OpenAI-Mode`

> 对应地，`smartroute.config.json` 中快模型的 `provider_type` 应设为 `"openai"`，`base_url` 应设为 `"https://api.minimaxi.com/v1"`（不是 `/anthropic` 结尾）。

---

## 坑 2：手动编写 config.toml 格式不对

### 症状

```
TOML parse error at line 32: missing field `provider_type`
TOML parse error at line 32: missing field `models`
```

### 原因

不同版本的 CCM 对 config.toml 的字段要求不同。手动编写很容易遗漏必要字段。

### 解决方案：不要手动写 config.toml

1. 删除已有的 config.toml：
   ```powershell
   del $env:USERPROFILE\.claude-code-mux\config.toml
   ```
2. 启动 CCM，让它自动生成默认配置：
   ```powershell
   ccm start
   ```
3. 打开浏览器 `http://127.0.0.1:13456`，通过 Web UI 配置 Provider 和 Router
4. 在 Web UI 中点击 **Save to Server** 保存

---

## 坑 3：CCM 日志文件不存在

### 症状

`~/.claude-code-mux/ccm.log` 文件不存在，无法查看路由日志。

### 原因

CCM 默认不输出日志文件，需要通过环境变量开启。

### 解决方案

PowerShell：
```powershell
$env:RUST_LOG="info"
ccm start
```

Git Bash：
```bash
RUST_LOG=info ccm start
```

日志会输出到终端。如需写入文件：
```powershell
$env:RUST_LOG="info"
ccm start 2>&1 | Tee-Object -FilePath "$env:USERPROFILE\.claude-code-mux\ccm.log"
```

更简单的方式：直接在 CCM Web UI 的 **Test** 标签页发测试请求查看路由结果。

---

## 坑 4：CC Switch 的"本地代理"开关和 CCM 冲突

### 症状

开启 CC Switch 的本地代理后，Claude Code 请求异常或超时。

### 原因

CC Switch 本地代理和 CCM 都是本地代理服务。同时开启会形成双重代理，请求链路变成：

```
Claude Code → CC Switch 代理 → CCM → 实际 API
               ↑ 多余的一层
```

### 解决方案

两者只开一个。推荐**关闭 CC Switch 本地代理开关**，只用 CCM。

CC Switch 本地代理的功能是**故障转移**（Provider A 挂了切 Provider B），而 CCM 的功能是**按任务类型智能路由**（think 走 Opus，普通走 MiniMax）。两者用途不同，不能互相替代。

---

## 坑 5：CC Switch 切换 Provider 后不生效

### 症状

在 CC Switch 中切换了 Provider，但 Claude Code 仍然使用旧的模型。

### 原因

环境变量优先级问题。如果你在 `.bashrc`/`.zshrc`/系统环境变量中设置了 `ANTHROPIC_API_KEY` 或 `ANTHROPIC_BASE_URL`，它们会覆盖 CC Switch 写入的配置。

### 解决方案

1. 检查并清除系统环境变量中的 Anthropic 相关变量
2. 切换后**新开终端**启动 Claude Code
3. 在 Claude Code 中用 `/status` 确认当前模型

---

## 坑 6：Clash Rule 模式下 CCM 访问外网 API 失败

### 症状

CCM 启动正常，但转发请求时返回连接超时。

### 原因

CCM 作为独立进程，可能不走系统代理。

### 解决方案

在 `smartroute.config.json` 的 `proxy` 部分配置：

```json
"proxy": {
    "http_proxy": "http://127.0.0.1:7890",
    "https_proxy": "http://127.0.0.1:7890"
}
```

运行 `python .pipeline/setup.py` 同步到 `.env`，或在 CCM config.toml 中手动添加 `PROXY_URL`。

先不配置，测试一下。能通就不用配。
