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
    
def obter_usuarios_que_estao_tecando(messages, usuario_id):
    # Dicionário para armazenar as conversas
    chats = defaultdict(list)

    # Agrupar mensagens por par de usuários
    for msg in messages:
        key = tuple(sorted([msg["sender_id"], msg["receiver_id"]]))  # Criando chave única para a conversa
        chats[key].append(msg)

    # Ordenar mensagens dentro de cada chat
    for key in chats:
        chats[key].sort(key=lambda x: datetime.fromisoformat(x["created_at"]))

    # Obter a última mensagem de cada conversa e verificar se o usuário está na conversa
    resultado = []
    for key, chat in chats.items():
        last_msg = chat[-1]
        if usuario_id in key:  # Verifica se o usuário está na conversa
            # Definir quem está enviando a mensagem (quem é o outro usuário)
            other_user_id = key[0] if key[1] == usuario_id else key[1]
            
            # Obter os detalhes do outro usuário
            if last_msg["sender_id"] == other_user_id:
                nome = last_msg["sender"]["nome"]
                username = last_msg["sender"].get("username", "")  # Username do remetente
                sky_user_id = last_msg["sender"].get("sky_user_id", "sk-282")  # Sky user id do remetente
                foto = last_msg["sender"].get("foto_perfil", None)  # Foto do remetente
            else:
                nome = last_msg["receiver"]["nome"]
                username = last_msg["receiver"].get("username", "")  # Username do destinatário
                sky_user_id = last_msg["receiver"].get("sky_user_id", "sk-282")  # Sky user id do destinatário
                foto = last_msg["receiver"].get("foto_perfil", None)  # Foto do destinatário

            resultado.append({
                "id":other_user_id,
                "nome": nome,
                "username": username,
                "sky_user_id": sky_user_id,
                "foto": foto,
                "ultima_mensagem": last_msg["content"],
                "data": last_msg["created_at"]
            })

    return resultado

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

@router.get('/mychat')
def mychat(db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    mensagens = db.query(MessageModel)\
        .options(joinedload(MessageModel.sender), joinedload(MessageModel.receiver))\
        .filter(
            (MessageModel.sender_id == current_user.id) | (MessageModel.receiver_id == current_user.id)
        )\
        .order_by(MessageModel.created_at.desc())\
        .all()
    mensagens_dict = [
        {
            "sender_id": msg.sender_id,
            "receiver_id": msg.receiver_id,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),  # Convertendo o timestamp para string
            "sender": {
                "nome": msg.sender.nome,
                "username":msg.sender.username,
                "sky_user_id":msg.sender.identificador_unico,
                "foto_perfil": msg.sender.foto_perfil
            },
            "receiver": {
                "nome": msg.receiver.nome,
                "username":msg.receiver.username,
                "sky_user_id":msg.receiver.identificador_unico,
                "foto_perfil": msg.receiver.foto_perfil
            }
        }
        for msg in mensagens
    ]
    
    return obter_usuarios_que_estao_tecando(mensagens_dict, current_user.id)

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

            except Exception as e:
                logging.error(f"Erro ao processar mensagem: {e}")
                # Envia uma resposta de erro para o cliente, mas não fecha a conexão
                await websocket.send_json({
                    "error": f"Ocorreu um erro ao processar sua mensagem: {str(e)}"
                })
                continue  # Continua o loop para receber novas mensagens

    except Exception as e:
        logging.error(f"Erro geral no WebSocket: {e}")
        await websocket.close(code=5000, reason="Erro interno no servidor")

        

    