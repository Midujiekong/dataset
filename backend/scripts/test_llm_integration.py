#!/usr/bin/env python3
"""
测试LLM集成功能
"""

import os
import sys
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

def test_deepseek_integration():
    """测试DeepSeek集成"""
    print("测试DeepSeek LLM集成")
    print("=" * 60)
    
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("⚠️  请先设置环境变量 DEEPSEEK_API_KEY")
        print("    export DEEPSEEK_API_KEY='your-api-key'")
        return False
    
    from src.services.evaluator.llm_integration import LLMManager
    
    try:
        llm_manager = LLMManager(provider="deepseek")
        
        test_prompt = "你好，请回复'测试成功'以确认连接正常。"
        
        print("发送测试请求...")
        response = llm_manager.call_with_retry(
            prompt=test_prompt,
            system_prompt="你是一个测试助手。",
            temperature=0.1,
            max_tokens=100
        )
        
        print(f"响应: {response}")
        
        if "测试成功" in response:
            print("✅ DeepSeek集成测试通过！")
            return True
        else:
            print("⚠️  响应不符合预期")
            return False
            
    except Exception as e:
        print(f"❌ DeepSeek集成测试失败: {e}")
        return False

def test_llm_evaluator():
    """测试LLM评估器"""
    print("\n测试LLM评估器")
    print("=" * 60)
    
    from src.services.evaluator.llm_evaluator import LLMEvaluator
    
    try:
        test_diagram = {
            "actors": [
                {"id": "actor1", "name": "用户", "description": "系统用户"}
            ],
            "use_cases": [
                {"id": "uc1", "name": "用户登录", "description": "用户登录系统"}
            ],
            "relationships": [
                {"id": "rel1", "type": "association", "from": "actor1", "to": "uc1"}
            ]
        }
        
        llm_evaluator = LLMEvaluator()
        
        print("1. 测试语义正确性评估...")
        semantic_result = llm_evaluator.evaluate_semantic_correctness(test_diagram)
        print(f"   分数: {semantic_result.get('score', 0):.2%}")
        print(f"   使用LLM: {semantic_result.get('llm_used', False)}")
        
        print("\n2. 测试元素无歧义性评估...")
        ambiguity_result = llm_evaluator.evaluate_element_ambiguity(test_diagram)
        print(f"   分数: {ambiguity_result.get('score', 0):.2%}")
        print(f"   使用LLM: {ambiguity_result.get('llm_used', False)}")
        
        print("\n✅ LLM评估器测试完成")
        return True
        
    except Exception as e:
        print(f"❌ LLM评估器测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("LLM集成测试")
    print("=" * 60)
    
    # 检查环境变量
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("⚠️  提示: 要使用真实LLM，请先设置环境变量:")
        print("    Linux/Mac: export DEEPSEEK_API_KEY='your-api-key'")
        print("    Windows: set DEEPSEEK_API_KEY=your-api-key")
        print("\n将继续运行模拟测试...")
    
    success = True
    
    if api_key:
        success = test_deepseek_integration() and success
    else:
        print("跳过DeepSeek集成测试（未设置API密钥）")
    
    success = test_llm_evaluator() and success
    
    if success:
        print("\n✅ 所有LLM集成测试通过！")
        sys.exit(0)
    else:
        print("\n❌ LLM集成测试失败")
        sys.exit(1)

if __name__ == "__main__":
    main()