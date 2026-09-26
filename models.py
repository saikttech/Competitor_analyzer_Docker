from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, ForeignKey, text, Index
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import NullPool
from pgvector.sqlalchemy import Vector
from config import DATABASE_URL

# NullPool критичен для Celery
engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Competitor(Base):
    __tablename__ = "competitors"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True)
    title = Column(String)
    description = Column(Text)
    full_text = Column(Text)
    niche = Column(String)
    geo = Column(String)
    status = Column(String)
    clean_text = Column(Text)
    cleaned = Column(Boolean, default=False)
    
    chunks = relationship("CompetitorChunk", back_populates="competitor", cascade="all, delete-orphan")

class CompetitorChunk(Base):
    __tablename__ = "competitor_chunks"
    chunk_id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"))
    chunk_text = Column(Text)
    chunk_length = Column(Integer)
    niche = Column(String)
    geo = Column(String)
    url = Column(String)
    title = Column(String)
    embedding = Column(Vector(1536))
    
    # Полнотекстовый индекс для BM25
    __table_args__ = (
        Index('idx_chunk_text_fts', 'chunk_text', postgresql_using='gin',
              postgresql_ops={'chunk_text': 'gin_trgm_ops'}),
    )
    
    competitor = relationship("Competitor", back_populates="chunks")

def init_db():
    """Создает таблицы и включает необходимые расширения PostgreSQL"""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.commit()
    Base.metadata.create_all(bind=engine)