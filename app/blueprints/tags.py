"""码牌台：当班码牌的现行列表、挂牌与摘牌。"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Plant, Pond, ShiftTag, User
from app.services.rules import (
    RuleError,
    hang_tag,
    is_admin,
    remove_tag,
)

bp = Blueprint("tags", __name__, url_prefix="/tags")


@bp.route("/")
@login_required
def board():
    active_tags = (
        ShiftTag.query.filter(ShiftTag.removed_at.is_(None))
        .join(Pond)
        .join(Plant)
        .order_by(Plant.name, Pond.code)
        .all()
    )
    # 可挂牌的池：当前没有未摘牌（已出灰池的旧牌摘除后也可重挂开启下一周期）。
    hangable = [
        pond
        for pond in Pond.query.join(Plant)
        .order_by(Plant.name, Pond.code)
        .all()
        if pond.active_tag is None
    ]
    holders = User.query.order_by(User.username).all()
    return render_template(
        "tags/board.html",
        active_tags=active_tags,
        hangable=hangable,
        holders=holders,
    )


@bp.route("/hang", methods=["POST"])
@login_required
def hang():
    pond_id = request.form.get("pond_id", type=int)
    pond = db.session.get(Pond, pond_id) if pond_id else None
    if pond is None:
        flash("请选择要挂牌的熟化池", "error")
        return redirect(url_for("tags.board"))

    # 操作工只能给自己挂牌；管理员可代任何人挂（默认自己）。
    if is_admin(current_user):
        holder_id = request.form.get("holder_id", type=int) or current_user.id
        holder = db.session.get(User, holder_id)
        if holder is None:
            flash("所选挂牌人不存在", "error")
            return redirect(url_for("tags.board"))
    else:
        holder = current_user

    try:
        hang_tag(pond, current_user, holder)
        db.session.commit()
    except RuleError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    except IntegrityError:
        # 两名操作工并发抢同一池：数据库的部分唯一索引只放一张。
        db.session.rollback()
        winner = (
            ShiftTag.query.filter_by(pond_id=pond.id)
            .filter(ShiftTag.removed_at.is_(None))
            .first()
        )
        if winner is not None:
            flash(
                f"手慢一步：{pond.code} 已被 {winner.holder.username} 抢先挂牌，"
                "同一池未摘牌最多一张",
                "error",
            )
        else:
            flash(f"{pond.code} 挂牌未成功，请重试", "error")
    else:
        flash(f"已为 {pond.code} 挂上 {holder.username} 的当班码牌", "ok")
    return redirect(url_for("tags.board"))


@bp.route("/<int:tag_id>/remove", methods=["POST"])
@login_required
def remove(tag_id: int):
    tag = ShiftTag.query.get_or_404(tag_id)
    pond_code = tag.pond.code
    try:
        remove_tag(tag, current_user)
        db.session.commit()
    except RuleError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    else:
        flash(f"已摘除 {pond_code} 的当班码牌", "ok")
    return redirect(url_for("tags.board"))
