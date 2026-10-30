from leadflow.agent import process_inquiry

from leadflow.database import (
    initialize_database,
    save_lead,
    log_action,
    update_lead_status
)


def process_and_save_lead(inquiry: str) -> dict:
    """
    Process inquiry, qualify lead and synchronize CRM status.
    """

    initialize_database()

    result = process_inquiry(inquiry)

    lead_data = result["lead"]

    lead_id, operation = save_lead(lead_data)

    update_lead_status(
        lead_id,
        result["status"]
    )

    log_action(
        lead_id,
        "LEAD_QUALIFIED",
        (
            f"Score: {result['score']}, "
            f"Category: {result['category']}, "
            f"Next action: {result['next_action']}"
        )
    )

    result["lead_id"] = lead_id
    result["database_operation"] = operation

    return result