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

    if not entrada:
        status = "incompleto_entrada"

    elif not saida:
        status = "incompleto_saida"

    else:
        dt_entrada = datetime.combine(dia, entrada.hora)
        dt_saida = datetime.combine(dia, saida.hora)

        if dt_saida <= dt_entrada:
            status = "invalido_horarios"

        else:
            total = int((dt_saida - dt_entrada).total_seconds() // 60)

            # intervalo obrigatório
            if funcionario.intervalo_obrigatorio:
                if not i_ini or not i_fim:
                    status = "incompleto_intervalo"
                else:
                    dt_i_ini = datetime.combine(dia, i_ini.hora)
                    dt_i_fim = datetime.combine(dia, i_fim.hora)

                    if dt_i_fim <= dt_i_ini:
                        status = "invalido_intervalo"
                    else:
                        intervalo = int((dt_i_fim - dt_i_ini).total_seconds() // 60)
                        minutos_trabalhados = max(total - intervalo, 0)
                        saldo_minutos = minutos_trabalhados - minutos_previstos
                        status = "completo"

            # intervalo não obrigatório
            else:
                if i_ini and i_fim:
                    dt_i_ini = datetime.combine(dia, i_ini.hora)
                    dt_i_fim = datetime.combine(dia, i_fim.hora)

                    # se intervalo invertido, ignora intervalo (não invalida o dia)
                    if dt_i_fim > dt_i_ini:
                        intervalo = int((dt_i_fim - dt_i_ini).total_seconds() // 60)
                        minutos_trabalhados = max(total - intervalo, 0)
                    else:
                        minutos_trabalhados = total
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