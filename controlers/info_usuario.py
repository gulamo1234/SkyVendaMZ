import os
import uuid
import shutil
from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile, File
from datetime import datetime
from models import InfoUsuario, Notificacao,Usuario
from schemas import InfoUsuarioCreate, InfoUsuarioUpdate

# Definindo caminhos de upload
PROFILE_UPLOAD_DIR = "uploads/perfil"
DOCUMENT_UPLOAD_DIR = "uploads/documentos"

# Criando diretórios se não existirem
os.makedirs(PROFILE_UPLOAD_DIR, exist_ok=True)
os.makedirs(DOCUMENT_UPLOAD_DIR, exist_ok=True)

def save_image(file: UploadFile, upload_dir: str) -> str:
    """
    Salva uma imagem no diretório especificado.

    Args:
        file (UploadFile): Arquivo da imagem enviada pelo usuário.
        upload_dir (str): Diretório onde a imagem será armazenada.

    Returns:
        str: Nome único do arquivo salvo.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="O arquivo enviado não é uma imagem.")

    # Gerando um nome de arquivo único
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)

    # Salvando a imagem no diretório apropriado
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return unique_filename
def create_info_usuario_db(db: Session, info_usuario: InfoUsuarioCreate, current_user: Usuario):
    """
    Cria uma nova entrada de InfoUsuario no banco de dados para o usuário autenticado.

    Args:
        db (Session): Sessão do banco de dados.
        info_usuario (InfoUsuarioCreate): Dados do usuário.
        current_user (Usuario): Instância do usuário autenticado.

    Returns:
        InfoUsuario: Instância do InfoUsuario criada.
    """
    # Verificar se o usuário já tem um InfoUsuario
    if db.query(InfoUsuario).filter(InfoUsuario.usuario_id == current_user.id).first():
        raise HTTPException(status_code=400, detail="Usuário já possui informações cadastradas.")
    
    # Criar InfoUsuario associado ao usuário autenticado
    db_info_usuario = InfoUsuario(**info_usuario.dict())
    db.add(db_info_usuario)
    db.commit()
    db.refresh(db_info_usuario)
    return db_info_usuario


def get_info_usuarios(db: Session):
    """
    Recupera todas as entradas de InfoUsuario no banco de dados.

    Args:
        db (Session): Sessão do banco de dados.

    Returns:
        List[InfoUsuario]: Lista de instâncias InfoUsuario.
    """
    return db.query(InfoUsuario).all()

def get_info_usuario(db: Session, info_usuario_id: int):
    """
    Recupera uma entrada de InfoUsuario pelo ID.

    Args:
        db (Session): Sessão do banco de dados.
        info_usuario_id (int): ID do InfoUsuario.

    Returns:
        InfoUsuario: Instância do InfoUsuario se encontrado, caso contrário None.
    """
    return db.query(InfoUsuario).filter(InfoUsuario.id == info_usuario_id).first()

def update_info_usuario_db(db: Session, info_usuario_id: int, info_usuario: InfoUsuarioUpdate):
    """
    Atualiza uma entrada existente de InfoUsuario no banco de dados.

    Args:
        db (Session): Sessão do banco de dados.
        info_usuario_id (int): ID do InfoUsuario.
        info_usuario (InfoUsuarioUpdate): Novos dados para o InfoUsuario.

    Returns:
        InfoUsuario: Instância do InfoUsuario atualizada se encontrado, caso contrário None.
    """
    db_info_usuario = db.query(InfoUsuario).filter(InfoUsuario.id == info_usuario_id).first()
    if db_info_usuario:
        for key, value in info_usuario.dict().items():
            setattr(db_info_usuario, key, value)
        db.commit()
        db.refresh(db_info_usuario)
    return db_info_usuario



def enviar_notificacao(db: Session, usuario_id: int, mensagem: str):
    """
    Função para enviar notificações para o usuário.
    
    Args:
        db (Session): Sessão do banco de dados.
        usuario_id (int): ID do usuário que receberá a notificação.
        mensagem (str): Mensagem da notificação.
    
    Returns:
        Notificação criada.
    """
    notificacao = Notificacao(
        usuario_id=usuario_id,
        mensagem=mensagem,
        data=datetime.utcnow()  # Adicionando a data aqui, se necessário
    )
    db.add(notificacao)
    db.commit()
    db.refresh(notificacao)
    return notificacao


def update_revisao_info_usuario(db_info_usuario, nova_revisao: str, db: Session, motivo: str = None):
    """
    Atualiza o campo 'revisao' do InfoUsuario e do Usuario, e cria uma notificação associada ao usuário.

    Args:
        db_info_usuario: Instância do InfoUsuario do banco de dados.
        nova_revisao (str): Novo valor para o campo 'revisao'.
        db (Session): Sessão do banco de dados.
        motivo (str, opcional): Motivo do não-aprovamento se a revisão for negativa.
    
    Returns:
        dict: Mensagem de sucesso e o InfoUsuario atualizado.
    """
    # Verifica se o db_info_usuario está corretamente associado a um usuário
    if not db_info_usuario.usuario_id:
        raise HTTPException(status_code=400, detail="InfoUsuario não está associado a um usuário válido.")

    # Atualiza o campo 'revisao' no InfoUsuario
    db_info_usuario.revisao = nova_revisao

    # Atualiza o campo 'revisao' no Usuario para True se a nova revisão for positiva
    if nova_revisao == "sim":
        usuario = db.query(Usuario).filter(Usuario.id == db_info_usuario.usuario_id).first()
        if usuario:
            usuario.revisao = nova_revisao  # Define revisao como True
        else:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    try:
        db.commit()  # Salvar as alterações no banco
        db.refresh(db_info_usuario)  # Atualiza a instância do InfoUsuario
    except Exception as e:
        db.rollback()  # Desfaz alterações em caso de erro
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar 'revisao': {str(e)}")

    # Cria a mensagem da notificação dependendo da revisão
    if nova_revisao == "nao":
        mensagem = f"Seu perfil foi reprovado. Motivo: {motivo}" if motivo else "Seu perfil foi reprovado."
    else:
        mensagem = "Seu perfil foi aprovado com sucesso."

    # Chama a função enviar_notificacao para criar a notificação
    try:
        enviar_notificacao(db, db_info_usuario.usuario_id, mensagem)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao enviar notificação: {str(e)}")

    return {
        "message": "Campo 'revisao' atualizado com sucesso e notificação enviada.",
        "info_usuario": db_info_usuario
    }


# Função para atualizar a foto de perfil no banco de dados
def update_info_usuario_profile_picture(db: Session, usuario: Usuario, new_filename: str):
    usuario.foto_perfil = new_filename  # Atualiza o campo 'foto_perfil'
    db.commit()  # Confirma as mudanças no banco de dados
    db.refresh(usuario)  # Atualiza o objeto com os dados mais recentes do banco



def update_info_usuario_document_picture(db: Session, info_usuario_id: int, new_document_picture: str):
    """
    Atualiza apenas a foto de documento do usuário no banco de dados.

    Args:
        db (Session): Sessão do banco de dados.
        info_usuario_id (int): ID do InfoUsuario.
        new_document_picture (str): Nome do novo arquivo de foto de documento.
    """
    db_info_usuario = db.query(InfoUsuario).filter(InfoUsuario.id == info_usuario_id).first()
    if db_info_usuario:
        db_info_usuario.foto_bi = new_document_picture
        db.commit()
        db.refresh(db_info_usuario)
    else:
        raise HTTPException(status_code=404, detail="Informações do usuário não encontradas.")

def delete_info_usuario(db: Session, info_usuario_id: int):
    """
    Remove uma entrada de InfoUsuario do banco de dados.

    Args:
        db (Session): Sessão do banco de dados.
        info_usuario_id (int): ID do InfoUsuario.

    Returns:
        InfoUsuario: Instância do InfoUsuario removido se encontrado, caso contrário None.
    """
    db_info_usuario = db.query(InfoUsuario).filter(InfoUsuario.id == info_usuario_id).first()
    if db_info_usuario:
        db.delete(db_info_usuario)
        db.commit()
    return db_info_usuario
