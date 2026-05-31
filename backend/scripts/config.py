"""
测试配置文件
"""
TEST_DIAGRAM = {
    "actors": [
        {"id": "actor1", "name": "用户"},
        {"id": "actor2", "name": "管理员"},
        {"id": "actor3", "name": "VIP用户"},
        {"id": "actor4", "name": "访客"},
    ],
    "use_cases": [
        {"id": "uc1", "name": "用户登录"},
        {"id": "uc2", "name": "验证密码"},
        {"id": "uc3", "name": "忘记密码"},
        {"id": "uc4", "name": "管理用户"},
        {"id": "uc5", "name": "查看报告"},
        {"id": "uc6", "name": "生成报表"},
    ],
    "relationships": [
        {"id": "rel1", "type": "association", "from": "actor1", "to": "uc1"},
        {"id": "rel2", "type": "association", "from": "actor2", "to": "uc4"},
        {"id": "rel3", "type": "association", "from": "actor3", "to": "uc1"},
        {"id": "rel4", "type": "association", "from": "actor4", "to": "uc1"},
        
        {"id": "rel5", "type": "include", "from": "uc1", "to": "uc2"},
        {"id": "rel6", "type": "extend", "from": "uc1", "to": "uc3"},
        
        {"id": "rel7", "type": "generalization", "from": "actor3", "to": "actor1"},
        
        {"id": "rel8", "type": "include", "from": "actor1", "to": "uc2"},  # 参与者不能有include
        {"id": "rel9", "type": "association", "from": "uc1", "to": "uc4"},  # 用例间不能关联
        {"id": "rel10", "type": "generalization", "from": "actor1", "to": "uc1"},  # 不同类型不能泛化
    ],
    "system_boundary": True
}

TEST_REQUIREMENTS = {
    "roles": [
        {"name": "用户"},
        {"name": "管理员"},
        {"name": "VIP用户"},
    ],
    "functional_requirements": [
        {"text": "用户能够登录系统"},
        {"text": "系统应该验证用户密码"},
        {"text": "用户忘记密码时可以重置"},
        {"text": "管理员可以管理用户账户"},
        {"text": "用户可以查看报告"},
        {"text": "系统可以生成报表"},
    ],
    "expected_relationships": [
        {"role": "用户", "function": "用户登录", "type": "association"},
        {"role": "管理员", "function": "管理用户", "type": "association"},
        {"role": "VIP用户", "function": "用户登录", "type": "association"},
        {"role": "用户", "function": "查看报告", "type": "association"},
    ],
    "terms": [
        {"term": "用户", "description": "使用系统的普通用户"},
        {"term": "管理员", "description": "具有管理权限的用户"},
        {"term": "VIP用户", "description": "付费的特殊用户"},
        {"term": "登录", "description": "验证身份进入系统"},
        {"term": "验证", "description": "检查信息的正确性"},
        {"term": "管理", "description": "对资源进行管理操作"},
        {"term": "报告", "description": "系统生成的数据汇总"},
    ]
}