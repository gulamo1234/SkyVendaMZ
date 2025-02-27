from sqlalchemy.orm import Session
from controlers.produto import *
from controlers.utils import formatar_contagem
from sqlalchemy import or_
from datetime import datetime
from fastapi import APIRouter,Form,File,Query
from models import Produto,Pesquisa,Usuario,Comentario,produto_likes
from sqlalchemy import func
from fastapi import HTTPException
from auth import *
from fuzzywuzzy import fuzz
from fuzzywuzzy import process



def salvar_pesquisa(termo: str, categoria: str, db: Session, usuario_id: int = None):
    """
    Função para salvar a pesquisa do usuário no banco de dados.
    
    Args:
        termo (str): O termo pesquisado.
        categoria (str): A categoria relacionada ao termo.
        db (Session): Sessão do banco de dados.
        usuario_id (int, opcional): O ID do usuário, se estiver logado.
    """
    pesquisa = Pesquisa(
        termo_pesquisa=termo,
        categoria_pesquisa=categoria,
        data_pesquisa=datetime.utcnow(),
        usuario_id=usuario_id  # Se o usuário não estiver logado, o ID será None
    )
    db.add(pesquisa)
    db.commit()
    db.refresh(pesquisa)

def executar_pesquisa_avancada(
    termo: str,
    db: Session,
    user_id: Optional[int] = None,
    limit: int = 10,
    offset: int = 1,
):
    """
    Pesquisa avançada por produtos com suporte a frases e fuzzy matching.
    """
    termos = [palavra.strip() for palavra in termo.split() if palavra.strip()]

    # Query base com filtro de produtos ativos
    query = db.query(Produto).filter(Produto.ativo.is_(True))

    # Aplicar filtros exatos, suportando múltiplas palavras (frases)
    if termos:
        query = query.filter(
            and_(
                or_(
                    Produto.nome.ilike(f"%{termo}%"),
                    Produto.descricao.ilike(f"%{termo}%"),
                    Produto.categoria.ilike(f"%{termo}%"),
                    Produto.tipo.ilike(f"%{termo}%"),
                    Produto.provincia.ilike(f"%{termo}%"),
                    Produto.distrito.ilike(f"%{termo}%"),
                    Produto.detalhes.ilike(f"%{termo}%"),
                    
                )
                for termo in termos
            )
        )

    # Aplicar paginação
    if offset < 1:
        offset = 1

    produtos = query.offset((offset - 1) * limit).limit(limit).all()

    # Se não encontrar resultados, aplicar fuzzy matching
    if not produtos:
        produtos = aplicar_fuzzy_matching(" ".join(termos), db, limit, offset)

    # Processar os produtos encontrados
    return [
        {
            "id": produto.id,
            "title": produto.nome,
            "thumb": produto.capa,
            "images": produto.fotos,
            "slug":produto.slug,
            "price": float(produto.preco),
            "description": produto.descricao,
            "category": produto.categoria,
            "state": produto.estado,
            "views": formatar_contagem(produto.visualizacoes),
            "negociavel": produto.negociavel,
            "province": produto.provincia,
            "district": produto.distrito,
            "user": {
                "id": produto.usuario.id,
                "name": produto.usuario.nome,
                "username":produto.usuario.username,
                "nome_pagina":produto.usuario.nome_pagina,
                "avatar": produto.usuario.foto_perfil,
                "average_stars": calcular_media_estrelas(produto.usuario.id, db),
            },
            "liked": user_id in [user.id for user in produto.usuarios_que_deram_like] if user_id else None,

        }
        for produto in produtos
    ]


def aplicar_fuzzy_matching(termo: str, db: Session, limit: int, offset: int):
    """
    Aplica fuzzy matching para encontrar produtos com frases semelhantes.
    """
    threshold = 85  # Limiar mínimo de similaridade
    produtos = db.query(Produto).filter(Produto.ativo.is_(True)).all()

    # Comparar o termo completo com nomes, descrições e categorias dos produtos
    resultados = []
    for produto in produtos:
        score_nome = fuzz.partial_ratio(termo.lower(), produto.nome.lower())
        score_descricao = fuzz.partial_ratio(termo.lower(), produto.descricao.lower())
        score_categoria = fuzz.partial_ratio(termo.lower(), produto.categoria.lower())

        # Verificar se algum campo atinge o limiar
        if max(score_nome, score_descricao, score_categoria) >= threshold:
            resultados.append((produto, max(score_nome, score_descricao, score_categoria)))

    # Ordenar pelos scores mais altos e aplicar paginação
    resultados = sorted(resultados, key=lambda x: x[1], reverse=True)
    resultados_paginados = resultados[(offset - 1) * limit : offset * limit]

    # Retornar apenas os produtos
    return [resultado[0] for resultado in resultados_paginados]
def calcular_media_estrelas(usuario_id: int, db: Session):
    """
    Calcula a média de estrelas de um usuário baseado nas avaliações.
    """
    avaliacoes = db.query(Avaliacao).filter(Avaliacao.avaliado_id == usuario_id).all()
    if not avaliacoes:
        return None  # Sem avaliações
    soma_estrelas = sum(avaliacao.estrelas for avaliacao in avaliacoes)
    return round(soma_estrelas / len(avaliacoes), 2)
    
def eliminar_pesquisa(db: Session, pesquisa_id: int = None, usuario_id: int = None):
    """
    Elimina uma pesquisa específica ou todas as pesquisas de um usuário.
    
    Args:
        db (Session): Sessão do banco de dados.
        pesquisa_id (int, opcional): ID da pesquisa a ser eliminada.
        usuario_id (int, opcional): ID do usuário cujas pesquisas devem ser eliminadas.
    
    Raises:
        HTTPException: Se a pesquisa ou usuário não forem encontrados.
    
    Returns:
        Mensagem de sucesso.
    """
    if pesquisa_id:
        # Deletar uma pesquisa específica
        pesquisa = db.query(Pesquisa).filter(Pesquisa.id == pesquisa_id).first()
        if not pesquisa:
            raise HTTPException(status_code=404, detail="Pesquisa não encontrada.")
        db.delete(pesquisa)
    elif usuario_id:
        # Deletar todas as pesquisas de um usuário
        pesquisas = db.query(Pesquisa).filter(Pesquisa.usuario_id == usuario_id).all()
        if not pesquisas:
            raise HTTPException(status_code=404, detail="Nenhuma pesquisa encontrada para esse usuário.")
        for pesquisa in pesquisas:
            db.delete(pesquisa)
    else:
        raise HTTPException(status_code=400, detail="ID da pesquisa ou do usuário deve ser fornecido.")
    
    db.commit()
    return {"msg": "Pesquisa(s) eliminada(s) com sucesso."}




def listar_pesquisas(db: Session, usuario_id: int = None, page: int = 1, limit: int = 10):
    """
    Lista todas as pesquisas realizadas, com a possibilidade de filtrar por usuário específico.
    
    Args:
        db (Session): Sessão do banco de dados.
        usuario_id (int, opcional): ID do usuário para filtrar as pesquisas (ou None para listar todas).
        page (int): Página de resultados (padrão: 1).
        limit (int): Limite de resultados por página (padrão: 10).
    
    Returns:
        Lista de pesquisas.
    """
    query = db.query(Pesquisa)
    
    # Se um usuário for especificado, filtra as pesquisas desse usuário
    if usuario_id:
        query = query.filter(Pesquisa.usuario_id == usuario_id)
    
    # Paginação
    pesquisas = query.offset((page - 1) * limit).limit(limit).all()
    
    return pesquisas


def calcular_peso_categorias_mais_pesquisadas(db: Session, top_n: int = 5):
    """
    Calcula o peso (frequência de pesquisa) das categorias mais pesquisadas.
    
    Args:
        db (Session): Sessão do banco de dados.
        top_n (int): Número de categorias mais pesquisadas a serem consideradas (padrão: 5).
    
    Returns:
        Lista de dicionários com categorias e seus pesos (quantidade de pesquisas).
    """
    # Seleciona as categorias mais pesquisadas e conta o número de vezes que foram pesquisadas
    categorias_mais_pesquisadas = db.query(
        Pesquisa.categoria_pesquisa,
        func.count(Pesquisa.categoria_pesquisa).label('total_pesquisas')
    ).group_by(Pesquisa.categoria_pesquisa).order_by(func.count(Pesquisa.categoria_pesquisa).desc()).limit(top_n).all()

    resultados = []
    
    # Cria a lista de resultados com categoria e peso (total de pesquisas)
    for categoria, total_pesquisas in categorias_mais_pesquisadas:
        resultados.append({
            "categoria": categoria,
            "peso": total_pesquisas  # Peso é o número de pesquisas realizadas para essa categoria
        })
    
    return resultados
