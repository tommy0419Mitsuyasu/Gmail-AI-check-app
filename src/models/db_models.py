from datetime import datetime
from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum
from pydantic import validator

class ExperienceLevel(str, Enum):
    JUNIOR = "junior"
    MID_LEVEL = "mid"
    SENIOR = "senior"
    LEAD = "lead"

class SkillBase(SQLModel):
    name: str = Field(index=True)
    category: str = Field(index=True)  # 例: "programming", "framework", "cloud"
    experience_years: float
    level: str  # 例: "beginner", "intermediate", "expert"

class Skill(SkillBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    engineer_id: int = Field(foreign_key="engineer.id")

class EngineerBase(SQLModel):
    name: str
    email: str = Field(index=True, unique=True)
    total_experience_years: float
    current_role: str
    desired_roles: str  # カンマ区切りで保存
    location: str
    willing_to_relocate: bool
    current_salary: Optional[float] = None
    expected_salary: Optional[float] = None
    availability: str  # 例: "immediate", "1_month", "3_months"

class Engineer(EngineerBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # リレーションシップ
    skills: List[Skill] = Relationship(back_populates="engineer")

class ProjectRequirementBase(SQLModel):
    skill: str
    level: str
    required: bool = True
    weight: float = 1.0  # この要件の重要度 (0.0-1.0)
    project_id: int = Field(foreign_key="project.id")

class ProjectRequirement(ProjectRequirementBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class ProjectBase(SQLModel):
    source_email_id: str
    project_name: str
    client_name: str
    description: str
    location: str
    work_type: str  # 例: "remote", "onsite", "hybrid"
    duration_months: Optional[int] = None
    start_date: Optional[datetime] = None
    min_budget: Optional[float] = None
    max_budget: Optional[float] = None
    is_active: bool = True

class Project(ProjectBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    received_date: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # リレーションシップ
    requirements: List[ProjectRequirement] = Relationship(back_populates="project")

# Pydanticモデル（レスポンス用）
class EngineerResponse(EngineerBase):
    id: int
    created_at: datetime
    updated_at: datetime
    skills: List[Skill] = []

class ProjectResponse(ProjectBase):
    id: int
    received_date: datetime
    created_at: datetime
    updated_at: datetime
    requirements: List[ProjectRequirement] = []
