"""權限常數與預設角色對應

設計原則:路由檢查的是 permission,不是角色名稱。
新增角色只要調整 ROLE_PERMISSIONS 即可。
"""


class Permission:
    # 測試管理
    TEST_VIEW = "test:view"
    TEST_CREATE = "test:create"
    TEST_UPDATE = "test:update"
    TEST_DELETE = "test:delete"
    TEST_EXECUTE = "test:execute"

    # 報表
    REPORT_VIEW_OWN = "report:view_own"
    REPORT_VIEW_ALL = "report:view_all"
    REPORT_EXPORT = "report:export"

    # 儀表板
    DASHBOARD_VIEW = "dashboard:view"

    # 使用者管理
    USER_VIEW = "user:view"
    USER_MANAGE = "user:manage"

    # 系統
    SYSTEM_CONFIG = "system:config"
    AUDIT_VIEW = "audit:view"


# 預設角色名稱
class Role:
    ADMIN = "admin"
    TE = "TE"                     # Test Engineer
    TE_TEC = "TE_tec"             # TE 技術員
    TEC = "Tec"                   # 技術員
    NORMAL = "normal_user"


# 所有權限列表(seed 時會自動建立)
ALL_PERMISSIONS: list[str] = [
    v for k, v in vars(Permission).items()
    if not k.startswith("_") and isinstance(v, str)
]


# 角色 → 權限對應(初始化資料)
ROLE_PERMISSIONS: dict[str, list[str]] = {
    Role.ADMIN: ALL_PERMISSIONS,  # 全權

    Role.TE: [
        Permission.TEST_VIEW, Permission.TEST_CREATE,
        Permission.TEST_UPDATE, Permission.TEST_DELETE,
        Permission.TEST_EXECUTE,
        Permission.REPORT_VIEW_OWN, Permission.REPORT_VIEW_ALL,
        Permission.REPORT_EXPORT,
        Permission.DASHBOARD_VIEW,
    ],

    Role.TE_TEC: [
        Permission.TEST_VIEW, Permission.TEST_EXECUTE,
        Permission.REPORT_VIEW_OWN, Permission.REPORT_VIEW_ALL,
        Permission.DASHBOARD_VIEW,
    ],

    Role.TEC: [
        Permission.TEST_VIEW, Permission.TEST_EXECUTE,
        Permission.REPORT_VIEW_OWN,
        Permission.DASHBOARD_VIEW,
    ],

    Role.NORMAL: [
        Permission.DASHBOARD_VIEW,
        Permission.REPORT_VIEW_OWN,
    ],
}
