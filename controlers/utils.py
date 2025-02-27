from models import Log,Produto,Usuario
from sqlalchemy.orm import Session
from datetime import datetime
import random
from models import Produto, Usuario  # Importe seus modelos corretamente
from decimal import Decimal
from database import SessionLocal





def registrar_acao_com_categoria(
    db: Session,
    usuario_id: int,
    tipo_acao: str,
    produto_id: int,
    entidade: str,
    detalhes: dict
):
    """
    Registra a ação de um usuário, associando à categoria do produto.
    """
    
    # Recupera a categoria do produto
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise ValueError("Produto não encontrado ao registrar ação.")
    
    # Adiciona a categoria nos detalhes
    detalhes["categoria"] = produto.categoria

    # Registra o log
    log = Log(
        usuario_id=usuario_id,
        tipo_acao=tipo_acao,
        entidade=entidade,
        detalhes=detalhes,
        data_hora=datetime.utcnow(),
    )
    db.add(log)
    db.commit()
    return log


def formatar_contagem(numero: int) -> str:
    """
    Formata um número para um formato mais amigável, como '1 mil', '2 mil' etc.
    :param numero: O número a ser formatado.
    :return: Uma string representando o número formatado.
    """
    if numero >= 1_000_000:
        return f"{numero // 1_000_000}M"  # Milhões
    elif numero >= 1_000:
        return f"{numero // 1_000} mil"  # Milhares
    else:
        return str(numero)  # Números menores que mil são retornados como estão



def gerar_identificador_unico(db: Session):
    """
    Gera um identificador único no formato "sk-123456789".
    Verifica se já existe no banco antes de retornar.
    """
    while True:
        identificador = f"sk-{random.randint(100000000, 999999999)}"
        if not db.query(Usuario).filter(Usuario.identificador_unico == identificador).first():
            return identificador



def renovar_produtos_automaticamente(db: Session):
    """
    Renova produtos automaticamente para usuários com renovação ativa e saldo suficiente.
    """
    produtos = (
        db.query(Produto)
        .filter(
            Produto.renovacao_automatica == True,  # Apenas produtos com renovação automática ativa
            Produto.data_expiracao <= datetime.utcnow(),  # Produtos expirados
        )
        .all()
    )

    for produto in produtos:
        usuario = db.query(Usuario).filter(Usuario.id == produto.usuario_id).first()
        if not usuario:
            continue

        # Calcular taxa de renovação com base no preço do produto
        taxa = calcular_taxa_publicacao(Decimal(produto.preco))  # Função que você já deve ter

        if usuario.saldo_principal >= taxa:
            # Descontar do saldo principal
            usuario.saldo_principal -= taxa
            produto.data_expiracao = datetime.utcnow() + timedelta(days=30)
        elif usuario.bonus >= taxa:
            # Descontar do saldo bônus
            usuario.bonus -= taxa
            produto.data_expiracao = datetime.utcnow() + timedelta(days=30)
        else:
            # Se não houver saldo, não renovar
            continue

        db.add(produto)
        db.add(usuario)

    db.commit()

