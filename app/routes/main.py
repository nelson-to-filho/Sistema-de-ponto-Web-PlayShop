from flask import Blueprint, redirect, url_for
from flask_login import login_required, current_user

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def index ():
    # I roteador : cada perfil vai para sua area
    if current_user.tipo =="admin":
        return redirect(url_for("admin.dashboard"))

    return redirect(url_for("ponto.dashboard"))