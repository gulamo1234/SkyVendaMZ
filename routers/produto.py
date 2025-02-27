from controlers.produto import *
from controlers.pesquisa import *
from schemas import *
from controlers.utils import *
from auth import *
from models import Message, MessageType,Avaliacao
from fastapi import APIRouter,Form,File,Query,Body
from decimal import Decimal
from sqlalchemy.sql.expression import func, or_, and_
import random
from uuid import uuid4
from typing import List
from datetime import datetime, timedelta
from connection_manager import ConnectionManager

connection_manager=ConnectionManager()



router=APIRouter(prefix="/produtos",tags=["rotas de produtos"])


@router.post("/anuncios/{anuncio_id}/clique")
def registrar_clique(anuncio_id: int, db: Session = Depends(get_db)):
    # Busca o anúncio
    anuncio = db.query(AnuncioUsuario).filter(AnuncioUsuario.id == anuncio_id, AnuncioUsuario.activo == True, AnuncioUsuario.status == "aprovado").first()

    if not anuncio:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado ou não aprovado")

    # Incrementa o número de cliques
    anuncio.cliques += 1
    db.commit()

    return {"message": "Clique registrado com sucesso", "total_cliques": anuncio.cliques}


@router.post("/{produto_id}/ativar-automatica")
async def ativar_renovacao_automatica(
    produto_id: int,
    ativar: bool,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Ativa ou desativa a renovação automática para um produto.
    """
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    # Verificar se o usuário é dono do produto
    if produto.CustomerID != current_user.id:
        raise HTTPException(status_code=403, detail="Não autorizado")

    # Atualizar a renovação automática
    produto.renovacao_automatica = ativar
    db.commit()

    return {
        "message": f"Renovação automática {'ativada' if ativar else 'desativada'} com sucesso",
        "renovacao_automatica": produto.renovacao_automatica
    }






@router.put("/status/atualizar/{status_id}")
def atualizar_status(
    status_id: int,
    duracao_dias: int = Form(...),  # Corrigido para "duracao_dias"
    conteudo: str = Form(None),
    imagem: UploadFile = Form(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Rota para atualizar um status existente do usuário.
    """
    try:
        resultado = atualizar_status_controller(
            db=db,
            usuario_id=current_user.id,
            status_id=status_id,
            dias_adicionais=duracao_dias,  # Use "duracao_dias" aqui
            conteudo=conteudo,
            imagem=imagem
        )
        return resultado
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{status_id}/visualizar/")
async def visualizar(status_id: int, db: Session = Depends(get_db)):
    resultado = visualizar_status(status_id=status_id, db=db)
    return resultado


@router.post("/promover", status_code=201)
def promover_produto_route(
    dados: PromoverProdutoSchema,  # Recebendo o schema Pydantic
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)  # Verifica o usuário autenticado
    
):
    # Verifica o ID do usuário autenticado
    usuario_id = current_user.id
    desativar_anuncios_expirados(db)
    # Chama a função de promover produto, desempacotando os dados do schema
    
    return promover_produto(
        produto_id=dados.produto_id,
        dias=dados.dias,
        db=db,
        usuario_id=usuario_id,
        titulo=dados.titulo,
        descricao=dados.descricao,
        tipo=dados.tipo,
       
    )



@router.get("/anuncios/tipo", response_model=List[dict])
def listar_anuncios_aleatorios(
    tipo_anuncio: str = Query(None, description="Tipo do anúncio para filtrar (opcional)"),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
    
):
    """
    Rota para listar anúncios de forma aleatória, com dados do produto associado.
    Agora desativa anúncios expirados em segundo plano.
    """
    # Executa a tarefa de desativar anúncios expirados em segundo plano
    desativar_anuncios_expirados(db)
   

    # Construção da consulta
    stmt = (
        select(Anuncio, Produto)
        .join(Produto, Anuncio.produto_id == Produto.id)
        .where(
            and_(
                Anuncio.ativo == True,
                Produto.ativo == True
            )
        )
        .order_by(func.random())  # Ordenação aleatória
    )
    
    # Filtro por tipo de anúncio, se fornecido
    if tipo_anuncio:
        stmt = stmt.filter(Anuncio.tipo_anuncio == tipo_anuncio)
    
    # Aplicar limite de resultados
    stmt = stmt.limit(limit)

    # Executar consulta
    result = db.execute(stmt).all()

    if not result:
        raise HTTPException(status_code=404, detail="Nenhum anúncio encontrado.")

    # Formatação do resultado
    anuncios = [
        {
            "anuncio": {
                "id": anuncio.id,
                "titulo": anuncio.titulo,
                "descricao": anuncio.descricao,
                "tipo_anuncio": anuncio.tipo_anuncio,
                "produto_id": anuncio.produto_id,
                "expira_em": anuncio.expira_em.isoformat() if anuncio.expira_em else None,
                "dias_restantes": (anuncio.expira_em - datetime.utcnow()).days if anuncio.expira_em else None,
                "promovido_em": anuncio.promovido_em.isoformat() if anuncio.promovido_em else None,
            },
            "produto": {
                "id": produto.id,
                "nome": produto.nome,
                "descricao": produto.descricao,
                "preco": float(produto.preco),
                "capa": produto.capa,
                "slug": produto.slug,
                "likes": produto.likes,
                "views": produto.visualizacoes,
            },
        }
        for anuncio, produto in result
    ]

    return anuncios

@router.post("/{produto_id}/reativar/")
def reativar_produto_endpoint(produto_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return reativar_produto(produto_id=produto_id, current_user=current_user, db=db) 


@router.get("/pegar/{produto_id}")
async def get_produto(produto_id: int, db: Session = Depends(get_db)):
    # Busca o produto pelo ID
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    
    # Calcula o tempo de publicação em formato legível
    tempo_publicacao = calcular_tempo_publicacao(produto.data_publicacao)
    
    # Retorna os dados do produto com o tempo de publicação formatado
    return {
        "id": produto.id,
        "nome": produto.nome,
        "capa": produto.capa,
        "preco": str(produto.preco),
        "quantidade_estoque": produto.quantidade_estoque,
        "estado": produto.estado,
        "provincia": produto.provincia,
        "distrito": produto.distrito,
        "localizacao": produto.localizacao,
        "revisao": produto.revisao,
        "disponiblidade": produto.disponiblidade,
        "descricao": produto.descricao,
        "categoria": produto.categoria,
        "renovacao":produto.renovacao_automatica,
        "detalhes": produto.detalhes,
        "tipo": produto.tipo,
        "visualizacoes": formatar_contagem(produto.visualizacoes),
        "likes": formatar_contagem(produto.likes),
        "data_publicacao": tempo_publicacao
    }


@router.post("/publicar")
async def create_produto(
    nome: str = Form(...),
    preco: Decimal = Form(...),
    quantidade_estoque: Optional[int] = Form(None),
    estado: str = Form(...),
    distrito: str = Form(...),
    provincia: str = Form(...),
    localizacao: str = Form(...),
    revisao:  Optional[str] = Form(None),
    disponiblidade: str = Form(...),
    descricao: str = Form(...),
    categoria: str = Form(...),
    detalhes: str = Form(...),
    tipo: str = Form(...),
    fotos: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)  # Renomeie para evitar confusão
):
    # Verifica se pelo menos uma foto foi enviada
    if not fotos:
        raise HTTPException(status_code=400, detail="Pelo menos uma foto deve ser enviada.")
    
    # A primeira foto será a capa, as demais serão adicionais
    capa = fotos[0]
    outras_fotos = fotos[1:]

    # Criação do objeto ProdutoCreate
    produto_data = ProdutoCreate(
        nome=nome,
        preco=preco,
        quantidade_estoque=quantidade_estoque,
        estado=estado,
        provincia=provincia,
        distrito=distrito,
        localizacao=localizacao,
        revisao=revisao,
        disponiblidade=disponiblidade,
        descricao=descricao,
        categoria=categoria,
        detalhes=detalhes,
        tipo=tipo,
        CustomerID=current_user.id,  # Use o ID do usuário
    )

    # Gera o slug único
    slug = gerar_slug_unico(produto_data.nome, db)
    produto_data.slug = slug  # Atribui o slug gerado ao produto

    # Verifica se o usuário completou o registro antes de salvar o produto
    try:
        db_produto = create_produto_db_with_image(
            db=db, 
            produto=produto_data,
            user_id=current_user.id,  # Passe o ID do usuário aqui também
            files=fotos,  # Passa todas as fotos
            extra_files=outras_fotos  # Fotos adicionais
        )
        # Enviar notificação de forma assíncrona
        try:
            await connection_manager.send_notification(
                'Publicado',
                'post_new',
                f'Novo produto publicado: {produto_data.nome}'
            )
        except Exception as e:
            print(f"Erro ao enviar notificação: {str(e)}")
            # Não interrompe o fluxo se a notificação falhar

        return {"message": "Produto criado com sucesso", "produto": db_produto}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pesquisa/")
def pesquisa_avancada(
    termo: str,
    offset: int = Query(1, description="Número da página para paginação (começa em 1)"),
    limit: int = Query(10, description="Limite de itens por página"),
    db: Session = Depends(get_db),
    user_id: Optional[int] = Query(None, description="ID opcional do usuário"),
):
    """
    Rota para pesquisa avançada de produtos ativos.
    """
    # Chamada da função `executar_pesquisa_avancada`
    resultados = executar_pesquisa_avancada(
        termo=termo,
        db=db,
        user_id=user_id,
        limit=limit,
        offset=offset
    )

    return resultados







ANUCIO_UPLOAD_DIR = "uploads/anuncios"
os.makedirs(ANUCIO_UPLOAD_DIR, exist_ok=True)

@router.post("/anuncios/enviar")
def enviar_anuncio(
    nome: str = Form(...),
    descricao: str = Form(...),
    dias: int = Form(...),
    preco: Optional[float] = Form(None),
    link: Optional[str] = Form(None),
    imagem: UploadFile = File(...),
    usuario_id: int = Form(...),
    db: Session = Depends(get_db)
):
    # Verifica se o usuário existe
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    # Verifica se a imagem é válida
    if not imagem.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="O arquivo deve ser uma imagem")
    
    # Salvar a imagem
    image_path = os.path.join(ANUCIO_UPLOAD_DIR, imagem.filename)
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(imagem.file, buffer)
    
    # Criar anúncio pendente de aprovação
    anuncio = AnuncioUsuario(
        nome=nome,
        descricao=descricao,
        preco=preco,
        link=link,
        foto=image_path,
        criado_em=datetime.utcnow(),
        expira_em=datetime.utcnow() + timedelta(days=dias),
        usuario_id=usuario_id
    )
    db.add(anuncio)
    db.commit()
    
    return {"message": "Anúncio enviado para revisão", "anuncio_id": anuncio.id}

from pathlib import Path
ANUNCIO_UPLOAD_DIR = Path("uploads/anuncios")

@router.get("/anuncios/listar", response_model=List[dict])
def listar_anuncios(db: Session = Depends(get_db)):
    anuncios = db.query(AnuncioUsuario).filter(
        AnuncioUsuario.status == "aprovado",
        AnuncioUsuario.activo == True
    ).all()

    # **Embaralhar os anúncios aleatoriamente**
    random.shuffle(anuncios)

    return [
        {
            "id": anuncio.id,
            "nome": anuncio.nome,
            "descricao": anuncio.descricao,
            "preco": anuncio.preco,
            "link": anuncio.link,
            "imagem": anuncio.foto,
            "criado_em": anuncio.criado_em.isoformat(),
            "expira_em": anuncio.expira_em.isoformat()
        }
        for anuncio in anuncios
    ]

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

@router.get("/{pedido_id}/details", response_model=dict)
def get_order_details(
    pedido_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Get detailed information for a specific order.
    Returns data with English keys.
    """
    try:
        # Busca o pedido e faz join com produto
        order = (
            db.query(Pedido)
            .filter(
                Pedido.id == pedido_id,
                Pedido.status != "Eliminado"
            )
            .first()
        )

        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # Verifica se o usuário tem permissão (comprador ou vendedor)
        product = db.query(Produto).filter(Produto.id == order.produto_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        if order.customer_id != current_user.id and product.CustomerID != current_user.id:
            raise HTTPException(
                status_code=403, 
                detail="You don't have permission to view this order"
            )

        # Busca dados do comprador e vendedor
        buyer = db.query(Usuario).filter(Usuario.id == order.customer_id).first()
        seller = db.query(Usuario).filter(Usuario.id == product.CustomerID).first()

        # Monta o dicionário de resposta
        order_details = {
            "order": {
                "id": order.id,
                "status": order.status,
                "type": order.tipo,
                "quantity": order.quantidade,
                "total_price": float(order.preco_total) if order.preco_total else None,
                "order_date": order.data_pedido.isoformat() if order.data_pedido else None,
                "acceptance_date": order.data_aceite.isoformat() if order.data_aceite else None,
                "shipping_date": order.data_envio.isoformat() if order.data_envio else None,
                "delivery_date": order.data_entrega.isoformat() if order.data_entrega else None,
                "confirmation_date": order.data_confirmacao_recebimento.isoformat() 
                    if hasattr(order, 'data_confirmacao_recebimento') and order.data_confirmacao_recebimento 
                    else None,
                "accepted_by_seller": order.aceito_pelo_vendedor,
                "received_by_buyer": order.recebido_pelo_cliente
            },
            "product": {
                "id": product.id,
                "name": product.nome,
                "price": float(product.preco) if product.preco else None,
                "cover_image": product.capa,
                "description": product.descricao,
                "category": product.categoria
            },
            "buyer": {
                "id": buyer.id if buyer else None,
                "name": buyer.nome if buyer else None,
                "email": buyer.email if buyer else None,
                "phone": buyer.telefone if buyer else None
            },
            "seller": {
                "id": seller.id if seller else None,
                "name": seller.nome if seller else None,
                "email": seller.email if seller else None,
                "phone": seller.telefone if seller else None
            }
        }

        return order_details

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting order details for order {pedido_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{slug}")
def obter_produto(
    slug: str,
    db: Session = Depends(get_db),
    user_id: int = Query(None, description="ID opcional do usuário para verificar likes"),
):
    """
    Retorna os detalhes de um produto específico baseado no `slug` e aumenta as visualizações.
    Se `user_id` for fornecido, indica se o usuário deu like no produto.

    Args:
        slug (str): Slug do produto para buscar o produto.
        user_id (int): ID opcional do usuário para verificar os likes.

    Returns:                                                                                    
        dict: Detalhes do  produto.
    """
    # Buscar o produto pelo slug
    produto = db.query(Produto).filter(Produto.slug == slug).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    
    # Se não for o dono e o produto não estiver ativo, retorna 404
    if user_id != produto.CustomerID and not produto.ativo:
        raise HTTPException(status_code=404, detail="Produto não encontrado ou não está ativo.")

    # Verificar se o usuário deu like
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first() if user_id else None

    # Função auxiliar para calcular a média de estrelas do vendedor
    def calcular_media_estrelas(usuario_id: int):
        avaliacoes = db.query(Avaliacao).filter(Avaliacao.avaliado_id == usuario_id).all()
        if not avaliacoes:
            return None  # Sem avaliações
        soma_estrelas = sum(avaliacao.estrelas for avaliacao in avaliacoes)
        return round(soma_estrelas / len(avaliacoes), 2)

    # Retorna os detalhes do produto
    return {
            "id": produto.id,
            "title": produto.nome,
            "thumb": produto.capa,
            "images": produto.fotos,
            "price": float(produto.preco),
            "stock_quantity": produto.quantidade_estoque,
            "state": produto.estado,
            "province": produto.provincia,
            "negociavel": produto.negociavel,
            "district": produto.distrito,
            "location": produto.localizacao,
            "review": produto.revisao,
            "availability": produto.disponiblidade,
            "description": produto.descricao,
            "category": produto.categoria,
            "details": produto.detalhes,
            "type": produto.tipo,
            "views": formatar_contagem(produto.visualizacoes),
            "active": produto.ativo,
            "customer_id": produto.CustomerID,
            "likes": formatar_contagem(produto.likes),
            "slug": produto.slug,
            "time": calcular_tempo_publicacao(produto.data_publicacao),
            "user": {
                "id": produto.usuario.id,
                "name": produto.usuario.nome,
                "avatar": produto.usuario.foto_perfil,
                "average_stars": calcular_media_estrelas(produto.usuario.id),  # Média de estrelas do usuário
            },
        "liked": usuario in produto.usuarios_que_deram_like if usuario else None,
        "comments": [
                {
                    "id": comentario.id,
                    "text": comentario.comentario,
                    "date": calcular_tempo_publicacao(comentario.data_comentario),
                    "user": {
                        "id": comentador.id,
                        "username": comentador.username,
                        "name": comentador.nome,
                        "avatar": comentador.foto_perfil
                    }
                }
                for comentario, comentador in (
                    db.query(Comentario, Usuario)
                    .join(Usuario, Usuario.id == Comentario.usuarioID)
                    .filter(Comentario.produtoID == produto.id)
                    .all()
                )
            ]
    }




@router.put("/{produto_id}/negociavel")
def atualizar_negociabilidade(
    produto_id: int,
    negociavel: bool,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    produto = db.query(Produto).filter_by(id=produto_id, CustomerID=current_user.id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado ou não pertence a você")
    
    produto.negociavel = negociavel
    db.commit()

    return {"message": f"O produto {produto.nome} foi atualizado para {'negociável' if negociavel else 'não negociável'}"}
@router.put("/{produto_id}/promocao")
def marcar_promocao(
    produto_id: int,
    dias_promocao: int,
    preco_promocional: float,  # Novo preço promocional
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Coloca um produto em promoção, define um preço promocional e deduz o custo da promoção do saldo do usuário.
    """
    # Buscar o produto e verificar se pertence ao usuário
    produto = db.query(Produto).filter(
        Produto.id == produto_id,
        Produto.CustomerID == current_user.id  # Certifique-se de usar 'usuario_id' ao invés de 'usuario'
    ).first()

    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado ou não pertence a você.")
    
    # Verificar se o produto já está em promoção
    if produto.promocao:
        raise HTTPException(status_code=400, detail="Este produto já está em promoção.")

    # Validar o preço promocional
    if preco_promocional >= produto.preco:
        raise HTTPException(status_code=400, detail="O preço promocional deve ser menor que o preço original.")
    
    # Cálculo do custo da promoção
    custo_total = dias_promocao * 10

    # Buscar a carteira do usuário
    carteira = db.query(Wallet).filter(Wallet.usuario_id == current_user.id).first()
    if not carteira:
        raise HTTPException(status_code=404, detail="Carteira não encontrada.")

    # Verificar se o saldo é suficiente
    if carteira.saldo_principal < custo_total:
        raise HTTPException(status_code=400, detail="Saldo insuficiente para colocar o produto em promoção.")
    
    # Atualizar o produto para promoção
    produto.promocao = True
    produto.preco_promocional = preco_promocional  # Define o novo preço promocional
    produto.data_promocao = datetime.utcnow()
    produto.dias_promocao = dias_promocao

    # Deduzir o saldo da carteira
    carteira.saldo_principal -= custo_total

    # Salvar alterações no banco
    db.commit()

    return {
        "message": f"O produto '{produto.nome}' foi colocado em promoção por {dias_promocao} dias.",
        "preco_promocional": preco_promocional
    }



@router.get("/produtos/promocao")
def listar_produtos_em_promocao(
    db: Session = Depends(get_db),
    limite: int = 10,  # Número máximo de produtos a serem retornados
    pagina: int = 1  # Página atual para a paginação
):
    """
    Retorna a lista de produtos em promoção.
    """
    # Cálculo de offset para paginação
    offset = (pagina - 1) * limite

    # Buscar os produtos em promoção no banco de dados
    produtos = (
        db.query(Produto)
        .filter(Produto.promocao == True)
        .order_by(Produto.data_promocao.desc())  # Ordenar pela data de promoção
        .limit(limite)
        .offset(offset)
        .all()
    )

    # Verificar se existem produtos em promoção
    if not produtos:
        raise HTTPException(status_code=404, detail="Nenhum produto em promoção encontrado.")

    # Retornar os produtos com as informações relevantes
    return {
        "total": len(produtos),
        "pagina": pagina,
        "limite": limite,
        "produtos": [
            {
                "id": produto.id,
                "nome": produto.nome,
                "preco": produto.preco,
                "preco_promocional": produto.preco_promocional,
                "usuario_id": produto.usuario_id,
                "data_promocao": produto.data_promocao,
                "dias_restantes": max(0, (produto.dias_promocao or 0) - (datetime.utcnow() - produto.data_promocao).days)
            }
            for produto in produtos
        ]
    }


@router.get("/detalhe/{slug}")
def obter_produto(
    slug: str,
    db: Session = Depends(get_db),
    user_id: int = Query(None, description="ID opcional do usuário para verificar likes"),
):
    """
    Retorna os detalhes de um produto específico baseado no `slug` e aumenta as visualizações.
    Se `user_id` for fornecido, indica se o usuário deu like no produto.

    Args:
        slug (str): Slug do produto para buscar o produto.
        user_id (int): ID opcional do usuário para verificar os likes.

    Returns:
        dict: Detalhes do produto.
    """
    # Buscar o produto pelo slug
    produto = db.query(Produto).filter(Produto.slug == slug).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    
    if  not produto.ativo:
        raise HTTPException(status_code=404, detail="Produto não encontrado ou não está ativo.")

    # Aumentar as visualizações do produto
    produto.visualizacoes += 1
    db.commit()
    db.refresh(produto)

    # Verificar se o usuário deu like
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first() if user_id else None

    # Função auxiliar para calcular a média de estrelas do vendedor
    def calcular_media_estrelas(usuario_id: int):
        avaliacoes = db.query(Avaliacao).filter(Avaliacao.avaliado_id == usuario_id).all()
        if not avaliacoes:
            return None  # Sem avaliações
        soma_estrelas = sum(avaliacao.estrelas for avaliacao in avaliacoes)
        return round(soma_estrelas / len(avaliacoes), 2)

    # Retorna os detalhes do produto
    return {
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
            "negociavel": produto.negociavel,
            "details": produto.detalhes,
            "type": produto.tipo,
            "views": formatar_contagem(produto.visualizacoes),
            "active": produto.ativo,
            "customer_id": produto.CustomerID,
            "likes": formatar_contagem(produto.likes),
            "slug": produto.slug,
            "time": calcular_tempo_publicacao(produto.data_publicacao),
            "user": {
                "id": produto.usuario.id,
                "name": produto.usuario.nome,
                "avatar": produto.usuario.foto_perfil,
                "average_stars": calcular_media_estrelas(produto.usuario.id),  # Média de estrelas do usuário
            },
        "liked": usuario in produto.usuarios_que_deram_like if usuario else None,
        "comments": [
                {
                    "id": comentario.id,
                    "text": comentario.comentario,
                    "date": calcular_tempo_publicacao(comentario.data_comentario),
                    "user": {
                        "id": comentador.id,
                        "name": comentador.nome,
                        "username": comentador.username,
                        "avatar": comentador.foto_perfil
                    }
                }
                for comentario, comentador in (
                    db.query(Comentario, Usuario)
                    .join(Usuario, Usuario.id == Comentario.usuarioID)
                    .filter(Comentario.produtoID == produto.id)
                    .all()
                )
            ]
    }

@router.get("/produto/{produto_id}/likes")
def produto_likes(produto_id: int, db: Session = Depends(get_db)):
    return get_produto_likes(db, produto_id)

@router.delete("/produtos/{slug}")
def delete_produto(slug: str, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    """
    Deleta um produto baseado no slug. Apenas o proprietário do produto pode deletá-lo.
    """
    # Buscar produto pelo slug
    db_produto = db.query(Produto).filter(Produto.slug == slug).first()

    if db_produto is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    # Verificar se o usuário atual é o proprietário do produto
    if db_produto.CustomerID != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado. Você não pode deletar este produto.")

    # Remover o produto do banco de dados
    db.delete(db_produto)
    db.commit()

    return {"detail": "Produto deletado com sucesso."}


@router.put("/{slug}/capa")
async def update_produto_capa(
    slug: str,
    capa: UploadFile = File(...),  # Apenas um arquivo é permitido
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Atualiza apenas a foto de capa de um produto baseado no slug. 
    Apenas o proprietário do produto pode fazer a atualização.
    """
    # Validar o arquivo enviado
    if not capa.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="O arquivo enviado não é uma imagem válida. Certifique-se de enviar uma imagem no formato correto (jpeg, png, etc.)."
        )

    # Buscar produto pelo slug
    db_produto = db.query(Produto).filter(Produto.slug == slug).first()

    if db_produto is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    # Verificar se o usuário atual é o proprietário do produto
    if db_produto.CustomerID != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado. Você não pode atualizar as imagens deste produto.")

    # Salvar a nova imagem
    nome_arquivo = await salvar_imagem(capa)

    # Atualizar a foto de capa no banco de dados
    db_produto.capa = nome_arquivo  # Salvar apenas o nome do arquivo
    db.commit()
    db.refresh(db_produto)

    return {
        "message": "Foto de capa do produto atualizada com sucesso.",
        "capa": nome_arquivo,
    }


async def salvar_imagem(arquivo: UploadFile) -> str:
    """
    Salva a imagem enviada e retorna apenas o nome do arquivo gerado.
    """
    # Gerar um nome único para a imagem
    nome_arquivo = f"{uuid4().hex}_{arquivo.filename}"
    caminho_pasta = os.path.join("uploads", "produto")  # Diretório onde os arquivos serão salvos
    caminho_completo = os.path.join(caminho_pasta, nome_arquivo)

    # Certifique-se de que o diretório existe
    os.makedirs(caminho_pasta, exist_ok=True)

    # Salvar o arquivo no sistema de arquivos
    with open(caminho_completo, "wb") as f:
        f.write(await arquivo.read())

    # Retornar apenas o nome do arquivo gerado
    return nome_arquivo






@router.put("/{slug}")
async def update_produto(
    slug: str,
    nome: Optional[str] = Form(None),
    preco: Optional[float] = Form(None),
    quantidade_estoque: Optional[int] = Form(None),
    estado: Optional[str] = Form(None),
    disponiblidade: Optional[str] = Form(None),
    descricao: Optional[str] = Form(None),
    detalhes: Optional[str] = Form(None),
    tipo: Optional[str] = Form(None),
    categoria: Optional[str] = Form(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Buscar o produto pelo slug
    db_produto = db.query(Produto).filter(Produto.slug == slug).first()
    
    if not db_produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    
    # Verificar se o usuário autenticado é o proprietário do produto
    if db_produto.CustomerID != current_user.id:
        raise HTTPException(
            status_code=403, detail="Você não tem permissão para atualizar este produto"
        )
    
    produto = ProdutoUpdate(
        nome=nome,
        preco=preco,
        quantidade_estoque=quantidade_estoque,
        estado=estado,
        disponiblidade=disponiblidade,
        descricao=descricao,
        detalhes=detalhes,
        tipo=tipo,
        categoria=categoria,
        CustomerID=current_user.id,
    )

    # Atualizar o produto no banco de dados, processando arquivos se forem enviados
    db_produto = update_produto_db_with_images(db=db, produto_id=slug, produto=produto)
    
    if db_produto is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    
    return {"message": "Produto atualizado com sucesso", "produto": db_produto}


@router.post("/{produto_slug}/like")
def like_produto(
    produto_slug: str, 
    db: Session = Depends(get_db),
    user_id: Usuario = Depends(get_current_user)
):
    return toggle_like_produto(db, produto_slug, user_id.id)


@router.get("/anuncios/")
def listar_anuncios(db: Session = Depends(get_db)):
    """
    Rota para listar todos os anúncios válidos junto com os produtos associados.
    """
    return listar_anuncios_com_produtos(db)

@router.get("/produtos/promovidos", response_model=List[dict])
def listar_anuncios_produtos(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    anuncios = db.query(Anuncio).join(Produto).filter(Anuncio.ativo == True, Produto.CustomerID == current_user.id).all()
    return [
        {
            "id": anuncio.id,
            "titulo": anuncio.titulo,
            "descricao": anuncio.descricao,
            "tipo_anuncio": anuncio.tipo_anuncio,
            "produto_id": anuncio.produto_id,
            "produto_nome": anuncio.produto.nome if anuncio.produto else None,
            "produto_capa": anuncio.produto.capa if anuncio.produto else None,
            "promovido_em": anuncio.promovido_em,
            "expira_em": anuncio.expira_em,
            "ativo": anuncio.ativo
        }
        for anuncio in anuncios
    ]

@router.get("/")
def listar_produtos(
    db: Session = Depends(get_db),
    user_id: int = Query(None, description="ID opcional do usuário para verificar likes"),
    limit: int = Query(10, description="Quantidade de produtos por página"),
    offset: int = Query(0, description="Ponto inicial para a paginação")
):
    """
    Lista produtos ativos com informações detalhadas e ordenados por relevância.
    """
    # Buscar produtos usando o sistema de pontuação
    produtos = get_produtos_home(db, limit)

    if not produtos:
        raise HTTPException(status_code=404, detail="Nenhum produto encontrado.")

    # Consulta o usuário apenas se user_id for fornecido
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first() if user_id else None

    # Função auxiliar para calcular a média de estrelas do usuário
    def calcular_media_estrelas(usuario_id: int):
        avaliacoes = db.query(Avaliacao).filter(Avaliacao.avaliado_id == usuario_id).all()
        if not avaliacoes:
            return None  # Sem avaliações
        soma_estrelas = sum(avaliacao.estrelas for avaliacao in avaliacoes)
        return round(soma_estrelas / len(avaliacoes), 2)

    # Criar o JSON com os detalhes do produto e os comentários
    return [
        {
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
            "user": {
                "id": produto.usuario.id,
                "name": produto.usuario.nome,
                "username":produto.usuario.username,
                "nome_pagina":produto.usuario.nome_pagina,
                "avatar": produto.usuario.foto_perfil,
                "average_stars": calcular_media_estrelas(produto.usuario.id),
            },
            "liked": usuario in produto.usuarios_que_deram_like if usuario else None,
            "comments": [
                {
                    "id": comentario.id,
                    "text": comentario.comentario,
                    "date": calcular_tempo_publicacao(comentario.data_comentario),
                    "user": {
                        "id": comentador.id,
                        "name": comentador.nome,
                        "username": comentador.username,
                        "avatar": comentador.foto_perfil
                    }
                }
                for comentario, comentador in (
                    db.query(Comentario, Usuario)
                    .join(Usuario, Usuario.id == Comentario.usuarioID)
                    .filter(Comentario.produtoID == produto.id)
                    .all()
                )
            ]
        }
        for produto in produtos
    ]

@router.get("/produtos/")
def get_produtos_usuario_logado(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
    q: Optional[str] = Query(None, description="Texto para buscar nos produtos.")  # Novo parâmetro para pesquisa
):
    """
    Rota que retorna todos os produtos do usuário logado (ativos e inativos) com suporte à pesquisa.
    """
    # Iniciar consulta básica com filtro pelo usuário logado
    produtos_query = db.query(Produto).filter(Produto.CustomerID == current_user.id).all()

    # Adicionar filtro de pesquisa, se fornecido
    if q:
        produtos_query = produtos_query.filter(
            (Produto.nome.ilike(f"%{q}%")) |  # Pesquisar no nome
            (Produto.descricao.ilike(f"%{q}%"))  # Pesquisar na descrição
        )

    # Contar o total de produtos após aplicar os filtros
    

    # Aplicar paginação
    

    if not produtos_query:
        raise HTTPException(status_code=404, detail="Nenhum produto encontrado para este usuário.")

    # Preparar a resposta
    produtos_response = []
    for produto in produtos_query:
        # Calcular tempo desde a publicação
        tempo_publicacao = calcular_tempo_publicacao(produto.data_publicacao)

        # Verificar se o usuário logado deu like no produto
        liked = current_user.id in [u.id for u in produto.usuarios_que_deram_like]

        # Buscar comentários com usuários associados
        comentarios = db.query(Comentario, Usuario).join(Usuario, Usuario.id == Comentario.usuarioID).filter(
            Comentario.produtoID == produto.id).all()
        comentarios_response = [
            {
                "id": comentario.id,
                "text": comentario.comentario,
                "date": calcular_tempo_publicacao(comentario.data_comentario),
                "user": {
                    "id": comentador.id,
                    "name": comentador.nome,
                    "username": comentador.username,
                    "avatar": comentador.foto_perfil,
                }
            }
            for comentario, comentador in comentarios
        ]

        # Adicionar produto à resposta
        produtos_response.append({
            "id": produto.id,
            "title": produto.nome,
            "thumb": produto.capa,
            "images": produto.fotos,
            "price": Decimal(produto.preco) if produto.preco is not None else Decimal("0.0"),
            "stock_quantity": produto.quantidade_estoque,
            "state": produto.estado,
            "province": produto.provincia,
            "district": produto.distrito,
            "location": produto.localizacao,
            "review": produto.revisao,
            "negociavel": produto.negociavel,
            "availability": produto.disponiblidade,
            "description": produto.descricao,
            "renovacao":produto.renovacao_automatica,
            "category": produto.categoria,
            "details": produto.detalhes,
            "type": produto.tipo,
            "views": formatar_contagem(produto.visualizacoes),
            "active": produto.ativo,
            "customer_id": produto.CustomerID,
            "likes": formatar_contagem(produto.likes),
            "slug": produto.slug,
            "time": tempo_publicacao,
            "liked": liked,
            "comments": comentarios_response,
        })

    return {
        
        "produtos": produtos_response,
              
    }


@router.post("/usuarios/{usuario_id}/status/")
async def criar_status(
    usuario_id: int,
    conteudo: str = Form(None),
    imagem: UploadFile = File(None),
    duracao_dias: int = Form(...),
    db: Session = Depends(get_db)
):
    # Chamar o controlador para criar o status
    resultado = criar_status_controller(
        usuario_id=usuario_id,
        conteudo=conteudo,
        imagem=imagem,
        duracao_dias=duracao_dias,
        db=db
    )

    return resultado

@router.post("/status/{status_id}/responder")
def responder_status(
    status_id: int,
    sender_id: int,
    receiver_id: int,
    conteudo: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    # Verificar se o status existe
    status = db.query(Status).filter(Status.id == status_id).first()
    if not status:
        raise HTTPException(status_code=404, detail="Status não encontrado")

    # Verificar se o conteúdo é fornecido
    if not conteudo and not status.imagem_url:
        raise HTTPException(status_code=400, detail="Conteúdo ou imagem do status é necessário para responder")

    # Criar a mensagem de resposta
    nova_mensagem = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        content=conteudo,
        message_type=MessageType.TEXT if not status.imagem_url else MessageType.IMAGE,
        file_url=status.imagem_url  # Usar a imagem do status
    )

    db.add(nova_mensagem)
    db.commit()

    return {"message": "Resposta enviada com sucesso", "message_id": nova_mensagem.id}

@router.get("/categorias/populares", summary="Categorias mais populares no geral")
def obter_categorias_populares(db: Session = Depends(get_db)):
    """
    Retorna as categorias mais interagidas no geral.
    """
    categorias = categorias_mais_populares(db)
    if not categorias:
        raise HTTPException(status_code=404, detail="Nenhuma interação encontrada no sistema.")
    return categorias




@router.post("/publicacoes/{publicacao_id}/like")
def like_publicacao(
    publicacao_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Adiciona ou remove um like de uma publicação.
    """
    publicacao = db.query(Publicacao).filter(Publicacao.id == publicacao_id).first()

    if not publicacao:
        raise HTTPException(status_code=404, detail="Publicação não encontrada.")

    # Verifica se o usuário já deu like
    like = db.query(LikePublicacao).filter(
        LikePublicacao.publicacao_id == publicacao_id,
        LikePublicacao.usuario_id == current_user.id
    ).first()

    if like:
        # Remove o like
        db.delete(like)
        db.commit()
        return {"mensagem": "Like removido com sucesso."}

    # Adiciona o like
    novo_like = LikePublicacao(usuario_id=current_user.id, publicacao_id=publicacao_id)
    db.add(novo_like)
    db.commit()

    return {"mensagem": "Like adicionado com sucesso."}


@router.post("/publicacoes/{publicacao_id}/comentario")
def comentar_publicacao(
    publicacao_id: int,
    conteudo: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Adiciona um comentário a uma publicação.
    """
    publicacao = db.query(Publicacao).filter(Publicacao.id == publicacao_id).first()

    if not publicacao:
        raise HTTPException(status_code=404, detail="Publicação não encontrada.")

    # Adiciona o comentário
    novo_comentario = ComentarioPublicacao(
        usuario_id=current_user.id,
        publicacao_id=publicacao_id,
        conteudo=conteudo
    )
    db.add(novo_comentario)
    db.commit()

    return {"mensagem": "Comentário adicionado com sucesso."}


@router.get("/publicacoes/{publicacao_id}/detalhes")
def detalhes_publicacao(
    publicacao_id: int,
    db: Session = Depends(get_db)
):
    """
    Retorna os detalhes da publicação, incluindo likes e comentários.
    """
    publicacao = db.query(Publicacao).filter(Publicacao.id == publicacao_id).first()

    if not publicacao:
        raise HTTPException(status_code=404, detail="Publicação não encontrada.")

    # Contar likes
    total_likes = db.query(LikePublicacao).filter(LikePublicacao.publicacao_id == publicacao_id).count()

    # Obter comentários
    comentarios = db.query(ComentarioPublicacao).filter(ComentarioPublicacao.publicacao_id == publicacao_id).all()

    return {
        "id": publicacao.id,
        "conteudo": publicacao.conteudo,
        "usuario": {
            "id": publicacao.usuario.id,
            "nome": publicacao.usuario.nome,
            "username": publicacao.usuario.username
        },
        "likes": total_likes,
        "comentarios": [
            {
                "id": comentario.id,
                "conteudo": comentario.conteudo,
                "data_criacao": comentario.data_criacao.isoformat(),
                "usuario": {
                    "id": comentario.usuario.id,
                    "nome": comentario.usuario.nome,
                    "username": comentario.usuario.username
                }
            }
            for comentario in comentarios
        ]
    }

@router.post("/{produto_id}/renovar")
async def renovar_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Renova um produto expirado por mais 30 dias, descontando a taxa do saldo principal ou bônus do usuário.
    """
    # Buscar o produto
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
        
    # Verificar se o usuário é dono do produto
    if produto.CustomerID != current_user.id:
        raise HTTPException(status_code=403, detail="Não autorizado a renovar este produto")
    
    # Calcular a taxa de renovação com base no valor do produto
    taxa = calcular_taxa_publicacao(Decimal(produto.preco))
    
    # Verificar se o saldo total (principal + bônus) é suficiente
    saldo_total = current_user.wallet.saldo_principal + current_user.wallet.bonus
    if saldo_total < taxa:
        raise HTTPException(status_code=400, detail="Saldo insuficiente para renovar o produto")
    
    # Descontar do saldo principal e complementar com bônus, se necessário
    restante = taxa
    if current_user.wallet.saldo_principal >= restante:
        current_user.wallet.saldo_principal -= restante
    else:
        restante -= current_user.wallet.saldo_principal
        current_user.wallet.saldo_principal = Decimal("0.0")
        current_user.wallet.bonus -= restante

    # Atualizar o produto
    produto.ativo = True
    produto.data_publicacao = datetime.utcnow()  # Reset da data de publicação

    # Commit no banco de dados
    db.commit()
    
    return {
        "message": "Produto renovado com sucesso",
        "nova_data_expiracao": produto.data_publicacao + timedelta(days=30),
        "taxa_descontada": float(taxa),
        "saldo_principal_restante": float(current_user.wallet.saldo_principal),
        "saldo_bonus_restante": float(current_user.wallet.bonus)
    }


@router.get("/destaques/")
def listar_produtos_destacados(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Lista produtos destacados combinando recentes, populares e mais interagidos.
    """
    produtos = get_produtos_destacados(db, limit)
    
    return {
        "total": len(produtos),
        "produtos": [
            {
                "id": p.id,
                "nome": p.nome,
                "descricao": p.descricao,
                "preco": float(p.preco),
                "categoria": p.categoria,
                "capa": p.capa,
                "slug": p.slug,
                "visualizacoes": p.visualizacoes,
                "likes": p.likes,
                "data_publicacao": p.data_publicacao.isoformat(),
                "vendedor": {
                    "id": p.usuario.id,
                    "nome": p.usuario.nome,
                    "username": p.usuario.username
                },
                "metricas": {
                    "tempo_publicado": calcular_tempo_publicacao(p.data_publicacao),
                    "popularidade": p.visualizacoes + p.likes
                }
            }
            for p in produtos
        ]
    }
