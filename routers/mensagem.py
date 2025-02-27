from fastapi import APIRouter, WebSocket, UploadFile, File, Depends, HTTPException, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import aiofiles
import os
from datetime import datetime
import shortuuid
from database import SessionLocal
from models import Message, MessageType, Produto, Usuario, Notificacao
# from controlers.connection_mannager import ConnectionManager
#from database import get_db  # Importa sua função de obter a sessão do banco de dados
from auth import * # Supondo que você tenha uma dependência para obter o usuário atual
from pydantic import BaseModel
router = APIRouter()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class MessageSchema(BaseModel):
    sender: str
    receiver: str
    data:str
# conection_manager=ConnectionManager()   
@router.post("/send_message")
async def send_message(message: MessageSchema, db: Session = Depends(get_db)):
    # conection_manager.send_personal_message(message.data, message.receiver)
    return message