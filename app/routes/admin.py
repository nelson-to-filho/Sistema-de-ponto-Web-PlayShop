import json
from datetime import date, time as dtime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Funcionario, Ponto, CorrecaoPonto, DiaTrabalho
from app.services.ponto_calc import calcular_e_atualizar_dia

import csv
from io import StringIO

import secrets
import string
from werkzeug.security import generate_password_hash
from app.models import Usuario  



admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _admin_only():
    if current_user.tipo != "admin":
        return render_template("403.html"), 403
    return None

def _gerar_senha_temporaria(tamanho: int = 10) -> str:
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))


def _hhmm_to_minutos(hhmm: str) -> int:
    # aceita "08:00" ou "8:00"
    partes = hhmm.strip().split(":")
    if len(partes) != 2:
        raise ValueError("Formato inválido")
    h = int(partes[0])
    m = int(partes[1])
    if h < 0 or m < 0 or m >= 60:
        raise ValueError("Formato inválido")
    return h * 60 + m

def _min_to_hhmm(mins: int | None) -> str:
    if mins is None:
        return "-"
    sign = "-" if mins < 0 else ""
    mins = abs(int(mins))
    h = mins // 60
    m = mins % 60
    return f"{sign}{h:02d}:{m:02d}"


def _month_range(ano: int, mes: int):
    # retorna (inicio_mes, inicio_prox_mes)
    inicio = date(ano, mes, 1)
    if mes == 12:
        prox = date(ano + 1, 1, 1)
    else:
        prox = date(ano, mes + 1, 1)
    return inicio, prox

def ponto_snapshot(p: Ponto) -> dict:
    return {
        "id": p.id,
        "funcionario_id": p.funcionario_id,
        "tipo": p.tipo,
        "data": p.data.isoformat(),
        "hora": p.hora.strftime("%H:%M:%S"),
        "origem": p.origem,
    }


@admin_bp.route("/")
@login_required
def dashboard():
    blocked = _admin_only()
    if blocked:
        return blocked

    return render_template("admin/dashboard.html")


@admin_bp.route("/funcionarios")
@login_required
def funcionarios():
    blocked = _admin_only()
    if blocked:
        return blocked

    lista = Funcionario.query.order_by(Funcionario.id.asc()).all()
    return render_template("admin/funcionarios.html", funcionarios=lista)


@admin_bp.route("/funcionarios/novo", methods=["GET", "POST"])
@login_required
def novo_funcionario():
    blocked = _admin_only()
    if blocked:
        return blocked

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "").strip()  # opcional (pode vir vazio)
        carga_diaria = request.form.get("carga_diaria", "").strip()  # "05:00"
        intervalo_obrigatorio = request.form.get("intervalo_obrigatorio") == "on"

        # validações mínimas
        if not nome or not email or not carga_diaria:
            flash("Preencha nome, e-mail e carga diária.", "error")
            return render_template("admin/novo_funcionario.html")

        try:
            carga_diaria_min = _hhmm_to_minutos(carga_diaria)
        except ValueError:
            flash("Carga diária inválida. Use HH:MM (ex.: 08:00).", "error")
            return render_template("admin/novo_funcionario.html")

        if carga_diaria_min <= 0:
            flash("Carga diária deve ser maior que zero.", "error")
            return render_template("admin/novo_funcionario.html")

        # senha: se não veio, gera temporária
        senha_final = senha if senha else _gerar_senha_temporaria()

        # cria Usuario
        user = Usuario(
            nome=nome,
            email=email,
            senha_hash=generate_password_hash(senha_final),
            tipo="funcionario",
            ativo=True,
        )

        try:
            db.session.add(user)
            db.session.flush()  # garante user.id

            

            func = Funcionario(
                id=user.id,
                carga_diaria_min=carga_diaria_min,
                intervalo_obrigatorio=intervalo_obrigatorio,
            )

            db.session.add(func)
            db.session.commit()

        except IntegrityError:
            db.session.rollback()
            flash("E-mail já cadastrado. Tente outro.", "error")
            return render_template("admin/novo_funcionario.html")

        # IMPORTANTE: só mostramos a senha se foi gerada automaticamente
        if not senha:
            flash(f"Funcionário criado. Senha temporária: {senha_final}", "success")
        else:
            flash("Funcionário criado com sucesso.", "success")

        return redirect(url_for("admin.funcionarios"))

    return render_template("admin/novo_funcionario.html")

@admin_bp.route("/funcionario/<int:func_id>/editar", methods=["GET", "POST"])
@login_required
def editar_funcionario(func_id: int):
    blocked = _admin_only()
    if blocked:
        return blocked

    funcionario = Funcionario.query.get_or_404(func_id)

    if request.method == "POST":
        carga_diaria = request.form.get("carga_diaria", "").strip()
        intervalo_obrigatorio = request.form.get("intervalo_obrigatorio") == "on"

        if not carga_diaria:
            flash("Informe a carga diária.", "error")
            return render_template("admin/editar_funcionario.html", funcionario=funcionario)

        try:
            carga_diaria_min = _hhmm_to_minutos(carga_diaria)
        except ValueError:
            flash("Carga diária inválida. Use HH:MM (ex.: 08:00).", "error")
            return render_template("admin/editar_funcionario.html", funcionario=funcionario)

        if carga_diaria_min <= 0:
            flash("Carga diária deve ser maior que zero.", "error")
            return render_template("admin/editar_funcionario.html", funcionario=funcionario)

        funcionario.carga_diaria_min = carga_diaria_min
        funcionario.intervalo_obrigatorio = intervalo_obrigatorio

       

        db.session.commit()
        flash("Funcionário atualizado.", "success")
        return redirect(url_for("admin.funcionarios"))

    return render_template("admin/editar_funcionario.html", funcionario=funcionario)


@admin_bp.route("/usuario/<int:user_id>/reset_senha", methods=["POST"])
@login_required
def reset_senha(user_id: int):
    blocked = _admin_only()
    if blocked:
        return blocked

    user = Usuario.query.get_or_404(user_id)

    # gera senha temporária e salva hash
    nova = _gerar_senha_temporaria()
    user.senha_hash = generate_password_hash(nova)

    db.session.commit()
    flash(f"Senha resetada para {user.email}. Nova senha temporária: {nova}", "success")
    return redirect(url_for("admin.funcionarios"))




@admin_bp.route("/funcionario/<int:func_id>/pontos")
@login_required
def pontos_funcionario(func_id: int):
    blocked = _admin_only()
    if blocked:
        return blocked

    funcionario = Funcionario.query.get_or_404(func_id)

    dia_str = request.args.get("dia", "")
    if dia_str:
        try:
            dia = date.fromisoformat(dia_str)
        except ValueError:
            dia = date.today()
            flash("Data inválida. Mostrando hoje.", "error")
    else:
        dia = date.today()

    pontos = (
        Ponto.query
        .filter_by(funcionario_id=funcionario.id, data=dia)
        .order_by(Ponto.hora.asc())
        .all()
    )

    return render_template(
        "admin/pontos_funcionario.html",
        funcionario=funcionario,
        dia=dia,
        pontos=pontos
    )

@admin_bp.route("/funcionario/<int:func_id>/pontos/adicionar", methods=["GET", "POST"])
@login_required
def adicionar_ponto(func_id: int):
    blocked = _admin_only()
    if blocked:
        return blocked

    funcionario = Funcionario.query.get_or_404(func_id)

    # Dia vem via querystring: ?dia=YYYY-MM-DD
    dia_str = request.args.get("dia", "").strip()
    if not dia_str:
        flash("Informe o dia para adicionar o ponto.", "error")
        return redirect(url_for("admin.pontos_funcionario", func_id=funcionario.id))

    try:
        dia = date.fromisoformat(dia_str)
    except ValueError:
        flash("Data inválida.", "error")
        return redirect(url_for("admin.pontos_funcionario", func_id=funcionario.id))

    if request.method == "POST":
        tipo = request.form.get("tipo", "").strip()
        hora_str = request.form.get("hora", "").strip()
        motivo = request.form.get("motivo", "").strip()

        TIPOS_VALIDOS = {"entrada", "intervalo_inicio", "intervalo_fim", "saida"}
        if tipo not in TIPOS_VALIDOS:
            flash("Tipo inválido.", "error")
            return render_template("admin/adicionar_ponto.html", funcionario=funcionario, dia=dia)

        if not hora_str:
            flash("Informe a hora.", "error")
            return render_template("admin/adicionar_ponto.html", funcionario=funcionario, dia=dia)

        # aceita HH:MM (html time) ou HH:MM:SS
        try:
            if len(hora_str) == 5:
                hora = dtime.fromisoformat(hora_str + ":00")
            else:
                hora = dtime.fromisoformat(hora_str)
        except ValueError:
            flash("Hora inválida.", "error")
            return render_template("admin/adicionar_ponto.html", funcionario=funcionario, dia=dia)

        # Cria o ponto (origem admin)
        novo_ponto = Ponto(
            funcionario_id=funcionario.id,
            tipo=tipo,
            data=dia,
            hora=hora.replace(microsecond=0),
            origem="admin",
        )

        # Auditoria: registrar correção mesmo sendo "criação"
        antes = {"acao": "criar", "ponto": None}
        depois = {
            "acao": "criar",
            "ponto": {
                "funcionario_id": funcionario.id,
                "tipo": tipo,
                "data": dia.isoformat(),
                "hora": hora.replace(microsecond=0).strftime("%H:%M:%S"),
                "origem": "admin",
            }
        }

        correcao = CorrecaoPonto(
            ponto=novo_ponto,
            admin_id=current_user.id,
            antes=json.dumps(antes, ensure_ascii=False),
            depois=json.dumps(depois, ensure_ascii=False),
            motivo=motivo if motivo else None,
        )

        try:
            db.session.add(novo_ponto)
            db.session.add(correcao)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Duplicidade: já existe esse tipo de ponto nesse dia para o funcionário.", "error")
            return render_template("admin/adicionar_ponto.html", funcionario=funcionario, dia=dia)

        # Recalcula o dia
        calcular_e_atualizar_dia(funcionario, dia)

        flash("Ponto adicionado e dia recalculado.", "success")
        return redirect(url_for("admin.pontos_funcionario", func_id=funcionario.id, dia=dia.isoformat()))

    return render_template("admin/adicionar_ponto.html", funcionario=funcionario, dia=dia)



@admin_bp.route("/ponto/<int:ponto_id>/editar", methods=["GET", "POST"])
@login_required
def editar_ponto(ponto_id: int):
    blocked = _admin_only()
    if blocked:
        return blocked

    ponto = Ponto.query.get_or_404(ponto_id)
    funcionario = Funcionario.query.get_or_404(ponto.funcionario_id)

    if request.method == "POST":
        hora_str = request.form.get("hora", "").strip()
        motivo = request.form.get("motivo", "").strip()

        if not hora_str:
            flash("Informe a hora.", "error")
            return render_template("admin/editar_ponto.html", ponto=ponto, funcionario=funcionario)

        # aceita HH:MM (html time) ou HH:MM:SS
        try:
            if len(hora_str) == 5:
                nova_hora = dtime.fromisoformat(hora_str + ":00")
            else:
                nova_hora = dtime.fromisoformat(hora_str)
        except ValueError:
            flash("Hora inválida.", "error")
            return render_template("admin/editar_ponto.html", ponto=ponto, funcionario=funcionario)

        antes = ponto_snapshot(ponto)

        # aplica alteração
        ponto.hora = nova_hora.replace(microsecond=0)

        depois = ponto_snapshot(ponto)

        correcao = CorrecaoPonto(
            ponto_id=ponto.id,
            admin_id=current_user.id,
            antes=json.dumps(antes, ensure_ascii=False),
            depois=json.dumps(depois, ensure_ascii=False),
            motivo=motivo if motivo else None
        )

        try:
            db.session.add(correcao)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Conflito: essa alteração gerou duplicidade para esse tipo no mesmo dia.", "error")
            return render_template("admin/editar_ponto.html", ponto=ponto, funcionario=funcionario)

        # Recalcula o dia do ponto alterado
        calcular_e_atualizar_dia(funcionario, ponto.data)

        flash("Ponto corrigido e dia recalculado.", "success")
        return redirect(url_for("admin.pontos_funcionario", func_id=funcionario.id, dia=ponto.data.isoformat()))

    return render_template("admin/editar_ponto.html", ponto=ponto, funcionario=funcionario)

def _json_safe_load(s: str):
    """Tenta converter string JSON em dict. Se falhar, retorna texto cru."""
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return s


@admin_bp.route("/correcoes")
@login_required
def correcoes():
    blocked = _admin_only()
    if blocked:
        return blocked

    # filtros (opcionais)
    func_id = request.args.get("func_id", "").strip()
    dia_str = request.args.get("dia", "").strip()

    query = CorrecaoPonto.query

    # Se algum filtro depende de Ponto, faz JOIN apenas uma vez
    precisa_join_ponto = (func_id.isdigit() or bool(dia_str))
    if precisa_join_ponto:
        query = query.join(Ponto, CorrecaoPonto.ponto_id == Ponto.id)

    # Se veio func_id, filtra correções por funcionário via Ponto.funcionario_id
    if func_id.isdigit():
        query = query.filter(Ponto.funcionario_id == int(func_id))

    # Se veio dia, filtra por data do ponto (Ponto.data)
    if dia_str:
        try:
            dia = date.fromisoformat(dia_str)
            query = query.filter(Ponto.data == dia)
        except ValueError:
            flash("Data inválida no filtro de correções. Use YYYY-MM-DD.", "error")

    # ordena por mais recentes
    correcoes = []

    if func_id.isdigit() or dia_str:
        correcoes = (
            query
            .order_by(CorrecaoPonto.criado_em.desc())
            .limit(100)
            .all()
        )

    # Pré-processa antes/depois para exibir melhor no HTML
    itens = []
    for c in correcoes:
        # Carrega o ponto (pode ser lazy)
        p = c.ponto

        itens.append({
            "id": c.id,
            "criado_em": c.criado_em,
            "motivo": c.motivo,
            "admin_nome": c.admin.nome if c.admin else f"(id {c.admin_id})",
            "ponto_id": c.ponto_id,
            "ponto_tipo": p.tipo if p else "(ponto removido)",
            "ponto_data": p.data if p else None,
            "ponto_hora": p.hora if p else None,
            "funcionario_id": p.funcionario_id if p else None,
            "antes": _json_safe_load(c.antes),
            "depois": _json_safe_load(c.depois),
        })

    # lista de funcionarios pra facilitar filtro no html (simples)
    funcionarios = Funcionario.query.order_by(Funcionario.id.asc()).all()

    return render_template(
        "admin/correcoes.html",
        itens=itens,
        funcionarios=funcionarios,
        filtro_func_id=func_id,
        filtro_dia=dia_str,
    )


@admin_bp.route("/funcionario/<int:func_id>/correcoes")
@login_required
def correcoes_funcionario(func_id: int):
    blocked = _admin_only()
    if blocked:
        return blocked

    # redireciona para a tela geral já filtrada
    return redirect(url_for("admin.correcoes", func_id=func_id))

@admin_bp.route("/relatorios/mensal")
@login_required
def relatorio_mensal():
    blocked = _admin_only()
    if blocked:
        return blocked

    # filtros
    func_id = request.args.get("func_id", "").strip()
    mes_str = request.args.get("mes", "").strip()  # "2026-02" vindo do input type="month"

    funcionarios = Funcionario.query.order_by(Funcionario.id.asc()).all()

    # valores padrão
    hoje = date.today()
    ano = hoje.year
    mes = hoje.month

    if mes_str:
        try:
            ano = int(mes_str.split("-")[0])
            mes = int(mes_str.split("-")[1])
        except Exception:
            flash("Mês inválido. Use o seletor de mês.", "error")

    funcionario = None
    linhas = []
    total_prev = 0
    total_trab = 0
    total_saldo = 0

    if func_id.isdigit():
        funcionario = Funcionario.query.get(int(func_id))

        if not funcionario:
            flash("Funcionário não encontrado.", "error")
        else:
            inicio, prox = _month_range(ano, mes)

            dias = (
                DiaTrabalho.query
                .filter(
                    DiaTrabalho.funcionario_id == funcionario.id,
                    DiaTrabalho.data >= inicio,
                    DiaTrabalho.data < prox,
                )
                .order_by(DiaTrabalho.data.asc())
                .all()
            )

            for d in dias:
                total_prev += (d.minutos_previstos or 0)
                total_trab += (d.minutos_trabalhados or 0)
                total_saldo += (d.saldo_minutos or 0)

                linhas.append({
                    "data": d.data,
                    "status": d.status,
                    "prev": d.minutos_previstos,
                    "trab": d.minutos_trabalhados,
                    "saldo": d.saldo_minutos,
                })

    # mes em formato "YYYY-MM" para preencher o input month
    mes_value = f"{ano:04d}-{mes:02d}"

    return render_template(
        "admin/relatorio_mensal.html",
        funcionarios=funcionarios,
        funcionario=funcionario,
        filtro_func_id=func_id,
        mes_value=mes_value,
        linhas=linhas,
        total_prev=total_prev,
        total_trab=total_trab,
        total_saldo=total_saldo,
        min_to_hhmm=_min_to_hhmm,
    )

@admin_bp.route("/relatorios/mensal.csv")
@login_required
def relatorio_mensal_csv():
    blocked = _admin_only()
    if blocked:
        return blocked

    func_id = request.args.get("func_id", "").strip()
    mes_str = request.args.get("mes", "").strip()

    if not func_id.isdigit():
        flash("Selecione um funcionário para exportar.", "error")
        return redirect(url_for("admin.relatorio_mensal", mes=mes_str))

    funcionario = Funcionario.query.get(int(func_id))
    if not funcionario:
        flash("Funcionário não encontrado.", "error")
        return redirect(url_for("admin.relatorio_mensal", mes=mes_str))

    hoje = date.today()
    ano = hoje.year
    mes = hoje.month
    if mes_str:
        try:
            ano = int(mes_str.split("-")[0])
            mes = int(mes_str.split("-")[1])
        except Exception:
            flash("Mês inválido. Use o seletor de mês.", "error")
            return redirect(url_for("admin.relatorio_mensal"))

    inicio, prox = _month_range(ano, mes)

    dias = (
        DiaTrabalho.query
        .filter(
            DiaTrabalho.funcionario_id == funcionario.id,
            DiaTrabalho.data >= inicio,
            DiaTrabalho.data < prox,
        )
        .order_by(DiaTrabalho.data.asc())
        .all()
    )

    # CSV em memória
    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(["data", "status", "previsto_hhmm", "trabalhado_hhmm", "saldo_hhmm"])

    for d in dias:
        writer.writerow([
            d.data.isoformat(),
            d.status,
            _min_to_hhmm(d.minutos_previstos),
            _min_to_hhmm(d.minutos_trabalhados),
            _min_to_hhmm(d.saldo_minutos),
        ])

    csv_text = sio.getvalue()
    sio.close()

    # Response simples (sem dependência extra)
    from flask import Response
    filename = f"relatorio_{funcionario.usuario.nome}_{ano:04d}-{mes:02d}.csv".replace(" ", "_")

    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )