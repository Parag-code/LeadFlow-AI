
from typing import TypedDict, Optional, Any


class LeadFlowState(TypedDict, total=False):

    # =========================================
    # Incoming customer inquiry
    # =========================================

    inquiry: str

    # =========================================
    # Extracted lead information
    # =========================================

    lead: dict[str, Any]
    lead_id: Optional[int]

    # =========================================
    # Customer information validation
    # =========================================

    missing_fields: list[str]
    clarification_questions: list[str]
    qualification_summary: str

    next_action: str
    status: str

    # =========================================
    # CRM operations
    # =========================================

    database_operation: Optional[str]

    # =========================================
    # Autonomous email workflow
    # =========================================

    email_draft: Optional[dict[str, Any]]

    approval_status: str
    email_send_status: str
    email_send_result: Optional[dict[str, Any]]

    # =========================================
    # Workflow execution tracking
    # =========================================

    workflow_id: str
    errors: list[str]

    # =========================================
    # Workflow completion
    # =========================================

    workflow_status: str
    completed_at: Optional[str]
