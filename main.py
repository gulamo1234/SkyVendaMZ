from sqlalchemy.orm import Session
from database import SessionLocal, engine
from typing import List, Dict,Any
from fastapi.staticfiles import StaticFiles
import os
from sqlalchemy.orm import joinedload
from models import Base
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect,HTTPException, status,Form,Body,Query,Depends
#OLA MUNDOd
from fastapi.responses import HTMLResponse
from routers.admin import router as admin_router
from routers.comentario import router as comentario_router
from routers.ai import router as ai_router
from routers.denuncia_produto import router as denuncia_produto_router
from routers.endereco_envio import router as endereco_envio_router
from routers.info_usuario import router as info_usuario_router
from routers.mensagem import router as mensagem_router
from routers.pedido import router as pedido_router
from routers.produto import router as produto_router
from routers.usuario import router as usuario_router
from routers.pesquisa import router as pesquisa_router
from routers.websocket_routes import router as ws
from fastapi_utils.tasks import repeat_every
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse,HTMLResponse
# from controlers.scheduler import init_scheduler
# from controlers.produto import verificar_produtos_expiracao
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, WebSocketException
from fastapi.staticfiles import StaticFiles
from connection_manager import ConnectionManager,Connection
from pydantic import BaseModel
app = FastAPI(swagger_ui_parameters={"defaultModelsExpandDepth": -1})

# init_scheduler(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Manipulador de exceção para erros de validação
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Mostra detalhes do erro no console
    print("Erro de validação:", exc.errors())
    
    # Retorna o erro como uma resposta JSON, transformando-o em um formato serializável
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )


BASE_UPLOAD_DIR = "uploads/"
#PRODUCT_UPLOAD_DIR = "uploads/produto"
#app.mount("/video", StaticFiles(directory=os.path.join(BASE_UPLOAD_DIR, "")), name="")

# Montar o diretório de produtos
app.mount("/produto", StaticFiles(directory=os.path.join(BASE_UPLOAD_DIR, "produto")), name="produto")

# Montar o diretório de perfil
app.mount("/perfil", StaticFiles(directory=os.path.join(BASE_UPLOAD_DIR, "perfil")), name="perfil")

# Montar o diretório de documentos
app.mount("/documentos", StaticFiles(directory=os.path.join(BASE_UPLOAD_DIR, "documentos")), name="documentos")

# Montar o diretório de estatus
app.mount("/status", StaticFiles(directory=os.path.join(BASE_UPLOAD_DIR, "status")), name="status")
 
app.mount("/anuncios", StaticFiles(directory=os.path.join(BASE_UPLOAD_DIR, "anuncios")), name="anuncios")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Registrar os routers
app.include_router(admin_router)
app.include_router(ai_router)
app.include_router(comentario_router)
app.include_router(denuncia_produto_router)
app.include_router(endereco_envio_router)
app.include_router(info_usuario_router)
app.include_router(mensagem_router)
app.include_router(pedido_router)
app.include_router(produto_router)
app.include_router(usuario_router)
app.include_router(pesquisa_router)

#websocket route
app.include_router(ws)


def create_db():
    Base.metadata.create_all(bind=engine)

# @app.on_event("startup")
# @repeat_every(seconds=60 * 60 * 12)  # Executa a cada 12 horas
# async def verificar_expiracoes():
#     await verificar_produtos_expiracao()

if __name__ == "__main__":
     import uvicorn
     uvicorn.run(app,host='0.0.0.0',port=8000)
