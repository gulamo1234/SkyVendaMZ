from controlers.info_usuario import *
from schemas import *
from auth import *
from fastapi import APIRouter,Form



router=APIRouter(prefix="/info_usuario",tags=["rotas de infousuario"])

@router.post("/")
async def create_info_usuario(
    foto_retrato: UploadFile = File(...),  # Foto do rosto do usuário
    foto_bi_frente: UploadFile = File(...),  # Frente do BI
    foto_bi_verso: UploadFile = File(...),  # Verso do BI
    provincia: str = Form(...),
    distrito: str = Form(...),
    data_nascimento: str = Form(...),
    sexo: str = Form(...),
    nacionalidade: Optional[str] = Form(None),
    bairro: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    # Salvando as imagens
    foto_retrato_filename = save_image(foto_retrato, DOCUMENT_UPLOAD_DIR)  # Foto do rosto
    foto_bi_frente_filename = save_image(foto_bi_frente, DOCUMENT_UPLOAD_DIR)  # Frente do BI
    foto_bi_verso_filename = save_image(foto_bi_verso, DOCUMENT_UPLOAD_DIR)  # Verso do BI

    # Criando o objeto InfoUsuarioCreate
    info_usuario_data = InfoUsuarioCreate(
        foto_retrato=foto_retrato_filename,  # Foto do rosto
        foto_bi_frente=foto_bi_frente_filename,  # Frente do BI
        foto_bi_verso=foto_bi_verso_filename,  # Verso do BI
        provincia=provincia,
        distrito=distrito,
        data_nascimento=data_nascimento,
        sexo=sexo,
        nacionalidade=nacionalidade,
        bairro=bairro,
        usuario_id=current_user.id
    )

    # Criando a entrada no banco de dados
    db_info_usuario = create_info_usuario_db(db=db, info_usuario=info_usuario_data, current_user=current_user)

    # Atualizando o campo `revisado` no modelo Usuario para "pendente"
    usuario = db.query(Usuario).filter(Usuario.id == current_user.id).first()
    if usuario:
        usuario.revisao = "pendente"
        db.add(usuario)
        db.commit()
        db.refresh(usuario)

    return {"message": "Informações do usuário criadas com sucesso", "info_usuario": db_info_usuario}

@router.put("/perfil")
async def upload_profile_picture(
    perfil: Usuario = Depends(get_current_user),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Verifique o tipo de arquivo
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="O arquivo deve ser uma imagem")

    # Salva a imagem no servidor
    new_filename = save_image(file, PROFILE_UPLOAD_DIR)

    # Atualiza a foto de perfil no banco de dados
    update_info_usuario_profile_picture(db, perfil, new_filename)

    return {"filename": new_filename}


@router.get("/{info_usuario_id}")
def read_info_usuario(info_usuario_id: int, db: Session = Depends(get_db)):
    db_info_usuario = get_info_usuario(db=db, info_usuario_id=info_usuario_id)
    if db_info_usuario is None:
        raise HTTPException(status_code=404, detail="InfoUsuario not found")
    return db_info_usuario


@router.delete("/{info_usuario_id}")
def delete_info_usuario(info_usuario_id: int, db: Session = Depends(get_db)):
    db_info_usuario = delete_info_usuario(db=db, info_usuario_id=info_usuario_id)
    if db_info_usuario is None:
        raise HTTPException(status_code=404, detail="InfoUsuario not found")
    return db_info_usuario

@router.put("/{info_usuario_id}")
def update_info_usuario(info_usuario: InfoUsuarioUpdate, db: Session = Depends(get_db),info_usuario_id:Usuario = Depends(get_current_user),):
    db_info_usuario = update_info_usuario_db(db=db, info_usuario_id=info_usuario_id, info_usuario=info_usuario)
    if db_info_usuario is None:
        raise HTTPException(status_code=404, detail="InfoUsuario not found")
    return db_info_usuario