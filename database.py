from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

DB_URL = "mysql+pymysql://root:1234567890@localhost:3306/hospital"

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(
    autoflush=False,
    autocommit=False,
    bind=engine
)
  
Base.metadata.create_all(bind=engine)
