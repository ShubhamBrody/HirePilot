"""
Recruiter & Outreach Schemas
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.recruiter import ConnectionStatus, OutreachStatus


class RecruiterResponse(BaseModel):
    id: str
    name: str
    title: str | None = None
    company: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    profile_image_url: str | None = None
    connection_status: ConnectionStatus
    platform: str
    discovered_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v: object) -> str:
        return str(v)


class RecruiterListResponse(BaseModel):
    recruiters: list[RecruiterResponse]
    total: int


class OutreachMessageRequest(BaseModel):
    message_type: str = Field(description="connection_request, follow_up, inmail")
    custom_message: str | None = Field(
        None, description="Override AI-generated message"
    )
    job_listing_id: str | None = Field(
        None, description="Job context for AI message generation"
    )


class OutreachMessageResponse(BaseModel):
    id: str
    recruiter_id: str
    message_type: str
    subject: str | None = None
    body: str
    ai_generated: bool
    status: OutreachStatus
    sent_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", "recruiter_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v: object) -> str:
        return str(v)


class FindRecruitersRequest(BaseModel):
    """Request to discover recruiters at a company."""
    company: str = Field(description="Target company name")
    role: str | None = Field(None, description="Target role (e.g. 'SDE 2', 'Backend Engineer')")


class FindRecruitersResponse(BaseModel):
    recruiters: list[RecruiterResponse]
    total: int
    source: str = Field(description="How recruiters were discovered: 'llm' or 'linkedin'")


class GenerateMessageRequest(BaseModel):
    """Preview AI-generated message without sending."""
    recruiter_id: str
    job_listing_id: str | None = None
    message_type: str = "connection_request"
    tone: str = Field("professional", description="professional, casual, enthusiastic")


class GenerateMessageResponse(BaseModel):
    suggested_message: str
    recruiter_name: str
    company: str | None = None
    job_title: str | None = None
