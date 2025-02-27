from decimal import Decimal

def calcular_taxa_publicacao(valor_produto: Decimal) -> Decimal:
    """
    Calcula a taxa para publicação de um produto com base no valor do produto.
    """
    if valor_produto <= 100:
        return Decimal("3.0")
    elif 100 < valor_produto <= 200:
        return Decimal("8.0")
    elif 200 < valor_produto <= 500:
        return Decimal("10.0")
    else:
        return Decimal("22.0")  # Taxa fixa para valores acima de 500

def calcular_taxa_envio_dinheiro(valor_transferencia: float) -> float:
    """
    Calcula a taxa para envio de dinheiro com base no valor da transferência.
    """
    if valor_transferencia <= 100:
        return 2.0
    elif 100 < valor_transferencia <= 200:
        return 5.0
    elif 200 < valor_transferencia <= 500:
        return 10.0
    elif 500 < valor_transferencia <= 1000:
        return 20.0
    elif 1000 < valor_transferencia <= 5000:
        return 50.0
    elif 5000 < valor_transferencia <= 10000:
        return 100.0
    elif 10000 < valor_transferencia <= 50000:
        return 250.0
    elif 50000 < valor_transferencia <= 100000:
        return 500.0
    elif 100000 < valor_transferencia <= 1000000:
        return 1500.0
    elif 1000000 < valor_transferencia <= 10000000:
        return 3000.0
    else:
        return 5000.0  # Taxa fixa para valores acima de 10 milhões


def calcular_taxa_postar_status() -> float:
    """
    Retorna a taxa fixa para postar status.
    """
    return 9.0  # Taxa fixa para postar status


def calcular_custo_anuncio(tipo: str, dias: int) -> Decimal:
    """
    Calcula o custo de um anúncio baseado no tipo de anúncio e no número de dias.

    Tipos de anúncio e seus custos:
    - "ofertas_diarias": 8 MT por dia
    - "melhores_boladas": 12 MT por dia
    - "para_si": 6 MT por dia
    - "em_promocao": 10 MT por dia

    Args:
        tipo_anuncio (str): Tipo do anúncio.
        dias (int): Número de dias que o anúncio ficará ativo.

    Returns:
        Decimal: Custo total do anúncio.
    """
    # Dicionário com os preços por tipo de anúncio
    precos_por_tipo = {
        "ofertas_diarias": Decimal("20"),
        "melhores_boladas": Decimal("50"),
        "para_si": Decimal("25"),
        "top": Decimal("30"),
    }

    # Verifica se o tipo de anúncio é válido
    if tipo not in precos_por_tipo:
        raise ValueError(f"Tipo de anúncio inválido: {tipo}")

    # Calcula o custo total
    preco_por_dia = precos_por_tipo[tipo]
    custo_total = preco_por_dia * Decimal(dias)

    return custo_total
