from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatusMatch:
    event: str
    suggested_status: str
    confidence: str
    priority: int
    legal_status_update: bool = True
    needs_confirmation: bool = False


RULES: list[tuple[tuple[str, ...], StatusMatch]] = [
    (
        ("驳回决定通知书", "驳回决定", "驳回"),
        StatusMatch("驳回决定通知书", "驳回", "高", 100),
    ),
    (
        ("发明专利证书", "专利证书", "证书(签章)", "证书（签章）"),
        StatusMatch("专利证书", "授权", "高", 90),
    ),
    (
        ("专利申请受理通知书", "专利受理通知书转达", "受理通知书"),
        StatusMatch("专利申请受理通知书", "受理", "高", 80),
    ),
    (
        ("办理登记手续通知书",),
        StatusMatch(
            "办理登记手续通知书",
            "待登记/办理登记手续",
            "高",
            70,
            needs_confirmation=True,
        ),
    ),
    (
        ("收费减缴审批通知书",),
        StatusMatch(
            "收费减缴审批通知书",
            "费减审批通过/收费减缴",
            "中",
            60,
            legal_status_update=False,
            needs_confirmation=True,
        ),
    ),
    (
        ("补正通知书", "补正"),
        StatusMatch("补正通知书", "补正", "高", 50, needs_confirmation=True),
    ),
    (
        ("审查意见通知书", "第一次审查意见", "第二次审查意见", "审查意见"),
        StatusMatch("审查意见通知书", "审查意见", "高", 40, needs_confirmation=True),
    ),
    (
        ("缴费通知书", "缴纳年费", "缴费"),
        StatusMatch(
            "缴费通知",
            "缴费通知",
            "中",
            30,
            legal_status_update=False,
            needs_confirmation=True,
        ),
    ),
]


def detect_status(text: str) -> StatusMatch | None:
    candidates: list[StatusMatch] = []
    for keywords, match in RULES:
        if any(keyword in text for keyword in keywords):
            candidates.append(match)
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.priority, reverse=True)[0]

