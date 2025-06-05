from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

class ExperienceLevel(str, Enum):
    JUNIOR = "junior"
    MID_LEVEL = "mid"
    SENIOR = "senior"
    LEAD = "lead"

class Skill(BaseModel):
    name: str
    category: str  # e.g., "programming", "framework", "cloud"
    experience_years: float
    level: str  # e.g., "beginner", "intermediate", "expert"

class ProjectRequirement(BaseModel):
    skill: str
    level: str
    required: bool = True
    weight: float = 1.0  # Importance of this requirement (0.0-1.0)


class EngineerProfile(BaseModel):
    id: str
    name: str
    email: str
    skills: List[Skill]
    total_experience_years: float
    current_role: str
    desired_roles: List[str]
    location: str
    willing_to_relocate: bool
    current_salary: Optional[float]
    expected_salary: Optional[float]
    availability: str  # e.g., "immediate", "1_month", "3_months"
    last_updated: datetime = Field(default_factory=datetime.utcnow)

class ProjectDetails(BaseModel):
    id: str
    source_email_id: str
    received_date: datetime
    project_name: str
    client_name: str
    description: str
    required_skills: List[ProjectRequirement]
    location: str
    work_type: str  # e.g., "remote", "onsite", "hybrid"
    duration_months: Optional[int]
    start_date: Optional[datetime]
    budget_range: Optional[Dict[str, float]]  # e.g., {"min": 1000, "max": 2000}
    is_active: bool = True

class MatchingResult(BaseModel):
    engineer_id: str
    project_id: str
    match_score: float  # 0.0 to 1.0
    skill_matches: Dict[str, float]  # skill -> match_score
    notes: Optional[str]
    last_updated: datetime = Field(default_factory=datetime.utcnow)

class Notification(BaseModel):
    id: str
    recipient_email: str
    subject: str
    content: str
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    read: bool = False
    metadata: Dict[str, Any] = {}

class SearchCriteria(BaseModel):
    skills: Optional[List[str]] = None
    min_experience: Optional[float] = None
    location: Optional[str] = None
    work_type: Optional[str] = None
    min_salary: Optional[float] = None
    max_salary: Optional[float] = None
    availability: Optional[str] = None
    sort_by: str = "match_score"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 10
