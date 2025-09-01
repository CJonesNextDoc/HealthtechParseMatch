from sqlalchemy import BigInteger, Column, ForeignKey, String

from app.models.modelbase import Base


class Assignment(Base):
    __tablename__ = "assignment"
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    employee_id = Column(BigInteger, ForeignKey("employee.id"), index=True)
    project_id = Column(BigInteger, ForeignKey("project.id"), index=True)
    role = Column(String, nullable=False)

    # projects = relationship("Project", back_populates="assignment")
    # employees = relationship("Employee", back_populates="assignment")
