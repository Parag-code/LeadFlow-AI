
import sqlite3
from pathlib import Path
from uuid import uuid4
from typing import Literal, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from leadflow.config import settings
from leadflow.agent_state import LeadFlowState
from leadflow.agent import process_inquiry

from leadflow.database import (
    initialize_database,
    save_lead,
    update_lead_status,
    log_action,
    update_lead_workflow,
    save_email_draft,
    update_email_workflow_status,
    update_workflow_status,
)

from leadflow.email_generator import generate_followup_email
from leadflow.email_sender import send_customer_email


# ==================================================
# 1. CHECKPOINT DATABASE
# ==================================================

CHECKPOINT_DB = (
    Path(settings.database_file).parent / "workflow_checkpoints.db"
)

CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)

checkpoint_connection = sqlite3.connect(
    str(CHECKPOINT_DB),
    check_same_thread=False,
)

checkpointer = SqliteSaver(checkpoint_connection)
checkpointer.setup()


# ==================================================
# 2. EXTRACT AND VALIDATE CUSTOMER INFORMATION
# ==================================================

def qualify_lead_node(state: LeadFlowState) -> dict:

    result = process_inquiry(state["inquiry"])

    return {
        "lead": result["lead"],
        "missing_fields": result["missing_fields"],
        "clarification_questions": result["clarification_questions"],
        "qualification_summary": result["qualification_summary"],
        "next_action": result["next_action"],
        "status": result["status"],
        "errors": [],
    }


# ==================================================
# 3. SAVE OR UPDATE CUSTOMER IN CRM
# ==================================================

def save_lead_node(state: LeadFlowState) -> dict:

    initialize_database()

    lead_id, operation = save_lead(state["lead"])

    update_lead_status(
        lead_id,
        state["status"],
    )

    update_lead_workflow(
        lead_id=lead_id,
        workflow_id=state["workflow_id"],
        approval_status="not_required",
        email_send_status="NOT_STARTED",
    )

    update_workflow_status(
        lead_id,
        "RUNNING",
    )

    log_action(
        lead_id,
        "LANGGRAPH_INFORMATION_CHECK",
        (
            f"Database operation: {operation}. "
            f"Missing fields: {state.get('missing_fields', [])}. "
            f"Next action: {state['next_action']}."
        ),
    )

    return {
        "lead_id": lead_id,
        "database_operation": operation,
        "workflow_status": "RUNNING",
    }


# ==================================================
# 4. CONDITIONAL ROUTER
# ==================================================

def route_lead(
    state: LeadFlowState,
) -> Literal["clarification", "email_generation"]:

    if state.get("missing_fields"):
        return "clarification"

    return "email_generation"


# ==================================================
# 5. CLARIFICATION NODE
# ==================================================

def clarification_node(state: LeadFlowState) -> dict:

    questions = state.get("clarification_questions", [])

    log_action(
        state["lead_id"],
        "CLARIFICATION_REQUIRED",
        "; ".join(questions),
    )

    update_email_workflow_status(
        state["lead_id"],
        approval_status="not_required",
        email_send_status="NOT_REQUIRED",
    )

    update_workflow_status(
        state["lead_id"],
        "WAITING_FOR_CUSTOMER",
        completed=False,
    )

    return {
        "approval_status": "not_required",
        "email_send_status": "NOT_REQUIRED",
        "workflow_status": "WAITING_FOR_CUSTOMER",
        "next_action": "REQUEST_CLARIFICATION",
    }


# ==================================================
# 6. GENERATE PERSONALIZED CUSTOMER EMAIL
# ==================================================

def email_generation_node(state: LeadFlowState) -> dict:

    draft = generate_followup_email(
        state["lead"],
        [],
    )

    if not isinstance(draft, dict):
        raise ValueError(
            "Email generator returned an invalid draft."
        )

    subject = str(
        draft.get("subject") or ""
    ).strip()

    body = str(
        draft.get("body") or ""
    ).strip()

    # Always use the verified CRM email.
    recipient = str(
        state["lead"].get("email") or ""
    ).strip().lower()

    if not recipient:
        raise ValueError("Customer email address is missing.")

    if not subject or not body:
        raise ValueError(
            "Generated email subject or body is empty."
        )

    draft["subject"] = subject
    draft["body"] = body
    draft["recipient"] = recipient
    draft["status"] = "READY_TO_SEND"

    save_email_draft(
        lead_id=state["lead_id"],
        workflow_id=state["workflow_id"],
        draft=draft,
    )

    update_email_workflow_status(
        state["lead_id"],
        approval_status="not_required",
        email_send_status="PENDING",
    )

    log_action(
        state["lead_id"],
        "EMAIL_DRAFT_GENERATED",
        "Personalized customer email generated automatically.",
    )

    return {
        "email_draft": draft,
        "approval_status": "not_required",
        "email_send_status": "PENDING",
        "next_action": "AUTOMATIC_EMAIL_SEND",
    }


# ==================================================
# 7. AUTOMATIC CUSTOMER EMAIL SENDING
# ==================================================

def send_email_node(state: LeadFlowState) -> dict:

    draft = state.get("email_draft")

    if not draft:
        raise ValueError("Email draft is missing.")

    recipient = str(
        draft.get("recipient") or ""
    ).strip().lower()

    crm_email = str(
        state["lead"].get("email") or ""
    ).strip().lower()

    if not recipient or recipient != crm_email:
        raise ValueError(
            "Email recipient does not match the CRM lead."
        )

    try:

        result = send_customer_email(
            lead_id=state["lead_id"],
            draft=draft,
            workflow_id=state["workflow_id"],
        )

        send_status = result.get("status", "FAILED")

        if send_status == "SENT":

            workflow_status = "COMPLETED"
            next_action = "WORKFLOW_COMPLETED"

        elif send_status == "DUPLICATE_BLOCKED":

            workflow_status = "DUPLICATE_BLOCKED"
            next_action = "DUPLICATE_BLOCKED"

        else:

            workflow_status = "FAILED"
            next_action = "EMAIL_FAILED"

        update_email_workflow_status(
            state["lead_id"],
            approval_status="not_required",
            email_send_status=send_status,
        )

        update_workflow_status(
            state["lead_id"],
            workflow_status,
            completed=True,
        )

        log_action(
            state["lead_id"],
            "EMAIL_EXECUTION_RESULT",
            (
                f"Email result: {send_status}. "
                f"Workflow status: {workflow_status}."
            ),
        )

        return {
            "email_send_status": send_status,
            "email_send_result": result,
            "workflow_status": workflow_status,
            "next_action": next_action,
        }

    except Exception as error:

        update_email_workflow_status(
            state["lead_id"],
            approval_status="not_required",
            email_send_status="FAILED",
        )

        update_workflow_status(
            state["lead_id"],
            "FAILED",
            completed=True,
        )

        log_action(
            state["lead_id"],
            "EMAIL_EXECUTION_FAILED",
            type(error).__name__,
        )

        return {
            "email_send_status": "FAILED",
            "email_send_result": {
                "status": "FAILED",
                "message": "Customer email could not be sent.",
            },
            "workflow_status": "FAILED",
            "errors": [type(error).__name__],
            "next_action": "EMAIL_FAILED",
        }


# ==================================================
# 8. BUILD AUTONOMOUS LANGGRAPH
# ==================================================

builder = StateGraph(LeadFlowState)

builder.add_node("qualify_lead", qualify_lead_node)
builder.add_node("save_lead", save_lead_node)
builder.add_node("clarification", clarification_node)
builder.add_node("email_generation", email_generation_node)
builder.add_node("send_email", send_email_node)

builder.add_edge(START, "qualify_lead")
builder.add_edge("qualify_lead", "save_lead")

builder.add_conditional_edges(
    "save_lead",
    route_lead,
    {
        "clarification": "clarification",
        "email_generation": "email_generation",
    },
)

builder.add_edge("clarification", END)
builder.add_edge("email_generation", "send_email")
builder.add_edge("send_email", END)

leadflow_graph = builder.compile(
    checkpointer=checkpointer
)


# ==================================================
# 9. START AUTONOMOUS WORKFLOW
# ==================================================

def run_leadflow(
    inquiry: str,
    workflow_id: Optional[str] = None,
) -> dict:

    workflow_id = workflow_id or str(uuid4())

    initial_state: LeadFlowState = {
        "inquiry": inquiry,
        "errors": [],
        "approval_status": "not_required",
        "email_send_status": "NOT_STARTED",
        "workflow_status": "RUNNING",
        "workflow_id": workflow_id,
    }

    config = {
        "configurable": {
            "thread_id": workflow_id,
        }
    }

    result = leadflow_graph.invoke(
        initial_state,
        config=config,
    )

    result["workflow_id"] = workflow_id

    return result
