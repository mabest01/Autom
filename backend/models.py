from pydantic import BaseModel
from typing import Optional


class JobResponse(BaseModel):
    id: int
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    url: str
    description: Optional[str] = None
    generated_message: Optional[str] = None
    status: str = "pending"
    applied_at: Optional[str] = None
    created_at: Optional[str] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None

    class Config:
        from_attributes = True


class JobUpdate(BaseModel):
    message: str


class StatsResponse(BaseModel):
    total: int
    applied_today: int
    pending: int
    failed: int
    success_rate: float


class ScrapeResponse(BaseModel):
    message: str
    jobs_found: int
    jobs_new: int


class ApplyResponse(BaseModel):
    success: bool
    message: str


class SessionStatusResponse(BaseModel):
    logged_in: bool
    last_check: Optional[str] = None
    last_login: Optional[str] = None
    consecutive_failures: int = 0
    blocked_until: Optional[str] = None
