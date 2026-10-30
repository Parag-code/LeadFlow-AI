
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, EmailStr

from leadflow.graph import run_leadflow
from leadflow.database import (
    initialize_database,
    get_all_leads,
    get_lead_by_id,
    get_audit_logs,
)


# ==================================================
# APPLICATION CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "leadflow" / "templates"

app = FastAPI(
    title="LeadFlow AI",
    description="Autonomous Lead Capture, Information Validation and CRM Automation",
    version="3.1.0",
)

initialize_database()


# ==================================================
# REQUEST MODELS
# ==================================================

class InquiryRequest(BaseModel):
    inquiry: str = Field(min_length=5, max_length=10000)


class LeadFormRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    company: str = Field(min_length=2, max_length=150)
    business_type: str = Field(min_length=2, max_length=100)
    requirement: str = Field(min_length=10, max_length=3000)
    budget: str = Field(min_length=1, max_length=100)
    timeline: str = Field(min_length=1, max_length=100)
    additional_details: str = Field(default="", max_length=3000)


class FollowUpRequest(BaseModel):
    lead_id: int = Field(gt=0)
    email: EmailStr
    intent: str = Field(min_length=3, max_length=1000)
    additional_details: str = Field(default="", max_length=2000)


# ==================================================
# HELPER: MERGE ADDITIONAL DETAILS
# ==================================================

def merge_additional_details(
    existing_details: str | None,
    new_details: str | None,
) -> str | None:
    """
    Preserve existing customer details and append new follow-up details.
    Avoid duplicating identical text.
    """

    existing = (existing_details or "").strip()
    new = (new_details or "").strip()

    if not existing:
        return new or None

    if not new:
        return existing

    if new.casefold() == existing.casefold():
        return existing

    return (
        f"Initial Details:\n{existing}\n\n"
        f"Follow-up Details:\n{new}"
    )


# ==================================================
# WORKFLOW RESPONSE HELPER
# ==================================================

def build_workflow_response(result: dict, message: str) -> dict:

    lead_id = result.get("lead_id")
    missing_fields = result.get("missing_fields") or []

    needs_follow_up = (
        bool(missing_fields)
        or result.get("next_action") == "REQUEST_CLARIFICATION"
    )

    response = {
        "success": True,
        "message": message,
        "lead_id": lead_id,
        "workflow_id": result.get("workflow_id"),
        "status": result.get("status"),
        "next_action": result.get("next_action"),
        "missing_fields": missing_fields,
        "clarification_questions": result.get(
            "clarification_questions", []
        ),
        "needs_follow_up": needs_follow_up,
        "approval_status": result.get("approval_status"),
        "email_send_status": result.get("email_send_status"),
        "workflow_status": result.get("workflow_status"),
    }

    if needs_follow_up and lead_id:
        response["redirect_url"] = f"/follow-up?lead_id={lead_id}"
    else:
        response["redirect_url"] = None

    return response


# ==================================================
# CUSTOMER-FACING INITIAL FORM
# ==================================================

@app.get("/")
def lead_capture_page():

    form_path = TEMPLATE_DIR / "index.html"

    if not form_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Lead capture form has not been created yet.",
        )

    return FileResponse(form_path)


# ==================================================
# INITIAL LEAD SUBMISSION
# ==================================================

@app.post("/submit-lead")
def submit_lead(request: LeadFormRequest):

    inquiry = f"""
Customer Name: {request.name}
Email: {request.email}
Company: {request.company}
Business Type: {request.business_type}
Requirement: {request.requirement}
Budget: {request.budget}
Timeline: {request.timeline}

Initial Additional Details:
{request.additional_details or 'Not provided'}
"""

    try:

        result = run_leadflow(inquiry)

        return build_workflow_response(
            result,
            "Your inquiry has been submitted successfully.",
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        print(f"Lead submission error: {error}")

        raise HTTPException(
            status_code=502,
            detail=(
                "Your inquiry could not be processed. "
                "Please try again later."
            ),
        )


# ==================================================
# CUSTOMER FOLLOW-UP FORM PAGE
# ==================================================

@app.get("/follow-up")
def follow_up_page():

    form_path = TEMPLATE_DIR / "follow_up.html"

    if not form_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Follow-up form has not been created yet.",
        )

    return FileResponse(form_path)


# ==================================================
# CUSTOMER FOLLOW-UP SUBMISSION
# ==================================================

@app.post("/follow-up")
def submit_follow_up(request: FollowUpRequest):

    existing_lead = get_lead_by_id(request.lead_id)

    if not existing_lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found.",
        )

    registered_email = str(
        existing_lead["email"]
    ).strip().lower()

    submitted_email = str(
        request.email
    ).strip().lower()

    if registered_email != submitted_email:
        raise HTTPException(
            status_code=403,
            detail="Email does not match this lead.",
        )

    if existing_lead.get("lead_status") != "NEEDS_INFORMATION":
        raise HTTPException(
            status_code=409,
            detail="This lead does not currently require clarification.",
        )

    # Preserve initial details and append new follow-up details.
    combined_details = merge_additional_details(
        existing_lead.get("additional_details"),
        request.additional_details,
    )

    inquiry = f"""
Existing Customer Lead - Follow-up Submission

Customer Name: {existing_lead['name']}
Email: {existing_lead['email']}
Company: {existing_lead['company']}
Business Type: {existing_lead.get('business_type') or 'Not provided'}
Requirement: {existing_lead.get('requirement') or 'Not provided'}
Budget: {existing_lead.get('budget') or 'Not provided'}
Timeline: {existing_lead.get('timeline') or 'Not provided'}

Customer Buying Intent:
{request.intent}

Combined Additional Details:
{combined_details or 'Not provided'}

IMPORTANT:
This is an update to an existing customer lead.
Preserve all existing information.
Use the supplied buying intent and additional details.
Do not create a new customer identity.
"""

    try:

        result = run_leadflow(inquiry)

        return build_workflow_response(
            result,
            "Your follow-up response has been submitted successfully.",
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        print(f"Follow-up submission error: {error}")

        raise HTTPException(
            status_code=502,
            detail=(
                "Your follow-up could not be processed. "
                "Please try again later."
            ),
        )


# ==================================================
# TEXT-BASED LEAD ENDPOINT
# ==================================================

@app.post("/process-lead")
def process_lead(request: InquiryRequest):

    try:
        return run_leadflow(request.inquiry)

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        print(f"Lead processing error: {error}")

        raise HTTPException(
            status_code=502,
            detail="Lead processing failed. Check server logs.",
        )


# ==================================================
# CRM ENDPOINTS
# ==================================================

@app.get("/leads")
def list_leads():

    leads = get_all_leads()

    return {
        "total": len(leads),
        "leads": leads,
    }


@app.get("/leads/{lead_id}")
def lead_details(lead_id: int):

    lead = get_lead_by_id(lead_id)

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found.",
        )

    return lead


@app.get("/leads/{lead_id}/history")
def lead_history(lead_id: int):

    lead = get_lead_by_id(lead_id)

    if not lead:
        raise HTTPException(
            status_code=404,
            detail="Lead not found.",
        )

    return {
        "lead_id": lead_id,
        "history": get_audit_logs(lead_id),
    }


# ==================================================
# HEALTH CHECK
# ==================================================

@app.get("/health")
def health_check():

    return {
        "status": "running",
        "application": "LeadFlow AI",
        "version": "3.1.0",
    }
