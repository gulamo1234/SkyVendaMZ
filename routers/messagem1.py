from fastapi import APIRouter, WebSocket, UploadFile, File, Depends, HTTPException, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import aiofiles
import os
from datetime import datetime
import shortuuid
from database import SessionLocal
from models import Message, MessageType, Produto, Usuario, Notificacao
from controlers.websocket_manager import manager
#from database import get_db  # Importa sua função de obter a sessão do banco de dados
from auth import * # Supondo que você tenha uma dependência para obter o usuário atual

router = APIRouter()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Configuração para upload de arquivos
UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def save_upload_file(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
        
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{shortuuid.uuid()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    async with aiofiles.open(file_path, 'wb') as out_file:
        while content := await file.read(1024 * 1024):  # 1MB chunks
            await out_file.write(content)
            
    return unique_filename

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int,
    db: Session = Depends(get_db)
):
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "typing":
                await manager.notify_typing(
                    typing_user_id=user_id,
                    receiver_id=data["receiver_id"],
                    is_typing=data["is_typing"]
                )
                
            elif data["type"] == "message":
                # Verificar se é uma mensagem sobre produto
                produto_id = data.get("produto_id")
                if produto_id:
                    produto = db.query(Produto).filter(Produto.id == produto_id).first()
                    if produto:
                        content = f"Sobre o produto '{produto.nome}': {data['content']}"
                    else:
                        content = data['content']
                else:
                    content = data['content']

                message = Message(
                    sender_id=user_id,
                    receiver_id=data["receiver_id"],
                    content=content,
                    message_type=MessageType.TEXT,
                    produto_id=produto_id  # Adicionar referência ao produto
                )
                db.add(message)
                db.commit()
                
                await manager.send_personal_message(
                    {
                        "type": "message",
                        "message": {
                            "id": message.id,
                            "sender_id": message.sender_id,
                            "content": message.content,
                            "created_at": message.created_at.isoformat(),
                            "message_type": message.message_type,
                            "produto_id": produto_id
                        }
                    },
                    data["receiver_id"]
                )
                
    except Exception as e:
        manager.disconnect(user_id)

@router.post("/upload/{receiver_id}")
async def upload_file(
    receiver_id: int,
    file: UploadFile = File(...),
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")
        
    file_ext = os.path.splitext(file.filename)[1].lower()
    message_type = None
    
    if file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
        message_type = MessageType.IMAGE
    elif file_ext == '.pdf':
        message_type = MessageType.PDF
    elif file_ext in ['.mp3', '.wav']:
        message_type = MessageType.AUDIO
    elif file_ext in ['.mp4', '.mov']:
        message_type = MessageType.VIDEO
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")
        
    file_path = await save_upload_file(file)
    
    message = Message(
        sender_id=current_user_id,
        receiver_id=receiver_id,
        message_type=message_type,
        file_url=file_path,
        file_name=file.filename,
        file_size=file_size
    )
    db.add(message)
    db.commit()
    
    await manager.send_personal_message(
        {
            "type": "message",
            "message": {
                "id": message.id,
                "sender_id": message.sender_id,
                "message_type": message_type,
                "file_url": file_path,
                "file_name": message.file_name,
                "file_size": message.file_size,
                "created_at": message.created_at.isoformat()
            }
        },
        receiver_id
    )
    
    return {"message": "File uploaded successfully"}

@router.get("/messages/{other_user_id}")
async def get_messages(
    other_user_id: int,
    current_user: Usuario = Depends(get_current_user),
    produto_id: Optional[int] = Query(None, description="ID do produto para filtrar mensagens"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Busca mensagens entre dois usuários, com opção de filtrar por produto.
    """
    # Query base para mensagens entre os usuários
    query = db.query(Message).filter(
        (
            (Message.sender_id == current_user.id) & 
            (Message.receiver_id == other_user_id)
        ) |
        (
            (Message.sender_id == other_user_id) & 
            (Message.receiver_id == current_user.id)
        )
    )

    # Se produto_id for fornecido, filtra mensagens daquele produto
    if produto_id:
        produto = db.query(Produto).filter(Produto.id == produto_id).first()
        if not produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
            
        # Verifica se o usuário tem permissão para ver as mensagens do produto
        if current_user.id != produto.CustomerID and current_user.id != other_user_id:
            raise HTTPException(
                status_code=403,
                detail="Você não tem permissão para ver estas mensagens"
            )
            
        query = query.filter(Message.produto_id == produto_id)

    # Ordenar e paginar resultados
    messages = query.order_by(Message.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()

    # Formatar resposta
    return {
        "total": len(messages),
        "messages": [
            {
                "id": msg.id,
                "sender": {
                    "id": msg.sender_id,
                    "nome": db.query(Usuario).get(msg.sender_id).nome
                },
                "receiver": {
                    "id": msg.receiver_id,
                    "nome": db.query(Usuario).get(msg.receiver_id).nome
                },
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
                "message_type": msg.message_type,
                "produto": {
                    "id": msg.produto_id,
                    "nome": db.query(Produto).get(msg.produto_id).nome
                } if msg.produto_id else None
            }
            for msg in messages
        ]
    }

@router.post("/send/{receiver_id}")
async def send_message(
    receiver_id: int,
    content: str = Form(...),
    produto_id: Optional[int] = Form(None),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Envia uma mensagem para outro usuário, opcionalmente relacionada a um produto.
    """
    try:
        # Se produto_id for fornecido, verifica e formata a mensagem
        if produto_id:
            produto = db.query(Produto).filter(Produto.id == produto_id).first()
            if not produto:
                raise HTTPException(status_code=404, detail="Produto não encontrado")
            
            # Verifica se não está tentando enviar mensagem para si mesmo
            if produto.CustomerID == current_user.id:
                raise HTTPException(
                    status_code=400,
                    detail="Você não pode enviar mensagem para si mesmo"
                )
            
            content = f"Sobre o produto '{produto.nome}': {content}"
            receiver_id = produto.CustomerID

        # Criar e salvar a mensagem
        message = Message(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=content,
            message_type=MessageType.TEXT,
            produto_id=produto_id
        )
        db.add(message)
        
        # Criar notificação
        notificacao = Notificacao(
            usuario_id=receiver_id,
            mensagem=f"Nova mensagem de {current_user.nome}",
            data=datetime.utcnow()
        )
        db.add(notificacao)
        
        db.commit()
        db.refresh(message)

        # Enviar mensagem em tempo real
        await manager.send_personal_message(
            {
                "type": "message",
                "message": {
                    "id": message.id,
                    "sender_id": message.sender_id,
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                    "message_type": message.message_type,
                    "produto_id": produto_id
                }
            },
            receiver_id
        )

        return {
            "message": "Mensagem enviada com sucesso",
            "id": message.id,
            "created_at": message.created_at.isoformat()
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao enviar mensagem: {str(e)}"
        )

@router.post("/produto/{produto_id}/mensagem")
async def enviar_mensagem_vendedor(
    produto_id: int,
    mensagem: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Envia uma mensagem para o vendedor de um produto específico.
    """
    # Buscar o produto e seu vendedor
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    # Verificar se o usuário não está tentando enviar mensagem para si mesmo
    if produto.CustomerID == current_user.id:
        raise HTTPException(
            status_code=400, 
            detail="Você não pode enviar mensagem para si mesmo"
        )

    try:
        # Criar a mensagem
        nova_mensagem = Message(
            sender_id=current_user.id,
            receiver_id=produto.CustomerID,
            content=f"Sobre o produto '{produto.nome}': {mensagem}",
            message_type=MessageType.TEXT
        )
        db.add(nova_mensagem)
        db.commit()
        db.refresh(nova_mensagem)

        # Enviar notificação em tempo real se o vendedor estiver conectado
        await manager.send_personal_message(
            {
                "type": "message",
                "message": {
                    "id": nova_mensagem.id,
                    "sender_id": nova_mensagem.sender_id,
                    "content": nova_mensagem.content,
                    "created_at": nova_mensagem.created_at.isoformat(),
                    "message_type": nova_mensagem.message_type,
                    "produto_id": produto_id,
                    "produto_nome": produto.nome
                }
            },
            produto.CustomerID
        )

        # Criar uma notificação para o vendedor
        notificacao = Notificacao(
            usuario_id=produto.CustomerID,
            mensagem=f"Nova mensagem de {current_user.nome} sobre o produto '{produto.nome}'",
            data=datetime.utcnow()
        )
        db.add(notificacao)
        db.commit()

        return {
            "message": "Mensagem enviada com sucesso",
            "details": {
                "message_id": nova_mensagem.id,
                "produto": {
                    "id": produto.id,
                    "nome": produto.nome
                },
                "vendedor": {
                    "id": produto.CustomerID
                },
                "data_envio": nova_mensagem.created_at.isoformat()
            }
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao enviar mensagem: {str(e)}"
        )

@router.get("/produto/{produto_id}/conversas")
async def listar_conversas_produto(
    produto_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Lista todas as mensagens relacionadas a um produto específico.
    Apenas o vendedor pode ver todas as conversas sobre seu produto.
    """
    # Buscar o produto
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    # Verificar se o usuário é o vendedor
    if produto.CustomerID != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Apenas o vendedor pode ver todas as conversas sobre o produto"
        )

    # Buscar mensagens que mencionam o produto
    mensagens = db.query(Message).filter(
        Message.content.like(f"%Sobre o produto '{produto.nome}':%")
    ).order_by(
        Message.created_at.desc()
    ).offset(skip).limit(limit).all()

    return {
        "produto": {
            "id": produto.id,
            "nome": produto.nome
        },
        "mensagens": [
            {
                "id": msg.id,
                "remetente": {
                    "id": msg.sender_id,
                    "nome": db.query(Usuario).get(msg.sender_id).nome
                },
                "conteudo": msg.content,
                "data": msg.created_at.isoformat(),
                "tipo": msg.message_type
            }
            for msg in mensagens
        ]
    }
