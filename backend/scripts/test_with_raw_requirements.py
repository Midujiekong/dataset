# scripts/test_with_raw_requirements.py
#!/usr/bin/env python3
"""
测试基于原始需求文本的评估流程
先抽取需求，再传入评估引擎
"""
import sys
import json
from pathlib import Path

# 添加项目根目录到 sys.path
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from src.services.evaluator import EvaluationService
from src.services.evaluator.requirements_parser import extract_structured_requirements

def build_sample_diagram():
    """构建示例用例图（与之前相同）"""
    return {
        "actors": [
            {"id": "actor_student", "name": "学员", "description": "购买课程并学习的人"},
            {"id": "actor_instructor", "name": "讲师", "description": "发布课程的人"},
            {"id": "actor_admin", "name": "管理员", "description": "审核课程的人"},
            {"id": "actor_payment", "name": "支付平台", "description": "第三方支付服务"}
        ],
        "use_cases": [
            {"id": "uc_register", "name": "注册", "description": "新用户注册账号"},
            {"id": "uc_login", "name": "登录", "description": "用户登录系统"},
            {"id": "uc_browse", "name": "浏览课程", "description": "浏览课程列表和详情"},
            {"id": "uc_purchase", "name": "购买课程", "description": "购买课程并支付"},
            {"id": "uc_watch", "name": "观看课程", "description": "观看已购课程视频"},
            {"id": "uc_refund", "name": "申请退款", "description": "在规定时间内申请退款"},
            {"id": "uc_publish", "name": "发布课程", "description": "讲师发布新课程"},
            {"id": "uc_review", "name": "审核课程", "description": "管理员审核课程上架"},
            {"id": "uc_pay", "name": "支付订单", "description": "调用支付平台完成支付"},
            {"id": "uc_refund_payment", "name": "原路退款", "description": "调用支付平台退款"},
            {"id": "uc_process", "name": "处理数据", "description": "处理系统数据"},          # 模糊名称
            {"id": "uc_export", "name": "导出报表", "description": "导出平台数据报表"}        # 冗余用例
        ],
        "relationships": [
            # 正确的关联关系
            {"id": "rel1", "type": "association", "from": "actor_student", "to": "uc_register"},
            {"id": "rel2", "type": "association", "from": "actor_student", "to": "uc_login"},
            {"id": "rel3", "type": "association", "from": "actor_student", "to": "uc_browse"},
            {"id": "rel4", "type": "association", "from": "actor_student", "to": "uc_purchase"},
            {"id": "rel5", "type": "association", "from": "actor_student", "to": "uc_watch"},
            {"id": "rel6", "type": "association", "from": "actor_student", "to": "uc_refund"},
            {"id": "rel7", "type": "association", "from": "actor_instructor", "to": "uc_publish"},
            {"id": "rel8", "type": "association", "from": "actor_admin", "to": "uc_review"},
            {"id": "rel9", "type": "association", "from": "actor_payment", "to": "uc_pay"},
            {"id": "rel10", "type": "association", "from": "actor_payment", "to": "uc_refund_payment"},
            # include 关系
            {"id": "rel11", "type": "include", "from": "uc_purchase", "to": "uc_pay"},
            {"id": "rel12", "type": "include", "from": "uc_refund", "to": "uc_refund_payment"},
            # extend 指向不存在的用例（故意制造问题）
            {"id": "rel13", "type": "extend", "from": "uc_login", "to": "nonexistent_uc", "description": "如果用户忘记密码"},
            # 语法错误的关系
            {"id": "rel14", "type": "include", "from": "actor_student", "to": "uc_process"},
            {"id": "rel15", "type": "association", "from": "uc_publish", "to": "uc_review"},
            # 冗余关系
            {"id": "rel16", "type": "association", "from": "actor_admin", "to": "uc_export"},
        ],
        "system_boundary": True
    }

def main():
    # 原始需求文本（来自 sample_requirements_raw_v2.md）
    raw_requirements = """
## 线上课程平台（需求原文草稿 v2）

这是一份来自产品经理的需求草稿，内容包含口语化描述、零散约束、以及部分半结构化条目（并不完全规范）。

### 1. 背景与范围
我们要做一个「线上课程平台」，主要面向学员购买课程并学习。讲师可以发布课程，管理员负责审核与运营配置。

### 2. 角色（可能的叫法不一致）
- 学员：购买课程并学习的人，有时也被称为“用户”
- 讲师：发布课程、管理自己课程内容的人
- 管理员：运营人员，负责审核课程、处理举报
- 支付平台：第三方支付服务（例如微信/支付宝等），用于收款与退款

### 3. 功能需求（混合表达）
1) 账号相关
- 新用户需要能注册；注册后才能购买课程。
- 登录：用户用手机号+验证码 或 账号密码都行（两种方式二选一实现也可以，优先手机号验证码）。

2) 课程浏览与购买
- 学员可以浏览课程列表、按关键字搜索课程、查看课程详情页（简介、价格、讲师、目录）。
- 购买课程：学员在课程详情页点击购买后进入结算。
  - 结算时系统需要创建订单并调用支付平台完成支付。
  - 如果学员输入了有效优惠券，就要在结算时抵扣金额；如果没有优惠券就按原价结算。
  - 支付成功后，系统给学员开通该课程的学习权限，并在“我的课程”中可见。

3) 学习与进度
- 学员可以观看已购买课程的视频；观看进度要自动保存（比如看到了第 10 分钟）。
- 学员可以在我的课程里继续上次进度继续播放。

4) 讲师侧
- 讲师可以发布课程（标题、封面、简介、价格、章节目录、视频上传）。
- 课程发布后需要管理员审核通过，才能对外上架展示。

5) 售后与退款
- 学员在购买后 24 小时内可以申请退款（前提：观看时长不超过 10 分钟）。
- 退款需要调用支付平台原路退回，退款成功后需要回收课程学习权限。

### 4. 约束与说明（零散）
- “快速”“友好”等体验类要求目前先不评估为用例。
- 术语可能混用：学员/用户、购买/下单、优惠券/折扣码。
- 退款条件里提到的“观看时长”从哪里拿：就用观看进度即可。
"""

    # 构建用例图
    diagram = build_sample_diagram()
    
    print("=" * 80)
    print("开始评估测试")
    print("需求文本长度:", len(raw_requirements))
    print("用例图统计:")
    print(f"  参与者: {len(diagram['actors'])}")
    print(f"  用例: {len(diagram['use_cases'])}")
    print(f"  关系: {len(diagram['relationships'])}")
    print("=" * 80)

    # 1. 抽取结构化需求（不使用LLM，用规则抽取）
    structured_req = extract_structured_requirements(raw_requirements, use_llm=False)
    
    # 打印抽取结果预览
    print("\n抽取的需求角色：", [r["name"] for r in structured_req.get("roles", [])])
    print("抽取的功能需求（前5条）：")
    for fr in structured_req.get("functional_requirements", [])[:5]:
        print(f"  {fr['id']}: {fr['text'][:50]}...")
    print("-" * 40)

    # 2. 构造输入数据并评估
    service = EvaluationService()
    input_data = {
        "use_case_diagram": diagram,
        "use_case_descriptions": [],
        "requirements": structured_req
    }
    
    try:
        result = service.evaluate(input_data)
        
        print("\n评估结果概要:")
        print(f"  用例图总体分数: {result.get('diagram_metrics', {}).get('overall_score', 0):.2%}")
        print(f"  综合总体分数: {result.get('overall_score', 0):.2%}")
        
        recommendations = result.get('recommendations', [])
        if recommendations:
            print("\n改进建议（前5条）:")
            for i, rec in enumerate(recommendations[:5], 1):
                print(f"  {i}. {rec}")
        
        # 保存完整结果
        output_file = "evaluation_result_with_raw_requirements.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n完整结果已保存至: {output_file}")
        
    except Exception as e:
        print(f"评估过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()