# Claw Gateway 一键多模型转发网关
**纯单机、无数据库、配置直接写回脚本、重启不丢、网页面板编辑**
支持自动负载、失败重试、流式转发、免费模型聚合

---

## 功能特性
✅ **原生支持 3 大免费模型供应商**
- Mistral AI
- Cerebras
- NVIDIA NIM

✅ **网页面板可视化编辑配置**
- 全局参数、模型列表、任务池优先级
- **保存直接写回 .py 脚本自身**
- 无需额外 config.json

✅**高可用转发**- 自动失败重试、跳过不可用模型
- 按任务类型自动选最优模型（短对话/长对话/代码/中文/绘图）
- 严格 RPM 限流，防止被封号
- 会话锁定，不打乱上下文

✅**纯内存 + 持久化**- 统计只在内存，不写日志泛滥
- 配置永久保存到自身脚本
- 重启不丢失

---

## 文件结构
```
claw_gateway.py       # 主程序（配置+代码一体）
README.md             # 说明文档
logs/                 # 自动生成的运行日志
```

---

## 快速启动
### 1. 安装依赖
```bash
pip install fastapi uvicorn requests slowapi pydantic
```

### 2. 直接运行
```bash
python claw_gateway.py
```

### 3. 打开面板
```
http://localhost:8123
```

---

## 配置说明（全部网页可视化修改）
### 全局配置 CONFIG
- GATEWAY_API_KEY 网关密钥
- HOST / PORT 监听地址
- MAX_RETRY 最大重试次数
- FAILED_TEMP_EXPIRE 临时失败冷却时间
- LONG_TURN_THRESHOLD 长对话轮数阈值

### 供应商 PROVIDERS
存放各平台 key 与 base_url

### 模型 MODEL_INFO
- 模型名称、真实API名、供应商
- rpm 每分钟请求限制
- tags 类型标记

### 任务池 TASK_MODEL_POOLS
定义每种任务优先用哪些模型：
- chat_short 短对话
- chat_long 长对话
- code 代码
- chinese 中文优先
- image 绘图
- video 视频

---

## 如何修改配置（最安全方式）
1. 打开面板 http://localhost:8123
2. 拉到最下面 **配置编辑**
3. 修改 JSON
4. 点击 **保存并写回脚本**
5. **自动覆盖 py 文件，重启依然保留**

---

## 兼容接口
完全兼容 OpenAI 格式，可直接接入任何前端：

### 聊天
```
POST /v1/chat/completions
```

### 绘图
```
POST /v1/images/generations
```

### 视频
```
POST /v1/videos/generations
```

---

## 前端接入示例
```json
{
  "baseUrl": "http://localhost:8123/v1",
  "apiKey": "你的网关密码",
  "model": "auto"
}
```

---

## 安全说明
- 配置**只写自身脚本**，不产生多余文件
- 鉴权严格，未带密钥无法调用与修改配置
- 失败模型自动冷却，不疯狂重试炸号
- 所有模型按官方免费层 RPM 限制

---

## 适合人群
- 自用多免费模型聚合网关
- 不想装数据库、不想配复杂文件
- 想要**面板改配置 + 重启不丢**
- 一键运行、干净轻量

---

需要我再给你配一个**简洁版 README（一行安装、一行启动）** 吗？
