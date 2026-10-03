"""石灰熟化池业务规则。"""

from __future__ import annotations

from app.extensions import db
from app.models import Pond, ShiftBadge, SlakeBatch, User, utcnow

MIN_PEAK_TEMP_FOR_DRAWN = 60.0


class RuleError(ValueError):
    """业务规则校验失败。"""


def latest_batch_for_pond(pond: Pond) -> SlakeBatch | None:
    if not pond.batches:
        return None
    return max(pond.batches, key=lambda b: b.started_at)


def open_badge_for_pond(pond: Pond) -> ShiftBadge | None:
    """该池当前未摘的当班码牌（最多一张）。"""
    return ShiftBadge.query.filter(
        ShiftBadge.pond_id == pond.id,
        ShiftBadge.removed_at.is_(None),
    ).first()


def can_mark_pond_drawn(pond: Pond) -> tuple[bool, str]:
    """
    熟化池转为「已出灰」(drawn) 的前提：
    最近一条熟化批次的峰值温度已记录，且 >= 60℃。
    """
    latest = latest_batch_for_pond(pond)
    if latest is None:
        return False, "该池尚无熟化批次，不能标记为已出灰"
    if latest.peak_temp_c is None:
        return False, "最近批次尚未记录峰值温度，不能标记为已出灰"
    if latest.peak_temp_c < MIN_PEAK_TEMP_FOR_DRAWN:
        return (
            False,
            f"最近批次峰值温度 {latest.peak_temp_c}℃ 低于 {MIN_PEAK_TEMP_FOR_DRAWN:.0f}℃，不能标记为已出灰",
        )
    return True, ""


def assert_pond_badge_operator(pond: Pond, user: User, action: str) -> None:
    """
    码牌核对：该池须有未摘牌，且当前用户是挂牌人或管理员。
    改池态与登记批次共用同一入口。
    """
    badge = open_badge_for_pond(pond)
    if badge is None:
        raise RuleError(f"{pond.code} 未挂当班码牌，不能{action}；请先到码牌台挂牌")
    if not user.is_admin and badge.hanger_id != user.id:
        raise RuleError(
            f"{pond.code} 的当班码牌由 {badge.hanger.username} 持有，"
            f"只有挂牌人本人或管理员才能{action}"
        )


def assert_can_set_pond_status(pond: Pond, new_status: str, user: User) -> None:
    """改池态统一入口：先核对当班码牌，出灰峰值门槛照旧。"""
    if new_status not in Pond.STATUS_CHOICES:
        raise RuleError(f"无效状态：{new_status}")
    assert_pond_badge_operator(pond, user, "更改池态")
    if new_status == Pond.STATUS_DRAWN:
        ok, msg = can_mark_pond_drawn(pond)
        if not ok:
            raise RuleError(msg)


def hang_badge(pond: Pond, hanger: User, actor: User) -> ShiftBadge:
    """
    挂牌：操作工只能给自己挂牌，管理员可代挂；
    已出灰池禁止新挂；同池已有未摘牌须先摘旧牌。
    并发双挂由数据库唯一索引兜底，冲突时抛 IntegrityError。
    """
    if pond.status == Pond.STATUS_DRAWN:
        raise RuleError(f"{pond.code} 已出灰，禁止新挂牌")
    if not actor.is_admin and hanger.id != actor.id:
        raise RuleError("操作工只能给自己挂牌")
    if open_badge_for_pond(pond) is not None:
        raise RuleError(f"{pond.code} 已有未摘的当班码牌，须先摘旧牌")
    badge = ShiftBadge(pond_id=pond.id, hanger_id=hanger.id)
    db.session.add(badge)
    db.session.commit()
    return badge


def remove_badge(badge: ShiftBadge, actor: User) -> None:
    """摘牌：可由挂牌人本人或管理员。"""
    if badge.removed_at is not None:
        raise RuleError("该码牌已经摘过")
    if not actor.is_admin and badge.hanger_id != actor.id:
        raise RuleError("只有挂牌人本人或管理员才能摘牌")
    badge.removed_at = utcnow()
    db.session.commit()
