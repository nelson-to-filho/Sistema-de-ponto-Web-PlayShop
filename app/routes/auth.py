from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import  check_password_hash

from app.models import Usuario

auth_bp =  Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        # Se já está logado, redireciona por perfil
        if current_user.tipo == "admin":
            return redirect(url_for("main.home"))
        return redirect(url_for("main.home"))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        user = Usuario.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.senha_hash, senha):
            flash("Email ou senha inválidos.", "error")
            return render_template("login.html")
        
        if not user.ativo:
            flash("Usuário inativo. Contate o administrador.", "error")
            return render_template("login.html")
        
        login_user(user)
        
        # Redirecionamento pós-login (vamos aprimorar depois)

        next_page = request.args.get("next")
        if next_page:
            return redirect(next_page)
        if user.tipo == "admin":
            return redirect(url_for("main.index"))
        return redirect(url_for("main.index"))
    
    return render_template("login.html")

   

  


@auth_bp.route("/logout")   
@login_required
def logout():
    logout_user()
    flash("Você saiu com sucesso.", "success")
    return redirect(url_for("auth.login"))