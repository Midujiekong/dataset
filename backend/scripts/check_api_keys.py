"""
API 密鑰診斷腳本
逐一測試 DeepSeek、通義千問、智譜、Moonshot(Kimi) 的 API Key 是否有效
運行：在 backend 目錄下執行  python scripts/check_api_keys.py
"""
import os
import sys
from pathlib import Path

# 確保能載入 .env 和 src 模組
_backend = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_backend / "src"))
try:
    from dotenv import load_dotenv
    load_dotenv(_backend / ".env")
except ImportError:
    pass

# 測試用的簡單消息
TEST_MSG = [{"role": "user", "content": "回覆「收到」即可"}]


def test_deepseek():
    """測試 DeepSeek API"""
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        return "未設置", None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.deepseek.com", timeout=30)
        r = client.chat.completions.create(model="deepseek-chat", messages=TEST_MSG)
        return "成功", r.choices[0].message.content[:50] if r.choices else ""
    except Exception as e:
        return "失敗", str(e)


def test_qwen():
    """測試通義千問 API"""
    key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not key:
        return "未設置", None
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            timeout=30,
        )
        r = client.chat.completions.create(model="qwen-plus", messages=TEST_MSG)
        return "成功", r.choices[0].message.content[:50] if r.choices else ""
    except Exception as e:
        return "失敗", str(e)


def test_zhipu():
    """測試智譜 API"""
    key = os.getenv("ZHIPUAI_API_KEY", "").strip()
    if not key:
        return "未設置", None
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=key,
            base_url="https://open.bigmodel.cn/api/paas/v4",
            timeout=30,
        )
        r = client.chat.completions.create(model="glm-5", messages=TEST_MSG)
        return "成功", r.choices[0].message.content[:50] if r.choices else ""
    except Exception as e:
        return "失敗", str(e)


def test_moonshot():
    """測試 Moonshot (Kimi) API"""
    key = os.getenv("MOONSHOT_API_KEY", "").strip()
    if not key:
        return "未設置", None
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=key,
            base_url="https://api.moonshot.cn/v1",
            timeout=30,
        )
        r = client.chat.completions.create(model="moonshot-v1-8k", messages=TEST_MSG)
        return "成功", r.choices[0].message.content[:50] if r.choices else ""
    except Exception as e:
        return "失敗", str(e)


def main():
    print("=" * 50)
    print("API 密鑰診斷")
    print("=" * 50)

    # 顯示 Key 前幾位（不暴露完整密鑰）
    def mask(k):
        return f"{k[:8]}...{k[-4:]}" if k and len(k) > 12 else "(空)"

    ds = os.getenv("DEEPSEEK_API_KEY", "").strip()
    qw = os.getenv("DASHSCOPE_API_KEY", "").strip()
    zp = os.getenv("ZHIPUAI_API_KEY", "").strip()
    ms = os.getenv("MOONSHOT_API_KEY", "").strip()

    print(f"\nDEEPSEEK_API_KEY:   {mask(ds) if ds else '(未設置)'}")
    print(f"DASHSCOPE_API_KEY:  {mask(qw) if qw else '(未設置)'}")
    print(f"ZHIPUAI_API_KEY:    {mask(zp) if zp else '(未設置)'}")
    print(f"MOONSHOT_API_KEY:   {mask(ms) if ms else '(未設置)'}")
    print()

    results = []
    for name, fn in [
        ("DeepSeek", test_deepseek),
        ("通義千問", test_qwen),
        ("智譜", test_zhipu),
        ("Moonshot(Kimi)", test_moonshot),
    ]:
        status, detail = fn()
        results.append((name, status, detail))
        icon = "✓" if status == "成功" else "✗"
        print(f"  {icon} {name}: {status}")
        if detail:
            print(f"      {detail[:80]}{'...' if len(str(detail)) > 80 else ''}")
        print()

    ok = sum(1 for _, s, _ in results if s == "成功")
    total = len(results)
    print("=" * 50)
    print(f"結果: {ok}/{total} 個密鑰可用")
    if ok >= 2:
        print("\n✓ 多智能體可用（至少 2 個模型）")
    if ok < total:
        print("\n若某密鑰失敗，請檢查：")
        print("  1. 密鑰是否從對應平台正確複製（無多餘空格）")
        print("  2. 通義千問：阿里雲百煉 https://dashscope.console.aliyun.com/")
        print("  3. 智譜：智譜開放平台 https://open.bigmodel.cn/")
        print("  4. Moonshot：https://platform.moonshot.cn/console/account")
    print("=" * 50)


if __name__ == "__main__":
    main()
