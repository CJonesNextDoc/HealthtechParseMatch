from sqlalchemy import BigInteger, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import declarative_base  #, relationship


Base = declarative_base()


class Employee(Base):
    __tablename__ = "employee" 
    id = Column(BigInteger, primary_key = True, index = True, autoincrement = True)
    email = Column(String, unique = True, index = True)
    full_name = Column(String)
    clearance_level = Column(Integer)

    __table_args__ = (UniqueConstraint("email", name="uq_email"),)


class Project(Base):
    __tablename__ = "project" 
    id = Column(BigInteger, primary_key = True, index = True, autoincrement = True)
    code = Column(String, unique = True, index = True)
    title = Column(String)
    min_clearance = Column(Integer)


class Assignment(Base):
    __tablename__ = "assignment" 
    id = Column(BigInteger, primary_key = True, index = True, autoincrement = True)
    employee_id = Column(BigInteger, ForeignKey("employee.id"), index = True)
    project_id = Column(BigInteger, ForeignKey("project.id"), index = True)
    role = Column(String, nullable=False)

    # projects = relationship("Project", back_populates="assignment")
    # employees = relationship("Employee", back_populates="assignment")
