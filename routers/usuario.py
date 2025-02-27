from fastapi import APIRouter, Depends, HTTPException, status,Form,Body,Query
from sqlalchemy.orm import Session
from models import Usuario, Transacao, Publicacao, Notificacao,Seguidor,OTP
from schemas import *
import random
from urllib.parse import urlencode
from database import SessionLocal
from fastapi.security import OAuth2PasswordRequestForm
from models import *
from passlib.context import CryptContext
from controlers.usuario import *
from controlers.utils import *
from controlers.produto import seguir_usuario,get_seguidores,calcular_tempo_publicacao
from auth import get_current_user, create_access_token, authenticate_user
from passlib.context import CryptContext
from datetime import datetime, timedelta
from auth import *
from fastapi.responses import RedirectResponse
import requests
#atsk_b4716771c78e659d863ad07c5292284d5501df7a3d5ec4997de3657581d8f3388203aabe
from sqlalchemy import or_
import httpx
import json
from decimal import Decimal
from controlers.utils import gerar_identificador_unico
import logging
import jwt


SECRET_KEY = "sua_chave_secreta_forte"
ALGORITHM = "HS256"
RESET_TOKEN_EXPIRATION = 10  # minutos
# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URLs do frontend
FRONTEND_URL = "https://skyvenda-mz.vercel.app"
SUCCESS_URL = f"{FRONTEND_URL}/auth/success"
ERROR_URL = f"{FRONTEND_URL}/auth/error"

router = APIRouter(prefix="/usuario", tags=["rotas de usuarios"])



#FUNCOES
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
#mpesa
url = "https://api.sandbox.vm.co.mz:18352/ipg/v1x/c2bPayment/singleStage/"
#google
GOOGLE_CLIENT_ID ="176605076915-cvolrc3k1hjlkedlu7b9c19hi8ft7tuc.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
GOOGLE_REDIRECT_URI = "https://skyvendamz.up.railway.app/usuario/auth/callback"

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI = "https://www.googleapis.com/oauth2/v3/userinfo"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()





# Modelo para entrada de pagamento
class PagamentoModel(BaseModel):
    msisdn: str  # Número de telefone do cliente
    valor: str   # Valor a ser carregado


# Função para adicionar saldo usando M-Pesa (sem autenticação)
@router.post("/{user_id}/pagamento/")
def adicionar_saldo_via_mpesa(msisdn: str, valor: int, db: Session = Depends(get_db),current_user: Usuario = Depends(get_current_user)):
    # Buscar o usuário no banco de dados
    usuario = db.query(Usuario).filter(Usuario.id == current_user.id).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    # Verifica se o usuário passou pela revisão
    info_usuario = db.query(InfoUsuario).filter(InfoUsuario.usuario_id == usuario.id).first()
    if not info_usuario or info_usuario.revisao != "sim":
        raise HTTPException(status_code=403, detail="Usuário não passou pela revisão e não pode adicionar saldo.")
    
    # Cabeçalhos e payload para a requisição M-Pesa
    # Cabeçalhos da solicitação
    token="XfsLebYAsnNPRsMu6JKfRPH9W5fhzSb+W3cdizVQ/Bm5ho2Xi/tn/Oo4bwHmFLqYlHQVnrog3MziMmxZLN5NnPEqCu5F9tLeYwmIo4mqNp544Ai5B8s+IAbxr//WLIS+pk992fp6uZl8IgFkQreqsN+leWSgQdeW7oiGl7Z5k6e10uc4xuD3KOEldtye0Pzjj0DmHNdhDh8SzpdgkjyEmWPhvyMwCVxn80pqaKAH5UUDGxv+dbY4HgsoAprMC+hclhHkVfk5VfqNlOToxpn6LmfeoZZ5BJJysEA/Y/T3zlK9JYq+dWahlWyMv+UoMEh7VG1lw3k/Hb7dqKkSRmrhStsuRrHjAITKRSoWv98ZWntQQua+Fz/BGV7v6f6qsytTBHCWVJD3qWl3phKztYWpr0CeJ3aGYns+gtKP04V2WdPrqVylYJFEQILGCfKmtFqYZ3rhdKhgs4UDAOQMCkED4uS+op0p+I6kW6ftAyw6WDu5dqQ5OFKV3++f/015kptDzRpoieB1EfUltgabnfWCNzivi7ZJY6S+5+ZJPDI9ORjYq+QlF+Qi/RQmJiGWDh+S/UY2sA2d9692lfmWKk3+10YAUoZlQTlq9qCvqVXYVwquiLkUpHhnpNMbidVBwuBM03IxA0SrmervTM7RY2mS1BXTwO2IQekX+9bnJ6+Tpkk="
    headers = {
           "Content-Type": "application/json",
           "Authorization": f"Bearer {token}",
           "Origin": "developer.mpesa.vm.co.mz"
    }

    # Dados da requisição
    data = {
        "input_TransactionReference": "T12344C",  # Gere uma referência única para cada transação
        "input_CustomerMSISDN": msisdn,           # Número de telefone do cliente
        "input_Amount": str(valor),               # Valor a ser carregado
        "input_ThirdPartyReference": "11115",     # Referência única de terceiros
        "input_ServiceProviderCode": "171717"     # Código do provedor de serviço
    }

    url_pyment = 'https://api.sandbox.vm.co.mz:18345/ipg/v1x/b2cPayment/'
# Enviar a requisição para a API da M-Pesa
    response = requests.post(url_pyment, headers=headers,verify=True, data=json.dumps(data))

    if response.status_code ==422:
        transacao = Transacao(usuario_id=usuario.id, msisdn=msisdn, valor=valor, referencia=data["input_TransactionReference"], status="saldo insuficiente")
        db.add(transacao)
        db.commit()
        return {"msg": "Saldo insuficiente."}

    if response.status_code ==400:
        return {"msg": "ocorreu um erro"}
    

    # Verifique se o status da resposta é de sucesso
    if response.status_code == 200 or response.status_code == 201:
        # Buscar ou criar a wallet do usuário
        wallet = db.query(Wallet).filter(Wallet.usuario_id == usuario.id).first()
        
        # Se a wallet não existe, cria uma nova
        if not wallet:
            wallet = Wallet(usuario_id=usuario.id, saldo_principal=0)  # Inicializa com saldo 0
            db.add(wallet)
            db.commit()
            db.refresh(wallet)
 
        # Adicionar o valor ao saldo da wallet
        wallet.saldo_principal -= valor
        db.commit()
        db.refresh(wallet)

        # Registrar transação com sucesso
        transacao = Transacao(usuario_id=usuario.id, msisdn=msisdn, valor=valor, referencia=data["input_TransactionReference"], status="sucesso",tipo="saida")
        db.add(transacao)
        db.commit()
        
        return {f"msg": "confirmado retirou o valor {valor}", "saldo_atual": wallet.saldo_principal}
    else:
        # Exibir o conteúdo bruto da resposta para depuração
        print(f"Resposta da M-Pesa: {response.text}")
        raise HTTPException(status_code=400, detail=f"Erro ao processar a transação: {response.text}")
    

@router.get("/anuncios/listar", response_model=List[dict])
def listar_anuncios(db: Session = Depends(get_db)):
    anuncios = db.query(Anuncio).filter(Anuncio.aprovado == True, Anuncio.ativo == True).all()
    return [
        {
            "id": anuncio.id,
            "nome": anuncio.nome,
            "descricao": anuncio.descricao,
            "preco": anuncio.preco,
            "link": anuncio.link,
            "imagem": anuncio.imagem,
            "criado_em": anuncio.criado_em,
            "expira_em": anuncio.expira_em
        }
        for anuncio in anuncios
    ]

@router.put("/atualizar")
def atualizar_usuario(
    username: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    contacto: Optional[str] = Form(None),
    biografia: Optional[str] = Form(None),
    sexo: Optional[str] = Form(None),
    nome_pagina:Optional[str]=Form(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)  # 🔐 Obtém usuário autenticado
):
    usuario = db.query(Usuario).filter(Usuario.id == current_user.id).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Verifica se os novos valores já pertencem a outro usuário
    if username and db.query(Usuario).filter(Usuario.username == username, Usuario.id != current_user.id).first():
        raise HTTPException(status_code=400, detail="Username já está em uso")
    if email and db.query(Usuario).filter(Usuario.email == email, Usuario.id != current_user.id).first():
        raise HTTPException(status_code=400, detail="Email já está em uso")
    if contacto and db.query(Usuario).filter(Usuario.contacto == contacto, Usuario.id != current_user.id).first():
        raise HTTPException(status_code=400, detail="Contacto já está em uso")

    # Atualiza apenas os campos informados
    if username:
        usuario.username = username
    if email:
        usuario.email = email
    if contacto:
        usuario.contacto = contacto
    if biografia:
        usuario.biografia = biografia
    if sexo:
        usuario.sexo = sexo
    if nome_pagina:
        usuario.nome_pagina = nome_pagina
    db.commit()
    return {"message": "Usuário atualizado com sucesso"}

@router.get("/auth/callback")
async def google_auth_callback(
    code: str, 
    db: Session = Depends(get_db),
    error: Optional[str] = None
):
    """
    Processa o callback do Google OAuth2 e cria/atualiza usuário
    """
    if error:
        logger.error(f"Erro na autenticação Google: {error}")
        return _redirect_error(f"Erro na autenticação Google: {error}")

    try:
        # Obter token e informações do usuário Google
        google_user = await _get_google_user_info(code)
        
        # Processar usuário no banco de dados
        usuario = await _process_user(db, google_user)
        
        # Gerar token e preparar resposta
        return await _prepare_success_response(usuario)

    except HTTPException as he:
        logger.error(f"Erro HTTP: {he.detail}")
        return _redirect_error(he.detail)
    except Exception as e:
        logger.exception("Erro não esperado no callback do Google")
        return _redirect_error("Erro interno do servidor")

async def _get_google_user_info(code: str) -> dict:
    """Obtém informações do usuário do Google"""
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient() as client:
        # Obter token de acesso
        token_response = await client.post(
            GOOGLE_TOKEN_URI,
            data=data,
            headers={"Accept": "application/json"}
        )
        
        if token_response.status_code != 200:
            logger.error(f"Erro ao obter token Google: {token_response.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Falha ao obter token do Google"
            )

        google_token = token_response.json().get("access_token")
        if not google_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token não encontrado na resposta"
            )

        # Obter informações do usuário
        userinfo = await client.get(
            GOOGLE_USERINFO_URI,
            headers={"Authorization": f"Bearer {google_token}"}
        )
        
        if userinfo.status_code != 200:
            logger.error(f"Erro ao obter dados do usuário: {userinfo.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Falha ao obter dados do usuário"
            )

        return userinfo.json()

async def _process_user(db: Session, google_user: dict) -> Usuario:
    """Processa o usuário no banco de dados"""
    try:
        usuario = db.query(Usuario).filter(
            Usuario.email == google_user["email"]
        ).first()

        if not usuario:
            usuario = await _create_new_user(db, google_user)
            await _create_user_wallet(db, usuario)
            
        return usuario

    except Exception as e:
        logger.exception("Erro ao processar usuário")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao processar usuário"
        )

async def _create_new_user(db: Session, google_user: dict) -> Usuario:
    """Cria novo usuário"""
    identificador_unico = gerar_identificador_unico(db)
    
    usuario = Usuario(
        email=google_user["email"],
        nome=google_user["name"],
        username=google_user["email"].split("@")[0],
        google_id=google_user["sub"],
        foto_perfil=google_user.get("picture"),
        identificador_unico=identificador_unico,
        ativo=True,
        tipo="cliente",
        limite_diario_publicacoes=5,
        data_cadastro=datetime.utcnow(),
        revisao="nao"
    )
    
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    logger.info(f"Novo usuário criado: {usuario.id}")
    return usuario

async def _create_user_wallet(db: Session, usuario: Usuario):
    """Cria wallet para novo usuário"""
    wallet = Wallet(
        usuario_id=usuario.id,
        saldo_principal=0,
        saldo_bonus=0,
        saldo_congelado=0
    )
    db.add(wallet)
    db.commit()
    logger.info(f"Wallet criada para usuário: {usuario.id}")

async def _prepare_success_response(usuario: Usuario):
    """Prepara resposta de sucesso"""
    try:
        access_token = create_access_token(
            user_id=usuario.id,
            user_role=usuario.tipo
        )
        
        logger.info(f"Token gerado com sucesso para usuário: {usuario.id}")
        return RedirectResponse(
            url=f"{SUCCESS_URL}?token={access_token}&id={usuario.id}",
            status_code=status.HTTP_302_FOUND
        )
    except Exception as e:
        logger.error(f"Erro ao preparar resposta de sucesso: {str(e)}")
        return _redirect_error("Erro ao gerar token de acesso")

def _redirect_error(message: str):
    """Helper para redirecionamento de erro"""
    return RedirectResponse(
        url=f"{ERROR_URL}?error={urlencode({'message': message})}",
        status_code=status.HTTP_302_FOUND
    )

@router.get("/perfil")
def read_perfil(db: Session = Depends(get_db),current_user: Usuario = Depends(get_current_user)):
    print(current_user.id)
    perfil = get_perfil(db=db, usuario_id=current_user.id)
    if perfil is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return perfil

@router.get("/user")
def read_perfil(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Retorna informações detalhadas sobre o perfil do usuário atual.
    Inclui verificação se o usuário:
    - Postou status.
    - É PRO ou não.
    - Total de seguidores com usernames.
    """
    # Busca o perfil do usuário atual
    perfil = db.query(Usuario).filter_by(id=current_user.id).first()
    if perfil is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    # Verifica se o usuário postou status
    status_postado = db.query(Status).filter_by(usuario_id=perfil.id).first() is not None
    produtos_publicados = db.query(Produto).filter(Produto.CustomerID == perfil.id,Produto.ativo == True).all()
    total_produto=len(produtos_publicados)

    # Busca os seguidores
    total_seguidores = db.query(Seguidor).filter(Seguidor.usuario_id == perfil.id).count()
    seguidores_info = db.query(Usuario).join(Seguidor, Usuario.id == Seguidor.seguidor_id).filter(
    Seguidor.usuario_id == perfil.id).all()

    # Total de pessoas que ele está seguindo e informações
    total_seguindo = db.query(Seguidor).filter(Seguidor.seguidor_id == perfil.id).count()
    seguindo_info = db.query(Usuario).join(Seguidor, Usuario.id == Seguidor.usuario_id).filter(
        Seguidor.seguidor_id == perfil.id).all()
    referencias = db.query(Usuario).filter(Usuario.referenciador_id == current_user.id).all()
    
    # Adiciona informações dos seguidores (ID e username)

  
    # Monta a resposta com os dados do perfil
    return {
        "id": perfil.id,
        "username": perfil.username,
        "email": perfil.email,
        "name": perfil.nome,
        "nr": perfil.contacto,
        "bloqueado": perfil.bloqueado,
        "id_unico":perfil.identificador_unico,
        "conta_pro": perfil.conta_pro,  # Indica se a conta é PRO
        "tipo": perfil.tipo,
        "ref":perfil.referencias,
        "biografia":perfil.biografia,
        "sexo":perfil.sexo,
        "nome_pagina":perfil.nome_pagina,
        "ativo":perfil.ativo,
        "contacto":perfil.contacto,
        "perfil": perfil.foto_perfil,
        "revisado": perfil.revisao,
        # Se o visitante segue o dono do perfil
        "total_seguidores": total_seguidores,
        "seguidores": [{"id": seg.id, "nome": seg.nome, "username": seg.username, "perfil": seg.foto_perfil} for seg in seguidores_info],
        "total_seguindo": total_seguindo,
        "a_seguir": [{"id": seguindo.id, "nome": seguindo.nome, "username": seguindo.username, "perfil": seguindo.foto_perfil} for seguindo in seguindo_info],
     
        "status_postado": status_postado,
        "total_seguidores": total_seguidores,
        "total_produtos":total_produto,
        
        
    }

@router.put("/contacto")
def atualizar_contacto(
    contacto: str = Form(...),  # Agora usando Form para receber os dados
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)  # Usuário autenticado
):
    # Recarregar a instância do usuário para garantir que esteja na sessão atual
    user_in_db = db.query(Usuario).filter(Usuario.id == current_user.id).first()
    if not user_in_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )

    # Verificar se o novo contacto já está em uso por outro usuário
    existing_user = db.query(Usuario).filter(Usuario.contacto == contacto).first()
    if existing_user and existing_user.id != user_in_db.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O contacto informado já está em uso por outro usuário."
        )

    # Atualizar o contacto do usuário
    user_in_db.contacto = contacto
    db.commit()
    db.refresh(user_in_db)

    return {"message": "Contacto atualizado com sucesso", "contacto": user_in_db.contacto}



@router.put("/idioma")
def atualizar_contacto(
    idioma: str = Form(...),  # Agora usando Form para receber os dados
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)  # Usuário autenticado
):
    # Recarregar a instância do usuário para garantir que esteja na sessão atual
    user_in_db = db.query(Usuario).filter(Usuario.id == current_user.id).first()
    if not user_in_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )

    # Verificar se o novo contacto já está em uso por outro usuário
    existing_user = db.query(Usuario).filter(Usuario.idioma == idioma).first()
    if existing_user and existing_user.id != user_in_db.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O contacto informado já está em uso por outro usuário."
        )

    # Atualizar o contacto do usuário
    user_in_db.idioma = idioma
    db.commit()
    db.refresh(user_in_db)

    return {"message": "Contacto atualizado com sucesso", "contacto": user_in_db.idioma}


@router.get("/{username}/produtos")
def read_perfil_produtos(
    username: str,
    visitante_identificador: Optional[str] = Query(None),  # Identificador do visitante (opcional)
    db: Session = Depends(get_db)
):
    # Buscar o perfil do usuário pelo username
    perfil = db.query(Usuario).filter(Usuario.username == username).first()
    if not perfil:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Buscar visitante se for informado
    visitante = None
    if visitante_identificador:
        visitante = db.query(Usuario).filter(Usuario.identificador_unico == visitante_identificador).first()
    
    # Buscar os produtos publicados pelo usuário que estão ativos
    produtos_publicados = db.query(Produto).filter(
        Produto.CustomerID == perfil.id,
        Produto.ativo == True
    ).all()

    # Criar JSON dos produtos
    produtos_info = []
    for produto in produtos_publicados:
        # Verificar se o visitante deu like no produto
        liked = False
        if visitante:
            from models import produto_likes
            liked = visitante.id in produto.likes if isinstance(produto.likes, list) else False
        produtos_info.append({
            "id": produto.id,
            "title": produto.nome,
            "thumb": produto.capa,
            "images": produto.fotos,
            "price": float(produto.preco),
            "stock_quantity": produto.quantidade_estoque,
            "state": produto.estado,
            "province": produto.provincia,
            "district": produto.distrito,
            "location": produto.localizacao,
            "review": produto.revisao,
            "availability": produto.disponiblidade,
            "description": produto.descricao,
            "category": produto.categoria,
            "details": produto.detalhes,
            "type": produto.tipo,
            "negociavel": produto.negociavel,
            "views": formatar_contagem(produto.visualizacoes),
            "active": produto.ativo,
            "customer_id": produto.CustomerID,
            "likes": formatar_contagem(produto.likes),
            "slug": produto.slug,
            "time": calcular_tempo_publicacao(produto.data_publicacao),
            "liked": liked  # Se o visitante deu like no produto
        })

    return {
        "produtos": produtos_info
    }








@router.get("/perfil/{username}")
def read_perfil(
    username: str,
    visitante_identificador: Optional[str] = Query(None),  # Identificador do visitante (opcional)
    db: Session = Depends(get_db)
):
    # Buscar o perfil do usuário pelo username
    perfil = db.query(Usuario).filter(Usuario.username == username).first()
    if not perfil:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Buscar visitante se for informado
    visitante = None
    seguindo_o_dono = False
    if visitante_identificador:
        visitante = db.query(Usuario).filter(Usuario.identificador_unico == visitante_identificador).first()
        if visitante:
            seguindo_o_dono = db.query(Seguidor).filter(
                Seguidor.usuario_id == perfil.id,
                Seguidor.seguidor_id == visitante.id
            ).first() is not None

    mesmo_usuario = visitante.id == perfil.id if visitante else False

    # Total de seguidores e informações dos seguidores
    total_seguidores = db.query(Seguidor).filter(Seguidor.usuario_id == perfil.id).count()
    seguidores_info = db.query(Usuario).join(Seguidor, Usuario.id == Seguidor.seguidor_id).filter(
        Seguidor.usuario_id == perfil.id).all()

    # Total de pessoas que ele está seguindo e informações
    total_seguindo = db.query(Seguidor).filter(Seguidor.seguidor_id == perfil.id).count()
    seguindo_info = db.query(Usuario).join(Seguidor, Usuario.id == Seguidor.usuario_id).filter(
        Seguidor.seguidor_id == perfil.id).all()

    # Buscar os produtos publicados pelo usuário
    produtos_publicados = db.query(Produto).filter(Produto.CustomerID == perfil.id,Produto.ativo == True).all()
    total_produtos = len(produtos_publicados)

    # Criar JSON dos produtos
    produtos_info = []
    for produto in produtos_publicados:
        # Verificar se o visitante deu like no produto
        liked = visitante.id in produto.likes if isinstance(produto.likes, list) else False


        # Calcular total de estrelas (média das avaliações)
        #total_estrelas = db.query(func.avg(Avaliacao.estrelas)).filter(Avaliacao.produto_id == produto.id).scalar()
        # Calcular total de estrelas (média das avaliações do usuário)

        produtos_info.append({
            "id": produto.id,
            "nome": produto.nome,
            "preco": float(produto.preco),
            "capa": produto.capa,
            "slug": produto.slug,
            "publicado_em": produto.data_publicacao,
            "liked": liked,  # Se o visitante deu like no produto
              # Média de avaliações do produto
        })
    total_estrelas = db.query(func.avg(Avaliacao.estrelas)).filter(Avaliacao.avaliado_id == perfil.id).scalar()
    total_estrelas = round(total_estrelas, 1) if total_estrelas is not None else 0.0

    # Montar a resposta com os dados do perfil
    return {
        "id": perfil.id,
        "total_estrelas": total_estrelas,
        "identificador_unico": perfil.identificador_unico,
        "username": perfil.username,
        "name": perfil.nome,
        "nome_pagina":perfil.nome_pagina,
        "email": perfil.email,
        "contacto": perfil.contacto,
        "biografia": perfil.biografia,
        "sexo": perfil.sexo,
        "conta_pro": perfil.conta_pro,
        "tipo": perfil.tipo,
        "perfil": perfil.foto_perfil,
        "revisado": perfil.revisao,
        "seguindo": seguindo_o_dono,  # Se o visitante segue o dono do perfil
        "total_seguidores": total_seguidores,
        "seguidores": [{"id": seg.id, "nome": seg.nome, "username": seg.username, "perfil": seg.foto_perfil} for seg in seguidores_info],
        "total_seguindo": total_seguindo,
        "a_seguir": [{"id": seguindo.id, "nome": seguindo.nome, "username": seguindo.username, "perfil": seguindo.foto_perfil} for seguindo in seguindo_info],
        "total_produtos": total_produtos,
        "produtos": produtos_info,
        "mesmo_usuario": mesmo_usuario,  # True se o visitante for o mesmo que o dono do perfil
    }

# Rotas relacionadas a usuários
@router.put("/{usuario_id}/desativar_pro/")
def desativar_conta_pro(usuario_id: int, db: Session = Depends(get_db)):
    db_usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()

    if not db_usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if not db_usuario.conta_pro:
        raise HTTPException(status_code=400, detail="Conta PRO já está desativada para este usuário.")

    db_usuario.conta_pro = False
    db_usuario.limite_diario_publicacoes = 1
    db.commit()
    db.refresh(db_usuario)

    return {"message": "Conta PRO desativada com sucesso.", "usuario": db_usuario}


@router.get("/publicacoes/")
def listar_publicacoes(
    usuario_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 10,
    seed: Optional[int] = None,  # Seed para garantir ordem consistente
    db: Session = Depends(get_db)
):
    """
    Lista publicações aleatoriamente com paginação.
    Inclui informações:
    - Total de likes e comentários
    - Dados dos comentários (pessoa, foto, etc.)
    - Dados do publicador (nome, foto)
    - Se o usuário deu like (opcional)
    """
    # Buscar todas as publicações
    publicacoes_query = db.query(Publicacao).all()

    # Verificar se há publicações
    if not publicacoes_query:
        raise HTTPException(status_code=404, detail="Nenhuma publicação encontrada.")

    # Embaralhar a lista de publicações
    if seed is None:
        seed = random.randint(1, 1000000)  # Seed aleatória se não for fornecida
    random.seed(seed)
    random.shuffle(publicacoes_query)

    # Aplicar paginação manualmente
    total_publicacoes = len(publicacoes_query)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    publicacoes_paginadas = publicacoes_query[start_idx:end_idx]

    # Preparar o resultado com informações adicionais
    resultado = []
    for publicacao in publicacoes_paginadas:
        # Obter total de likes e comentários
        total_likes = db.query(LikePublicacao).filter(LikePublicacao.publicacao_id == publicacao.id).count()
        total_comentarios = db.query(ComentarioPublicacao).filter(ComentarioPublicacao.publicacao_id == publicacao.id).count()

        # Verificar se o usuário deu like
        deu_like = False
        if usuario_id:
            deu_like = db.query(LikePublicacao).filter(
                LikePublicacao.publicacao_id == publicacao.id,
                LikePublicacao.usuario_id == usuario_id
            ).first() is not None

        # Obter informações de quem comentou
        comentarios = db.query(ComentarioPublicacao).filter(ComentarioPublicacao.publicacao_id == publicacao.id).all()
        detalhes_comentarios = [
            {
                "id": comentario.id,
                "conteudo": comentario.conteudo,
                "data_criacao": comentario.data_criacao.isoformat(),
                "usuario": {
                    "id": comentario.usuario.id,
                    "nome": comentario.usuario.nome,
                    "foto_perfil": comentario.usuario.foto_perfil,
                }
            }
            for comentario in comentarios
        ]

        # Obter dados do publicador
        publicador = publicacao.usuario

        resultado.append({
            "id": publicacao.id,
            "conteudo": publicacao.conteudo,
            "publicador": {
                "id": publicador.id,
                "nome": publicador.nome,
                "foto_perfil": publicador.foto_perfil,
            },
            "total_likes": total_likes,
            "total_comentarios": total_comentarios,
            "comentarios": detalhes_comentarios,
            "deu_like": deu_like,
        })

    # Retornar resultado paginado
    return {
        "total": total_publicacoes,
        "page": page,
        "per_page": per_page,
        "seed": seed,  # Retornamos a seed para consistência
        "items": resultado
    }

@router.post("/{usuario_id}/seguir")
def seguir_usuario_route(
    usuario_id: int,
    db: Session = Depends(get_db),
    seguidor: Usuario = Depends(get_current_user)
):
    # Chama a função que implementa a lógica de seguir ou deixar de seguir
    resultado = seguir_usuario(db, usuario_id, seguidor.id)
    return resultado

@router.get("/usuarios/{usuario_id}/seguindo")
def get_usuario_seguindo(usuario_id: int, db: Session = Depends(get_db)):
    return get_seguidores(usuario_id, db)




def gerar_otp() -> str:
    """Gera um código OTP de 6 dígitos."""
    return str(random.randint(100000, 999999))


# 1️⃣ Enviar OTP
@router.post("/recuperar_senha/")
async def enviar_otp(email: str, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    otp_code = gerar_otp()
    expiration_time = datetime.utcnow() + timedelta(minutes=5)

    otp_entry = db.query(OTP).filter(OTP.email == email).first()
    if otp_entry:
        otp_entry.otp = otp_code
        otp_entry.expires_at = expiration_time
    else:
        otp_entry = OTP(email=email, otp=otp_code, expires_at=expiration_time)
        db.add(otp_entry)

    db.commit()
    subject = "Seu código OTP para redefinição de senha"
    body = f"""
     <html>
    <body>
        <p>Olá, {usuario.nome},</p>
        <p>Seu código OTP é:</p>
        <h3>{otp_code}</h3>
        <p>Este código é válido por 5 minutos.</p>
        <br>
        <p>Equipe SkyVenda.</p>
    </body>
    </html>
  """
    if not send_email(recipient=email, subject=subject, body=body,is_html=True):
        raise HTTPException(status_code=500, detail="Erro ao enviar e-mail. Tente novamente mais tarde.")

    return {"message": "Código OTP enviado para o e-mail."}


# 2️⃣ Verificar OTP e gerar token de redefinição
@router.post("/verificar_otp/")
async def verificar_otp(email: str, otp: str, db: Session = Depends(get_db)):
    otp_entry = db.query(OTP).filter(OTP.email == email, OTP.otp == otp).first()

    if not otp_entry:
        raise HTTPException(status_code=400, detail="Código OTP inválido.")
    
    if otp_entry.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Código OTP expirado.")

    # Gera token temporário para resetar senha
    reset_token = jwt.encode(
        {"email": email, "exp": datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRATION)},
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return {"message": "Código OTP válido. Agora você pode redefinir sua senha.", "reset_token": reset_token}


# 3️⃣ Resetar senha usando o token gerado
@router.post("/resetar_senha/")
async def resetar_senha(reset_token: str, nova_senha: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(reset_token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("email")

        if not email:
            raise HTTPException(status_code=400, detail="Token inválido.")

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token expirado. Solicite um novo código OTP.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Token inválido.")

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    # Atualiza a senha do usuário
    usuario.senha = pwd_context.hash(nova_senha)
    db.commit()

    # Remove o OTP após o uso
    db.query(OTP).filter(OTP.email == email).delete()
    db.commit()

    return {"message": "Senha redefinida com sucesso."}


# Função para adicionar saldo usando M-Pesa (sem autenticação)
@router.post("/{user_id}/adicionar_saldo/")
def adicionar_saldo_via_mpesa(msisdn: str, valor: int, db: Session = Depends(get_db),current_user: Usuario = Depends(get_current_user)):
    # Buscar o usuário no banco de dados
    usuario = db.query(Usuario).filter(Usuario.id == current_user.id).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    # Verifica se o usuário passou pela revisão
    info_usuario = db.query(InfoUsuario).filter(InfoUsuario.usuario_id == usuario.id).first()
    if not info_usuario or info_usuario.revisao != "sim":
        raise HTTPException(status_code=403, detail="Usuário não passou pela revisão e não pode adicionar saldo.")

    # Cabeçalhos e payload para a requisição M-Pesa
    # Cabeçalhos da solicitação
    token="XfsLebYAsnNPRsMu6JKfRPH9W5fhzSb+W3cdizVQ/Bm5ho2Xi/tn/Oo4bwHmFLqYlHQVnrog3MziMmxZLN5NnPEqCu5F9tLeYwmIo4mqNp544Ai5B8s+IAbxr//WLIS+pk992fp6uZl8IgFkQreqsN+leWSgQdeW7oiGl7Z5k6e10uc4xuD3KOEldtye0Pzjj0DmHNdhDh8SzpdgkjyEmWPhvyMwCVxn80pqaKAH5UUDGxv+dbY4HgsoAprMC+hclhHkVfk5VfqNlOToxpn6LmfeoZZ5BJJysEA/Y/T3zlK9JYq+dWahlWyMv+UoMEh7VG1lw3k/Hb7dqKkSRmrhStsuRrHjAITKRSoWv98ZWntQQua+Fz/BGV7v6f6qsytTBHCWVJD3qWl3phKztYWpr0CeJ3aGYns+gtKP04V2WdPrqVylYJFEQILGCfKmtFqYZ3rhdKhgs4UDAOQMCkED4uS+op0p+I6kW6ftAyw6WDu5dqQ5OFKV3++f/015kptDzRpoieB1EfUltgabnfWCNzivi7ZJY6S+5+ZJPDI9ORjYq+QlF+Qi/RQmJiGWDh+S/UY2sA2d9692lfmWKk3+10YAUoZlQTlq9qCvqVXYVwquiLkUpHhnpNMbidVBwuBM03IxA0SrmervTM7RY2mS1BXTwO2IQekX+9bnJ6+Tpkk="
    headers = {
           "Content-Type": "application/json",
           "Authorization": f"Bearer {token}",
           "Origin": "developer.mpesa.vm.co.mz"
    }

    # Dados da requisição
    data = {
        "input_TransactionReference": "T12344C",  # Gere uma referência única para cada transação
        "input_CustomerMSISDN": msisdn,           # Número de telefone do cliente
        "input_Amount": str(valor),               # Valor a ser carregado
        "input_ThirdPartyReference": "11115",     # Referência única de terceiros
        "input_ServiceProviderCode": "171717"     # Código do provedor de serviço
    }
 
# Enviar a requisição para a API da M-Pesa
    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code ==422:
        transacao = Transacao(usuario_id=usuario.id, msisdn=msisdn,tipo="entrada", valor=valor, referencia=data["input_TransactionReference"], status="saldo insuficiente")
        db.add(transacao)
        db.commit()
        return {"msg": "Saldo insuficiente."}

    if response.status_code ==400: 
        return {"msg": "ocorreu um erro"}
    
    # Verifique se o status da resposta é de sucesso
    if response.status_code == 200 or response.status_code == 201:
        # Buscar ou criar a wallet do usuário
        wallet = db.query(Wallet).filter(Wallet.usuario_id == usuario.id).first()
        
        # Se a wallet não existe, cria uma nova
        if not wallet:
            wallet = Wallet(usuario_id=usuario.id, saldo_principal=0)  # Inicializa com saldo 0
            db.add(wallet)
            db.commit()
            db.refresh(wallet)
            
        # Adicionar o valor ao saldo da wallet
        wallet.saldo_principal += valor
        db.commit()
        db.refresh(wallet)

        # Registrar transação com sucesso
        transacao = Transacao(usuario_id=usuario.id, msisdn=msisdn, valor=valor, referencia=data["input_TransactionReference"], status="sucesso",tipo="entrada")
        db.add(transacao)
        db.commit()
        
        return {"msg": "Saldo adicionado com sucesso!", "saldo_atual": wallet.saldo_principal}
    else:
        # Exibir o conteúdo bruto da resposta para depuração
        print(f"Resposta da M-Pesa: {response.text}")
        raise HTTPException(status_code=400, detail=f"Erro ao processar a transação: {response.text}")




@router.get("/{user_id}/saldo/")
def obter_saldo(db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    # Buscar o usuário no banco de dados
    usuario = db.query(Usuario).filter(Usuario.id == current_user.id).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    # Buscar a wallet do usuário
    wallet = db.query(Wallet).filter(Wallet.usuario_id == usuario.id).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet não encontrada para o usuário.")

    # Pegando o saldo principal da wallet
    saldo_principal = wallet.saldo_principal

    # Pegando o saldo de bônus (por exemplo, se houver uma tabela de Bônus relacionada ao usuário)
    bonus = wallet.bonus if hasattr(wallet, 'bonus') else 0.0  # Atribuindo 0 se não houver bônus

    # Pegando o saldo congelado (por exemplo, relacionado a transações pendentes)
    saldo_congelado = wallet.saldo_congelado if hasattr(wallet, 'saldo_congelado') else 0.0  # Atribuindo 0 se não houver saldo congelado

    return {
        "saldo_principal": saldo_principal,
        "saldo_bonus": bonus,
        "saldo_congelado": saldo_congelado
    }
@router.put("/{usuario_id}/ativar_pro/")
def ativar_conta_pro(
    usuario_id: int, 
    db: Session = Depends(get_db)
):
    """
    Ativa a conta PRO de um usuário.
    - Custa 1500MT, descontados do saldo principal do usuário.
    - Registra a transação correspondente.
    - Verifica se o usuário foi revisado antes de ativar.
    """
    # Busca o usuário no banco de dados
    db_usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()

    if not db_usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    # Verifica se o usuário foi revisado
    if not db_usuario.revisao:
        raise HTTPException(
            status_code=403, 
            detail="A ativação da conta PRO está disponível apenas para usuários revisados."
        )

    # Verifica se o usuário já possui uma conta PRO ativa
    if db_usuario.conta_pro:
        raise HTTPException(status_code=400, detail="Usuário já possui uma conta PRO ativa.")
    
    # Verifica se o usuário tem saldo suficiente
    custo_pro = Decimal("1500.0")
    if db_usuario.wallet is None:
        raise HTTPException(status_code=400, detail="Usuário não possui uma carteira associada.")
    if db_usuario.wallet.saldo_principal < custo_pro:
        raise HTTPException(status_code=400, detail="Saldo insuficiente para ativar a conta PRO.")

    # Atualiza a conta do usuário para PRO e desconta o valor
    db_usuario.conta_pro = True
    db_usuario.data_ativacao_pro = datetime.utcnow()
    db_usuario.wallet.saldo_principal -= custo_pro

    # Gerar dados para a transação
    msisdn = db_usuario.username  # Substitua por `db_usuario.msisdn` se você tiver esse campo no modelo
    referencia = f"PRO-{usuario_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"  # Referência única
    status = "sucesso"  # Status da transação

    # Cria e registra a transação no banco de dados
    transacao = Transacao(
        usuario_id=db_usuario.id,
        msisdn=msisdn,
        valor=custo_pro,
        referencia=referencia,
        status=status,
        tipo="debito",  # Tipo de transação: débito
        data_hora=datetime.utcnow()
    )
    db.add(transacao)

    # Salva as alterações no banco de dados
    db.commit()
    db.refresh(db_usuario)

    return {
        "message": "Conta PRO ativada com sucesso.",
        "usuario": {
            "id": db_usuario.id,
            "nome": db_usuario.nome,
            "email": db_usuario.email,
            "conta_pro": db_usuario.conta_pro,
            "data_ativacao_pro": db_usuario.data_ativacao_pro,
            "saldo_restante": float(db_usuario.wallet.saldo_principal),
        },
        "transacao": {
            "id": transacao.id,
            "usuario_id": transacao.usuario_id,
            "msisdn": transacao.msisdn,
            "valor": float(transacao.valor),
            "referencia": transacao.referencia,
            "status": transacao.status,
            "tipo": transacao.tipo,
            "data_hora": transacao.data_hora,
        },
    }

    

# Rota para o login (gera o token com ID e tipo de usuário)
@router.post("/token")
def login_user(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    # Autenticação do usuário usando username, email ou contacto
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Gera o token de acesso com ID e tipo de usuário
    access_token = create_access_token(user_id=user.id, user_role=user.tipo)  # Inclui ID e tipo no token
    return {"access_token": access_token, "token_type": "bearer", "id": user.id}



@router.get("/usuarios/{usuario_id}/avaliacoes/")
def consultar_avaliacoes(
    usuario_id: int,
    db: Session = Depends(get_db),
):
    """
    Consultar a média de estrelas e número de avaliações de um usuário.
    """
    usuario_avaliado = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario_avaliado:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    # Calcular a média de estrelas
    avaliacoes = db.query(Avaliacao).filter(Avaliacao.avaliado_id == usuario_id).all()
    if not avaliacoes:
        return {"usuario_id": usuario_id, "media_estrelas": None, "total_avaliacoes": 0}

    total_avaliacoes = len(avaliacoes)
    media_estrelas = sum([avaliacao.estrelas for avaliacao in avaliacoes]) / total_avaliacoes

    return {
        "usuario_id": usuario_id,
        "media_estrelas": round(media_estrelas, 2),
        "total_avaliacoes": total_avaliacoes,
    }




@router.post("/usuarios/{avaliado_id}/avaliar/")
def avaliar_usuario(
    avaliado_id: int,
    avaliacao: AvaliacaoSchema = Body(..., description="Dados da avaliação"),  # O valor virá no corpo da requisição
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Avaliar um usuário com uma nota de 1 a 5 estrelas.
    """
    # Verificar se o usuário avaliado existe
    usuario_avaliado = db.query(Usuario).filter(Usuario.id == avaliado_id).first()
    if not usuario_avaliado:
        raise HTTPException(status_code=404, detail="Usuário avaliado não encontrado.")

    # Verificar se o usuário autenticado está avaliando a si mesmo
    if current_user.id == avaliado_id:
        raise HTTPException(status_code=400, detail="Você não pode se autoavaliar.")

    # Criar ou atualizar a avaliação
    avaliacao_existente = db.query(Avaliacao).filter(
        Avaliacao.avaliador_id == current_user.id,
        Avaliacao.avaliado_id == avaliado_id,
    ).first()

    if avaliacao_existente:
        # Atualizar a avaliação existente
        avaliacao_existente.estrelas = avaliacao.estrelas
        avaliacao_existente.data_criacao  = datetime.utcnow()
    else:
        # Criar nova avaliação
        nova_avaliacao = Avaliacao(
            avaliador_id=current_user.id,
            avaliado_id=avaliado_id,
            estrelas=avaliacao.estrelas,
            data_criacao=datetime.utcnow(),
        )
        db.add(nova_avaliacao)

    db.commit()

    return {"message": "Avaliação registrada com sucesso.", "estrelas": avaliacao.estrelas}




@router.post("/{user_id}/publicar/")
def publicar_texto(user_id: int, publicacao: PublicacaoCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Usuário não autorizado a publicar para este ID.")

    nova_publicacao = Publicacao(usuario_id=current_user.id, conteudo=publicacao.conteudo)
    
    db.add(nova_publicacao)
    db.commit()
    db.refresh(nova_publicacao)

    return {"msg": "Publicação criada com sucesso!", "publicacao": nova_publicacao}

@router.post("/cadastro")
def create_usuario_endpoint(
    nome: str = Form(...),
    username: str = Form(...),
    email: EmailStr = Form(...),
    senha: Optional[str] = Form(None),
    tipo: Optional[str] = Form(None),
    referencia: Optional[str] = Query(None),  # Recebe o identificador do referenciador
    db: Session = Depends(get_db)
):
    """
    Rota para cadastrar um novo usuário. Se um link de referência for usado,
    vincula o novo usuário ao referenciador.
    """
    # Verifica se já existe um usuário com o mesmo email ou username
    existing_user = db.query(Usuario).filter(
        (Usuario.email == email) | (Usuario.username == username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário com este email ou username já existe."
        )

    # Gera o identificador único
    identificador_unico = gerar_identificador_unico(db)

    # Verifica se o identificador de referência é válido
    referenciador = None
    if referencia:
        referenciador = db.query(Usuario).filter(Usuario.identificador_unico == referencia).first()
        if not referenciador:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Link de referência inválido."
            )

    # Cria o novo usuário
    novo_usuario = register_user(
        db,
        nome=nome,
        username=username,
        email=email,
        senha=senha,
        tipo=tipo or "cliente",
        identificador_unico=identificador_unico,
        referencia=referenciador
    )

    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    # Gerar o link de referência do novo usuário
    link_referencia = f"https://skyvenda-mz.vercel.app/ref/{novo_usuario.identificador_unico}"

    return {
        "id": novo_usuario.id,
        "identificador_unico": novo_usuario.identificador_unico,
        "link_referencia": link_referencia,
       # Quantas referências ele tem
        "mensagem": "Usuário cadastrado com sucesso!"
    }





@router.get("/referencias", response_model=dict)
def listar_referencias(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista todos os usuários que se cadastraram usando o link de referência do usuário atual.
    Também retorna o total de referências.
    """

    # Verifica se o usuário possui referências
    referencias = db.query(Usuario).filter(Usuario.referenciador_id == current_user.id).all()

    # Formata os dados de resposta
    usuarios_referenciados = [
        {
            "id": usuario.id,
            "nome": usuario.nome,
            "username": usuario.username,
            "email": usuario.email,
            "data_cadastro": usuario.data_cadastro.isoformat()
        }
        for usuario in referencias
    ]

    return {
        "total_referencias": len(usuarios_referenciados),
        "usuarios": usuarios_referenciados
    }



@router.get("/pro/")
def listar_usuarios_pro(db: Session = Depends(get_db)):
    usuarios_pro = db.query(Usuario).filter(Usuario.conta_pro == True).all()

    if not usuarios_pro:
        raise HTTPException(status_code=404, detail="Nenhum usuário com conta PRO encontrado.")

    return {"usuarios_pro": usuarios_pro}


@router.get("/{usuario_id}/notificacoes/")
def listar_notificacoes(usuario_id: int, db: Session = Depends(get_db)):
    notificacoes = db.query(Notificacao).filter(Notificacao.usuario_id == usuario_id).all()
    return notificacoes


# Função auxiliar para calcular a média de estrelas
def calcular_media_estrelas(usuario_id: int, db: Session):
    # Calcula a média das estrelas para o usuário
    media_estrelas = db.query(func.avg(Avaliacao.estrelas)).filter(Avaliacao.avaliado_id == usuario_id).scalar()
    return media_estrelas if media_estrelas else 0



# Função para calcular a média de estrelas
def calcular_media_estrelas2(db: Session, usuario_id: int) -> Optional[float]:
    avaliacoes = db.query(Avaliacao).filter(Avaliacao.avaliado_id == usuario_id).all()
    if not avaliacoes:
        return None  # Caso o usuário não tenha avaliações
    soma_estrelas = sum(avaliacao.estrelas for avaliacao in avaliacoes)
    return round(soma_estrelas / len(avaliacoes), 2)

@router.get("/pesquisar_usuarios")
def pesquisar_usuarios(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, alias="q"),  # Pesquisa pelo nome ou username
    page: int = Query(1, ge=1),  # Página (1 por padrão)
    page_size: int = Query(10, le=100),  # Tamanho da página (máximo de 100)
    identificador_unico: Optional[str] = None  # Identificador único do usuário logado (opcional)
):
    # Filtrando apenas usuários ativos
    query = db.query(Usuario).filter(Usuario.ativo == True)

    # Se houver uma pesquisa por nome ou username
    if search:
        query = query.filter(
            or_(
                Usuario.nome.ilike(f"%{search}%"),
                Usuario.username.ilike(f"%{search}%")
            )
        )

    # Ordenando os usuários: PRO primeiro, depois os simples (ativos e não PRO)
    query = query.order_by(
        Usuario.conta_pro.desc(),  # Usuários PRO primeiro
        Usuario.nome.asc()  # Ordenando pelo nome para os usuários simples
    )

    # Paginação
    usuarios = query.offset((page - 1) * page_size).limit(page_size).all()

    # Buscar o usuário logado pelo identificador_unico (se fornecido)
    usuario_logado = None
    if identificador_unico:
        usuario_logado = db.query(Usuario).filter(Usuario.identificador_unico == identificador_unico).first()

    usuarios_resposta = []
    for usuario in usuarios:
        # Buscando a quantidade de seguidores
        total_seguidores = db.query(Seguidor).filter(Seguidor.usuario_id == usuario.id).count()
        
        # Calculando a média de estrelas
        media_estrelas = calcular_media_estrelas2(db, usuario.id)

        # Calculando o número de produtos do usuário
        total_produtos = db.query(Produto).filter(Produto.CustomerID == usuario.id).count()

        # Calculando o número de publicações (por exemplo, status ou posts)
        total_publicacoes = db.query(Publicacao).filter(Publicacao.usuario_id == usuario.id).count()

        # Verificar se o identificador_unico foi fornecido e se o usuário está seguindo o outro
        if usuario_logado:
            segue_usuario = (
                db.query(Seguidor)
                .filter(Seguidor.usuario_id == usuario.id, Seguidor.seguidor_id == usuario_logado.id)
                .count() > 0
            )
        else:
            segue_usuario = False  # Não forneceu identificador_unico

        usuarios_resposta.append({
            "id":usuario.id,
            "username": usuario.username,
            "identificador_unico": usuario.identificador_unico,
            "name": usuario.nome,
            "email": usuario.email,
            "foto_perfil": usuario.foto_perfil,
            "total_seguidores": total_seguidores,
            "media_estrelas": media_estrelas,
            "conta_pro": usuario.conta_pro,
            "total_produtos": total_produtos,
            "total_publicacoes": total_publicacoes,
            "segue_usuario": segue_usuario
        })

    return usuarios_resposta

@router.get("/usuarios/lojas")
async def listar_usuarios(
    skip: int = 0, 
    limit: int = 10, 
    identificador_unico: Optional[str] = None,  # Identificador único do usuário logado
    db: Session = Depends(get_db)
):
    # Listar usuários com paginação
    usuarios = db.query(Usuario).offset(skip).limit(limit).all()

    usuarios_response = []
    
    # Se o identificador_unico for fornecido, busca o usuário logado
    usuario_logado = None
    if identificador_unico:
        usuario_logado = db.query(Usuario).filter(Usuario.identificador_unico == identificador_unico).first()

    for usuario in usuarios:
        # Calculando a média de estrelas para o usuário
        media_estrelas = calcular_media_estrelas(usuario.id, db)

        # Contar total de seguidores
        total_seguidores = db.query(Seguidor).filter(Seguidor.usuario_id == usuario.id).count()
        
        # Contar total de produtos publicados
        total_produtos = db.query(Produto).filter(Produto.CustomerID == usuario.id).count()
        
        # Contar o total de publicações
        total_publicacoes = len(usuario.publicacoes)

        # Verificar se o usuário logado segue esse usuário
        if usuario_logado:
            segue_usuario = (
                db.query(Seguidor)
                .filter(Seguidor.usuario_id == usuario.id, Seguidor.seguidor_id == usuario_logado.id)
                .count() > 0
            )
        else:
            segue_usuario = False  # Se não foi passado o identificador_unico, assume que não segue

        usuarios_response.append({
            "id":usuario.id,
            "username": usuario.username,
            "identificador_unico": usuario.identificador_unico,
            "name": usuario.nome,
            "email": usuario.email,
            "foto_perfil": usuario.foto_perfil,
            "total_seguidores": total_seguidores,
            "media_estrelas": media_estrelas,
            "conta_pro": usuario.conta_pro,
            "total_produtos": total_produtos,
            "total_publicacoes": total_publicacoes,
            "segue_usuario": segue_usuario  # Verificação de quem segue o usuário
        })
    
    return {"usuarios": usuarios_response}


@router.put("/{usuario_id}")
def update_usuario_endpoint(usuario_id: int, usuario: UsuarioUpdate, db: Session = Depends(get_db)):
    db_usuario = update_usuario_db(db=db, usuario_id=usuario_id, usuario=usuario)
    if db_usuario is None:
        raise HTTPException(status_code=404, detail="Usuario not found")
    return db_usuario

@router.put("/{user_id}/atualizar_senha/")
def atualizar_senha(user_id: int, senha_atual: str, nova_senha: str, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if not usuario.senha or usuario.senha == "":
        raise HTTPException(status_code=400, detail="Usuários cadastrados via Google não podem alterar a senha.")
    if not verify_password(senha_atual, usuario.senha):
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")

    hashed_nova_senha = hash_password(nova_senha)
    usuario.senha = hashed_nova_senha
    db.commit()

    return {"msg": "Senha atualizada com sucesso."}


@router.get("/saldo")
def get_saldo(db: Session = Depends(get_db), 
              current_user: Usuario = Depends(get_current_user)):  # Usuário autenticado é extraído automaticamente
    
    # Verifica se o usuário existe no banco de dados
    usuario = db.query(Usuario).filter(Usuario.id == current_user.id).first()
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    # Retorna o saldo do usuário autenticado
    return {"saldo": usuario.saldo}




# Rota para obter todas as transações de um usuário específico
@router.get("/{user_id}/transacoes/")
def listar_transacoes(db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    # Verificar se o usuário existe
    usuario = db.query(Usuario).filter(Usuario.id ==  current_user.id).first()
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    # Buscar todas as transações do usuário
    transacoes = db.query(Transacao).filter(Transacao.usuario_id == current_user.id).all()

    # Verificar se existem transações
    if not transacoes:
        raise HTTPException(status_code=404, detail="Nenhuma transação encontrada.")
    
    return transacoes

@router.get("/transacoes/")
def listar_todas_transacoes(db: Session = Depends(get_db)):
    # Buscar todas as transações do sistema
    transacoes = db.query(Transacao).all()

    # Verificar se existem transações
    if not transacoes:
        raise HTTPException(status_code=404, detail="Nenhuma transação encontrada.")
    
    return transacoes

# Rota para obter todas as transações de um usuário específico
@router.get("/{user_id}/transacoes/")
def listar_transacoes(db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    # Verificar se o usuário existe
    usuario = db.query(Usuario).filter(Usuario.id ==  current_user.id).first()
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    # Buscar todas as transações do usuário
    transacoes = db.query(Transacao).filter(Transacao.usuario_id == current_user.id).all()

    # Verificar se existem transações
    if not transacoes:
        raise HTTPException(status_code=404, detail="Nenhuma transação encontrada.")
    
    return transacoes    


@router.get("/categorias/{usuario_id}", summary="Categorias preferidas de um usuário")
def obter_categorias_preferidas(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """
    Retorna as categorias mais interagidas por um usuário.
    """
    categorias = categorias_preferidas_por_usuario(db, usuario_id)
    if not categorias:
        raise HTTPException(status_code=404, detail="Nenhuma interação encontrada para o usuário.")
    return categorias
