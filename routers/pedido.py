from controlers.pedido import *
from schemas import *
from auth import *
from fastapi import APIRouter,Form,Query

router=APIRouter(prefix="/pedidos",tags=["rotas de pedido"])


@router.get("/{user_id}/verificar_saldo/")
def verificar_saldo(user_id: int, db: Session = Depends(get_db)):
    try:
        return verificar_integridade_saldo(db, user_id)  # Ordem correta dos parâmetros
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{pedido_id}/aceitar/")
def aceitar_pedido_route(pedido_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    return aceitar_pedido(db, pedido_id, current_user.id)




@router.put("/{pedido_id}/confirmar-recebimento")
def confirmar_recebimento(
    pedido_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Confirma o recebimento do pedido pelo cliente e libera os saldos.
    """
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
        
    if pedido.customer_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Você não tem permissão para confirmar o recebimento deste pedido."
        )
        
    if pedido.status != "aguardando_confirmacao":
        raise HTTPException(
            status_code=400,
            detail="Este pedido não está aguardando confirmação de recebimento."
        )
        
    try:
        # Buscar as carteiras do vendedor e comprador
        wallet_vendedor = db.query(Wallet).filter(
            Wallet.usuario_id == pedido.produto.CustomerID
        ).first()
        
        wallet_comprador = db.query(Wallet).filter(
            Wallet.usuario_id == pedido.customer_id
        ).first()
        
        if pedido.tipo == "skywallet":
            # Liberar saldo congelado para o vendedor
            if wallet_vendedor and wallet_vendedor.saldo_congelado >= pedido.preco_total:
                wallet_vendedor.saldo_congelado -= pedido.preco_total
                wallet_vendedor.saldo_principal += pedido.preco_total
                
            # Remover saldo congelado do comprador
            if wallet_comprador and wallet_comprador.saldo_congelado >= pedido.preco_total:
                wallet_comprador.saldo_congelado -= pedido.preco_total
        
        pedido.status = "concluido"
        pedido.data_confirmacao_recebimento = datetime.utcnow()
        
        db.commit()
        
        return {
            "id": pedido.id,
            "status": pedido.status,
            "data_confirmacao": pedido.data_confirmacao_recebimento,
            "mensagem": "Recebimento confirmado e saldos liberados com sucesso."
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao confirmar recebimento: {str(e)}"
        )




@router.post("/{pedido_id}/confirmar-pagamento/")
def confirmar_pagamento_route(pedido_id: int, CustomerID: int, db: Session = Depends(get_db)):
    return confirmar_pagamento_vendedor(db, pedido_id, CustomerID)


@router.put("/{pedido_id}/cancelar")
def cancelar_pedido_route(
    pedido_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Rota para cancelar um pedido baseado no ID do pedido e do usuário autenticado.
    """
    try:
        resultado = cancelar_pedido(db, pedido_id, current_user.id)
        return resultado
    except HTTPException as e:
        raise e

@router.put("/{pedido_id}/recusar")  # Corrigido o caminho da rota
def recusar_pedido_pelo_vendedor(
    pedido_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Recusa um pedido e libera os saldos congelados.
    """
    try:
        pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado.")

        produto = db.query(Produto).filter(Produto.id == pedido.produto_id).first()
        if not produto or produto.CustomerID != current_user.id:
            raise HTTPException(status_code=403, detail="Você não tem permissão para recusar este pedido.")

        if pedido.status != "pendente":
            raise HTTPException(status_code=400, detail="Apenas pedidos pendentes podem ser recusados.")

        # Normaliza o tipo do pedido para minúsculas
        tipo_pedido = pedido.tipo.lower() if pedido.tipo else None

        if tipo_pedido == "skywallet":
            # Liberar saldo congelado do comprador
            wallet_comprador = db.query(Wallet).filter(Wallet.usuario_id == pedido.customer_id).first()
            if not wallet_comprador:
                raise HTTPException(status_code=404, detail="Carteira do comprador não encontrada.")
            
            if wallet_comprador.saldo_congelado < pedido.preco_total:
                raise HTTPException(status_code=400, detail="Erro: Saldo congelado do comprador inconsistente.")
            
            # Devolve o saldo para o comprador
            wallet_comprador.saldo_congelado -= pedido.preco_total
            wallet_comprador.saldo_principal += pedido.preco_total

            # Liberar saldo congelado do vendedor
            wallet_vendedor = db.query(Wallet).filter(Wallet.usuario_id == produto.CustomerID).first()
            if not wallet_vendedor:
                raise HTTPException(status_code=404, detail="Carteira do vendedor não encontrada.")
            
            if wallet_vendedor.saldo_congelado < pedido.preco_total:
                raise HTTPException(status_code=400, detail="Erro: Saldo congelado do vendedor inconsistente.")
            
            # Remove o saldo congelado do vendedor
            wallet_vendedor.saldo_congelado -= pedido.preco_total

            logger.info(f"Saldo liberado: Pedido {pedido_id}, Comprador ID {pedido.customer_id}, Vendedor ID {produto.CustomerID}, Valor {pedido.preco_total}")

        pedido.status = "recusado"
        
        # Tenta enviar notificação para o comprador
        try:
            mensagem = f"Seu pedido #{pedido.id} foi recusado pelo vendedor."
            enviar_notificacao(db, pedido.customer_id, mensagem)
        except Exception as e:
            logger.error(f"Erro ao enviar notificação: {str(e)}")

        db.commit()

        return {
            "id": pedido.id,
            "status": pedido.status,
            "mensagem": "Pedido recusado com sucesso pelo vendedor e saldo liberado."
        }
        
    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao recusar pedido {pedido_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao recusar pedido: {str(e)}")


@router.delete("/item_pedidos/{item_pedido_id}")
def delete_item_pedido(item_pedido_id: int, db: Session = Depends(get_db)):
    db_item_pedido = delete_item_pedido(db=db, item_pedido_id=item_pedido_id)
    if db_item_pedido is None:
        raise HTTPException(status_code=404, detail="ItemPedido not found")
    return db_item_pedido



# Rota para listar todos os pedidos feitos pelo usuário autenticado
@router.get("/feitos", response_model=List[dict])
def get_pedidos_feitos(
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    pedidos_feitos = db.query(Pedido).filter(Pedido.customer_id == current_user.id).all()

    if not pedidos_feitos:
        raise HTTPException(status_code=404, detail="Nenhum pedido feito encontrado.")

    return [
        {
            "id": pedido.id,
            "customer_id": pedido.customer_id,
            "produto_id": pedido.produto_id,
            "quantidade": pedido.quantidade,
            "preco_total": float(pedido.preco_total) if pedido.preco_total else None,
            "data_pedido": pedido.data_pedido.isoformat() if pedido.data_pedido else None,
            "status": pedido.status,
            "aceito_pelo_vendedor": pedido.aceito_pelo_vendedor,
            "tipo": pedido.tipo,
            "recebido_pelo_cliente": pedido.recebido_pelo_cliente,
            "data_aceite": pedido.data_aceite.isoformat() if pedido.data_aceite else None,
            "data_envio": pedido.data_envio.isoformat() if pedido.data_envio else None,
            "data_entrega": pedido.data_entrega.isoformat() if pedido.data_entrega else None,
        }
        for pedido in pedidos_feitos
    ]




# Rota para listar os pedidos recebidos pelo usuário autenticado
@router.get("/recebidos", response_model=List[dict])
def get_pedidos_recebidos(
    db: Session = Depends(get_db), 
    current_user:Usuario = Depends(get_current_user)
):
    pedidos_recebidos = (
        db.query(Pedido)
        .join(Pedido.produto)  # Relacionamento com Produto
        .filter(Pedido.produto.has(vendedor_id=current_user.id))  # Verifica se o produto pertence ao vendedor atual
        .all()
    )

    if not pedidos_recebidos:
        raise HTTPException(status_code=404, detail="Nenhum pedido recebido encontrado.")

    return [
        {
            "id": pedido.id,
            "customer_id": pedido.customer_id,
            "produto_id": pedido.produto_id,
            "quantidade": pedido.quantidade,
            "preco_total": float(pedido.preco_total) if pedido.preco_total else None,
            "data_pedido": pedido.data_pedido.isoformat() if pedido.data_pedido else None,
            "status": pedido.status,
            "aceito_pelo_vendedor": pedido.aceito_pelo_vendedor,
            "tipo": pedido.tipo,
            "recebido_pelo_cliente": pedido.recebido_pelo_cliente,
            "data_aceite": pedido.data_aceite.isoformat() if pedido.data_aceite else None,
            "data_envio": pedido.data_envio.isoformat() if pedido.data_envio else None,
            "data_entrega": pedido.data_entrega.isoformat() if pedido.data_entrega else None,
        }
        for pedido in pedidos_recebidos
    ]


@router.get("/", response_model=List[dict])
def listar_pedidos(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
):
    """
    Lista pedidos feitos pelo usuário e pedidos recebidos (como vendedor),
    excluindo aqueles com status 'Eliminado' ou com 'status_visivel_comprador' ou 
    'status_visivel_vendedor' marcado como True.
    """
    # Filtro para excluir pedidos eliminados
    pedidos_feitos = (
        db.query(Pedido)
        .filter(
            Pedido.customer_id == current_user.id,
            Pedido.status != "eliminado",  # Excluindo pedidos eliminados
            Pedido.status_visivel_comprador == False  # Pedido não eliminado para o comprador
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Filtro para pedidos recebidos (como vendedor)
    pedidos_recebidos = (
        db.query(Pedido)
        .join(Produto, Produto.id == Pedido.produto_id)
        .filter(
            Produto.CustomerID == current_user.id,  # Produto vinculado ao vendedor
            Pedido.status != "eliminado",  # Excluindo pedidos eliminados
            Pedido.status_visivel_vendedor == False  # Pedido não eliminado para o vendedor
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    def obter_dados_produto_e_usuario(pedido):
        produto = db.query(Produto).filter(Produto.id == pedido.produto_id).first()
        vendedor = db.query(Usuario).filter(Usuario.id == produto.CustomerID).first()
        comprador = db.query(Usuario).filter(Usuario.id == pedido.customer_id).first()
        return {
            "foto_capa": produto.capa if produto else None,
            "nome_vendedor": vendedor.nome if vendedor else None,
            "nome_comprador": comprador.nome if comprador else None,
            "nome": produto.nome if produto else None,
            "id_comprador": comprador.identificador_unico if comprador else None,
            "id_vendedor": vendedor.identificador_unico if vendedor else None,
        }

    # Combina os resultados e inclui o tipo de pedido ("compra" ou "venda")
    todos_pedidos = [
        {
            "id": pedido.id,
            "customer_id": pedido.customer_id,
            "produto_id": pedido.produto_id,
            "quantidade": pedido.quantidade,
            "preco_total": float(pedido.preco_total) if pedido.preco_total else None,
            "data_pedido": pedido.data_pedido.isoformat() if pedido.data_pedido else None,
            "status": pedido.status,
            "tipo": pedido.tipo,
            "aceito_pelo_vendedor": pedido.aceito_pelo_vendedor,
            "compra": "compra",  # Pedido feito pelo usuário
            "recebido_pelo_cliente": pedido.recebido_pelo_cliente,
            "data_aceite": pedido.data_aceite.isoformat() if pedido.data_aceite else None,
            "data_envio": pedido.data_envio.isoformat() if pedido.data_envio else None,
            "data_entrega": pedido.data_entrega.isoformat() if pedido.data_entrega else None,
            **obter_dados_produto_e_usuario(pedido),
        }
        for pedido in pedidos_feitos
    ] + [
        {
            "id": pedido.id,
            "customer_id": pedido.customer_id,
            "produto_id": pedido.produto_id,
            "quantidade": pedido.quantidade,
            "preco_total": float(pedido.preco_total) if pedido.preco_total else None,
            "data_pedido": pedido.data_pedido.isoformat() if pedido.data_pedido else None,
            "status": pedido.status,
            "tipo": pedido.tipo,
            "aceito_pelo_vendedor": pedido.aceito_pelo_vendedor,
            "venda": "venda",  # Pedido recebido pelo usuário
            "recebido_pelo_cliente": pedido.recebido_pelo_cliente,
            "data_aceite": pedido.data_aceite.isoformat() if pedido.data_aceite else None,
            "data_envio": pedido.data_envio.isoformat() if pedido.data_envio else None,
            "data_entrega": pedido.data_entrega.isoformat() if pedido.data_entrega else None,
            **obter_dados_produto_e_usuario(pedido),
        }
        for pedido in pedidos_recebidos
    ]

    if not todos_pedidos:
        raise HTTPException(status_code=404, detail="Nenhum pedido encontrado.")

    return todos_pedidos

@router.put("/{pedido_id}/eliminar")
def eliminar_pedido(
    pedido_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Rota para eliminar um pedido, tanto pelo vendedor quanto pelo comprador.
    O status global do pedido será alterado para 'Eliminado' quando ambas as partes o eliminarem.
    Só funciona para pedidos 'Cancelados' ou 'Concluídos'.
    """
    # Buscar o pedido no banco de dados
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()

    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")

    # Verificar se o status do pedido permite exclusão
    if pedido.status not in ["cancelado", "concluido","recusado"]:
        raise HTTPException(
            status_code=400,
            detail="Apenas pedidos com status 'Cancelado' ou 'Concluído' podem ser eliminados.",
        )

    # Verificar se o usuário é o comprador ou o vendedor
    produto = db.query(Produto).filter(Produto.id == pedido.produto_id).first()

    if not produto:
        raise HTTPException(status_code=404, detail="Produto associado ao pedido não encontrado.")

    is_comprador = pedido.customer_id == current_user.id
    is_vendedor = produto.CustomerID == current_user.id

    if not is_comprador and not is_vendedor:
        raise HTTPException(
            status_code=403, detail="Você não tem permissão para eliminar este pedido."
        )

    # Marcar como eliminado para o comprador ou vendedor
    if is_comprador:
        pedido.recebido_pelo_cliente = True  # Marcando como eliminado pelo cliente
        mensagem = "Pedido eliminado para o comprador."
        # Atualiza status visível para o comprador
        pedido.status_visivel_comprador = True  # Coloca como True (eliminado para o comprador)
    if is_vendedor:
        pedido.aceito_pelo_vendedor = True  # Marcando como eliminado pelo vendedor
        mensagem = "Pedido eliminado para o vendedor."
        # Atualiza status visível para o vendedor
        pedido.status_visivel_vendedor = True  # Coloca como True (eliminado para o vendedor)

    # Alterar status para 'Eliminado' se ambos já eliminaram
    if pedido.recebido_pelo_cliente and pedido.aceito_pelo_vendedor:
        pedido.status = "eliminado"

    # Commit das mudanças
    db.commit()

    # Retornar a resposta
    return {
        "id": pedido.id,
        "status": pedido.status,
        "mensagem": mensagem,
        "status_visivel_comprador": pedido.status_visivel_comprador,
        "status_visivel_vendedor": pedido.status_visivel_vendedor,
    }


@router.get("/eliminados", response_model=List[dict])
def listar_pedidos_eliminados(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
):
    """
    Lista pedidos eliminados feitos pelo usuário (como comprador) e recebidos (como vendedor).
    """
    # Busca pedidos eliminados feitos pelo usuário (como comprador)
    pedidos_feitos_eliminados = (
        db.query(Pedido)
        .filter(
            Pedido.customer_id == current_user.id,
            Pedido.status == "eliminado",  # Apenas pedidos eliminados
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Busca pedidos eliminados recebidos pelo usuário (como vendedor)
    pedidos_recebidos_eliminados = (
        db.query(Pedido)
        .join(Produto, Produto.id == Pedido.produto_id)
        .filter(
            Produto.CustomerID == current_user.id,  # Produto vinculado ao vendedor
            Pedido.status == "eliminado",  # Apenas pedidos eliminados
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    def obter_dados_produto_e_usuario(pedido):
        produto = db.query(Produto).filter(Produto.id == pedido.produto_id).first()
        vendedor = db.query(Usuario).filter(Usuario.id == produto.CustomerID).first()
        comprador = db.query(Usuario).filter(Usuario.id == pedido.customer_id).first()
        return {
            "foto_capa": produto.capa if produto else None,
            "nome_vendedor": vendedor.nome if vendedor else None,
            "nome_comprador": comprador.nome if comprador else None,
            "nome": produto.nome if produto else None,
            "id_comprador": comprador.identificador_unico if comprador else None,
            "id_vendedor": vendedor.identificador_unico if vendedor else None,
        }

    # Combina os resultados e inclui o tipo de pedido ("compra" ou "venda")
    todos_pedidos_eliminados = [
        {
            "id": pedido.id,
            "customer_id": pedido.customer_id,
            "produto_id": pedido.produto_id,
            "quantidade": pedido.quantidade,
            "preco_total": float(pedido.preco_total) if pedido.preco_total else None,
            "data_pedido": pedido.data_pedido.isoformat() if pedido.data_pedido else None,
            "status": pedido.status,
            "aceito_pelo_vendedor": pedido.aceito_pelo_vendedor,
            "compra": "compra",  # Pedido feito pelo usuário
            "recebido_pelo_cliente": pedido.recebido_pelo_cliente,
            "data_aceite": pedido.data_aceite.isoformat() if pedido.data_aceite else None,
            "data_envio": pedido.data_envio.isoformat() if pedido.data_envio else None,
            "data_entrega": pedido.data_entrega.isoformat() if pedido.data_entrega else None,
            **obter_dados_produto_e_usuario(pedido),
        }
        for pedido in pedidos_feitos_eliminados
    ] + [
        {
            "id": pedido.id,
            "customer_id": pedido.customer_id,
            "produto_id": pedido.produto_id,
            "quantidade": pedido.quantidade,
            "preco_total": float(pedido.preco_total) if pedido.preco_total else None,
            "data_pedido": pedido.data_pedido.isoformat() if pedido.data_pedido else None,
            "status": pedido.status,
            "aceito_pelo_vendedor": pedido.aceito_pelo_vendedor,
            "venda": "venda",  # Pedido recebido pelo usuário
            "recebido_pelo_cliente": pedido.recebido_pelo_cliente,
            "data_aceite": pedido.data_aceite.isoformat() if pedido.data_aceite else None,
            "data_envio": pedido.data_envio.isoformat() if pedido.data_envio else None,
            "data_entrega": pedido.data_entrega.isoformat() if pedido.data_entrega else None,
            **obter_dados_produto_e_usuario(pedido),
        }
        for pedido in pedidos_recebidos_eliminados
    ]

    if not todos_pedidos_eliminados:
        raise HTTPException(status_code=404, detail="Nenhum pedido eliminado encontrado.")

    return todos_pedidos_eliminados



@router.put("/pedido/{pedido_id}")
def update_pedido(pedido_id: int, pedido: PedidoUpdate, db: Session = Depends(get_db)):
    db_pedido = update_pedido(db=db, pedido_id=pedido_id, pedido=pedido)
    if db_pedido is None:
        raise HTTPException(status_code=404, detail="Pedido not found")
    return db_pedido

# Rota para pegar os pedidos recebidos por um usuário específico
@router.get("/recebido/{user_id}")
def pedidos_recebidos(user_id: int, db: Session = Depends(get_db)):
    return get_pedidos_recebidos(db, user_id)

# Rota para pegar os pedidos feitos por um usuário específico
@router.get("/feito/{user_id}")
def pedidos_feitos(user_id: int, db: Session = Depends(get_db)):
    return get_pedidos_feitos(db, user_id)

@router.get("/{pedido_id}")
def read_pedido(pedido_id: int, db: Session = Depends(get_db)):
    db_pedido = get_pedido(db=db, pedido_id=pedido_id)
    if db_pedido is None:
        raise HTTPException(status_code=404, detail="Pedido not found")
    return db_pedido

@router.post("/pedidos/criar/")
def criar_pedido(
    produto_id: int=Form(...),
    quantidade: int=Form(...),
    tipo: Optional[str] = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Rota para criar um pedido.

    Args:
    - produto_id (int): ID do produto.
    - quantidade (int): Quantidade desejada.
    - tipo (str): Tipo do pedido ("normal" ou "fora do sistema").
    - db: Sessão do banco de dados.
    - current_user: Usuário autenticado.

    Returns:
    - Pedido criado.
    """
    # Cria o objeto PedidoCreate
    pedido_data = PedidoCreate(
        produto_id=produto_id,
        quantidade=quantidade,
        customer_id=current_user.id,
        tipo=tipo
    )

    # Chama a função de criação do pedido
    return create_pedido_db(pedido=pedido_data, db=db)

# Rota para confirmar um pedido
@router.post("/{pedido_id}/confirmar/")
def confirmar_pedid(
    pedido_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    return aceitar_pedido(pedido_id=pedido_id, db=db, vendedor_id=current_user.id)




@router.put("/{pedido_id}/entrega")
def confirmar_entrega(
    pedido_id: int, 
    current_user: Usuario = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Confirma a entrega de um pedido pelo vendedor.
    
    Args:
        pedido_id: ID do pedido a ser confirmado
        current_user: Usuário autenticado (vendedor)
        db: Sessão do banco de dados
    
    Returns:
        dict: Detalhes do pedido atualizado
    """
    # Buscar o pedido com join em Produto para ter acesso ao CustomerID
    pedido = (
        db.query(Pedido)
        .join(Produto, Pedido.produto_id == Produto.id)
        .filter(Pedido.id == pedido_id)
        .first()
    )

    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")

    # Verificar se o usuário autenticado é o vendedor do produto
    if pedido.produto.CustomerID != current_user.id:
        raise HTTPException(
            status_code=403, 
            detail="Você não tem permissão para confirmar a entrega deste pedido."
        )

    # Verificar se o pedido está em um status válido para confirmação
    if pedido.status != "aceite":
        raise HTTPException(
            status_code=400, 
            detail=f"Não é possível confirmar a entrega de um pedido com status '{pedido.status}'"
        )

    try:
        # Atualizar o status do pedido e registrar a confirmação
        pedido.status = "aguardando_confirmacao"
        pedido.data_entrega = datetime.utcnow()
        pedido.data_entrega = datetime.utcnow()

        db.commit()
        db.refresh(pedido)

        return {
            "id": pedido.id,
            "status": pedido.status,
            "data_entrega": pedido.data_entrega,
            "data_confirmacao": pedido.data_entrega,
            "mensagem": "Entrega confirmada com sucesso"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao confirmar entrega: {str(e)}"
        )
