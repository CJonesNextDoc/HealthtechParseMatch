from sqlalchemy import BigInteger, Column, Integer, String, UniqueConstraint
from app.models.modelbase import Base


class Employee(Base):
    __tablename__ = "employee" 
    id = Column(BigInteger, primary_key = True, index = True, autoincrement = True)
    email = Column(String, unique = True, index = True)
    full_name = Column(String)
    clearance_level = Column(Integer)

    __table_args__ = (UniqueConstraint("email", name="uq_email"),)
