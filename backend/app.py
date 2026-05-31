"""
Flask应用入口文件
"""
import sys
from pathlib import Path

# 将 src 加入路径，以便导入 api、services 等模块
_backend_root = Path(__file__).resolve().parent
_src = _backend_root / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from flask import Flask, send_from_directory
from flask_cors import CORS
from config import Config
from api import api_bp

# 與 backend 同級的臨時實驗前端（純靜態，同源打 /api 無需額外 CORS）
_EXPERIMENT_LAB_DIR = Path(__file__).resolve().parent.parent / "experiment_lab"


def create_app():
    """创建Flask应用"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # 启用CORS
    CORS(app, origins=Config.CORS_ORIGINS)
    
    # 注册蓝图
    app.register_blueprint(api_bp, url_prefix='/api')

    @app.route("/experiment-lab")
    @app.route("/experiment-lab/")
    def experiment_lab_index():
        if not _EXPERIMENT_LAB_DIR.is_dir():
            return (
                "experiment_lab 目录不存在：请在仓库根目录创建 experiment_lab/index.html",
                404,
            )
        return send_from_directory(str(_EXPERIMENT_LAB_DIR), "index.html")

    @app.route("/experiment-lab/<path:name>")
    def experiment_lab_static(name: str):
        if not _EXPERIMENT_LAB_DIR.is_dir():
            return ("", 404)
        return send_from_directory(str(_EXPERIMENT_LAB_DIR), name)
    
    @app.route('/')
    def index():
        return {'message': '用例模型质量评估系统API', 'status': 'running'}
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
