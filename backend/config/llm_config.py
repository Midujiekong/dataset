"""
LLM配置
"""

LLM_CONFIG = {
    "default_provider": "deepseek",

    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "temperature": 0.1,
        "max_tokens": 2000,
    },
    
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-3.5-turbo",
        "temperature": 0.1,
        "max_tokens": 2000,
    },
    
    "local": {
        "base_url": "http://localhost:11434/api",
        "model": "qwen:7b",
        "temperature": 0.1,
        "max_tokens": 2000,
    },
    
    "cache": {
        "enabled": True,
        "max_size": 1000,
        "ttl": 3600,
    },
    
    "retry": {
        "max_retries": 3,
        "backoff_factor": 1,
    },
    
    "enabled_evaluations": {
        "semantic_correctness": True,
        "element_unambiguity": True,
        "terminology_consistency": True,
        "use_case_verifiability": True,
        "expression_unambiguity": True,
    }
}