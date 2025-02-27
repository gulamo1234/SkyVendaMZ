from controlers.pesquisa import *
from schemas import *
from auth import *
from fastapi import APIRouter, Query
from sqlalchemy import or_, and_, func
from unidecode import unidecode
from typing import Optional
from decimal import Decimal

router = APIRouter(prefix="/pesquisa", tags=["rotas de pesquisa"])

@router.get("/produtos/")
def pesquisar_produtos(
    termo: str = Query(None),
    preco_min: float = Query(None, description="Preço mínimo"),
    preco_max: float = Query(None, description="Preço máximo"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Pesquisa produtos com termos mais flexíveis e filtro de preço.
    - Divide os termos de pesquisa
    - Remove acentos
    - Pesquisa parcial
    - Considera variações
    - Filtro por faixa de preço
    """
    # Query base
    query = db.query(Produto)
    
    # Filtro de visibilidade
    if user_id:
        query = query.filter(
            or_(
                Produto.CustomerID == user_id,
                and_(Produto.ativo == True, Produto.CustomerID != user_id)
            )
        )
    else:
        query = query.filter(Produto.ativo == True)

    # Filtro de preço
    if preco_min is not None:
        query = query.filter(Produto.preco >= func.cast(preco_min, Decimal))
    if preco_max is not None:
        query = query.filter(Produto.preco <= func.cast(preco_max, Decimal))

    # Pesquisa por termo se fornecido
    if termo:
        # Normaliza e divide os termos de pesquisa
        termos = [unidecode(t.lower().strip()) for t in termo.split() if t.strip()]
        
        # Aplica os filtros de pesquisa para cada termo
        for termo in termos:
            query = query.filter(
                or_(
                    # Pesquisa no nome do produto
                    func.unaccent(func.lower(Produto.nome)).contains(termo),
                    # Pesquisa na descrição
                    func.unaccent(func.lower(Produto.descricao)).contains(termo),
                    # Pesquisa na categoria
                    func.unaccent(func.lower(Produto.categoria)).contains(termo),
                    # Pesquisa nos detalhes
                    func.unaccent(func.lower(Produto.detalhes)).contains(termo)
                )
            )

        # Registra a pesquisa
        if user_id:
            nova_pesquisa = Pesquisa(
                termo_pesquisa=termo,
                usuario_id=user_id,
                data_pesquisa=datetime.utcnow()
            )
            db.add(nova_pesquisa)
            db.commit()

    # Paginação
    total = query.count()
    produtos = query.offset((page - 1) * limit).limit(limit).all()

    if not produtos and termo:
        # Tenta uma pesquisa mais flexível se não encontrou resultados
        query = db.query(Produto)
        
        # Mantém os filtros de visibilidade e preço
        if user_id:
            query = query.filter(
                or_(
                    Produto.CustomerID == user_id,
                    and_(Produto.ativo == True, Produto.CustomerID != user_id)
                )
            )
        else:
            query = query.filter(Produto.ativo == True)

        if preco_min is not None:
            query = query.filter(Produto.preco >= func.cast(preco_min, Decimal))
        if preco_max is not None:
            query = query.filter(Produto.preco <= func.cast(preco_max, Decimal))

        # Pesquisa mais flexível usando 'like' com cada termo
        for termo in termos:
            query = query.filter(
                or_(
                    func.unaccent(func.lower(Produto.nome)).like(f"%{termo}%"),
                    func.unaccent(func.lower(Produto.descricao)).like(f"%{termo}%"),
                    func.unaccent(func.lower(Produto.categoria)).like(f"%{termo}%"),
                    func.unaccent(func.lower(Produto.detalhes)).like(f"%{termo}%")
                )
            )
        
        total = query.count()
        produtos = query.offset((page - 1) * limit).limit(limit).all()

    # Formata a resposta
    return {
        "total": total,
        "page": page,
        "total_pages": (total + limit - 1) // limit,
        "filtros_aplicados": {
            "termo": termo if termo else None,
            "preco_min": preco_min,
            "preco_max": preco_max
        },
        "produtos": [
            {
                "id": p.id,
                "nome": p.nome,
                "descricao": p.descricao,
                "preco": float(p.preco),
                "categoria": p.categoria,
                "capa": p.capa,
                "slug": p.slug,
                "ativo": p.ativo,
                "visualizacoes": p.visualizacoes,
                "likes": p.likes,
                "data_publicacao": p.data_publicacao.isoformat(),
                "usuario": {
                    "id": p.usuario.id,
                    "nome": p.usuario.nome,
                    "username": p.usuario.username
                }
            }
            for p in produtos
        ]
    }


@router.get("/categorias/peso/")
def calcular_peso_categorias_route(db: Session = Depends(get_db), top_n: int = 5):
    """
    Rota para calcular o peso (frequência de pesquisa) das categorias mais pesquisadas.
    
    Args:
        db (Session): Sessão do banco de dados.
        top_n (int): Número de categorias mais pesquisadas a serem consideradas (padrão: 5).
    
    Returns:
        Lista de categorias e seus pesos (número de pesquisas).
    """
    return calcular_peso_categorias_mais_pesquisadas(db=db, top_n=top_n)



#ROTAS DE DELITE
@router.delete("/{pesquisa_id}/")
def eliminar_pesquisa_route(pesquisa_id: int, db: Session = Depends(get_db)):
    """
    Rota para eliminar uma pesquisa específica pelo seu ID.
    
    Args:
        pesquisa_id (int): ID da pesquisa a ser eliminada.
    
    Returns:
        Mensagem de sucesso.
    """
    return eliminar_pesquisa(db=db, pesquisa_id=pesquisa_id)


@router.get("/lista")
def listar_pesquisas_route(page: int = 1, limit: int = 10, usuario_id: int = None, db: Session = Depends(get_db)):
    """
    Rota para listar todas as pesquisas realizadas, com opção de filtrar por usuário.
    
    Args:
        page (int): Página de resultados.
        limit (int): Limite de resultados por página.
        usuario_id (int, opcional): ID do usuário para filtrar as pesquisas.
    
    Returns:
        Lista de pesquisas.
    """
    return listar_pesquisas(db=db, usuario_id=usuario_id, page=page, limit=limit)


