from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Plant, Pond, ShiftBadge, User
from app.services.rules import RuleError, hang_badge, remove_badge

bp = Blueprint("badges", __name__, url_prefix="/badges")

STATUS_LABELS = {
    Pond.STATUS_FILLING: "注水中",
    Pond.STATUS_SLAKING: "熟化中",
    Pond.STATUS_DRAWN: "已出灰",
}


@bp.route("/")
@login_required
def station():
    open_badges = (
        ShiftBadge.query.filter(ShiftBadge.removed_at.is_(None))
        .join(Pond)
        .join(Plant)
        .order_by(Plant.name, Pond.code)
        .all()
    )
    badged_pond_ids = {badge.pond_id for badge in open_badges}
    ponds = Pond.query.join(Plant).order_by(Plant.name, Pond.code).all()
    users = User.query.order_by(User.username).all()
    return render_template(
        "badges/list.html",
        open_badges=open_badges,
        badged_pond_ids=badged_pond_ids,
        ponds=ponds,
        users=users,
        status_labels=STATUS_LABELS,
    )


@bp.route("/hang", methods=["POST"])
@login_required
def hang():
    pond_id_raw = request.form.get("pond_id") or ""
    pond = db.session.get(Pond, int(pond_id_raw)) if pond_id_raw.isdigit() else None
    if pond is None:
        flash("熟化池不存在或不可挂牌", "error")
        return redirect(url_for("badges.station"))
    if current_user.is_admin:
        hanger_id = int(request.form.get("hanger_id") or current_user.id)
    else:
        hanger_id = current_user.id
    hanger = db.session.get(User, hanger_id)
    if hanger is None:
        flash("挂牌人不存在", "error")
        return redirect(url_for("badges.station"))
    try:
        badge = hang_badge(pond, hanger, current_user)
    except RuleError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    except IntegrityError:
        # 两人同时挂同一池：唯一索引只放行一张，其余在此被挡下
        db.session.rollback()
        flash(f"手慢了：{pond.code} 刚被挂上码牌，同一池只许一张未摘牌", "error")
    else:
        flash(f"已为 {pond.code} 挂上 {badge.hanger.username} 的当班码牌", "ok")
    return redirect(url_for("badges.station"))


@bp.route("/<int:badge_id>/remove", methods=["POST"])
@login_required
def remove(badge_id: int):
    badge = ShiftBadge.query.get_or_404(badge_id)
    try:
        remove_badge(badge, current_user)
    except RuleError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    else:
        flash(f"{badge.pond.code} 的当班码牌已摘", "ok")
    return redirect(url_for("badges.station"))
