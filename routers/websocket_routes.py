from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect,status,HTTPException
from starlette.websockets import WebSocketState
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload
from auth import get_db
from pydantic import BaseModel
from typing import Any
from models import Usuario
from models import Message as MessageModel
from auth import get_db, get_current_user_socket, get_current_user
from collections import defaultdict
from datetime import datetime
import logging

from connection_manager import ConnectionManager, Connection

class Message(BaseModel):
    to_user: str
    content: str
    

router = APIRouter()  

#conexao com websocket
manager = ConnectionManager()

@router.get("/")
async def get():
    with open("static/index.html") as f:
        return HTMLResponse(f.read())

@router.get("/online-users")
async def get_online_users():
    return manager.get_online_users()

@router.get('/chats')
def listar_chats(db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    # Buscar todas as mensagens onde o usuário atual está envolvido
    mensagens = db.query(MessageModel)\
        .options(joinedload(MessageModel.sender), joinedload(MessageModel.receiver))\
        .filter(
            (MessageModel.sender_id == current_user.id) | (MessageModel.receiver_id == current_user.id)
        )\
        .order_by(MessageModel.created_at.asc())\
        .all()

    # Estrutura de dicionário para agrupar as mensagens por usuário
    chats = {}

    for msg in mensagens:
        # Identificar o outro usuário na conversa
        if msg.sender_id == current_user.id:
            outro_usuario = msg.receiver
        else:
            outro_usuario = msg.sender

        # Se o outro usuário ainda não estiver no dicionário, adicionamos
        if outro_usuario.id not in chats:
            chats[outro_usuario.id] = {
                "id": outro_usuario.id,
                "nome": outro_usuario.nome,
                "avatar":outro_usuario.foto_perfil,
                "username": outro_usuario.username,
                "sky_user_id": outro_usuario.identificador_unico,
                "foto": outro_usuario.foto_perfil,
                "mensagens": []
            }

        # Adicionar mensagem à conversa correspondente
        chats[outro_usuario.id]["mensagens"].append({
            "id": msg.id,
            "sender_id": msg.sender_id,
            "receiver_id": msg.receiver_id,
            "content": msg.content,
            "created_at": msg.created_at.isoformat()
        })

    return list(chats.values())  # Retornar a lista de chats formatada

@router.get('/testepush')
async def testepush():
    await manager.send_notification('Publicado', 'post_new', 'Novo post publicado')

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)) -> None:
    try:
        token: str | None = websocket.query_params.get("token")
        
        if not token:
            await websocket.close(code=4003, reason="Token JWT é obrigatório")
            return
        
        # Validação de token centralizada
        current_user: Usuario = get_current_user_socket(token, db)
        perfil: Usuario | None = db.query(Usuario).filter_by(id=current_user.id).first()
        
        if not perfil:
            await websocket.close(code=4004, reason="Perfil de usuário não encontrado")
            return

        connection: Connection = Connection(
            id=perfil.id,
            sky_user_id=perfil.identificador_unico,
            username=perfil.username,
            name=perfil.nome,
            avatar=perfil.foto_perfil,
            websocket=websocket
        )
        
        # Conectar e registrar a conexão
        await manager.connect(connection)
        logging.info(f"Usuário {perfil.username} conectado ao WebSocket")

        while True:
            try:
                data: dict[str, Any] = await websocket.receive_json()
                
                if data.get("type") == "typing":
                    # Verifica se há 'to_user' antes de enviar notificação
                    if "to_user" in data:
                        await manager.send_typing_notification(
                            from_user=perfil.id,
                            to_user=data["to_user"]
                        )
                    continue  # Continua o loop para o próximo recebimento

                # Envio de mensagem
                if data.get("type") == "message":
                    await manager.send_message(
                        message=data["content"],
                        from_user=perfil.id,
                        user_id=perfil.id,
                        to_user=data["to_user"],
                        db=db
                    )
                else:
                    await websocket.send_json({
                        "error": "Formato inválido. Campos obrigatórios: content, to_user"
                    })

            except WebSocketDisconnect:
                await manager.disconnect(perfil.id)

            except Exception as e:
                await websocket.send_json({
                    "error": f"Ocorreu um erro ao processar sua mensagem: {str(e)}"
                })
                continue  # Continua o loop para receber novas mensagens
    except Exception as e:
        logging.error(f"Erro geral no WebSocket: {e}")
        await websocket.close(code=5000, reason="Erro interno no servidor")

        

    