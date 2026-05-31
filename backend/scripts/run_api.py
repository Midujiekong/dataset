#!/usr/bin/env python3
"""
启动评估API服务
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from flask import Flask
from src.api.evaluation import api_bp

def create_app():
    """创建Flask应用"""
    app = Flask(__name__)
    
    # 注册蓝图
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    
    @app.route('/')
    def index():
        return {
            "service": "用例模型质量评估系统",
            "version": "1.0.0",
            "endpoints": {
                "评估用例模型": "POST /api/v1/evaluate",
                "健康检查": "GET /api/v1/health",
                "API文档": "GET /api/v1/docs"
            }
        }
    
    return app

if __name__ == "__main__":
    app = create_app()
    
    print("用例模型质量评估系统 API")
    print("=" * 50)
    print("服务地址: http://127.0.0.1:5000")
    print("API端点: http://127.0.0.1:5000/api/v1/evaluate")
    print("按 Ctrl+C 停止服务")
    print("-" * 50)
    
    app.run(host="127.0.0.1", port=5000, debug=True)