import os

from flask import Flask

from app.extensions import db, login_manager


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "limeslake-dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://limeslake:limeslake@127.0.0.1:6130/limeslake",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.board import bp as board_bp
    from app.blueprints.badges import bp as badges_bp
    from app.blueprints.batches import bp as batches_bp
    from app.blueprints.ponds import bp as ponds_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(board_bp)
    app.register_blueprint(badges_bp)
    app.register_blueprint(ponds_bp)
    app.register_blueprint(batches_bp)

    @app.route("/")
    def index():
        from flask import redirect, url_for
        from flask_login import current_user

        if current_user.is_authenticated:
            return redirect(url_for("board.floor_plan"))
        return redirect(url_for("auth.login"))

    return app


def seed_demo_data() -> None:
    from datetime import timedelta

    from app.models import Plant, Pond, ShiftBadge, SlakeBatch, User, utcnow

    def ensure_user(username: str, role: str) -> User:
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, role=role)
            db.session.add(user)
        user.set_password("123456")
        user.role = role
        return user

    admin = ensure_user("admin", "admin")
    worker = ensure_user("worker", "worker")
    worker2 = ensure_user("worker2", "worker")

    if not Plant.query.first():
        plant = Plant(name="东湾石灰厂", location="江北码头侧", notes="熟化池示范厂区")
        db.session.add(plant)
        db.session.flush()

        p1 = Pond(plant=plant, code="P-01", status=Pond.STATUS_SLAKING, capacity_m3=48.0)
        p2 = Pond(plant=plant, code="P-02", status=Pond.STATUS_FILLING, capacity_m3=36.0)
        p3 = Pond(plant=plant, code="P-03", status=Pond.STATUS_DRAWN, capacity_m3=40.0)
        p4 = Pond(plant=plant, code="P-04", status=Pond.STATUS_SLAKING, capacity_m3=42.0)
        p5 = Pond(plant=plant, code="P-05", status=Pond.STATUS_FILLING, capacity_m3=38.0)
        p6 = Pond(plant=plant, code="P-06", status=Pond.STATUS_DRAWN, capacity_m3=44.0)
        db.session.add_all([p1, p2, p3, p4, p5, p6])
        db.session.flush()

        now = utcnow()
        db.session.add_all(
            [
                SlakeBatch(
                    pond=p1,
                    started_at=now - timedelta(hours=6),
                    target_temp_c=85.0,
                    peak_temp_c=72.0,
                    notes="峰值已过，可出灰",
                ),
                SlakeBatch(
                    pond=p2,
                    started_at=now - timedelta(hours=2),
                    target_temp_c=80.0,
                    peak_temp_c=None,
                    notes="注水中，尚未测得峰值",
                ),
                SlakeBatch(
                    pond=p3,
                    started_at=now - timedelta(days=1),
                    target_temp_c=82.0,
                    peak_temp_c=91.0,
                    notes="已出灰批次",
                ),
                SlakeBatch(
                    pond=p4,
                    started_at=now - timedelta(hours=9),
                    target_temp_c=84.0,
                    peak_temp_c=66.0,
                    notes="熟化中段",
                ),
                SlakeBatch(
                    pond=p5,
                    started_at=now - timedelta(hours=1),
                    target_temp_c=80.0,
                    peak_temp_c=None,
                    notes="刚开池注水",
                ),
                SlakeBatch(
                    pond=p6,
                    started_at=now - timedelta(days=2),
                    target_temp_c=83.0,
                    peak_temp_c=88.0,
                    notes="东侧池已出灰",
                ),
            ]
        )
        db.session.flush()

    # 当班码牌种子：熟化中 / 注水中的池各挂一张，唯独留一口熟化中无牌
    if not ShiftBadge.query.first():
        hangers = {"slaking": worker, "filling": worker2}
        ponds = (
            Pond.query.filter(Pond.status.in_([Pond.STATUS_SLAKING, Pond.STATUS_FILLING]))
            .order_by(Pond.code)
            .all()
        )
        slaking_left = [p for p in ponds if p.status == Pond.STATUS_SLAKING]
        skip_id = slaking_left[-1].id if slaking_left else None
        for pond in ponds:
            if pond.id == skip_id:
                continue
            hanger = hangers.get(pond.status, admin)
            db.session.add(ShiftBadge(pond_id=pond.id, hanger_id=hanger.id))

    db.session.commit()
