from controlers.endereco_envio import *
from schemas import *
from auth import *
from fastapi import APIRouter
router=APIRouter(prefix="/enderecos_envio",tags=["rotas de ederoco de envio"])


@router.put("/{endereco_envio_id}")
def update_endereco_envio(endereco_envio_id: int, endereco_envio: EnderecoEnvioUpdate, db: Session = Depends(get_db)):
    db_endereco_envio = update_endereco_envio_db(db=db, endereco_envio_id=endereco_envio_id, endereco_envio=endereco_envio)
    if db_endereco_envio is None:
        raise HTTPException(status_code=404, detail="EnderecoEnvio not found")
    return db_endereco_envio

# EnderecoEnvio routes
@router.post("/")
def create_endereco_envio(endereco_envio: EnderecoEnvioCreate, db: Session = Depends(get_db)):
    return create_endereco_envio_db(db=db, endereco_envio=endereco_envio)

@router.get("/{endereco_envio_id}")
def read_endereco_envio(endereco_envio_id: int, db: Session = Depends(get_db)):
    db_endereco_envio = get_endereco_envio(db=db, endereco_envio_id=endereco_envio_id)
    if db_endereco_envio is None:
        raise HTTPException(status_code=404, detail="EnderecoEnvio not found")
    return db_endereco_envio


@router.delete("/{endereco_envio_id}")
def delete_endereco_envio(endereco_envio_id: int, db: Session = Depends(get_db)):
    db_endereco_envio = delete_endereco_envio(db=db, endereco_envio_id=endereco_envio_id)
    if db_endereco_envio is None:
        raise HTTPException(status_code=404, detail="EnderecoEnvio not found")
    return db_endereco_envio