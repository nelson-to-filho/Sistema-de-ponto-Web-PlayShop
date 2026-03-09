from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user, logout_user
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import pytz

from app import db
from app.models import Funcionario, Ponto, DiaTrabalho
from app.services.ponto_calc import calcular_e_atualizar_dia

ponto_bp = Blueprint("ponto", __name__, url_prefix="/ponto")

def _get_funcionario_or_logout():
    """
    Garante que um usuário do tipo 'funcionario' tenha registro em Funcionario.
    Se não tiver, evita crash e força logout com mensagem.
    """
    funcionario = Funcionario.query.get(current_user.id)
    if not funcionario:
        flash("Seu usuário não está vinculado a um cadastro de funcionário. Contate o administrador.", "error")
        logout_user()
        return None
    return funcionario

def _saldo_mensal_minutos(funcionario: Funcionario, ref_dia: date) -> int:
    """
    Soma o saldo_minutos no mês de ref_dia, considerando apenas dias completos.
    Retorna saldo em minutos (pode ser negativo).
    """
    inicio_mes = date(ref_dia.year, ref_dia.month, 1)

    # próximo mês
    if ref_dia.month == 12:
        inicio_prox = date(ref_dia.year + 1, 1, 1)
    else:
        inicio_prox = date(ref_dia.year, ref_dia.month + 1, 1)

    dias = (
        DiaTrabalho.query
        .filter(
            DiaTrabalho.funcionario_id == funcionario.id,
            DiaTrabalho.data >= inicio_mes,
            DiaTrabalho.data < inicio_prox,
            DiaTrabalho.status == "completo",
        )
        .all()
    )

    return sum((d.saldo_minutos or 0) for d in dias)




@ponto_bp.route("/")
@login_required
def dashboard():
    # Segurança: só funcionário acessa
    if current_user.tipo != "funcionario":
        return render_template("403.html"), 403

    funcionario = _get_funcionario_or_logout()
    if not funcionario:
        return redirect(url_for("auth.login"))

    hoje = agora.date()

    pontos_dia = (
        Ponto.query
        .filter_by(funcionario_id=funcionario.id, data=hoje)
        .order_by(Ponto.hora.asc())
        .all()
    )

    dia_trabalho = (
        DiaTrabalho.query
        .filter_by(funcionario_id=funcionario.id, data=hoje)
        .first()
    )

    saldo_mes = _saldo_mensal_minutos(funcionario, hoje)


    return render_template(
        "ponto/dashboard.html",
        hoje=hoje,
        pontos_dia=pontos_dia,
        dia_trabalho=dia_trabalho,
        saldo_mes=saldo_mes,
    )


@ponto_bp.route("/bater/<tipo>", methods=["POST"])
@login_required
def bater_ponto(tipo: str):
    # Segurança: só funcionário acessa
    if current_user.tipo != "funcionario":
        return render_template("403.html"), 403

    TIPOS_VALIDOS = {"entrada", "intervalo_inicio", "intervalo_fim", "saida"}
    if tipo not in TIPOS_VALIDOS:
        flash("Tipo de ponto inválido.", "error")
        return redirect(url_for("ponto.dashboard"))

    funcionario = _get_funcionario_or_logout()
    if not funcionario:
        return redirect(url_for("auth.login"))


    hoje = date.today()

    # Regras básicas de sequência (MVP)
    if tipo == "saida":
        existe_entrada = Ponto.query.filter_by(
            funcionario_id=funcionario.id,
            data=hoje,
            tipo="entrada"
        ).first()
        if not existe_entrada:
            flash("Você não pode registrar Saída sem ter registrado Entrada.", "error")
            return redirect(url_for("ponto.dashboard"))

    if tipo == "intervalo_fim":
        existe_ini = Ponto.query.filter_by(
            funcionario_id=funcionario.id,
            data=hoje,
            tipo="intervalo_inicio"
        ).first()
        if not existe_ini:
            flash("Você não pode registrar Intervalo (Fim) sem Intervalo (Início).", "error")
            return redirect(url_for("ponto.dashboard"))

    tz = pytz.timezone("America/Sao_Paulo")
    agora = datetime.now(tz)

    ponto = Ponto(
        funcionario_id=funcionario.id,
        tipo=tipo,
        data=hoje,
        hora=agora.time().replace(microsecond=0),
        origem="funcionario",
    )

    try:
        db.session.add(ponto)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Esse ponto já foi registrado hoje (duplicidade).", "error")
        return redirect(url_for("ponto.dashboard"))

    # Recalcula o dia após bater o ponto
    calcular_e_atualizar_dia(funcionario, hoje)

    flash(f"Ponto registrado com sucesso: {tipo}.", "success")
    return redirect(url_for("ponto.dashboard"))
