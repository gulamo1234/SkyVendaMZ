from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import pymysql
pymysql.install_as_MySQLdb()

# URL de conexão MyS
DATABASE_URL = "postgresql://postgres:uCUCjSkArNRiteSTDrxMuwyldXGKeTQO@junction.proxy.rlwy.net:42999/railway"
#DATABASE_URL = "sqlite:///skyvendas.db"
# Criação do engine para MySQL
engine = create_engine(DATABASE_URL)

# Configuração da sessão
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base declarativa para as models
Base = declarative_base()