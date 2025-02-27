from controlers.admin import *
from controlers.usuario import listar_usuarios_nao_verificados
from schemas import *
from controlers.info_usuario import *
from models import InfoUsuario,Produto,Transacao,Wallet, Pedido, Usuario, AnuncioUsuario
from auth import *
from controlers.denuncia_produto import *
from sqlalchemy import func
from controlers.usuario import ativar_usuario,delete_usuario_db,desativar_usuario
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import APIRouter,Query
from fastapi import APIRouter, Depends, HTTPException, status,Form,Body,Query
from controlers.produto import calcular_tempo_publicacao
from sqlalchemy.orm import joinedload
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from pathlib import Path

router=APIRouter(prefix="/admin", tags=["rotas de admin"] )


@router.post("/token")
def login_admin(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Rota para autenticação do administrador.

    Args:
    - db: Conexão com o banco de dados.
    - form_data: Dados do formulário de login.

    Returns:
    - dict: Token de acesso e tipo do token.
    """
    admin = authenticate_admin(db, form_data.username, form_data.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Criação do token de acesso
    access_token = create_access_token_admin(
        subject={"sub": str(admin.id), "role": "admin"}  # Inclui os dados no token
    )
    return {"access_token": access_token, "token_type": "bearer"}



@router.put("/usuario/{usuario_id}/revisao")
def revisar_usuario(usuario_id: int, nova_revisao: str, motivo: str = None, db: Session = Depends(get_db),current_admin: Admin = Depends(get_current_admin)):
    # Recupera o InfoUsuario baseado no ID do usuário
    db_info_usuario = db.query(InfoUsuario).filter(InfoUsuario.usuario_id == usuario_id).first()
    if not db_info_usuario:
        raise HTTPException(status_code=404, detail="InfoUsuario não encontrado.")

    # Chama a função para atualizar a revisão e enviar a notificação
    return update_revisao_info_usuario(db_info_usuario, nova_revisao, db, motivo)


@router.post("/registro")
def create_admin(
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Rota para criar um administrador usando dados enviados via formulário.

    Args:
    - `nome` (str): Nome do administrador.
    - `email` (str): E-mail do administrador.
    - `senha` (str): Senha do administrador.

    Returns:
    - Dados do administrador registrado.
    """
    # Cria um objeto AdminCreate com os dados do formulário
    admin_data = AdminCreate(nome=nome, email=email, senha=senha)
    return register_admin(db=db, admin=admin_data)




ANUNCIO_UPLOAD_DIR = Path("uploads/anuncios")

# Criar o diretório se não existir
ANUNCIO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.put("/anuncios/revisar/{anuncio_id}")
async def revisar_anuncio(
    anuncio_id: int,
    status: str = Form(...),
    dias_para_expirar: int = Form(...),
    nome: str = Form(...),
    descricao: str = Form(...),
    preco: float = Form(...),
    link: str = Form(None),
    foto: UploadFile = File(...),  # Arquivo da foto
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    anuncio = db.query(AnuncioUsuario).filter(AnuncioUsuario.id == anuncio_id).first()

    if not anuncio:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado")

    if anuncio.expira_em and anuncio.expira_em < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Anúncio expirado, não pode ser atualizado")

    if status not in ["aprovado", "rejeitado"]:
        raise HTTPException(status_code=400, detail="Status inválido")

    # **Criar diretório se não existir**
    if not ANUNCIO_UPLOAD_DIR.exists():
        ANUNCIO_UPLOAD_DIR.mkdir(parents=True)

    # Remover a foto antiga, se existir
    if anuncio.foto:
        foto_antiga_path = ANUNCIO_UPLOAD_DIR / anuncio.foto
        if foto_antiga_path.exists():
            os.remove(foto_antiga_path)

    # Salvar a nova foto
    nova_foto_nome = f"{anuncio_id}_{datetime.utcnow().timestamp()}_{foto.filename}"
    nova_foto_path = ANUNCIO_UPLOAD_DIR / nova_foto_nome

    # **Garantir que a foto seja salva corretamente**
    try:
        with nova_foto_path.open("wb") as buffer:
            buffer.write(await foto.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar a foto: {str(e)}")

    # Atualizar os dados do anúncio
    anuncio.nome = nome
    anuncio.descricao = descricao
    anuncio.preco = preco
    anuncio.link = link
    anuncio.status = status
    anuncio.foto = nova_foto_nome  # Salva o nome do arquivo no banco
    anuncio.expira_em = datetime.utcnow() + timedelta(days=dias_para_expirar)

    db.commit()
    db.refresh(anuncio)

    return {
        "message": f"Anúncio {status} com sucesso!",
        "anuncio": {
            "id": anuncio.id,
            "nome": anuncio.nome,
            "descricao": anuncio.descricao,
            "foto": anuncio.foto,
            "preco": anuncio.preco,
            "link": anuncio.link,
            "status": anuncio.status,
            "criado_em": anuncio.criado_em.isoformat(),
            "expira_em": anuncio.expira_em.isoformat()
        }
    }


@router.put("/atualizar_role/")
async def atualizar_role(
    id: int = Form(...),
    role: bool = Form(...),
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Busca o usuário pelo e-mail
    usuario = db.query(Usuario).filter(Usuario.id == id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    # Atualiza o campo role
    usuario.role = role
    db.commit()
    db.refresh(usuario)

    return {"message": "Role atualizado com sucesso.", "id": usuario.id, "role": usuario.role}




@router.get("/anuncios/", response_model=List[dict])
def listar_anuncios(db: Session = Depends(get_db)):
    anuncios = db.query(AnuncioUsuario).filter(AnuncioUsuario.status == "aprovado", AnuncioUsuario.activo == True).all()
    return [
        {
            "id": anuncio.id,
            "nome": anuncio.nome,
            "descricao": anuncio.descricao,
            "preco": anuncio.preco,
            "link": anuncio.link,
            "imagem": anuncio.foto,
            "criado_em": anuncio.criado_em,
            "expira_em": anuncio.expira_em
        }
        for anuncio in anuncios
    ]

@router.get("/anuncios/listar", response_model=List[dict])
def listar_anuncios(db: Session = Depends(get_db),current_admin: Admin = Depends(get_current_admin)):
    anuncios = db.query(AnuncioUsuario).filter(AnuncioUsuario.status == "pendente", AnuncioUsuario.activo == True).all()
    return [
        {
            "id": anuncio.id,
            "nome": anuncio.nome,
            "descricao": anuncio.descricao,
            "preco": anuncio.preco,
            "link": anuncio.link,
            "imagem": anuncio.foto,
            "cliques": anuncio.cliques,
            "criado_em": anuncio.criado_em,
            "expira_em": anuncio.expira_em
        }
        for anuncio in anuncios
    ]

@router.get("/info/{admin_id}")
def read_admins(admin_id: int, db: Session = Depends(get_db),current_admin: Admin = Depends(get_current_admin)):
    db_admin = get_admin(db=db, admin_id=admin_id)
    if db_admin is None:
        raise HTTPException(status_code=404, detail="Admin not found")
    return db_admin


@router.delete("/delete/user/{usuario_id}")
def delete_usuario(usuario_id: int, db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)):
    db_usuario = delete_usuario_db(db=db, usuario_id=usuario_id)
    if db_usuario is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return {"msg": "Usuário excluído com sucesso"}


@router.delete("/delete/{admin_id}")
def delete_admins(admin_id: int, db: Session = Depends(get_db),current_admin: Admin = Depends(get_current_admin)):
    db_admin = delete_admin(db=db, admin_id=admin_id)
    if db_admin is None:
        raise HTTPException(status_code=404, detail="Admin not found")
    return db_admin


def listar_usuarios_verificado(db: Session):
    """
    Retorna todos os usuários não verificados, incluindo os dados completos da tabela InfoUsuario.
    """
    usuarios = (
        db.query(Usuario)
        .filter(Usuario.revisao == "sim")  # Filtra os usuários não verificados
        .options(joinedload(Usuario.info_usuario))  # Carrega os dados relacionados da tabela InfoUsuario
        .all()
    )
    return usuarios




def listar_os_pendentes(db: Session):
    """
    Retorna todos os usuários não verificados, incluindo os dados completos da tabela InfoUsuario.
    """
    usuarios = (
        db.query(Usuario)
        .filter(Usuario.revisao == "pendente")  # Filtra os usuários não verificados
        .options(joinedload(Usuario.info_usuario))  # Carrega os dados relacionados da tabela InfoUsuario
        .all()
    )
    return usuarios


@router.get("/usuarios/verificados/", response_model=List[dict])
def obter_usuarios_verificados(db: Session = Depends(get_db),current_admin: Admin = Depends(get_current_admin)):
    """
    Rota para obter todos os usuários verificados.
    """
    usuarios_verificados = db.query(Usuario).filter(Usuario.revisao == "sim").all()

    return [
        {
            "id": usuario.id,
            "username": usuario.username,
            "nome": usuario.nome,
            "email": usuario.email,
            "contacto": usuario.contacto,
            "tipo": usuario.tipo,
            "foto_perfil": usuario.foto_perfil,
            "foto_capa": usuario.foto_capa,
            "ativo": usuario.ativo,
            "conta_pro": usuario.conta_pro,
            "data_cadastro":calcular_tempo_publicacao( usuario.data_cadastro),
            "revisao": usuario.revisao,
            "info_usuario": {
                "id": usuario.info_usuario.id if usuario.info_usuario else None,
                "foto_retrato": usuario.info_usuario.foto_retrato if usuario.info_usuario else None,
                "foto_bi_frente": usuario.info_usuario.foto_bi_frente if usuario.info_usuario else None,
                "foto_bi_verso": usuario.info_usuario.foto_bi_verso if usuario.info_usuario else None,
                "provincia": usuario.info_usuario.provincia if usuario.info_usuario else None,
                "distrito": usuario.info_usuario.distrito if usuario.info_usuario else None,
                "data_nascimento": usuario.info_usuario.data_nascimento if usuario.info_usuario else None,
                "localizacao": usuario.info_usuario.localizacao if usuario.info_usuario else None,
                "sexo": usuario.info_usuario.sexo if usuario.info_usuario else None,
                "nacionalidade": usuario.info_usuario.nacionalidade if usuario.info_usuario else None,
                "bairro": usuario.info_usuario.bairro if usuario.info_usuario else None,
                "revisao": usuario.info_usuario.revisao if usuario.info_usuario else None,
            } if usuario.info_usuario else None,
        }
        for usuario in usuarios_verificados
    ]



@router.put("/admins/{admin_id}")
def update_admins(admin_id: int, admin: AdminUpdate, db: Session = Depends(get_db),current_admin: Admin = Depends(get_current_admin)):
    db_admin = update_admin(db=db, admin_id=admin_id, admin=admin)
    if db_admin is None:
        raise HTTPException(status_code=404, detail="Admin not found")
    return db_admin

# Rota para desativar o usuário
@router.put("/usuario/{usuario_id}/desativar")
def desativar_usuario_route(usuario_id: int, db: Session = Depends(get_db),current_admin: Admin = Depends(get_current_admin)):
    return desativar_usuario(db, usuario_id)

# Rota para ativar o usuário
@router.put("/usuario/{usuario_id}/ativar")
def ativar_usuario_route(usuario_id: int, db: Session = Depends(get_db),current_admin: Admin = Depends(get_current_admin)):
    return ativar_usuario(db, usuario_id)


@router.delete("/categorias/{categoria_id}")
def delete_categoria(categoria_id: int, db: Session = Depends(get_db),current_admin: Admin = Depends(get_current_admin)):
    db_categoria =delete_categoria(db=db, categoria_id=categoria_id)
    if db_categoria is None:
        raise HTTPException(status_code=404, detail="Categoria not found")
    return db_categoria


@router.get("/usuarios/", response_model=dict)
def listar_usuarios(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Lista todos os usuários com paginação, incluindo o total de usuários e total de produtos postados por cada um.
    """
    total_usuarios = db.query(Usuario).count()
    usuarios = (
        db.query(Usuario)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    resultado = []
    for usuario in usuarios:
        total_produtos = db.query(Produto).filter(Produto.CustomerID == usuario.id).count()
        resultado.append({
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "total_produtos": total_produtos,
            "saldo": usuario.wallet.saldo_principal if usuario.wallet else 0.0,
        })

    return {
        "total_usuarios": total_usuarios,
        "usuarios": resultado,
        "page": page,
        "per_page": per_page,
    }


@router.get("/usuarios/pendetes/")
def obter_usuarios_pendentes(db: Session = Depends(get_db),current_admin: Admin = Depends(get_current_admin)):
    """
    Rota para obter todos os usuários pendentes.
    """
    usuarios_nao_verificados = listar_os_pendentes(db=db)

    return [
        {
            "id": usuario.id,
            "username": usuario.username,
            "nome": usuario.nome,
            "email": usuario.email,
            "contacto": usuario.contacto,
            "tipo": usuario.tipo,
            "foto_perfil": usuario.foto_perfil,
            "foto_capa": usuario.foto_capa,
            "ativo": usuario.ativo,
            "conta_pro": usuario.conta_pro,
            "data_cadastro": usuario.data_cadastro,
            "revisao": usuario.revisao,
            "info_usuario": {
                "id": usuario.info_usuario.id if usuario.info_usuario else None,
                "foto_retrato": usuario.info_usuario.foto_retrato if usuario.info_usuario else None,
                "foto_bi_frente": usuario.info_usuario.foto_bi_frente if usuario.info_usuario else None,
                "foto_bi_verso": usuario.info_usuario.foto_bi_verso if usuario.info_usuario else None,
                "provincia": usuario.info_usuario.provincia if usuario.info_usuario else None,
                "distrito": usuario.info_usuario.distrito if usuario.info_usuario else None,
                "data_nascimento": usuario.info_usuario.data_nascimento if usuario.info_usuario else None,
                "localizacao": usuario.info_usuario.localizacao if usuario.info_usuario else None,
                "sexo": usuario.info_usuario.sexo if usuario.info_usuario else None,
                "nacionalidade": usuario.info_usuario.nacionalidade if usuario.info_usuario else None,
                "bairro": usuario.info_usuario.bairro if usuario.info_usuario else None,
                "revisao": usuario.info_usuario.revisao if usuario.info_usuario else None,
            },
        }
        for usuario in usuarios_nao_verificados
    ]

@router.get("/usuarios/nao_verificados/")
def listar_usuarios_verificados(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),current_admin: Admin = Depends(get_current_admin)
):
    """
    Lista todos os usuários nao verificados , com paginação.
    """
    total_verificados = db.query(Usuario).filter(Usuario.revisao == "nao").count()
    usuarios = (
        db.query(Usuario)
        .filter(Usuario.revisao == "nao")
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "total_usuarios": total_verificados,
        "usuarios": usuarios,
        "page": page,
        "per_page": per_page,
    }



@router.get("/{usuario_id}/produtos/")
def listar_produtos_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Rota para listar produtos de um usuário específico com paginação.

    - `usuario_id`: ID do usuário.
    - `page`: Página atual para paginação (inicia no 1).
    - `limit`: Número máximo de itens por página (default: 10, máximo: 100).
    """
    offset = (page - 1) * limit

    # Verificar se o usuário existe
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Consultar os produtos do usuário
    produtos = db.query(Produto).filter(Produto.CustomerID == usuario_id).offset(offset).limit(limit).all()

    return {
        "page": page,
        "limit": limit,
        "total": db.query(Produto).filter(Produto.CustomerID == usuario_id).count(),
        "produtos": produtos
    }

@router.get("/sistema/resumo/", response_model=dict)
def resumo_sistema(db: Session = Depends(get_db),current_admin: Admin = Depends(get_current_admin)):
    """
    Retorna um resumo do sistema, incluindo o saldo total, total de produtos ativos e total de usuários.
    """
    # Calcular o saldo total
    saldo_total = db.query(func.sum(Wallet.saldo_principal)).scalar() or 0.0

    # Contar os produtos ativos
    total_produtos_ativos = db.query(Produto).filter(Produto.ativo == True).count()

    # Contar o total de produtos
    total_produtos = db.query(Produto).count()

    # Contar o total de usuários
    total_usuarios = db.query(Usuario).count()
    usuarios_pro=db.query(Usuario).filter(Usuario.conta_pro == True).all()

    return {
        "saldo_total": saldo_total,
        "total_produtos_ativos": total_produtos_ativos,
        "total_produtos": total_produtos,
        "total_usuarios": total_usuarios,
        "usurios_pro":usuarios_pro,
    }


@router.get("/{usuario_id}/transacoes")
def listar_transacoes_usuario(
    usuario_id: int,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
   
):
    """
    Lista as transações de um usuário específico com paginação.
    """

    # Verificar se o usuário existe
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")


    # Paginação
    offset = (page - 1) * page_size
    transacoes = (
        db.query(Transacao)
        .filter(Transacao.usuario_id == usuario_id)
        .order_by(Transacao.data_hora.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    if not transacoes:
        return []

    return [
        {
            "id": transacao.id,
            "msisdn": transacao.msisdn,
            "valor": float(transacao.valor),
            "referencia": transacao.referencia,
            "status": transacao.status,
            "data_hora": calcular_tempo_publicacao(transacao.data_hora),
            "tipo": transacao.tipo,
        }
        for transacao in transacoes
    ]

# Alterar a rota de pedidos para evitar conflito
@router.get("/listar-pedidos")  # Mudamos de "/pedidos" para "/listar-pedidos"
def listar_todos_pedidos(
    db: Session = Depends(get_db),
    skip: int = Query(0, description="Número de registros para pular"),
    limit: int = Query(100, description="Limite de registros por página"),
    status: Optional[str] = Query(None, description="Filtrar por status"),
    data_inicio: Optional[datetime] = Query(None, description="Data inicial"),
    data_fim: Optional[datetime] = Query(None, description="Data final"),
    current_admin: Admin = Depends(get_current_admin),
):
    """
    Lista todos os pedidos do sistema com opções de filtro.
    Apenas administradores têm acesso.
    """
    query = db.query(Pedido)

    # Aplicar filtros
    if status:
        query = query.filter(Pedido.status == status)
    if data_inicio:
        query = query.filter(Pedido.data_pedido >= data_inicio)
    if data_fim:
        query = query.filter(Pedido.data_pedido <= data_fim)

    # Contar total antes da paginação
    total_pedidos = query.count()

    # Aplicar paginação
    pedidos = query.offset(skip).limit(limit).all()

    if not pedidos:
        raise HTTPException(status_code=404, detail="Nenhum pedido encontrado")

    # Formatar resposta
    return {
        "total": total_pedidos,
        "pedidos": [
            {
                "id": pedido.id,
                "produto": {
                    "id": pedido.produto.id,
                    "nome": pedido.produto.nome,
                    "preco": float(pedido.produto.preco)
                },
                "comprador": {
                    "id": pedido.customer.id,
                    "nome": pedido.customer.nome,
                    "email": pedido.customer.email
                },
                "vendedor": {
                    "id": pedido.produto.usuario.id,
                    "nome": pedido.produto.usuario.nome,
                    "email": pedido.produto.usuario.email
                },
                "quantidade": pedido.quantidade,
                "preco_total": float(pedido.preco_total),
                "status": pedido.status,
                "tipo": pedido.tipo,
                "data_pedido": pedido.data_pedido.isoformat(),
                "data_aceite": pedido.data_aceite.isoformat() if pedido.data_aceite else None,
                "data_envio": pedido.data_envio.isoformat() if pedido.data_envio else None,
                "data_entrega": pedido.data_entrega.isoformat() if pedido.data_entrega else None
            }
            for pedido in pedidos
        ]
    }

# Também precisamos atualizar a rota de detalhes do pedido
@router.get("/pedido/{pedido_id}")  # Mudamos de "/pedidos/{pedido_id}" para "/pedido/{pedido_id}"
def obter_detalhes_pedido(
    pedido_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """
    Obtém detalhes completos de um pedido específico.
    Apenas administradores têm acesso.
    """
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    # Formatar resposta detalhada
    return {
        "pedido": {
            "id": pedido.id,
            "status": pedido.status,
            "quantidade": pedido.quantidade,
            "preco_total": float(pedido.preco_total),
            "tipo": pedido.tipo,
            "datas": {
                "pedido": pedido.data_pedido.isoformat(),
                "aceite": pedido.data_aceite.isoformat() if pedido.data_aceite else None,
                "envio": pedido.data_envio.isoformat() if pedido.data_envio else None,
                "entrega": pedido.data_entrega.isoformat() if pedido.data_entrega else None,
                "confirmacao": pedido.data_confirmacao_recebimento.isoformat() if pedido.data_confirmacao_recebimento else None
            }
        },
        "produto": {
            "id": pedido.produto.id,
            "nome": pedido.produto.nome,
            "preco_unitario": float(pedido.produto.preco),
            "categoria": pedido.produto.categoria,
            "descricao": pedido.produto.descricao
        },
        "comprador": {
            "id": pedido.customer.id,
            "nome": pedido.customer.nome,
            "email": pedido.customer.email,
            "telefone": pedido.customer.contacto
        },
        "vendedor": {
            "id": pedido.produto.usuario.id,
            "nome": pedido.produto.usuario.nome,
            "email": pedido.produto.usuario.email,
            "telefone": pedido.produto.usuario.contacto
        },
        "status_detalhado": {
            "aceito_pelo_vendedor": pedido.aceito_pelo_vendedor,
            "recebido_pelo_cliente": pedido.recebido_pelo_cliente,
            "status_visivel_comprador": pedido.status_visivel_comprador,
            "status_visivel_vendedor": pedido.status_visivel_vendedor
        }
    }

# E a rota de atualização de status
@router.put("/pedido/{pedido_id}/status")  # Mudamos de "/pedidos/{pedido_id}/status" para "/pedido/{pedido_id}/status"
def atualizar_status_pedido(
    pedido_id: int,
    novo_status: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """
    Atualiza o status de um pedido.
    Apenas administradores têm acesso.
    """
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    # Lista de status válidos
    status_validos = ["pendente", "aceito", "enviado", "entregue", "cancelado", "concluido"]
    if novo_status not in status_validos:
        raise HTTPException(status_code=400, detail=f"Status inválido. Status válidos: {', '.join(status_validos)}")

    # Atualizar status
    pedido.status = novo_status
    
    # Atualizar datas relevantes
    if novo_status == "aceito":
        pedido.data_aceite = datetime.utcnow()
    elif novo_status == "enviado":
        pedido.data_envio = datetime.utcnow()
    elif novo_status == "entregue":
        pedido.data_entrega = datetime.utcnow()
    elif novo_status == "concluido":
        pedido.data_confirmacao_recebimento = datetime.utcnow()

    db.commit()

    return {"message": f"Status do pedido atualizado para {novo_status}"}
