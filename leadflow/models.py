
import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LeadData(BaseModel):
    """Validated structure for an incoming customer lead."""

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    business_type: Optional[str] = None
    requirement: Optional[str] = None
    additional_details: Optional[str] = None
    budget: Optional[str] = None
    timeline: Optional[str] = None
    intent: Optional[str] = None

    @field_validator(
        "name",
        "email",
        "company",
        "business_type",
        "requirement",
        "additional_details",
        "budget",
        "timeline",
        "intent",
        mode="before",
    )
    @classmethod
    def clean_text(cls, value):
        if value is None:
            return None

        if not isinstance(value, str):
            return value

        value = value.strip()
        return value if value else None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if value is None:
            return None

        pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

        if not re.match(pattern, value):
            raise ValueError("Invalid email address")

        return value.lower()


class LeadAnalysis(BaseModel):
    """Result of customer information extraction."""

    lead: LeadData
    missing_fields: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    qualification_summary: Optional[str] = None
