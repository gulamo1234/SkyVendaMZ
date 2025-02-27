from sqlalchemy.orm import Session
from models import Usuario,InfoUsuario,Status,Log
from schemas import UsuarioCreate, UsuarioUpdate
import smtplib
from email.mime.text import MIMEText
from fastapi import HTTPException
from email.mime.multipart import MIMEMultipart
import random
import string
from sqlalchemy import func,String
from datetime import datetime,timedelta

def create_usuario_db(db: Session, usuario: UsuarioCreate):
    db_usuario = Usuario(**usuario.dict())
    db.add(db_usuario)
    db.commit()
    db.refresh(db_usuario)
    return db_usuario

def get_usuarios(db: Session):
    return db.query(Usuario).all()

def get_usuario(db: Session, usuario_id: int):
    return db.query(Usuario).filter(Usuario.id == usuario_id).first()

def update_usuario_db(db: Session, usuario_id: int, usuario: UsuarioUpdate):
    # Certifique-se de usar o nome correto da coluna no modelo SQLAlchemy
    db_usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if db_usuario:
        for key, value in usuario.dict().items():
            setattr(db_usuario, key, value)
        db.commit()
        db.refresh(db_usuario)
    return db_usuario

def delete_usuario_db(db: Session, usuario_id: int):
    db_usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if db_usuario:
        db.delete(db_usuario)
        db.commit()
    return db_usuario


def send_email(recipient: str, subject: str, body: str,is_html=False):
    sender_email = "jorgepaulomepia@gmail.com"  # Seu e-mail
    sender_password = "ryyuofxscbisgrre"  # Sua senha do e-mail

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'html' if is_html else 'plain'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:  # Altere para o servidor SMTP do seu e-mail
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient, msg.as_string())
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False


def listar_usuarios_nao_verificados(db: Session):
    """
    Função para listar todos os usuários não verificados.
    
    Args:
        db (Session): Sessão do banco de dados.
    
    Returns:
        List[Usuario]: Lista de usuários não verificados.
    """
    return db.query(Usuario).filter(Usuario.revisao != "sim").all()

def ativar_usuario(db: Session, usuario_id: int):
    # Busca o usuário no banco de dados
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    # Verifica se o usuário já está ativado
    if usuario.ativo:
        raise HTTPException(status_code=400, detail="Usuário já está ativo")

    # Define o campo 'ativo' como True (ativado)
    usuario.ativo = True
    db.commit()  # Confirma as mudanças no banco
    return {"sucesso": "Usuário ativado com sucesso"}

def desativar_usuario(db: Session, usuario_id: int):
    # Busca o usuário no banco de dados
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    # Verifica se o usuário já está desativado
    if not usuario.ativo:
        raise HTTPException(status_code=400, detail="Usuário já está desativado")

    # Define o campo 'ativo' como False (desativado)
    usuario.ativo = False
    db.commit()  # Confirma as mudanças no banco
    return {"sucesso": "Usuário desativado com sucesso"}



def criar_status_controller(usuario_id: int, conteudo: str, imagem_url: str, duracao_dias: int, db: Session):
    # Buscar o usuário pelo ID
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    if usuario.ativo==False:
        raise HTTPException(status_code=404, detail="voce esta desactivado")
    # Verificar se o usuário tem uma carteira
    if not usuario.wallet:
        raise HTTPException(status_code=400, detail="Carteira não encontrada para o usuário")

    # Calcular o custo total do status
    custo_total = duracao_dias * 9.0

    # Verificar se o saldo principal é suficiente
    if usuario.wallet.saldo_principal < custo_total:
        raise HTTPException(status_code=400, detail="Saldo insuficiente para postar o status")

    # Deduzir o saldo principal
    usuario.wallet.saldo_principal -= custo_total

    # Criar o novo status
    novo_status = Status(
        usuario_id=usuario.id,
        conteudo=conteudo,
        imagem_url=imagem_url,
        expira_em=datetime.utcnow() + timedelta(days=duracao_dias),
        custo_total=custo_total
    )

    db.add(novo_status)
    db.commit()
    db.refresh(novo_status)

    return {"message": "Status criado com sucesso", "status_id": novo_status.id}

def get_perfil(db: Session, usuario_id: int):
    # Atualiza a consulta para fazer join entre Usuario e InfoUsuario
    usuario_info = db.query(Usuario, InfoUsuario).join(InfoUsuario, Usuario.id == InfoUsuario.id).filter(Usuario.id == usuario_id).first()
    
    if usuario_info:
        usuario, info_usuario = usuario_info
        return {
            "username": usuario.username,
            "nome": usuario.nome,
            "perfil": info_usuario.perfil
             
        }
    return None



def categorias_preferidas_por_usuario(db: Session, usuario_id: int):
    """
    Retorna as categorias mais interagidas por um usuário.
    """
    categorias = (
        db.query(
            Log.detalhes["categoria"].cast(String).label("categoria"),  # Corrigido aqui
            func.count(Log.id).label("total_interacoes"),
        )
        .filter(Log.usuario_id == usuario_id)
        .group_by(Log.detalhes["categoria"].cast(String))  # Corrigido aqui
        .order_by(func.count(Log.id).desc())
        .all()
    )

    return [{"categoria": c[0], "total_interacoes": c[1]} for c in categorias]

