from controlers.comentario import *
from schemas import *
from auth import *
from fastapi import APIRouter,status,HTTPException,Form

router=APIRouter(prefix="/comentarios",tags=["rotas de comentario"])
# Comentario routes


@router.post("/")
async def create_comentario(
    produto_slug: str = Form(...),
    conteudo: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),  # Autenticação do usuário
):
    """
    Cria um comentário para um produto.
    Apenas usuários autenticados podem criar comentários.
    """
    # Certifique-se de que o usuário está ativo
    if not current_user.ativo:
        raise HTTPException(
            status_code=403,
            detail="Usuário desativado não pode criar comentários."
        )
    
    # Monta o objeto de comentário com os dados recebidos
    comentario_data = {
        "produtoSlug": produto_slug,
        "comentario": conteudo,
    }

    # Passa o objeto ComentarioCreate diretamente para a função create_comentario_db
    return create_comentario_db(db=db, comentario=comentario_data, usuario_id=current_user.id)

@router.get("/{comentario_id}")
def read_comentario(comentario_id: int, db: Session = Depends(get_db)):
    db_comentario = get_comentario(db=db, comentario_id=comentario_id)
    if db_comentario is None:
        raise HTTPException(status_code=404, detail="Comentario not found")
    return db_comentario

@router.delete("/{comentario_id}")
def delete_comentario(comentario_id: int, db: Session = Depends(get_db)):
    db_comentario = delete_comentario(db=db, comentario_id=comentario_id)
    if db_comentario is None:
        raise HTTPException(status_code=404, detail="Comentario not found")
    return db_comentario

def update_comentario(comentario_id: int, comentario: ComentarioUpdate, db: Session = Depends(get_db)):
    db_comentario = update_comentario_db(db=db, comentario_id=comentario_id, comentario=comentario)
    if db_comentario is None:
        raise HTTPException(status_code=404, detail="Comentario not found")
    return db_comentario
