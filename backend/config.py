"""
配置文件
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 优先从 backend 目录加载 .env，便于无论从何路径启动都能读到密钥
_backend_dir = Path(__file__).resolve().parent
load_dotenv(_backend_dir / ".env")
load_dotenv()  # 再尝试当前工作目录

class Config:
    """应用配置类"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Flask配置
    DEBUG = os.environ.get('FLASK_DEBUG', 'True') == 'True'
    HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT = int(os.environ.get('FLASK_PORT', 5000))
    
    # CORS配置
    CORS_ORIGINS = ['http://localhost:5173', 'http://localhost:3000']
    
    # 评估配置
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    # 有 DEEPSEEK_API_KEY 时评估与需求抽取会使用 LLM（启动时从 .env 自动加载）
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    # 多智能體：True 時調用多個大模型並聚合結果以提升可信度
    MULTI_AGENT_ENABLED = os.environ.get("MULTI_AGENT_ENABLED", "false").lower() in ("true", "1", "yes")

    # 外部评估平台对接（默认启用，对接 3 Agent 多智能体接口）
    USE_EXTERNAL_EVALUATION = os.environ.get("USE_EXTERNAL_EVALUATION", "true").lower() in ("true", "1", "yes")
    EXTERNAL_EVALUATION_URL = os.environ.get(
        "EXTERNAL_EVALUATION_URL",
        "http://127.0.0.1:5000/uc_model/quality",
    ).strip()
    EXTERNAL_EVALUATION_TIMEOUT = int(os.environ.get("EXTERNAL_EVALUATION_TIMEOUT", "3600"))
    EXTERNAL_EVALUATION_MODE = os.environ.get("EXTERNAL_EVALUATION_MODE", "detailed").strip()
