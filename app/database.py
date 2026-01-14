from typing import Optional, List
from sqlmodel import Field, SQLModel, create_engine, Session, select
import os
from dotenv import load_dotenv

load_dotenv()

# Define Models

class Prompt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True) # e.g., "claude_system", "gemini_system"
    content: str

class Template(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    html_content: str
    image_data: bytes # Storing image as BLOB (BYTEA in Postgres)

class History(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str # Link to username/sub
    date: str
    keyword: str
    inputs_json: str # JSON string of inputs
    result_html: Optional[str] = None
    created_at_ts: int = Field(default=0) # Sortable timestamp

# Setup DB Connection
# Default to SQLite for local development if DATABASE_URL not set
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./local_database.db")

# Fix for Heroku/Railway style "postgres://" which SQLAlchemy stopped supporting in favor of "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
