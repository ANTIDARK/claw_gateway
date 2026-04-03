import os
import time
import json
import asyncio
import logging
import re
import threading
from datetime import datetime, timedelta
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
import requests
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from collections import deque
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ==============================================================================
# ======================== 全局配置（全自动热重载）=========================
# ==============================================================================
CONFIG = {
    "GATEWAY_API_KEY": "你的网关密码",
    "HOST": "0.0.0.0",
    "PORT": 8123,
    "MAX_RETRY": 1,
    "GATEWAY_RATE_LIMIT": "60 per minute",
    "FAILED_TEMP_EXPIRE": 180,  # 临时失败3分钟自动恢复
    "LONG_TURN_THRESHOLD": 4,   # 超过4轮自动判定为长对话
    "LONG_TEXT_THRESHOLD": 1200, # 超过1200字符自动判定为长对话
    "LOG_RETENTION_DAYS": 7,    # 日志自动保留7天
    "AUTO_RELOAD": True,        # 开启全自动配置热重载
}

# ==============================================================================
# 1. 供应商配置（同一家只写一次）
# ==============================================================================
PROVIDERS = {
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "api_key": "你的MISTRAL_KEY",
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "api_key": "你的CEREBRAS_KEY",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key": "你的NVIDIA_KEY",
    },
}

# ==============================================================================
# 2. 模型配置（2026年4月最新免费模型 + 官方准确RPM）
# ==============================================================================
MODEL_INFO = {
    # Mistral AI 系列
    "mistral-small-4": {
        "provider": "mistral",
        "model_name": "mistral-small-4",
        "tags": ["fast", "cheap", "chat", "code", "vision"],
        "rpm": 2,
    },
    "mistral-devstral-small-2": {
        "provider": "mistral",
        "model_name": "devstral-small-2",
        "tags": ["code", "fast", "cheap"],
        "rpm": 2,
    },
    "mistral-large-3": {
        "provider": "mistral",
        "model_name": "mistral-large-3",
        "tags": ["reasoning", "long_context", "vision"],
        "rpm": 2,
    },

    # Cerebras AI 系列
    "cerebras-llama4-scout": {
        "provider": "cerebras",
        "model_name": "llama-4-scout",
        "tags": ["fast", "chat", "cheap"],
        "rpm": 30,
    },
    "cerebras-llama3.3-70b": {
        "provider": "cerebras",
        "model_name": "llama-3.3-70b-instruct",
        "tags": ["code", "reasoning", "long_context"],
        "rpm": 30,
    },
    "cerebras-qwen3-235b": {
        "provider": "cerebras",
        "model_name": "qwen3-235b-instruct",
        "tags": ["chinese", "reasoning", "long_context"],
        "rpm": 30,
    },
    "cerebras-glm4.7": {
        "provider": "cerebras",
        "model_name": "glm-4.7",
        "tags": ["chinese", "chat"],
        "rpm": 30,
    },

    # NVIDIA NIM 系列
    "nvidia-llama4-maverick-17b": {
        "provider": "nvidia",
        "model_name": "meta/llama-4-maverick-17b-128e-instruct",
        "tags": ["fast", "chat", "reasoning"],
        "rpm": 40,
    },
    "nvidia-deepseek-v3.2": {
        "provider": "nvidia",
        "model_name": "deepseek-ai/deepseek-v3.2",
        "tags": ["code", "reasoning", "math"],
        "rpm": 40,
    },
    "nvidia-qwen3.5-397b": {
        "provider": "nvidia",
        "model_name": "qwen/qwen3.5-397b-a17b",
        "tags": ["chinese", "long_context", "reasoning"],
        "rpm": 40,
    },
    "nvidia-kimi-k2.5": {
        "provider": "nvidia",
        "model_name": "moonshotai/kimi-k2.5-instruct",
        "tags": ["long_context", "document"],
        "rpm": 40,
    },

    # 图像生成模型
    "nvidia-flux1-dev": {
        "provider": "nvidia",
        "model_name": "black-forest-labs/flux-1-dev",
        "tags": ["image"],
        "rpm": 10,
    },
    "nvidia-sdxl-1024": {
        "provider": "nvidia",
        "model_name": "stabilityai/stable-diffusion-xl-1024-v1-0",
        "tags": ["image"],
        "rpm": 10,
    },

    # 视频生成模型
    "nvidia-svd-xt-1.1": {
        "provider": "nvidia",
        "model_name": "stabilityai/stable-video-diffusion-img2vid-xt-1-1",
        "tags": ["video"],
        "rpm": 2,
    },
}

# ==============================================================================
# 3. 任务模型池（按优先级排序，失败自动fallback）
# ==============================================================================
TASK_MODEL_POOLS = {
    "chat_short": [
        "cerebras-llama4-scout",
        "nvidia-llama4-maverick-17b",
        "mistral-small-4",
    ],
    "chat_long": [
        "nvidia-kimi-k2.5",
        "cerebras-qwen3-235b",
        "nvidia-qwen3.5-397b",
    ],
    "code": [
        "nvidia-deepseek-v3.2",
        "cerebras-llama3.3-70b",
        "mistral-devstral-small-2",
    ],
    "chinese": [
        "cerebras-qwen3-235b",
        "nvidia-qwen3.5-397b",
        "cerebras-glm4.7",
    ],
    "image": [
        "nvidia-flux1-dev",
        "nvidia-sdxl-1024",
    ],
    "video": [
        "nvidia-svd-xt-1.1",
    ],
}

# ==============================================================================
# ======================== 核心初始化 ========================
# ==============================================================================
app = FastAPI(title="Claw Gateway 全自动热重载版")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 日志系统
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"logs/gateway_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 全局状态
failed_temp: Dict[str, float] = {}
failed_perm: set[str] = set()
session_locks: Dict[str, str] = {}
model_usage: Dict[str, int] = {m: 0 for m in MODEL_INFO}
task_usage: Dict[str, int] = {t: 0 for t in TASK_MODEL_POOLS}
token_usage: Dict[str, int] = {m: 0 for m in MODEL_INFO}
model_queues: Dict[str, deque] = {m: deque() for m in MODEL_INFO}
last_model = None
last_task = None

# 当前脚本文件路径
SCRIPT_PATH = os.path.abspath(__file__)

# ==============================================================================
# ======================== 工具函数 ========================
# ==============================================================================
def log(msg, level="info"):
    getattr(logger, level)(msg)

def auth(authorization: Optional[str] = Header(None)):
    if not CONFIG["GATEWAY_API_KEY"]:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if authorization.replace("Bearer ", "").strip() != CONFIG["GATEWAY_API_KEY"]:
        raise HTTPException(status_code=403, detail="Forbidden")

def is_model_available(model_key: str) -> bool:
    if model_key in failed_perm:
        return False
    if model_key in failed_temp:
        if time.time() - failed_temp[model_key] > CONFIG["FAILED_TEMP_EXPIRE"]:
            del failed_temp[model_key]
        else:
            return False
    return True

def mark_failed(model_key: str, permanent: bool = False):
    if permanent:
        failed_perm.add(model_key)
        log(f"模型永久失败: {model_key}", "error")
    else:
        failed_temp[model_key] = time.time()
        log(f"模型临时失败: {model_key}", "warning")

def get_model_conf(model_key: str) -> Optional[Dict]:
    if model_key not in MODEL_INFO:
        return None
    mi = MODEL_INFO[model_key]
    pv = PROVIDERS[mi["provider"]]
    return {
        "base_url": pv["base_url"],
        "api_key": pv["api_key"],
        "model_name": mi["model_name"],
        "tags": mi["tags"],
        "rpm": mi["rpm"],
    }

def clean_old_logs():
    for filename in os.listdir("logs"):
        if filename.startswith("gateway_") and filename.endswith(".log"):
            try:
                date_str = filename.split("_")[1].split(".")[0]
                log_date = datetime.strptime(date_str, "%Y%m%d")
                if datetime.now() - log_date > timedelta(days=CONFIG["LOG_RETENTION_DAYS"]):
                    os.remove(os.path.join("logs", filename))
            except:
                pass

async def acquire_token(model_key: str):
    rpm = MODEL_INFO[model_key]["rpm"]
    interval = 60 / rpm
    while True:
        now = time.time()
        if not model_queues[model_key] or now - model_queues[model_key][0] >= interval:
            if model_queues[model_key]:
                model_queues[model_key].popleft()
            model_queues[model_key].append(now)
            return
        await asyncio.sleep(0.05)

# ==============================================================================
# ======================== 全自动热重载核心 ========================
# ==============================================================================
def reload_config_from_file():
    """从Python文件重新加载所有配置，不中断服务"""
    global CONFIG, PROVIDERS, MODEL_INFO, TASK_MODEL_POOLS
    global model_usage, task_usage, token_usage, model_queues

    try:
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        # 提取并执行配置块
        local_vars = {}
        exec(re.search(r"CONFIG = \{.*?\}", content, flags=re.DOTALL).group(), {}, local_vars)
        exec(re.search(r"PROVIDERS = \{.*?\}", content, flags=re.DOTALL).group(), {}, local_vars)
        exec(re.search(r"MODEL_INFO = \{.*?\}", content, flags=re.DOTALL).group(), {}, local_vars)
        exec(re.search(r"TASK_MODEL_POOLS = \{.*?\}", content, flags=re.DOTALL).group(), {}, local_vars)

        # 更新全局配置
        CONFIG = local_vars["CONFIG"]
        PROVIDERS = local_vars["PROVIDERS"]
        MODEL_INFO = local_vars["MODEL_INFO"]
        TASK_MODEL_POOLS = local_vars["TASK_MODEL_POOLS"]

        # 初始化新增模型的统计和队列
        for m in MODEL_INFO:
            if m not in model_usage:
                model_usage[m] = 0
            if m not in token_usage:
                token_usage[m] = 0
            if m not in model_queues:
                model_queues[m] = deque()

        # 初始化新增任务的统计
        for t in TASK_MODEL_POOLS:
            if t not in task_usage:
                task_usage[t] = 0

        log("✅ 配置已自动热重载成功", "info")
        return True
    except Exception as e:
        log(f"❌ 配置热重载失败: {str(e)}", "error")
        return False

# 配置文件自动监控处理器
class ConfigFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path == SCRIPT_PATH and CONFIG["AUTO_RELOAD"]:
            # 防抖处理：避免编辑器多次保存触发多次重载
            time.sleep(0.5)
            reload_config_from_file()

# 启动文件监控线程
def start_file_watcher():
    event_handler = ConfigFileHandler()
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(SCRIPT_PATH), recursive=False)
    observer.start()
    log("📂 配置文件自动监控已启动")
    return observer

# ==============================================================================
# ======================== 智能任务路由 ========================
# ==============================================================================
def detect_task(messages: List[Any]) -> str:
    all_text = " ".join(str(m.get("content", "")) for m in messages).lower()
    user_turns = len([m for m in messages if m.get("role") == "user"])
    
    # 代码任务优先识别
    code_keywords = ["代码", "python", "debug", "编程", "函数", "java", "c++", "script", "bug", "code", "function"]
    if any(k in all_text for k in code_keywords):
        return "code"
    
    # 中文任务识别
    chinese_chars = sum(1 for c in all_text if '\u4e00' <= c <= '\u9fff')
    if chinese_chars > len(all_text) * 0.5:
        if user_turns >= CONFIG["LONG_TURN_THRESHOLD"] or len(all_text) > CONFIG["LONG_TEXT_THRESHOLD"]:
            return "chat_long"
        return "chinese"
    
    # 长对话/长文本识别
    if user_turns >= CONFIG["LONG_TURN_THRESHOLD"] or len(all_text) > CONFIG["LONG_TEXT_THRESHOLD"]:
        return "chat_long"
    
    # 默认短对话
    return "chat_short"

def select_best_model(task: str, session_id: Optional[str] = None) -> Optional[str]:
    # 会话模型锁定优先
    if session_id and session_id in session_locks:
        locked_model = session_locks[session_id]
        if is_model_available(locked_model):
            return locked_model
        else:
            del session_locks[session_id]
    
    # 按任务池顺序选择
    pool = TASK_MODEL_POOLS[task]
    for model_key in pool:
        if is_model_available(model_key):
            if session_id:
                session_locks[session_id] = model_key
            return model_key
    return None

# ==============================================================================
# ======================== 统一请求执行器 ========================
# ==============================================================================
async def run_task(task: str, payload: Dict, task_type: str = "text", session_id: Optional[str] = None):
    global last_model, last_task
    last_task = task
    
    for _ in range(CONFIG["MAX_RETRY"] + 1):
        model_key = select_best_model(task, session_id)
        if not model_key:
            return {"error": "所有模型不可用"}, 503, None
        
        conf = get_model_conf(model_key)
        await acquire_token(model_key)
        
        headers = {
            "Authorization": f"Bearer {conf['api_key']}",
            "Content-Type": "application/json"
        }
        full_payload = {**payload, "model": conf["model_name"]}
        
        # 选择对应端点
        if task_type == "image":
            url = f"{conf['base_url']}/images/generations"
        elif task_type == "video":
            url = f"{conf['base_url']}/videos/generations"
        else:
            url = f"{conf['base_url']}/chat/completions"
        
        try:
            response = requests.post(url, headers=headers, json=full_payload, timeout=90)
            response.raise_for_status()
            result = response.json()
            
            # 更新统计数据
            last_model = model_key
            task_usage[task] += 1
            model_usage[model_key] += 1
            if "usage" in result:
                token_usage[model_key] += result["usage"].get("total_tokens", 0)
            
            return result, 200, model_key
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            if status_code in (429, 402, 403):
                mark_failed(model_key, permanent=True)
            else:
                mark_failed(model_key, permanent=False)
        except Exception as e:
            mark_failed(model_key, permanent=False)
    
    return {"error": "所有模型均失败"}, 503, None

# 流式请求执行器（带自动降级）
async def run_stream_task(task: str, payload: Dict, session_id: Optional[str] = None):
    pool = TASK_MODEL_POOLS[task]
    for model_key in pool:
        if not is_model_available(model_key):
            continue
        
        conf = get_model_conf(model_key)
        await acquire_token(model_key)
        
        headers = {
            "Authorization": f"Bearer {conf['api_key']}",
            "Content-Type": "application/json"
        }
        full_payload = {**payload, "model": conf["model_name"], "stream": True}
        url = f"{conf['base_url']}/chat/completions"
        
        try:
            with requests.post(url, headers=headers, json=full_payload, stream=True, timeout=120) as r:
                r.raise_for_status()
                for chunk in r.iter_lines():
                    if chunk:
                        yield chunk.decode() + "\n"
                        await asyncio.sleep(0)
            return
        except Exception:
            mark_failed(model_key, permanent=False)
            continue
    
    yield b'data: [DONE]\n\n'

# ==============================================================================
# ======================== OpenAI兼容API接口 ========================
# ==============================================================================
class ChatRequest(BaseModel):
    messages: List[Any]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2048
    stream: Optional[bool] = False
    user: Optional[str] = None

class ImageRequest(BaseModel):
    prompt: str
    size: Optional[str] = "1024x1024"

class VideoRequest(BaseModel):
    image: str
    steps: Optional[int] = 25
    fps: Optional[int] = 10

@app.post("/v1/chat/completions")
@limiter.limit(CONFIG["GATEWAY_RATE_LIMIT"])
async def chat_completions(req: ChatRequest, request: Request, Authorization: str = Header(None)):
    auth(Authorization)
    task = detect_task(req.messages)
    session_id = req.user or request.client.host
    
    if not req.stream:
        payload = {
            "messages": req.messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": False
        }
        res, code, model = await run_task(task, payload, "text", session_id)
        if code == 200:
            res["gateway_task"] = task
            res["gateway_model"] = model
        return JSONResponse(res, status_code=code)
    else:
        payload = {
            "messages": req.messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens
        }
        return StreamingResponse(
            run_stream_task(task, payload, session_id),
            media_type="text/event-stream"
        )

@app.post("/v1/images/generations")
@limiter.limit(CONFIG["GATEWAY_RATE_LIMIT"])
async def generate_image(req: ImageRequest, request: Request, Authorization: str = Header(None)):
    auth(Authorization)
    payload = {"prompt": req.prompt, "size": req.size, "n": 1}
    res, code, _ = await run_task("image", payload, "image")
    return JSONResponse(res, status_code=code)

@app.post("/v1/videos/generations")
@limiter.limit(CONFIG["GATEWAY_RATE_LIMIT"])
async def generate_video(req: VideoRequest, request: Request, Authorization: str = Header(None)):
    auth(Authorization)
    payload = {"image": req.image, "num_inference_steps": req.steps, "fps": req.fps}
    res, code, _ = await run_task("video", payload, "video")
    return JSONResponse(res, status_code=code)

# API方式热重载
@app.get("/reload")
async def reload_config_api(Authorization: str = Header(None)):
    auth(Authorization)
    if reload_config_from_file():
        return {"status": "ok", "msg": "配置已通过API热重载成功"}
    else:
        return {"status": "error", "msg": "热重载失败"}

@app.get("/clear-failed")
async def clear_failed():
    failed_temp.clear()
    failed_perm.clear()
    return {"status": "ok"}

@app.get("/clear-sessions")
async def clear_sessions():
    session_locks.clear()
    return {"status": "ok"}

# 健康检查接口
@app.get("/health")
async def health():
    available_models = [m for m in MODEL_INFO if is_model_available(m)]
    failed_models = list(failed_perm) + [m for m in failed_temp if not is_model_available(m)]
    return {
        "status": "running",
        "available_models": available_models,
        "failed_models": failed_models,
        "last_task": last_task,
        "last_model": last_model,
        "total_requests": sum(task_usage.values()),
    }

# ==============================================================================
# ======================== Web管理面板 ========================
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
async def panel():
    clean_old_logs()
    failed_list = list(failed_perm) + [m for m in failed_temp if not is_model_available(m)]
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Claw Gateway 全自动热重载版</title>
        <style>
            :root {{--bg:#121212;--card:#1e1e1e;--text:#e0e0e0;--primary:#007bff;--danger:#dc3545;--success:#28a745;}}
            body{{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);max-width:900px;margin:0 auto;padding:20px;}}
            .card{{background:var(--card);padding:20px;border-radius:12px;margin-bottom:16px;box-shadow:0 2px 8px rgba(0,0,0,0.3);}}
            .btn{{padding:10px 16px;border:none;border-radius:8px;cursor:pointer;margin-right:8px;font-size:14px;}}
            .btn-primary{{background:var(--primary);color:white;}}
            .btn-danger{{background:var(--danger);color:white;}}
            .btn-secondary{{background:#6c757d;color:white;}}
            .grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;}}
            .success{{color:var(--success);}}.danger{{color:var(--danger);}}
        </style>
    </head>
    <body>
        <h1>🤖 Claw Gateway 全自动热重载版</h1>
        
        <div class="card">
            <h3>运行状态</h3>
            <div>自动热重载: <span class="success">{'已开启' if CONFIG['AUTO_RELOAD'] else '已关闭'}</span></div>
            <div>当前任务: {last_task or '无'}</div>
            <div>当前模型: {last_model or '无'}</div>
            <div>失败模型: <span class="danger">{failed_list or '无'}</span></div>
            <div>活跃会话: {len(session_locks)}</div>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>任务统计</h3>
                <div>短对话: {task_usage['chat_short']}</div>
                <div>长对话: {task_usage['chat_long']}</div>
                <div>中文: {task_usage['chinese']}</div>
                <div>代码: {task_usage['code']}</div>
                <div>画图: {task_usage['image']}</div>
                <div>视频: {task_usage['video']}</div>
            </div>
            <div class="card">
                <h3>模型统计（含官方RPM）</h3>
                {''.join([f'<div>{m}: {model_usage[m]} 次 (RPM: {MODEL_INFO[m]["rpm"]})</div>' for m in model_usage])}
            </div>
        </div>
        
        <div class="card">
            <h3>操作</h3>
            <button class="btn btn-primary" onclick="fetch('/clear-failed').then(r=>location.reload())">清空失败</button>
            <button class="btn btn-danger" onclick="fetch('/clear-sessions').then(r=>location.reload())">清空会话</button>
            <button class="btn btn-secondary" onclick="fetch('/reload').then(r=>location.reload())">手动重载</button>
            <button class="btn btn-secondary" onclick="location.reload()">刷新</button>
        </div>
    </body>
    </html>
    """

# ==============================================================================
# ======================== 启动 ========================
# ==============================================================================
if __name__ == "__main__":
    import uvicorn
    
    # 启动配置文件自动监控
    observer = None
    if CONFIG["AUTO_RELOAD"]:
        observer = start_file_watcher()
    
    try:
        log(f"网关启动: http://{CONFIG['HOST']}:{CONFIG['PORT']}")
        log(f"管理面板: http://{CONFIG['HOST']}:{CONFIG['PORT']}")
        uvicorn.run(app, host=CONFIG["HOST"], port=CONFIG["PORT"])
    finally:
        if observer:
            observer.stop()
            observer.join()
