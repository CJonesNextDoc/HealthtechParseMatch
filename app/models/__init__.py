# Import all models to ensure they're registered with SQLAlchemy metadata
from .assignment import Assignment
from .dob_training_db import DOBPipelineRun, DOBTrainingData
from .employee import Employee
from .project import Project

__all__ = [
    "Assignment",
    "DOBTrainingData",
    "DOBPipelineRun",
    "Employee",
    "Project",
]
