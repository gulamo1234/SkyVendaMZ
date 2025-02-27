from pydantic import BaseModel,EmailStr,Field, validator,ConfigDict
from typing import Optional,Literal,List
from datetime import datetime
import enum
from fastapi import  UploadFile



class PromoverProdutoSchema(BaseModel):
    produto_id: int
    dias: int
    titulo: str
    descricao: str
    tipo: Literal["ofertas_diarias", "melhores_boladas", "para_si", "em_promocao"]





class AnuncioUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    foto: Optional[str] = None
    preco: Optional[float] = None   # use float para representar o preço (DECIMAL)
    activo: Optional[bool] = None
    link: Optional[str] = None
    status: Optional[str] = None      # Valores esperados: "aprovado", "rejeitado" ou "pendente"
    expira_em: Optional[datetime] = None





class StatusCreate(BaseModel):
    conteudo: Optional[str] = None  # Conteúdo textual, se houver
    duracao_dias: int
    imagem_url: Optional[str] = None  # URL da imagem, se houver

    class Config:
       ConfigDict(from_attributes=True)

class AtualizarStatusSchema(BaseModel):
    duracao_dias: int
    conteudo: str = None
    imagem: UploadFile = None

# Schemas para Usuário
class UsuarioBase(BaseModel):
    nome:str
    username: str
    email: EmailStr
    senha: Optional[str] = None
    #identificador_unico:str
    tipo: Optional[str] = None  # Tipo do usuário (Google, email, etc.)


class UpdateContactRequest(BaseModel):
    contacto: str

class PublicacaoCreate(BaseModel):
    conteudo: str = Field(..., min_length=1)

    @validator('conteudo')
    def limitar_numero_de_palavras(cls, v):
        palavras = v.split()
        if len(palavras) > 10:
            raise ValueError("O texto não pode ter mais do que 10 palavras.")
        return v
# Esquema para o token JWT
class Token(BaseModel):
    access_token: str
    token_type: str


class CategoriaBase(BaseModel):
    nome: str

class CategoriaCreate(CategoriaBase):
    pass

class CategoriaUpdate(CategoriaBase):
    pass





class UsuarioCreate(UsuarioBase):
    senha: str
    

class AdminBase(BaseModel):
    nome: str
    email: str

class AdminCreate(AdminBase):
    senha: str

class AdminUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[str]
    senha: Optional[str] = None


class Admin(AdminBase):
    id: int

    class Config:
       ConfigDict(from_attributes=True)

class InfoUsuarioCreate(BaseModel):
    foto_retrato: str  # Foto do rosto do usuário
    foto_bi_frente: str  # Foto da frente do BI
    foto_bi_verso: str  # Foto do verso do BI
    provincia: str
    distrito: str
    data_nascimento: str
    sexo: str
    nacionalidade: Optional[str] = None
    bairro: Optional[str] = None
    usuario_id: int


class AvaliacaoSchema(BaseModel):
    estrelas: int = Field(..., ge=1, le=5, description="Nota da avaliação (1 a 5 estrelas)")

    class Config:
        from_attributes = True





class ItemPedidoCreate(BaseModel):
    pedidoID: int
    produtoID: int
    quantidade: int
    preco_unitario: float

    class Config:
        from_attributes = True  # Atualize a configuração para o Pydantic v2

class ItemPedidoUpdate(ItemPedidoCreate):
    pedidoID: int
    produtoID: int
    quantidade: int
    preco_unitario: float



class InfoUsuarioUpdate(BaseModel):
    perfil: str
    provincia: str
    foto_bi: str
    distrito: str
    data_nascimento: str
    avenida: Optional[str] = None
    revisao: Optional[str]=None
    bairro: Optional[str] = None



class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    apelido: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str]=None
    numero: Optional[str] = None
    whatsapp: Optional[str] = None
    tipo: Optional[str] = None
    estado: Optional[str] = None
    senha:Optional[str]=None
  

class ProdutoBase(BaseModel):
    nome: str
    preco: int
    quantidade_estoque: Optional[int] = None
    estado: str
    provincia:str
    distrito:str
    localizacao:str
    revisao: Optional[str] = None
    disponiblidade: str
    descricao: str
    categoria: str
    detalhes:str
    tipo:str
    slug: Optional[str] = None  
    CustomerID: int

class ProdutoCreate(ProdutoBase):
    pass


class ProdutoUpdate(BaseModel):
    nome: Optional[str] = None
    preco: Optional[float] = None
    quantidade_estoque: Optional[int] = None
    estado: Optional[str] = None
    disponiblidade: Optional[str] = None
    descricao: Optional[str] = None
    detalhes: Optional[str] = None
    tipo: Optional[str] = None
    categoria: Optional[str] = None
    CustomerID: Optional[int] = None


    class Config:
        from_attributes = True
    
# Schemas para Mensagem
class MensagemBase(BaseModel):
    remetenteID: int
    destinatarioID: int
    conteudo: str
    tipo_mensagem: str
    caminho_imagem: Optional[str] = None
    status: str

class MensagemCreate(MensagemBase):
    pass

class MensagemUpdate(BaseModel):
    conteudo: Optional[str] = None
    tipo_mensagem: Optional[str] = None
    caminho_imagem: Optional[str] = None
    status: Optional[str] = None

# Schemas para Pedido
class PedidoBase(BaseModel):
    customer_id: int  # Aqui também com letra minúscula
    data_pedido: Optional[datetime] = None
    quantidade: int
    produto_id: int
    status: str = "pendente"
    tipo: Optional[str] = "normal"
    
    class Config:
        ConfigDict(from_attributes=True)
class PedidoCreate(PedidoBase):
    pass

class PedidoUpdate(BaseModel):
    data_pedido: Optional[datetime] = None
    status: Optional[str] = None

# Schemas para Comentário
class ComentarioCreate(BaseModel):
    produto_id: int
    conteudo: str
    usuario_id: int
    data_comentario: datetime = None  # Adicionando o campo de data com valor padrão (pode ser opcional)

class ComentarioUpdate(BaseModel):
    comentario: Optional[str] = None
    avaliacao: Optional[int] = None

# Schemas para DenunciaProduto
class DenunciaProdutoBase(BaseModel):
    produtoID: int
    CustomerID: int
    motivo: str
    descricao: str
    data_denuncia: datetime
    status: str

class DenunciaProdutoCreate(DenunciaProdutoBase):
    pass

class DenunciaProdutoUpdate(BaseModel):
    motivo: Optional[str] = None
    descricao: Optional[str] = None
    status: Optional[str] = None

# Schemas para Endereco_Envio
class EnderecoEnvioBase(BaseModel):
    endereco_line1: str
    endereco_line2: Optional[str] = None
    cidade: str
    CustomerID:int
    pedidoID:int
    estado: str
    codigo_postal: str
    pais: str

class EnderecoEnvioCreate(EnderecoEnvioBase):
    pass


class EmailSchema(BaseModel):
    email: str

class EnderecoEnvioUpdate(BaseModel):
    endereco_line1: Optional[str] = None
    endereco_line2: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    codigo_postal: Optional[str] = None
    pais: Optional[str] = None
