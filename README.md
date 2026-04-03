# README.md
## Claw Gateway 全自动热重载版多模型网关
一个专为免费API设计的生产级多模型网关，支持**全自动配置热重载**，修改Python文件保存后立即生效，无需重启服务。完全兼容OpenAI API格式，可直接对接OpenClaw、ChatBox等客户端。

## ✨ 核心特性
- **全自动热重载**：修改配置文件保存后自动重载，零操作
- **模型级独立限流**：每个模型有自己的RPM限制，互不影响
- **智能任务路由**：自动识别短对话/长对话/代码/中文任务
- **会话模型锁定**：同一个对话全程使用一个模型，保证连贯性
- **自动失败降级**：模型失败自动切换到下一个，不中断服务
- **永久/临时失败区分**：额度耗尽永久标记，网络错误自动恢复
- **完整Web面板**：实时查看运行状态、统计数据
- **标准OpenAI API**：兼容所有支持OpenAI格式的客户端

## 🚀 快速开始
### 1. 安装依赖
```bash
pip install fastapi uvicorn requests slowapi watchdog
```

### 2. 配置API密钥
编辑`claw_gateway.py`文件，修改以下配置：
```python
CONFIG = {
    "GATEWAY_API_KEY": "设置你的网关密码",
}

PROVIDERS = {
    "mistral": {
        "api_key": "你的MISTRAL_API_KEY",
    },
    "cerebras": {
        "api_key": "你的CEREBRAS_API_KEY",
    },
    "nvidia": {
        "api_key": "你的NVIDIA_API_KEY",
    },
}
```

### 3. 启动网关
```bash
python claw_gateway.py
```

### 4. 访问管理面板
打开浏览器访问：`http://localhost:8123`

## 📱 客户端配置（以OpenClaw为例）
在OpenClaw中添加自定义API：
```json
{
    "baseUrl": "http://localhost:8123/v1",
    "apiKey": "你设置的网关密码",
    "model": "auto"
}
```

## ➕ 如何添加新模型
**无需重启网关，3步完成，保存即生效**

### 步骤1：确认供应商已存在
首先检查`PROVIDERS`配置块中是否已有该模型的供应商，如果没有则添加：
```python
PROVIDERS = {
    # 已有供应商...
    "新供应商名称": {
        "base_url": "供应商API基础地址",
        "api_key": "你的API密钥",
    },
}
```

### 步骤2：添加模型定义
在`MODEL_INFO`配置块中添加新模型，格式如下：
```python
MODEL_INFO = {
    # 已有模型...
    "自定义模型代号": {
        "provider": "对应供应商名称（和上面一致）",
        "model_name": "供应商官方模型ID",
        "tags": ["能力标签"], # 可选值：fast/cheap/chat/code/reasoning/long_context/chinese/image/video
        "rpm": 官方免费层每分钟请求数,
    },
}
```

**示例：添加一个新的NVIDIA文本模型**
```python
"nvidia-llama3.2-3b": {
    "provider": "nvidia",
    "model_name": "meta/llama-3.2-3b-instruct",
    "tags": ["fast", "cheap", "chat"],
    "rpm": 60,
},
```

**示例：添加一个新的画图模型**
```python
"nvidia-flux1-schnell": {
    "provider": "nvidia",
    "model_name": "black-forest-labs/flux-1-schnell",
    "tags": ["image"],
    "rpm": 15,
},
```

### 步骤3：加入对应任务池
在`TASK_MODEL_POOLS`中把新模型添加到合适的任务池，顺序就是优先级（越靠前越先使用）：
```python
TASK_MODEL_POOLS = {
    "chat_short": [
        "nvidia-llama3.2-3b", # 把新模型放在最前面，优先使用
        "cerebras-llama4-scout",
        "mistral-small-4",
    ],
    "image": [
        "nvidia-flux1-schnell", # 新画图模型优先
        "nvidia-flux1-dev",
        "nvidia-sdxl-1024",
    ],
}
```

### 完成
保存`claw_gateway.py`文件，网关会**自动检测到变化并热重载配置**，新模型立即生效。

## 🔧 配置更新方式
### 方式1：全自动热重载（推荐）
1. 用编辑器打开`claw_gateway.py`
2. 修改任意配置（加模型、改RPM、调参数）
3. 保存文件
4. 网关会**自动检测到变化并重载配置**，立即生效

### 方式2：API方式
```bash
curl -H "Authorization: Bearer 你的网关密码" http://localhost:8123/reload
```

### 方式3：Web面板
打开管理面板，点击**手动重载**按钮

## 📋 支持的模型（2026年4月最新）
### 文本模型
- Mistral: mistral-small-4, devstral-small-2, mistral-large-3
- Cerebras: llama-4-scout, llama-3.3-70b, qwen3-235b, glm4.7
- NVIDIA: llama-4-maverick-17b, deepseek-v3.2, qwen3.5-397b, kimi-k2.5

### 图像模型
- NVIDIA: flux1-dev, sdxl-1024

### 视频模型
- NVIDIA: svd-xt-1.1

## ⚠️ 注意事项
- 全自动热重载**只重载配置部分**，不会中断正在进行的请求
- 如果修改了核心逻辑代码（如`run_task`函数），还是需要重启网关
- 可以通过修改`CONFIG["AUTO_RELOAD"] = False`关闭全自动热重载
- 日志自动保存在`logs`目录下，保留最近7天

## 📄 许可证
powered by 豆包

# 用huggingface免费空间部署了一个模型在线体验站点，同时支持网页和api,支持切换模型
huggingface.co/spaces/antidark/smallmodels
