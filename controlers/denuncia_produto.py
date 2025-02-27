from sqlalchemy.orm import Session
from models import DenunciaProduto
from schemas import DenunciaProdutoCreate, DenunciaProdutoUpdate

def create_denuncia_produto_db(db: Session, denuncia_produto: DenunciaProdutoCreate):
    db_denuncia_produto = DenunciaProduto(**denuncia_produto.dict())
    db.add(db_denuncia_produto)
    db.commit()
    db.refresh(db_denuncia_produto)
    return db_denuncia_produto

def get_denuncia_produtos(db: Session):
    return db.query(DenunciaProduto).all()

def get_denuncia_produto(db: Session, denuncia_id: int):
    return db.query(DenunciaProduto).filter(DenunciaProduto.id == denuncia_id).first()

def update_denuncia_produto_db(db: Session, denuncia_id: int, denuncia_produto: DenunciaProdutoUpdate):
    db_denuncia_produto = db.query(DenunciaProduto).filter(DenunciaProduto.id == denuncia_id).first()
    if db_denuncia_produto:
        for key, value in denuncia_produto.dict().items():
            setattr(db_denuncia_produto, key, value)
        db.commit()
        db.refresh(db_denuncia_produto)
    return db_denuncia_produto

def delete_denuncia_produto(db: Session, denuncia_id: int):
    db_denuncia_produto = db.query(DenunciaProduto).filter(DenunciaProduto.id == denuncia_id).first()
    if db_denuncia_produto:
        db.delete(db_denuncia_produto)
        db.commit()
    return db_denuncia_produto
