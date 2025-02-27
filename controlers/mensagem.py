from sqlalchemy.orm import Session
from models import Message
from schemas import MensagemCreate, MensagemUpdate,U

def create_mensagem_db(db: Session, mensagem: MensagemCreate):
    db_mensagem = Message(**mensagem.dict())
    db.add(db_mensagem)
    db.commit()
    db.refresh(db_mensagem)
    return db_mensagem

def get_mensagens(db: Session):
    return db.query(Message).all()

def get_mensagem(db: Session, mensagem_id: int):
    return db.query(Message).filter(Message.id == mensagem_id).first()


def get_conversas_entre_usuarios(db: Session, usuario1_id: int, usuario2_id: int):
    return db.query(Message).filter(
        (Message.remetenteID == usuario1_id) & (Message.destinatarioID == usuario2_id) |
        (Message.remetenteID == usuario2_id) & (Message.destinatarioID == usuario1_id)
    ).all()


def update_mensagem_db(db: Session, mensagem_id: int, mensagem: MensagemUpdate):
    db_mensagem = db.query(Message).filter(Message.id == mensagem_id).first()
    if db_mensagem:
        for key, value in mensagem.dict().items():
            setattr(db_mensagem, key, value)
        db.commit()
        db.refresh(db_mensagem)
    return db_mensagem

def delete_mensagem(db: Session, mensagem_id: int):
    db_mensagem = db.query(Message).filter(Message.id == mensagem_id).first()
    if db_mensagem:
        db.delete(db_mensagem)
        db.commit()
    return db_mensagem
