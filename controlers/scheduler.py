from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from database import SessionLocal
from controlers.pedido import verificar_liberacao_automatica
from controlers.produto import verificar_produtos_expiracao
from controlers.utils import renovar_produtos_automaticamente

def init_scheduler(app: FastAPI):
    scheduler = AsyncIOScheduler()

    # Agendar verificação de liberação automática de pedidos (meia-noite)
    scheduler.add_job(
        verificar_liberacao_automatica,
        CronTrigger(hour=0, minute=0),
        id="verificar_liberacao",
        name="Verifica e libera pedidos após prazo de confirmação",
        replace_existing=True,
    )

    # Agendar verificação de produtos expirados (a cada 12 horas)
    scheduler.add_job(
        verificar_produtos_expiracao,
        CronTrigger(hour="*/12"),
        id="verificar_produtos",
        name="Verifica produtos expirados e envia notificações",
        replace_existing=True,
    )

    # Agendar renovação automática de produtos (meia-noite)
    scheduler.add_job(
        lambda: _renovar_produtos_wrapper(),
        CronTrigger(hour=0, minute=0),
        id="renovar_produtos",
        name="Renova produtos automaticamente",
        replace_existing=True,
    )

    @app.on_event("startup")
    async def start_scheduler():
        scheduler.start()

    @app.on_event("shutdown")
    async def shutdown_scheduler():
        scheduler.shutdown()

def _renovar_produtos_wrapper():
    """
    Função wrapper para chamar a lógica de renovação automática de produtos
    com controle de sessão do banco de dados.
    """
    db: Session = SessionLocal()
    try:
        renovar_produtos_automaticamente(db=db)
    finally:
        db.close()
