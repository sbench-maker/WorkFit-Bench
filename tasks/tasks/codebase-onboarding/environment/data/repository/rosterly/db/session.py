from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from rosterly.settings import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
