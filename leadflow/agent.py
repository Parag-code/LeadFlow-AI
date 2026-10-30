from leadflow.llm import extract_lead


def process_inquiry(inquiry: str) -> dict:
    """
    Extract customer information and check required fields.

    No lead scoring or HOT/WARM/COLD classification.
    """

    analysis = extract_lead(inquiry)

    lead = analysis.lead

    if analysis.missing_fields:
        next_action = "REQUEST_CLARIFICATION"
        status = "NEEDS_INFORMATION"
    else:
        next_action = "CONTINUE_WORKFLOW"
        status = "QUALIFIED"

    return {
        "lead": lead.model_dump(),
        "missing_fields": analysis.missing_fields,
        "clarification_questions": analysis.clarification_questions,
        "qualification_summary": analysis.qualification_summary,
        "next_action": next_action,
        "status": status,
    }
