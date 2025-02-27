from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from models import Usuario, Admin,Message  # Adicione a importação da classe Admin
from schemas import UsuarioCreate,AdminCreate,AdminBase
from database import SessionLocal
from controlers.utils import gerar_identificador_unico

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Configurações do JWT
SECRET_KEY = "your_secret_key_here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 43200

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="usuario/token")


# Contexto para hashing de senhas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Esquema para OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="usuario/token")

# Função para gerar um hash da senha
def hash_password(password):
    return pwd_context.hash(password)

# Funções de hash e verificação de senha
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Cria um novo token JWT
    
    Args:
        subject: Identificador do usuário (geralmente o ID)
        expires_delta: Tempo opcional de expiração do token
    
    Returns:
        str: Token JWT codificado
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def store_message(message:Message):
    db=get_db()
    db.add(message)
    db.commit()

def create_access_token_admin(subject: dict, expires_delta: timedelta = None):
    """
    Cria um token de acesso JWT.

    Args:
    - subject (dict): Dados a serem incluídos no token.
    - expires_delta (timedelta, optional): Duração do token.

    Returns:
    - str: Token JWT gerado.
    """
    to_encode = subject.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: int, user_role: str, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = {"sub": str(user_id), "role": user_role}  # Inclui o ID e o papel do usuário no token
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Função para buscar um usuário pelo ID
def get_user(db: Session, user_id: int):
    return db.query(Usuario).filter(Usuario.id == user_id).first()

# Função para buscar um administrador pelo ID
def get_admin(db: Session, admin_id: int):
    return db.query(Admin).filter(Admin.id == admin_id).first()

# Função para autenticar o usuário
# Função para autenticar o usuário
def authenticate_user(db: Session, identifier: str, password: str):
    # Busca o usuário pelo username, email ou contacto
    user = db.query(Usuario).filter(
        (Usuario.username == identifier) |
        (Usuario.identificador_unico == identifier) |
        (Usuario.email == identifier) |
        (Usuario.contacto == identifier)
    ).first()

    # Verifica se o usuário existe e se a senha é válida
    if not user or not verify_password(password, user.senha):
        return False

    # Verifica se o campo 'ativo' está como True
    if not user.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário desativado, por favor contate o administrador."
        )

    return user

# Função para autenticar o administrador
def authenticate_admin(db: Session, email: str, password: str):
    admin = db.query(Admin).filter(Admin.email == email).first()
    if not admin or not verify_password(password, admin.senha):
        return False
    return admin

# Função para obter o usuário atual, extraindo ID e tipo do token
def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = int(payload.get("sub"))
        user_role: str = payload.get("role")  # Recupera o tipo de usuário
        if user_id is None or user_role is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(db, user_id=user_id)
    if user is None:
        raise credentials_exception
    return user

# Função para obter o usuário atual, extraindo ID e tipo do token =WebSoket
def get_current_user_socket(token,db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = int(payload.get("sub"))
        user_role: str = payload.get("role")  # Recupera o tipo de usuário
        if user_id is None or user_role is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(db, user_id=user_id)
    if user is None:
        raise credentials_exception
    return user
# Função para obter o administrador atual
def get_current_admin(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        role = payload.get("role")
        if role != "admin":
            raise credentials_exception  # Se o papel não for admin, acesso negado
        admin_id: int = payload.get("sub")
        if admin_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    admin = get_admin(db, admin_id=admin_id)
    if admin is None:
        raise credentials_exception
    return admin
    
# Função para registrar um novo usuário (hashing da senha)
# Função para registrar um novo usuário no banco de dados

def register_user(
    db: Session, nome: str,identificador_unico:str, username: str, email: str, senha: Optional[str], tipo: Optional[str], referencia: Optional[str] = None
):
    hashed_password = get_password_hash(senha) if senha else None
    
    # Gera o identificador único para o novo usuário
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

    # Criando o usuário
    db_user = Usuario(
        nome=nome,
        username=username,
        email=email,
        tipo=tipo or "cliente",
        senha=hashed_password,
        identificador_unico=identificador_unico,
        referenciador_id=referenciador.id if referenciador else None  # Associa o usuário ao referenciador
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


    # Função para registrar um novo administrador (hashing da senha)
def register_admin(db: Session, admin: AdminCreate):
    hashed_password = get_password_hash(admin.senha)
    db_admin = Admin(
        nome=admin.nome,  # Use o nome fornecido
        email=admin.email,
        senha=hashed_password  # A senha deve ser hashada
    )
    
    db.add(db_admin)
    db.commit()
    db.refresh(db_admin)
    return db_admin
