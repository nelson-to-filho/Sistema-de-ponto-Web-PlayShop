from datetime import datetime, date
from app import db
from app.models import Funcionario, Ponto, DiaTrabalho


def calcular_e_atualizar_dia(funcionario: Funcionario, dia: date) -> DiaTrabalho:
    """
    Recalcula DiaTrabalho do dia com base nos pontos existentes.
    Regras do MVP:
    - entrada e saida obrigatórias para ficar completo
    - intervalo só altera o cálculo se existir par inicio/fim (ou se for obrigatório)
    - dias incompletos/invalidos NÃO computam saldo (saldo_minutos=None)
    """

    pontos = (
        Ponto.query
        .filter_by(funcionario_id=funcionario.id, data=dia)
        .order_by(Ponto.hora.asc())
        .all()
    )

    mapa = {p.tipo: p for p in pontos}
    entrada = mapa.get("entrada")
    saida = mapa.get("saida")
    i_ini = mapa.get("intervalo_inicio")
    i_fim = mapa.get("intervalo_fim")

    minutos_previstos = funcionario.carga_diaria_min

    # defaults: dia não computável
    status = "incompleto_entrada"
    minutos_trabalhados = None
    saldo_minutos = None

    dt_entrada = datetime.combine(dia, entrada.hora) if entrada else None
    dt_saida = datetime.combine(dia, saida.hora) if saida else None
    dt_i_ini = datetime.combine(dia, i_ini.hora) if i_ini else None
    dt_i_fim = datetime.combine(dia, i_fim.hora) if i_fim else None

    status = "incompleto_entrada"
    minutos_trabalhados = None
    saldo_minutos = None

    

    if not entrada:
        status = "incompleto_entrada"

    # sequência inválida básica
    elif i_fim and not i_ini:
        status = "invalido_sequencia"

    elif i_ini and dt_i_ini <= dt_entrada:
        status = "invalido_sequencia"

    elif i_fim and dt_i_fim <= dt_entrada:
        status = "invalido_sequencia"

    elif i_ini and i_fim and dt_i_fim <= dt_i_ini:
        status = "invalido_intervalo"

    elif saida and dt_saida <= dt_entrada:
        status = "invalido_horarios"

    elif saida and i_ini and dt_saida <= dt_i_ini:
        status = "invalido_sequencia"

    elif saida and i_fim and dt_saida <= dt_i_fim:
        status = "invalido_sequencia"

    # ainda em andamento: só entrada
    elif entrada and not saida and not i_ini and not i_fim:
        status = "em_andamento"

    # ainda em andamento: iniciou intervalo mas ainda não finalizou
    elif entrada and i_ini and not i_fim and not saida:
        status = "em_andamento"

    # voltou do intervalo, mas ainda não bateu saída
    elif entrada and i_ini and i_fim and not saida:
        status = "pendente"

    # bateu entrada e saída
    elif entrada and saida:
        total = int((dt_saida - dt_entrada).total_seconds() // 60)

        # funcionário com intervalo obrigatório
        if funcionario.intervalo_obrigatorio:
            if not i_ini or not i_fim:
                status = "pendente"
            else:
                intervalo = int((dt_i_fim - dt_i_ini).total_seconds() // 60)
                minutos_trabalhados = max(total - intervalo, 0)
                saldo_minutos = minutos_trabalhados - minutos_previstos
                status = "completo"

        # funcionário sem intervalo obrigatório
        else:
            if i_ini and i_fim:
                intervalo = int((dt_i_fim - dt_i_ini).total_seconds() // 60)
                minutos_trabalhados = max(total - intervalo, 0)
            else:
                minutos_trabalhados = total

            saldo_minutos = minutos_trabalhados - minutos_previstos
            status = "completo"

    

    dia_trabalho = DiaTrabalho.query.filter_by(funcionario_id=funcionario.id, data=dia).first()

    if not dia_trabalho:
        dia_trabalho = DiaTrabalho(
            funcionario_id=funcionario.id,
            data=dia,
            status=status,
            minutos_trabalhados=minutos_trabalhados,
            minutos_previstos=minutos_previstos,
            saldo_minutos=saldo_minutos
        )
        db.session.add(dia_trabalho)
    else:
        dia_trabalho.status = status
        dia_trabalho.minutos_trabalhados = minutos_trabalhados
        dia_trabalho.minutos_previstos = minutos_previstos
        dia_trabalho.saldo_minutos = saldo_minutos

    db.session.commit()
    return dia_trabalho