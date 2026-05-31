"""
多智能體評估快速測試
驗證多模型是否正確參與評估
運行：在 backend 目錄下執行  python scripts/test_multi_agent.py
"""
import os
import sys
from pathlib import Path

_backend = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_backend / "src"))
try:
    from dotenv import load_dotenv
    load_dotenv(_backend / ".env")
except ImportError:
    pass

TEST_MSG = [{"role": "user", "content": "回覆「收到」"}]


def _quick_connectivity_check():
    """與 check_api_keys 相同的連線測試，確認當前網路可達"""
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        return False, "DEEPSEEK_API_KEY 未設置"
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.deepseek.com", timeout=30)
        client.chat.completions.create(model="deepseek-chat", messages=TEST_MSG)
        return True, None
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 50)
    print("多智能體評估測試")
    print("=" * 50)

    # 0. 連線預檢（與 check_api_keys 相同邏輯）
    print("\n[0] 連線預檢...")
    ok, err = _quick_connectivity_check()
    if not ok:
        print(f"✗ 連線失敗: {err}")
        print("\n請先執行: python scripts/check_api_keys.py")
        print("若 check_api_keys 也失敗，可能是：")
        print("  - 網路不穩定或需 VPN")
        print("  - 需設置代理: set HTTP_PROXY=... HTTPS_PROXY=...")
        print("  - 防火牆阻擋對 api.deepseek.com 的訪問")
        return 1
    print("✓ 連線正常")

    # 1. 檢查多智能體是否啟用
    from services.evaluator.evaluation_service import EvaluationService
    svc = EvaluationService(use_llm=True)
    eng = svc.evaluation_engine
    metrics = eng.metrics

    if not metrics.llm_evaluator:
        print("\n✗ LLM 未啟用（請確認 DEEPSEEK_API_KEY 等已設置）")
        return 1

    ev = metrics.llm_evaluator
    if not hasattr(ev, "evaluators"):
        print("\n✓ 單一 LLM 模式（非多智能體）")
        return 0

    count = len(ev.evaluators)
    models = [e.llm_manager.provider.get_model_name() for e in ev.evaluators]
    print(f"\n已載入 {count} 個模型: {', '.join(models)}")

    if count < 2:
        print("\n⚠ 多智能體需至少 2 個模型，請在 .env 配置更多 API Key")
        return 1

    # 2. 執行最小評估（會觸發 LLM 調用）
    print("\n執行最小評估（約 30–60 秒）...")
    minimal_input = {
        "use_case_diagram": {
            "actors": [{"id": "a1", "name": "用戶"}],
            "use_cases": [{"id": "uc1", "name": "登入系統"}],
            "relationships": [
                {"id": "r1", "type": "association", "from": "a1", "to": "uc1"}
            ],
        },
        "use_case_descriptions": [],
        "requirements": {
            "roles": [{"name": "用戶"}],
            "functional_requirements": [{"text": "用戶登入系統"}],
            "expected_relationships": [],
        },
    }

    try:
        report = svc.evaluate(minimal_input)
        print("✓ 評估完成")

        # 檢查評估結果中是否有多模型參與
        def find_agents(d, depth=0):
            if depth > 5:
                return
            if isinstance(d, dict):
                if "agent_results" in d:
                    ar = d["agent_results"]
                    if ar:
                        providers = [a.get("provider", "?") for a in ar]
                        print(f"\n  參與模型: {providers}")
                if "agents_used" in d:
                    print(f"  使用模型數: {d['agents_used']}")
                for v in d.values():
                    find_agents(v, depth + 1)
            elif isinstance(d, list):
                for x in d:
                    find_agents(x, depth + 1)

        find_agents(report)
        print("\n" + "=" * 50)
        print("✓ 多智能體評估正常")
        return 0
    except Exception as e:
        print(f"\n✗ 評估失敗: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
