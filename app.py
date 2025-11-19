import os
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.abspath(os.path.dirname(__file__))

LOCAL_OFFSET = timedelta(hours=4)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "data.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    drawings = db.relationship("Drawing", backref="owner", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Drawing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    image_data = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Пожалуйста, войдите в систему для доступа к этой странице.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


@app.context_processor
def inject_globals():
    return {"current_year": datetime.utcnow().year}


@app.template_filter("local_dt")
def local_dt(value, fmt="%d.%m.%Y %H:%M"):
    if not value:
        return ""
    return (value + LOCAL_OFFSET).strftime(fmt)


def iso_local(dt: datetime) -> str:
    return (dt + LOCAL_OFFSET).isoformat()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if not username or not password or not password_confirm:
            flash("Все поля обязательны для заполнения.", "danger")
            return render_template("register.html")

        if len(password) < 6:
            flash("Пароль должен содержать не менее 6 символов.", "danger")
            return render_template("register.html")

        if password != password_confirm:
            flash("Пароли не совпадают.", "danger")
            return render_template("register.html")

        if User.query.filter_by(username=username).first():
            flash("Пользователь с таким именем уже существует.", "danger")
            return render_template("register.html")

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        session["user_id"] = user.id
        session["username"] = user.username
        flash("Регистрация прошла успешно!", "success")
        return redirect(url_for("studio"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            flash("Добро пожаловать!", "success")
            return redirect(url_for("studio"))

        flash("Неверное имя пользователя или пароль.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("index"))


@app.route("/studio", defaults={"drawing_id": None})
@app.route("/studio/<int:drawing_id>")
@login_required
def studio(drawing_id):
    drawing = None
    if drawing_id is not None:
        drawing = Drawing.query.filter_by(id=drawing_id, user_id=session["user_id"]).first_or_404()
    return render_template("studio.html", drawing=drawing)


@app.route("/profile")
@login_required
def profile():
    drawings = (
        Drawing.query.filter_by(user_id=session["user_id"])
        .order_by(Drawing.created_at.desc())
        .all()
    )
    return render_template("profile.html", drawings=drawings)


@app.post("/api/save_drawing")
@login_required
def save_drawing():
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "Без названия").strip() or "Без названия"
    image_data = payload.get("imageData")

    if not image_data or not image_data.startswith("data:image/png;base64,"):
        return jsonify({"error": "Неверные данные рисунка."}), 400

    drawing = Drawing(title=title, image_data=image_data, user_id=session["user_id"])
    db.session.add(drawing)
    db.session.commit()

    return jsonify(
        {
            "message": "Рисунок сохранён.",
            "drawingId": drawing.id,
            "createdAt": iso_local(drawing.created_at),
        }
    )


@app.put("/api/drawings/<int:drawing_id>")
@login_required
def update_drawing(drawing_id):
    drawing = Drawing.query.filter_by(id=drawing_id, user_id=session["user_id"]).first_or_404()
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "Без названия").strip() or "Без названия"
    image_data = payload.get("imageData")

    if not image_data or not image_data.startswith("data:image/png;base64,"):
        return jsonify({"error": "Неверные данные рисунка."}), 400

    drawing.title = title
    drawing.image_data = image_data
    db.session.commit()

    return jsonify(
        {
            "message": "Рисунок обновлён.",
            "drawingId": drawing.id,
            "updatedAt": iso_local(drawing.created_at),
        }
    )


@app.get("/api/drawings")
@login_required
def get_drawings():
    drawings = (
        Drawing.query.filter_by(user_id=session["user_id"])
        .order_by(Drawing.created_at.desc())
        .all()
    )


@app.delete("/api/drawings/<int:drawing_id>")
@login_required
def delete_drawing(drawing_id):
    drawing = Drawing.query.filter_by(id=drawing_id, user_id=session["user_id"]).first_or_404()
    db.session.delete(drawing)
    db.session.commit()
    return jsonify({"message": "Рисунок удалён."})
    return jsonify(
        [
            {
                "id": drawing.id,
                "title": drawing.title,
                "imageData": drawing.image_data,
                "createdAt": iso_local(drawing.created_at),
            }
            for drawing in drawings
        ]
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
