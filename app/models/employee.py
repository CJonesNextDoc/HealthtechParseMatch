from sqlalchemy import BigInteger, Column, Integer, String

from app.models.modelbase import Base


class Employee(Base):
    __tablename__ = "employee"
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    clearance_level = Column(Integer)
