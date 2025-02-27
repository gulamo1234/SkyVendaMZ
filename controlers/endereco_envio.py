from sqlalchemy.orm import Session
from models import EnderecoEnvio
from schemas import EnderecoEnvioCreate, EnderecoEnvioUpdate

def create_endereco_envio_db(db: Session, endereco_envio: EnderecoEnvioCreate):
    db_endereco_envio = EnderecoEnvio(**endereco_envio.dict())
    db.add(db_endereco_envio)
    db.commit()
    db.refresh(db_endereco_envio)
    return db_endereco_envio

def get_endereco_envios(db: Session):
    return db.query(EnderecoEnvio).all()

def get_endereco_envio(db: Session, endereco_envio_id: int):
    return db.query(EnderecoEnvio).filter(EnderecoEnvio.id == endereco_envio_id).first()

def update_endereco_envio_db(db: Session, endereco_envio_id: int, endereco_envio: EnderecoEnvioUpdate):
    db_endereco_envio = db.query(EnderecoEnvio).filter(EnderecoEnvio.id == endereco_envio_id).first()
    if db_endereco_envio:
        for key, value in endereco_envio.dict().items():
            setattr(db_endereco_envio, key, value)
        db.commit()
        db.refresh(db_endereco_envio)
    return db_endereco_envio

def delete_endereco_envio(db: Session, endereco_envio_id: int):
    db_endereco_envio = db.query(EnderecoEnvio).filter(EnderecoEnvio.id == endereco_envio_id).first()
    if db_endereco_envio:
        db.delete(db_endereco_envio)
        db.commit()
    return db_endereco_envio
