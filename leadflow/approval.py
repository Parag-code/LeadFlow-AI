from leadflow.database import log_action


def review_email_draft(
    lead_id: int,
    draft: dict,
    approved: bool,
    edited_subject: str | None = None,
    edited_body: str | None = None
) -> dict:
    """
    Review an email draft.
    Explicit approval is required before sending.
    This function does not send emails.
    """

    if not isinstance(approved, bool):
        raise ValueError("Approval must be True or False.")

    if not draft.get("recipient"):
        raise ValueError("Email recipient is missing.")

    if approved:
        subject = (
            edited_subject.strip()
            if edited_subject is not None
            else draft.get("subject", "").strip()
        )

        body = (
            edited_body.strip()
            if edited_body is not None
            else draft.get("body", "").strip()
        )

        if not subject or not body:
            raise ValueError("Email subject and body are required.")

        reviewed_draft = {
            **draft,
            "subject": subject,
            "body": body,
            "status": "APPROVED"
        }

        log_action(
            lead_id,
            "EMAIL_APPROVED",
            f"Email draft approved for {draft['recipient']}."
        )

        return reviewed_draft

    log_action(
        lead_id,
        "EMAIL_REJECTED",
        f"Email draft rejected for {draft['recipient']}."
    )

    return {
        **draft,
        "status": "REJECTED"
    }