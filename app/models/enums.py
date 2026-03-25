import enum


class UserRoleEnum(str, enum.Enum):
    MAIN_ADMIN = "org_main_admin"
    DEPARTMENT_ADMIN = "department_admin"
    DEPARTMENT_EMPLOYEE = "department_employee"
    REPORTER = "reporter"


class IssueStatusEnum(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class PriorityLevelEnum(str, enum.Enum):
    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"
