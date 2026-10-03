"""石灰熟化池业务规则。"""

from __future__ import annotations

from flask_login import UserMixin

from app.extensions import db
from app.models import Pond, ShiftTag, SlakeBatch, utcnow

MIN_PEAK_TEMP_FOR_DRAWN = 60.0


class RuleError(ValueError):
    """业务规则校验失败。"""


def latest_batch_for_pond(pond: Pond) -> SlakeBatch | None:
    if not pond.batches:
        return None
    return max(pond.batches, key=lambda b: b.started_at)


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


def assert_can_set_pond_status(pond: Pond, new_status: str) -> None:
    if new_status not in Pond.STATUS_CHOICES:
        raise RuleError(f"无效状态：{new_status}")
    if new_status == Pond.STATUS_DRAWN:
        ok, msg = can_mark_pond_drawn(pond)
        if not ok:
            raise RuleError(msg)


# ---------------------------------------------------------------------------
# 当班码牌
# ---------------------------------------------------------------------------

def is_admin(user: UserMixin) -> bool:
    return bool(getattr(user, "is_admin", False))


def assert_can_hang_tag(pond: Pond, user: UserMixin, holder: UserMixin) -> None:
    """挂牌前核对：旧牌须已摘除；已出灰池须先摘旧牌才能重挂；代挂须管理员。"""
    active = pond.active_tag
    if active is not None:
        if pond.status == Pond.STATUS_DRAWN:
            raise RuleError("该池已出灰，禁止新挂；请先由挂牌人本人或管理员摘除旧牌")
        raise RuleError(
            f"该池已有 {active.holder.username} 的未摘码牌，同一池未摘牌最多一张"
        )
    if holder.id != user.id and not is_admin(user):
        raise RuleError("操作工只能为自己挂牌，不能代他人挂牌")


def hang_tag(pond: Pond, user: UserMixin, holder: UserMixin) -> ShiftTag:
    """构造并写入一张码牌（不提交，提交由调用方负责以兜住并发冲突）。"""
    assert_can_hang_tag(pond, user, holder)
    tag = ShiftTag(pond_id=pond.id, holder_id=holder.id, hung_at=utcnow())
    db.session.add(tag)
    return tag


def assert_can_remove_tag(tag: ShiftTag, user: UserMixin) -> None:
    if tag.removed_at is not None:
        raise RuleError("该码牌已摘除，无需重复摘牌")
    if tag.holder_id != user.id and not is_admin(user):
        raise RuleError("仅挂牌人本人或管理员可摘牌")


def remove_tag(tag: ShiftTag, user: UserMixin) -> None:
    assert_can_remove_tag(tag, user)
    tag.removed_at = utcnow()


def assert_pond_operable(pond: Pond, user: UserMixin, action: str) -> ShiftTag:
    """
    改池态 / 登记批次的统一入口核对：
    该池须有未摘牌，且当前登录用户是挂牌人本人或管理员。
    通过则返回现行码牌，否则抛中文 RuleError。
    """
    tag = pond.active_tag
    if tag is None:
        raise RuleError(f"该池当前没有未摘码牌，不能{action}；请先到码牌台挂牌")
    if tag.holder_id != user.id and not is_admin(user):
        raise RuleError(
            f"该池码牌由 {tag.holder.username} 挂出，"
            f"只有挂牌人本人或管理员能{action}"
        )
    return tag
