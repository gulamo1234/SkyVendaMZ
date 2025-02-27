from sqlalchemy.orm import Session
from models import Comentario,Produto
from schemas import ComentarioCreate, ComentarioUpdate
from controlers.utils import *
from fastapi import HTTPException

def create_comentario_db(db: Session, comentario: dict, usuario_id: int):
    """
    Adiciona um comentário para um produto baseado no slug.
    """
    # Buscar o produto pelo slug, não pelo id
    produto = db.query(Produto).filter(Produto.slug == comentario["produtoSlug"]).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    
    # Cria o comentário
    db_comentario = Comentario(
        produtoID=produto.id,  # Usamos o ID do produto encontrado
        usuarioID=usuario_id,
        comentario=comentario["comentario"],
    )
    db.add(db_comentario)
    db.commit()
    db.refresh(db_comentario)

    # Registra a ação com a categoria
    registrar_acao_com_categoria(
        db=db,
        usuario_id=usuario_id,
        tipo_acao="comentario",
        produto_id=produto.id,
        entidade="Comentario",
        detalhes={
            "comentario": comentario["comentario"]
        }
    )

    return db_comentario




def get_comentarios(db: Session):
    return db.query(Comentario).all()
   


def get_comentario(db: Session, comentario_id: int):
    return db.query(Comentario).filter(Comentario.id == comentario_id).first()

def update_comentario_db(db: Session, comentario_id: int, comentario: ComentarioUpdate):
    db_comentario = db.query(Comentario).filter(Comentario.id == comentario_id).first()
    if db_comentario:
        for key, value in comentario.dict().items():
            setattr(db_comentario, key, value)
        db.commit()
        db.refresh(db_comentario)
    return db_comentario

def delete_comentario(db: Session, comentario_id: int):
    db_comentario = db.query(Comentario).filter(Comentario.id == comentario_id).first()
    if db_comentario:
        db.delete(db_comentario)
        db.commit()
    return db_comentario
