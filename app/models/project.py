from sqlalchemy import BigInteger, Column, Integer, String

from app.models.modelbase import Base


class Project(Base):
    __tablename__ = "project"
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    code = Column(String, unique=True, index=True)
    title = Column(String)
    min_clearance = Column(Integer)
