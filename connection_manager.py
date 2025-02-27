from fastapi import WebSocket
from typing import Dict
from dataclasses import dataclass
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models import Message,Usuario
import logging
@dataclass
class Connection:
    id:int
    sky_user_id: str
    username: str
    name: str
    avatar: str
    websocket: WebSocket

class Notification(BaseModel):
    type: str
    title: str
    message: str
    data: dict = {}

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Connection] = {}
    
    async def connect(self, connection: Connection):
        await connection.websocket.accept()
        self.active_connections[connection.id] = connection

    async def disconnect(self, id: int):
        if id in self.active_connections:
            disconnected_user = self.active_connections[id]
            notification = Notification(
                type="user_disconnected",
                title="Usuário offline",
                message=f"{disconnected_user.username} está offline",
                data={
                    "user_id": id,
                    "username": disconnected_user.username
                }
            )

            # Remove o usuário antes de enviar as notificações
            del self.active_connections[id]

            # Notifica os usuários restantes
            for connection in self.active_connections.values():
                await connection.websocket.send_json({
                    "type": "notification",
                    "data": notification.dict()
                })

    async def send_message(self, message: str, from_user: str, to_user: str, user_id,db: Session):
        
        new_message = Message(
            sender_id=user_id, 
            receiver_id=to_user, 
            content=message, 
            message_type="text",  # Altere de acordo com o tipo de mensagem
            is_read=False
        )
        db.add(new_message)
        db.commit()
        # Envia mensagem para um usuário específico 
        if to_user in self.active_connections:
            receiver_connection = self.active_connections[to_user]
            try:
                await receiver_connection.websocket.send_json({
                "type": "message",
                "data": {
                    "from_user": from_user,
                    "content": message
                    }
                })
                return True 
            except:
                pass
        
        return False

    async def send_notification(self, title: str, type: str, message: str):
        # Envia notificação para todos os usuários
        notification = Notification(
            type=type,
            title=title,
            message=message,
            data={"timestamp": "22:00"}
        )

        for connection in self.active_connections.values():
            try:
                await connection.websocket.send_json({
                    "type": "notification",
                    "data": notification.dict()
                })
            except:
                pass

    async def send_typing_notification(self, from_user: str, to_user: str):
        # Envia uma notificação de 'digitando...' para um usuário específico 
        if to_user in self.active_connections:
            sender = self.active_connections.get(from_user)  # Obtém os dados do remetente
            receiver_connection = self.active_connections[to_user]
            
            if sender:  
                message = {
                    "type": "typing",
                    "data": {
                        "from_user": from_user,
                        "username": sender.username,  # Inclui o username do remetente
                        "message": "está digitando..."
                    }
                }
                try:
                    await receiver_connection.websocket.send_json(message)
                except Exception as e:
                    pass

    def get_online_users(self):
        # Retorna a lista de usuários online
        return [
            {   
                "id":conn.id,
                "sky_user_id": conn.sky_user_id,
                "username": conn.username,
                "name": conn.name,
                "avatar": conn.avatar
            }
            for conn in self.active_connections.values()
        ]
