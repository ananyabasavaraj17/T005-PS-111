
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Database file location
DATABASE_URL = "sqlite:///crowdfunding.db"

# Create database engine
engine = create_engine(
    DATABASE_URL,
    echo=False
)

# Create database sessions
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

# Base class for all database models
class Base(DeclarativeBase):
    pass
