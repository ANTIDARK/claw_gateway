# 其他
在huggingface部署了一个大模型，可以在免费空间尝试一些小模型：https://huggingface.co/spaces/antidark/smallmodels

# Claw Gateway 多模型聚合网关
## 一键整合 Mistral / Cerebras / NVIDIA 免费模型 | 可视化面板 | 配置自动写回脚本 | 无需重启

这是一个**开箱即用、零额外配置文件**的 AI 模型聚合网关，自动路由最优免费模型，支持对话、代码、中文、长文本、图像、视频生成，所有修改直接写回自身 `.py` 脚本，重启不丢失。

---

# 🚀 快速启动
## 1. 安装依赖
```bash
pip install fastapi uvicorn requests slowapi
```

## 2. 填写密钥（推荐）
打开脚本，修改顶部配置：
```python
CONFIG = {
    "GATEWAY_API_KEY": "设置你的网关密码",
}

PROVIDERS = {
    "mistral": {"api_key": "你的Mistral密钥"},
    "cerebras": {"api_key": "你的Cerebras密钥"},
    "nvidia": {"api_key": "你的NVIDIA密钥"},
}
```

## 3. 启动网关
```bash
python claw_gateway.py
```

## 4. 打开面板
```
http://localhost:8123
```
所有功能、配置、统计、编辑都在这里完成。

---

# 📦 支持的模型（2026-04 最新免费）
## Mistral
- mistral-small-4
- mistral-devstral-small-2
- mistral-large-3

## Cerebras
- llama-4-scout
- llama-3.3-70b-instruct
- qwen3-235b-instruct
- glm-4.7

## NVIDIA
- llama-4-maverick-17b
- deepseek-v3.2
- qwen3.5-397b
- kimi-k2.5
- FLUX.1-dev
- SDXL 1024
- SVD-XT-1.1 视频

---

# 🔧 使用方法（兼容 OpenAI 格式）
## 对话 / 代码 / 中文 / 长文本
**Base URL**
```
http://localhost:8123/v1
```

**API Key**
你在 `CONFIG` 里设置的网关密码

**请求示例**
```json
{
  "model": "auto",
  "messages": [{"role":"user","content":"写一个快速排序"}]
}
```
网关会**自动识别任务类型**并分配最优模型。

## 图像生成
```
POST /v1/images/generations
```
```json
{
  "prompt": "一只可爱的猫",
  "size": "1024x1024"
}
```

## 视频生成
```
POST /v1/videos/generations
```
```json
{
  "image": "base64图片",
  "steps": 25,
  "fps": 10
}
```

---

# ➕ 添加新模型方法（可视化操作）
## 1. 打开面板 → 配置编辑 → 模型配置
直接在文本框里添加一段模型格式：

```json
"新模型ID": {
  "provider": "供应商名",
  "model_name": "官方模型名",
  "tags": ["chat","code"],
  "rpm": 30
}
```

示例：
```json
"my-new-model": {
  "provider": "nvidia",
  "model_name": "deepseek-ai/deepseek-model-name",
  "tags": ["code","reasoning"],
  "rpm": 40
}
```

## 2. 把模型加入任务池
打开「任务池」标签，把你的模型ID加入对应任务：
```json
"code": ["my-new-model", "nvidia-deepseek-v3.2"]
```

## 3. 点击「保存并写回脚本」
✅ 立即生效  
✅ 自动创建限流队列  
✅ 自动加入统计  
✅ 重启不丢失  

---

# 🎯 任务自动识别规则
网关会自动判断任务类型：
- **代码**：包含代码、python、debug、编程 → 分配代码模型
- **中文**：中文占比 >50% → 分配中文模型
- **长对话**：轮次>4 或 文本>1200字符 → 长上下文模型
- **短对话**：默认最快模型

---

# 🛠 配置说明（可网页直接编辑）
## 全局配置
- `GATEWAY_API_KEY`：网关访问密钥
- `HOST` / `PORT`：监听地址
- `MAX_RETRY`：失败重试次数
- `FAILED_TEMP_EXPIRE`：临时失败冷却时间
- `LONG_TURN_THRESHOLD`：长对话轮次阈值

## 模型配置
- `provider`：供应商（mistral / cerebras / nvidia）
- `model_name`：官方接口模型名
- `rpm`：每分钟请求数（限流）
- `tags`：标签（不影响逻辑）

## 任务池
- `chat_short`：短对话
- `chat_long`：长对话
- `code`：代码
- `chinese`：中文优化
- `image`：文生图
- `video`：视频生成

---

# ✅ 特色功能
✅ 零外部配置文件 → 全部写回自身脚本  
✅ 可视化配置编辑器 → 不用改代码  
✅ 自动任务识别 → 代码/中文/长对话智能分配  
✅ 模型失败自动降级  
✅ 会话锁定 → 同一场景不换模型  
✅ 实时统计面板 → 请求次数、Token、失败状态  
✅ 兼容 OpenAI 格式 → 所有客户端直接用  

---

# 📁 文件说明
- `claw_gateway.py`：主程序 + 配置 + 面板（唯一文件）
- `logs/`：自动日志目录
- 无其他文件

---
