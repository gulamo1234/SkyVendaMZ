from sqlalchemy import Column, Integer, String,JSON, ForeignKey, DateTime, Text, Table, DECIMAL,Float, Boolean,Enum,func
from sqlalchemy.orm import relationship
from database import Base,engine
from unidecode import unidecode
import re
import enum
from sqlalchemy import event
from sqlalchemy.orm import Session
from datetime import datetime,timedelta
import random

class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    PDF = "pdf"
    AUDIO = "audio"
    VIDEO = "video"

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    content = Column(Text, nullable=True)  # Pode ser null para tipos como IMAGE, PDF, etc.
    message_type = Column(Enum(MessageType), nullable=False)
    file_url = Column(String(250), nullable=True)  # URL do arquivo, se aplicável
    file_name = Column(String(250), nullable=True)  # Nome do arquivo, se aplicável
    file_size = Column(Integer, nullable=True)  # Tamanho do arquivo, se aplicável
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_read = Column(Boolean, default=False)

    sender = relationship("Usuario", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("Usuario", foreign_keys=[receiver_id], back_populates="received_messages")

class Avaliacao(Base):
    __tablename__ = "avaliacoes"

    id = Column(Integer, primary_key=True, index=True)
    avaliador_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)  # Usuário que avaliou
    avaliado_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)   # Usuário avaliado
    estrelas = Column(Integer, nullable=False)  # Número de estrelas (1 a 5)
    data_criacao = Column(DateTime, default=datetime.utcnow)

    # Relacionamento com o modelo Usuario
    avaliador = relationship("Usuario", foreign_keys=[avaliador_id], back_populates="avaliacoes_feitas")
    avaliado = relationship("Usuario", foreign_keys=[avaliado_id], back_populates="avaliacoes_recebidas")

class Status(Base):
    __tablename__ = "status"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    conteudo = Column(Text, nullable=True)
    imagem_url = Column(String(250), nullable=True)
    expira_em = Column(DateTime, nullable=False)
    custo_total = Column(DECIMAL, nullable=False)
    visualizacoes = Column(Integer, default=0)  # Contador de visualizações

    usuario = relationship("Usuario", back_populates="statuses")
    #respostas = relationship("RespostaStatus", back_populates="status")  # Relacionamento para respostas


    def calcular_expiracao(self, duracao_dias):
        self.expira_em = self.data_criacao + timedelta(days=duracao_dias)
        self.custo_total = duracao_dias * 9.0  # Custo de 9.0 MT por dia
        
produto_likes = Table(
    'produto_likes',
    Base.metadata,
    Column('produto_id', Integer, ForeignKey('produto.id'), primary_key=True),
    Column('usuario_id', Integer, ForeignKey('usuarios.id'), primary_key=True)
)



class Log(Base):
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)  # Pode ser None para ações anônimas.
    tipo_acao = Column(String(255), nullable=False)
    entidade = Column(String(255), nullable=False)  # Ex.: Produto, Pedido.
    detalhes = Column(JSON(255), nullable=True)  # Detalhes em formato JSON.
    data_hora = Column(DateTime, default=datetime.utcnow)


class Usuario(Base):
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True)
    nome = Column(String(250))
    identificador_unico = Column(String(255), unique=True, nullable=True, index=True)
    email = Column(String(255), unique=True, index=True)
    senha = Column(String(255), nullable=True)  # Pode ser null para login com Google
    google_id = Column(String(255), unique=True, nullable=True)
    tipo = Column(String(255), nullable=True,default="cliente")
    contacto=Column(String(255),nullable=True,unique=True)
    bloqueado=Column(Boolean, default=False)
    sexo = Column(String(20),nullable=True)
    idioma = Column(String, default="en")  # Idioma padrão é inglês
    foto_perfil = Column(String(500), nullable=True)
    min_perfil = Column(String(500), nullable=True)
    foto_capa = Column(String(500), nullable=True)
    nome_pagina=Column(String(100),nullable=True)
    biografia = Column(String(500), nullable=True)
    ativo = Column(Boolean, default=True)
    role = Column(Boolean, default=False)
    conta_pro = Column(Boolean, default=False)  # Indica se o usuário tem uma conta PRO
    limite_diario_publicacoes = Column(Integer, default=5)  # Limite de publicações diárias para usuários PRO
    notificacoes = relationship("Notificacao", back_populates="usuario")
    pesquisas = relationship("Pesquisa", back_populates="usuario") 
    transacoes = relationship("Transacao", back_populates="usuario")
    publicacoes = relationship("Publicacao", back_populates="usuario")
    data_cadastro =Column(DateTime, default=datetime.utcnow) 
    data_ativacao_pro = Column(DateTime, nullable=True)  # Data de ativação da conta PRO
    revisao=Column(String(20),nullable=True,default="nao")
    saldos_congelados = relationship("SaldoCongelado", back_populates="usuario") 
    #data_cadastro=Column(DateTime, nullable=True) 
    produtos = relationship("Produto", back_populates="usuario")
    comentarios = relationship("Comentario", back_populates="usuario")
    # Relacionamento com a tabela Avaliacao
    avaliacoes_feitas = relationship("Avaliacao", foreign_keys="[Avaliacao.avaliador_id]", back_populates="avaliador")
    avaliacoes_recebidas = relationship("Avaliacao", foreign_keys="[Avaliacao.avaliado_id]", back_populates="avaliado")
    anuncios = relationship("AnuncioUsuario", back_populates="usuario", cascade="all, delete-orphan")

    statuses = relationship("Status", back_populates="usuario")

    # Relacionamentos para mensagens
    sent_messages = relationship("Message", foreign_keys=[Message.sender_id], back_populates="sender")
    received_messages = relationship("Message", foreign_keys=[Message.receiver_id], back_populates="receiver")
    referenciador_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)  # Referência ao usuário que fez a indicação
    
    # Relacionamento para contar os usuários referenciados
    referencias = relationship("Usuario", backref="referenciador", remote_side=[id])
    # Relacionamento com a tabela Wallet
    wallet = relationship("Wallet", back_populates="usuario", uselist=False)  # Supondo que exista um relacionamento um-para-um
    pedidos = relationship("Pedido", backref="usuario")
    def verificar_expiracao_pro(self):
        if self.conta_pro and self.data_ativacao_pro:
            # Verifica se já passaram 30 dias
            if datetime.utcnow() > self.data_ativacao_pro + timedelta(days=30):
                self.conta_pro = False
                self.data_ativacao_pro = None

    # Relacionamento com a tabela InfoUsuario
    info_usuario = relationship("InfoUsuario", back_populates="usuario", uselist=False)
    produtos_curtidos = relationship(
        "Produto",
        secondary="produto_likes",  # Certifique-se de que o nome da tabela de associação está correto
        back_populates="usuarios_que_deram_like"
    )



class Referencia(Base):
    __tablename__ = "referencias"

    id = Column(Integer, primary_key=True, index=True)
    referenciador_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)  # Quem fez a indicação
    referenciado_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)  # Quem foi indicado
    data_criacao = Column(DateTime, default=datetime.utcnow)  # Quando foi criada a referência

    # Relacionamentos
    referenciador = relationship("Usuario", foreign_keys=[referenciador_id], backref="referencias_feitas")
    referenciado = relationship("Usuario", foreign_keys=[referenciado_id], backref="referencias_recebidas")



class Admin(Base):
    __tablename__ = "admin"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255))
    email = Column(String(100), unique=True, nullable=False)
    senha = Column(String(200))

class InfoUsuario(Base):
    __tablename__ = "info_usuario"
    
    id = Column(Integer, primary_key=True, index=True)
    foto_retrato = Column(String(350))  # Foto do rosto do usuário
    foto_bi_frente = Column(String(350))  # Frente do BI
    foto_bi_verso = Column(String(350))  # Verso do BI
    provincia = Column(String(350))
    distrito = Column(String(350))
    data_nascimento = Column(String(350))
    localizacao = Column(String(350))
    sexo = Column(String(20))
    nacionalidade = Column(String(255), nullable=True)
    bairro = Column(String(255), nullable=True)
    revisao = Column(String(255), default="pendente")
    # Relacionamento com Usuario
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    usuario = relationship("Usuario", back_populates="info_usuario")

class Publicacao(Base):
    __tablename__ = "publicacoes"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    conteudo = Column(String(250))

    # Relacionamento com o modelo Usuario
    usuario = relationship("Usuario", back_populates="publicacoes")

    # Relacionamento com likes e comentários específicos de publicações
    likes = relationship("LikePublicacao", back_populates="publicacao", cascade="all, delete-orphan")
    comentarios = relationship("ComentarioPublicacao", back_populates="publicacao", cascade="all, delete-orphan")

class LikePublicacao(Base):
    __tablename__ = "likes_publicacoes"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    publicacao_id = Column(Integer, ForeignKey("publicacoes.id"))

    # Relacionamentos
    usuario = relationship("Usuario")
    publicacao = relationship("Publicacao", back_populates="likes")


class ComentarioPublicacao(Base):
    __tablename__ = "comentarios_publicacoes"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    publicacao_id = Column(Integer, ForeignKey("publicacoes.id"))
    conteudo = Column(Text, nullable=False)
    data_criacao = Column(DateTime, default=func.now())

    # Relacionamentos
    usuario = relationship("Usuario")
    publicacao = relationship("Publicacao", back_populates="comentarios")

class Pesquisa(Base):
    __tablename__ = "pesquisas"

    id = Column(Integer, primary_key=True, index=True)
    termo_pesquisa = Column(String(250), index=True)
    categoria_pesquisa = Column(String(250), nullable=True)  # Categoria do termo de pesquisa
    data_pesquisa = Column(DateTime, default=datetime.utcnow)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)  # ID do usuário (opcional)

    usuario = relationship("Usuario", back_populates="pesquisas")

class DenunciaProduto(Base):
    __tablename__ = "denunciaProduto"
    id = Column(Integer, primary_key=True, index=True)
    produtoID = Column(Integer, ForeignKey("produto.id"))
    CustomerID = Column(Integer, ForeignKey("usuarios.id"))
    motivo = Column(String(350))
    descricao = Column(Text)
    data_denuncia = Column(DateTime)
    status = Column(String(350))

class Comentario(Base):
    __tablename__ = "comentarios"

    id = Column(Integer, primary_key=True, index=True)
    produtoID = Column(Integer, ForeignKey("produto.id", ondelete="CASCADE"), nullable=False)  # Ajustado para "produto.id"
    usuarioID = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    comentario = Column(String, nullable=False)
    data_comentario = Column(DateTime, default=datetime.utcnow)

    produto = relationship("Produto", back_populates="comentarios")
    usuario = relationship("Usuario", back_populates="comentarios")


class AnuncioUsuario(Base):
    __tablename__ = "anuncios_usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(350), nullable=False)
    descricao = Column(Text, nullable=False)
    foto = Column(String(350), nullable=False)
    preco = Column(DECIMAL, nullable=True)
    activo=Column(Boolean, default=True)
    link=Column(String(500),nullable=True)
    status = Column(String(20), default="pendente")  # 'pendente', 'aprovado', 'rejeitado'
    criado_em = Column(DateTime, default=datetime.utcnow)
    expira_em = Column(DateTime, nullable=False)
    cliques = Column(Integer, default=0) # Contador de cliques
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    usuario = relationship("Usuario") 

   

class OTP(Base):
    __tablename__ = "otps"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(200), nullable=False, index=True)
    otp = Column(String(50), nullable=False)
    expires_at = Column(DateTime, nullable=False)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

class Produto(Base):
    __tablename__ = "produto"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(350))
    capa = Column(String(350))
    fotos = Column(String(350))
    preco = Column(DECIMAL)
    quantidade_estoque = Column(Integer, nullable=True)
    estado = Column(String(350))
    provincia=Column(String(20))
    distrito=Column(String(20))
    localizacao=(String(100))
    renovacao_automatica = Column(Boolean, default=False)
    revisao = Column(String(350),default="nao")
    disponiblidade = Column(String(350))
    descricao = Column(Text)
    categoria = Column(String(350))
    detalhes = Column(String(1000))
    tipo = Column(String(350))
    preco_promocional = Column(Float, nullable=True)
    visualizacoes = Column(Integer, default=0)
    ativo = Column(Boolean, default=True)
    CustomerID = Column(Integer, ForeignKey("usuarios.id"))
    likes = Column(Integer, default=0)
    data_publicacao = Column(DateTime, default=datetime.utcnow)
    # Relacionamento com o usuário
    usuario = relationship("Usuario", back_populates="produtos", foreign_keys=[CustomerID])

    # Relacionamento com Anuncio (um para um)
    anuncio = relationship('Anuncio', back_populates='produto')
    slug = Column(String(250), unique=True, index=True)
        # Relacionamento com Comentarios (um para muitos)
    comentarios = relationship("Comentario", back_populates="produto",cascade="all, delete")
    # Novos campos
    negociavel = Column(Boolean, default=False)  # Indica se o produto é negociável
    promocao = Column(Boolean, default=False)  # Indica se o produto está em promoção
    data_promocao = Column(DateTime, nullable=True)  # Data de início da promoção
    custo_promocao = Column(DECIMAL, default=0.00)  # Custo acumulado da promoção
    pedidos = relationship("Pedido", back_populates="produto", cascade="all, delete-orphan")

    
    def calcular_custo_promocao(self):
        if self.promocao and self.data_promocao:
            dias_em_promocao = (datetime.utcnow() - self.data_promocao).days
            self.custo_promocao = dias_em_promocao * 10

    def gerar_slug(self):
        # Função para gerar slug baseado no nome do produto
        slug = unidecode(self.nome)
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', slug)
        self.slug = slug.lower()
    def verificar_status(self):
        if datetime.utcnow() > self.data_publicacao + timedelta(days=30):
            self.ativo = False

    usuarios_que_deram_like = relationship(
        "Usuario",
        secondary=produto_likes,
        back_populates="produtos_curtidos"
    )

class Anuncio(Base):
    __tablename__ = "anuncio"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(350))
    descricao = Column(Text)
    tipo_anuncio = Column(String(350))  # Exemplo: "promocional", "normal", etc.
    produto_id = Column(Integer, ForeignKey("produto.id"), unique=True)
    promovido_em = Column(DateTime, default=datetime.utcnow)
    expira_em = Column(DateTime, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    produto = relationship('Produto', back_populates='anuncio')

    def definir_promocao(self, dias: int):
        self.expira_em = datetime.utcnow() + timedelta(days=dias)

class Seguidor(Base):
    __tablename__ = "seguidores"
    
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    seguidor_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    
    # Relacionamento entre usuários
    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    seguidor = relationship("Usuario", foreign_keys=[seguidor_id])

class Transacao(Base):
    __tablename__ = "transacoes"
    
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'))
    msisdn = Column(String(250), nullable=False)  # Número do cliente
    valor = Column(DECIMAL, nullable=False)   # Valor da transação
    referencia = Column(String(250), nullable=False)  # Referência da transação M-Pesa
    status = Column(String(250), nullable=False)  # Status da transação (sucesso, erro, etc.)
    data_hora = Column(DateTime, default=datetime.utcnow)  # Data e hora da transação
    tipo=Column(String(20))

    usuario = relationship("Usuario", back_populates="transacoes")

class Notificacao(Base):
    __tablename__ = "notificacoes"
    
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    mensagem = Column(String(255), nullable=False)
    data = Column(DateTime, default=datetime.utcnow)
    estado=Column(String(10),default="nao")
    usuario = relationship("Usuario", back_populates="notificacoes")

class Pedido(Base):
    __tablename__ = "pedido"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("usuarios.id"))
    produto_id = Column(Integer, ForeignKey("produto.id"))
    quantidade = Column(Integer, nullable=False)
    preco_total = Column(DECIMAL)
    status_visivel_comprador = Column(Boolean, default=False)
    status_visivel_vendedor = Column(Boolean, default=False)
    data_pedido = Column(DateTime, default=datetime.utcnow)
    status = Column(String(350))
    aceito_pelo_vendedor = Column(Boolean, default=False)
    tipo = Column(String(20), nullable=True)
    recebido_pelo_cliente = Column(Boolean, default=False)
    data_aceite = Column(DateTime)
    data_envio = Column(DateTime)
    data_entrega = Column(DateTime)
    # Novos campos
    data_confirmacao_recebimento = Column(DateTime, nullable=True)
    data_limite_confirmacao = Column(DateTime, nullable=True)
    
    # Relacionamentos
    produto = relationship("Produto", back_populates="pedidos")
    customer = relationship("Usuario", back_populates="pedidos")

class Wallet(Base):
    __tablename__ = "wallet"
    
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), unique=True)
    saldo_principal = Column(DECIMAL, default=0.00)  # Saldo disponível
    saldo_congelado = Column(DECIMAL, default=0.00)  # Saldo congelado
    bonus = Column(DECIMAL, default=0.00)  # Bônus do usuário

    usuario = relationship("Usuario", back_populates="wallet")  # Relacionamento com o modelo Usuario

class EnderecoEnvio(Base):
    __tablename__ = "endereco_envio"
    id = Column(Integer, primary_key=True, index=True)
    CustomerID = Column(Integer, ForeignKey("usuarios.id"))
    pedidoID = Column(Integer, ForeignKey("pedido.id"))
    endereco_line1 = Column(String(350))
    endereco_line2 = Column(String(255), nullable=True)
    cidade = Column(String(350))
    estado = Column(String(350))
    codigo_postal = Column(String(350))
    pais = Column(String(350))

#tabelas de skywallet
# Modelo para Tokens de Serviço (ServiceToken)
class ServiceToken(Base):
    __tablename__ = "service_tokens"
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(500), nullable=False)  # Ex: SkyVenda
    token = Column(String(500), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # Nulo se o token não expira
    is_active = Column(Boolean, default=True)



# Tabela de Saldos Congelados
class SaldoCongelado(Base):
    __tablename__ = 'saldos_congelados'

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    valor = Column(Float, nullable=False)  # Valor congelado para pedidos em andamento
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="saldos_congelados")
