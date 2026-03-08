from datetime import datetime, timezone
from app import db
from flask_login import UserMixin


class Usuario(UserMixin,db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer,primary_key=True)

    nome  = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(250), nullable=False)

    # Adim ou funcionario
    tipo = db.Column(db.String(25), nullable=False)

    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_em = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    atualizado_em = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc) , onupdate=lambda: datetime.now(timezone.utc))

    # relacionamento 1:1 com Funcionario ( fazer depois)
    funcionario = db.relationship( "Funcionario", back_populates="usuario", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f" <Usuario id={self.id} email={self.email} tipo={self.tipo}>"    

class Funcionario(db.Model):
        __tablename__ = "funcionarios"
        # pk compartilhada: funcionarios.id = usuarios.id
        id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), primary_key=True)

        cargo = db.Column(db.String(80), nullable=True)
        cpf = db.Column(db.String(14), nullable=True)

        carga_diaria_min = db.Column(db.Integer, nullable=False)

        intervalo_obrigatorio= db.Column(db.Boolean, default=False, nullable=False)

        criado_em = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
        
        atualizado_em = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

        usuario = db.relationship("Usuario", back_populates="funcionario")

        pontos = db.relationship("Ponto", back_populates="funcionario", cascade="all, delete-orphan")

        dias_trabalho = db.relationship("DiaTrabalho", back_populates = "funcionario", cascade="all, delete-orphan")


        def __repr__(self):
            return f" <Funcionario id={self.id} cargo={self.cargo} cpf={self.cpf}>"

class Ponto(db.Model):
    __tablename__ = "pontos"
    id = db.Column(db.Integer, primary_key=True)

    funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=False, index=True)

    # entrada | intervalo inicio | intervalo fim | saida
    tipo = db.Column(db.String(30), nullable=False)

    data = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)

    # funcionario | admin
    origem= db.Column(db.String(20), nullable=False, default="funcionario")

    # IP v4 ou v6
    ip = db.Column(db.String(45), nullable=True)


    criado_em = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    atualizado_em =db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    funcionario = db.relationship("Funcionario", back_populates="pontos")
    correcoes = db.relationship("CorrecaoPonto", back_populates="ponto", cascade="all, delete-orphan")

    __table_args__ = (
         db.UniqueConstraint("funcionario_id", "data","tipo", name="uq_funcionario_data_tipo"),
    )
    def __repr__(self):
         return f"<Ponto id={self.id} funcionario_id={self.funcionario_id} data={self.data} tipo={self.tipo}>"

class DiaTrabalho(db.Model):
    __tablename__ = "dias_trabalho"

    id = db.Column(db.Integer, primary_key=True)

    funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=False, index=True)
    data = db.Column(db.Date, nullable=False)

    # compleo | incompleto_entrada| incompleto_saida | incompleto_intervalo
    status = db.Column(db.String(30), nullable=False)

    minutos_trabalhados = db.Column(db.Integer, nullable=True)
    minutos_previstos = db.Column(db.Integer, nullable=False)

    saldo_minutos = db.Column(db.Integer, nullable=True)

    criado_em = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    atualizado_em = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    funcionario = db.relationship("Funcionario", back_populates="dias_trabalho")

    __table_args__ = (
         db.UniqueConstraint("funcionario_id", "data", name="uq_diatrabalho_funcionario_data"),
    )

    def __repr__(self):
            return f"<DiaTrabalho id={self.id} funcionario_id={self.funcionario_id} data={self.data} status={self.status}>"
    
class CorrecaoPonto(db.Model):
     __tablename__="correcoes_ponto"

     id = db.Column(db.Integer, primary_key=True)
     
     ponto_id = db.Column(db.Integer, db.ForeignKey("pontos.id"), nullable=False, index=True)
     admin_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)

     # snapshot do que mudou
     antes = db.Column(db.Text, nullable=False)
     depois = db.Column(db.Text, nullable=False)

     motivo = db.Column(db.String(25), nullable=True)

     criado_em = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

     ponto = db.relationship("Ponto", back_populates="correcoes")
     admin = db.relationship("Usuario")

     def __repr__(self):
          return f"<CorrecaoPonto id={self.id} ponto_id={self.ponto_id} admin_id={self.admin_id}>"