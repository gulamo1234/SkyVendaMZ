from controlers.denuncia_produto import *
from schemas import *
from auth import *
from fastapi import APIRouter

router=APIRouter(prefix="/denucia",tags=["rotas de denucias"])


# DenunciaProduto routes
@router.post("/denuncia_produtos/")
def create_denuncia_produto(denuncia_produto: DenunciaProdutoCreate, db: Session = Depends(get_db)):
    return create_denuncia_produto_db(db=db, denuncia_produto=denuncia_produto)

@router.put("/denuncia_produtos/{denuncia_id}")
def update_denuncia_produto(denuncia_id: int, denuncia_produto: DenunciaProdutoUpdate, db: Session = Depends(get_db)):
    db_denuncia_produto = update_denuncia_produto_db(db=db, denuncia_id=denuncia_id, denuncia_produto=denuncia_produto)
    if db_denuncia_produto is None:
        raise HTTPException(status_code=404, detail="DenunciaProduto not found")
    return db_denuncia_produto