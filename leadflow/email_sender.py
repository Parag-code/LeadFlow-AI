
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr

from leadflow.config import settings

from leadflow.database import (
    log_action,
    get_audit_logs,
    claim_email_send,
    complete_email_send,
)


# ==================================================
# 1. EMAIL VALIDATION
# ==================================================

def validate_email_address(email: str) -> str:

    email = str(email or "").strip().lower()

    _, parsed_email = parseaddr(email)

    if not parsed_email or parsed_email != email:
        raise ValueError("Invalid email address.")

    if "@" not in email:
        raise ValueError("Invalid email address.")

    blocked_domains = {
        "example.com",
        "example.org",
        "example.net",
        "test.com",
        "localhost",
    }

    domain = email.rsplit("@", 1)[-1]

    if domain in blocked_domains or domain.endswith(".test"):
        raise ValueError(
            "Sending to reserved test email domains is disabled."
        )

    return email


# ==================================================
# 2. DUPLICATE EMAIL CHECK
# ==================================================

def email_already_sent(
    lead_id: int,
    recipient: str,
) -> bool:

    recipient = recipient.strip().lower()

    logs = get_audit_logs(lead_id)

    sent_actions = {
        "CUSTOMER_EMAIL_SENT",
        "TEST_EMAIL_SENT",
    }

    for log in logs:

        if log.get("action") not in sent_actions:
            continue

        details = str(log.get("details") or "").lower()

        if recipient in details:
            return True

    return False


# ==================================================
# 3. GMAIL SMTP CONFIGURATION
# ==================================================

def create_smtp_connection():

    if not settings.GMAIL_ADDRESS:
        raise ValueError("GMAIL_ADDRESS is missing in .env")

    if not settings.GMAIL_APP_PASSWORD:
        raise ValueError("GMAIL_APP_PASSWORD is missing in .env")

    smtp = smtplib.SMTP_SSL(
        "smtp.gmail.com",
        465,
        timeout=20,
    )

    try:
        smtp.login(
            settings.GMAIL_ADDRESS,
            settings.GMAIL_APP_PASSWORD,
        )
        return smtp

    except Exception:
        smtp.close()
        raise


# ==================================================
# 4. AUTOMATIC CUSTOMER EMAIL
# ==================================================

def send_customer_email(
    lead_id: int,
    draft: dict,
    workflow_id: str | None = None,
) -> dict:
    """
    Send a personalized customer email through Gmail SMTP.

    No dry-run mode is supported.
    Each lead/workflow combination can claim one send attempt.
    """

    if not isinstance(draft, dict):
        raise ValueError("Invalid email draft.")

    recipient = validate_email_address(
        draft.get("recipient", "")
    )

    subject = str(draft.get("subject") or "").strip()
    body = str(draft.get("body") or "").strip()

    if not subject:
        raise ValueError("Email subject is required.")

    if not body:
        raise ValueError("Email body is required.")

    if len(subject) > 250:
        raise ValueError("Email subject is too long.")

    if len(body) > 15000:
        raise ValueError("Email body is too long.")

    sender = validate_email_address(
        settings.GMAIL_ADDRESS
    )

    if not settings.GMAIL_APP_PASSWORD:
        raise ValueError("GMAIL_APP_PASSWORD is missing in .env")

    workflow_id = str(
        workflow_id or f"legacy-lead-{lead_id}"
    ).strip()

    if not workflow_id:
        raise ValueError("Workflow ID is required.")

    # ---------------------------------------------
    # 1. CHECK PREVIOUS SUCCESSFUL SEND
    # ---------------------------------------------

    if email_already_sent(lead_id, recipient):

        log_action(
            lead_id,
            "DUPLICATE_EMAIL_BLOCKED",
            f"Previously sent email blocked for {recipient}.",
        )

        return {
            "success": False,
            "status": "DUPLICATE_BLOCKED",
            "recipient": recipient,
            "workflow_id": workflow_id,
        }

    # ---------------------------------------------
    # 2. ATOMIC DATABASE CLAIM
    # ---------------------------------------------

    claimed = claim_email_send(
        lead_id=lead_id,
        workflow_id=workflow_id,
        recipient=recipient,
    )

    if not claimed:

        log_action(
            lead_id,
            "DUPLICATE_EMAIL_BLOCKED",
            (
                f"Email attempt already exists for "
                f"workflow {workflow_id}."
            ),
        )

        return {
            "success": False,
            "status": "DUPLICATE_BLOCKED",
            "recipient": recipient,
            "workflow_id": workflow_id,
        }

    # ---------------------------------------------
    # 3. CREATE EMAIL MESSAGE
    # ---------------------------------------------

    message = EmailMessage()

    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient

    message.set_content(body)

    # ---------------------------------------------
    # 4. SEND EMAIL THROUGH GMAIL SMTP
    # ---------------------------------------------

    try:

        with create_smtp_connection() as smtp:
            smtp.send_message(message)

        complete_email_send(
            lead_id=lead_id,
            workflow_id=workflow_id,
            status="SENT",
            provider_message="Gmail SMTP accepted the message.",
        )

        log_action(
            lead_id,
            "CUSTOMER_EMAIL_SENT",
            (
                f"SMTP accepted email for {recipient}. "
                f"Workflow: {workflow_id}. "
                f"Subject: {subject}"
            ),
        )

        return {
            "success": True,
            "status": "SENT",
            "recipient": recipient,
            "workflow_id": workflow_id,
            "message": "Gmail SMTP accepted the email.",
        }

    except Exception as error:

        try:

            complete_email_send(
                lead_id=lead_id,
                workflow_id=workflow_id,
                status="FAILED",
                provider_message=type(error).__name__,
            )

        except Exception:

            log_action(
                lead_id,
                "EMAIL_LEDGER_UPDATE_FAILED",
                f"Workflow: {workflow_id}",
            )

        log_action(
            lead_id,
            "CUSTOMER_EMAIL_FAILED",
            (
                f"Email attempt failed for {recipient}. "
                f"Workflow: {workflow_id}. "
                f"Error: {type(error).__name__}"
            ),
        )

        raise RuntimeError(
            f"Customer email sending failed: {type(error).__name__}"
        ) from error


# ==================================================
# 5. LEGACY APPROVED EMAIL FUNCTION
# ==================================================

def send_approved_email(
    lead_id: int,
    draft: dict,
    test_recipient: str,
) -> dict:
    """
    Legacy compatibility function.
    Requires an explicitly approved draft.
    """

    if not isinstance(draft, dict):
        raise ValueError("Invalid email draft.")

    if draft.get("status") != "APPROVED":
        raise ValueError(
            "Email must be approved before test sending."
        )

    recipient = validate_email_address(test_recipient)

    test_draft = dict(draft)
    test_draft["recipient"] = recipient

    return send_customer_email(
        lead_id=lead_id,
        draft=test_draft,
        workflow_id=f"legacy-test-lead-{lead_id}",
    )
