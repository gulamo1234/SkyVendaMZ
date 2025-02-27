from fastapi import APIRouter
from controlers.ai import getAnswer
from pydantic import BaseModel

router = APIRouter()

class UserMessage(BaseModel):
    message: str
    sender_id:str    

@router.post("/skai")
def read_root(message:UserMessage):
    return getAnswer(message.sender_id,message.message)