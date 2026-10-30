
import json

import pandas as pd
import streamlit as st

from leadflow.database import (
    initialize_database,
    get_all_leads,
    get_lead_by_id,
    get_audit_logs,
)


# ==================================================
# 1. PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="LeadFlow AI Dashboard",
    page_icon="🚀",
    layout="wide",
)

initialize_database()

st.title("🚀 LeadFlow AI")
st.caption(
    "Autonomous Lead Information Validation, CRM "
    "& Email Automation"
)

if st.button("🔄 Refresh Dashboard"):
    st.rerun()


# ==================================================
# 2. LOAD CRM DATA
# ==================================================

leads = get_all_leads()


def get_customer_status(lead):
    """Convert internal workflow status into simple CRM status."""

    lead_status = lead.get("lead_status")
    workflow_status = lead.get("workflow_status")

    if (
        lead_status == "NEEDS_INFORMATION"
        or workflow_status in (
            "WAITING_FOR_CUSTOMER",
            "WAITING_FOR_INFORMATION",
        )
    ):
        return "Needs Information"

    if workflow_status == "COMPLETED":
        return "Completed"

    return "Processing"


def get_email_status(lead):
    """Convert internal email status into simple display status."""

    status = (lead.get("email_send_status") or "").upper()

    if status == "SENT":
        return "Sent"

    if status in ("FAILED", "DUPLICATE_BLOCKED"):
        return "Failed"

    return "Pending"


total_leads = len(leads)

awaiting_information = sum(
    get_customer_status(lead) == "Needs Information"
    for lead in leads
)

sent_emails = sum(
    get_email_status(lead) == "Sent"
    for lead in leads
)

failed_emails = sum(
    get_email_status(lead) == "Failed"
    for lead in leads
)


# ==================================================
# 3. CRM OVERVIEW
# ==================================================

st.subheader("📊 CRM Overview")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Total Leads",
    total_leads,
)

col2.metric(
    "Awaiting Information",
    awaiting_information,
)

col3.metric(
    "Emails Sent",
    sent_emails,
)

col4.metric(
    "Failed Emails",
    failed_emails,
)

st.divider()


# ==================================================
# 4. CRM LEADS TABLE
# ==================================================

st.subheader("👥 CRM — All Leads")

if leads:

    crm_records = []

    for lead in leads:

        crm_records.append({
            "Lead ID": lead.get("id"),
            "Customer Name": lead.get("name") or "N/A",
            "Email": lead.get("email") or "N/A",
            "Company": lead.get("company") or "N/A",
            "Requirement": lead.get("requirement") or "N/A",
            "Budget": lead.get("budget") or "N/A",
            "Timeline": lead.get("timeline") or "N/A",
            "Customer Status": get_customer_status(lead),
            "Email Status": get_email_status(lead),
        })

    crm_df = pd.DataFrame(crm_records)

    st.dataframe(
        crm_df,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info(
        "No leads available. Submit a customer inquiry "
        "through the FastAPI customer form."
    )

st.divider()


# ==================================================
# 5. LEAD DETAILS
# ==================================================

st.subheader("🔎 Lead Details")

if leads:

    lead_ids = [lead["id"] for lead in leads]

    selected_lead_id = st.selectbox(
        "Select Lead",
        lead_ids,
        format_func=lambda lead_id: (
            f"Lead #{lead_id} — "
            f"{next(
                (
                    lead.get('name')
                    for lead in leads
                    if lead.get('id') == lead_id
                ),
                'Unknown'
            )}"
        ),
        key="details_lead_id",
    )

    selected_lead = get_lead_by_id(selected_lead_id)

    if selected_lead:

        # ------------------------------------------
        # Status Overview
        # ------------------------------------------

        st.markdown("### 📌 Lead Status")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Customer Status",
            get_customer_status(selected_lead),
        )

        col2.metric(
            "Workflow Status",
            selected_lead.get("workflow_status") or "N/A",
        )

        col3.metric(
            "Email Status",
            get_email_status(selected_lead),
        )

        st.divider()

        # ------------------------------------------
        # Customer Information
        # ------------------------------------------

        st.markdown("### 👤 Customer Information")

        col1, col2 = st.columns(2)

        with col1:

            st.write(
                "**Customer Name:**",
                selected_lead.get("name") or "N/A",
            )

            st.write(
                "**Email:**",
                selected_lead.get("email") or "N/A",
            )

            st.write(
                "**Company:**",
                selected_lead.get("company") or "N/A",
            )

            st.write(
                "**Business Type:**",
                selected_lead.get("business_type") or "N/A",
            )

        with col2:

            st.write(
                "**Requirement:**",
                selected_lead.get("requirement") or "N/A",
            )

            st.write(
                "**Budget:**",
                selected_lead.get("budget") or "N/A",
            )

            st.write(
                "**Timeline:**",
                selected_lead.get("timeline") or "N/A",
            )

            st.write(
                "**Intent:**",
                selected_lead.get("intent") or "N/A",
            )

        # ------------------------------------------
        # Additional Customer Details
        # ------------------------------------------

        st.markdown("### 📝 Additional Customer Details")

        additional_details = (
            selected_lead.get("additional_details") or ""
        ).strip()

        if additional_details:

            st.text_area(
                "Customer-provided Details",
                value=additional_details,
                height=150,
                disabled=True,
                key=f"additional_details_{selected_lead_id}",
            )

        else:

            st.info("No additional customer details provided.")

        # ------------------------------------------
        # Workflow Information
        # ------------------------------------------

        st.markdown("### ⚙️ Workflow Information")

        st.write(
            "**Workflow ID:**",
            selected_lead.get("workflow_id") or "N/A",
        )

        st.write(
            "**Created At:**",
            selected_lead.get("created_at") or "N/A",
        )

        st.write(
            "**Updated At:**",
            selected_lead.get("updated_at") or "N/A",
        )

        st.write(
            "**Completed At:**",
            selected_lead.get("completed_at") or "N/A",
        )

        # ------------------------------------------
        # Generated Email
        # ------------------------------------------

        st.markdown("### 📧 Generated Customer Email")

        email_draft = (
            selected_lead.get("email_draft")
            or selected_lead.get("email_draft_json")
        )

        if email_draft:

            if isinstance(email_draft, str):

                try:
                    email_draft = json.loads(email_draft)

                except (ValueError, TypeError):
                    email_draft = None

            if isinstance(email_draft, dict):

                st.write(
                    "**Recipient:**",
                    email_draft.get("recipient", "N/A"),
                )

                st.write(
                    "**Subject:**",
                    email_draft.get("subject", "N/A"),
                )

                st.text_area(
                    "Email Body",
                    value=email_draft.get("body", ""),
                    height=250,
                    disabled=True,
                    key=f"email_body_{selected_lead_id}",
                )

                st.caption(
                    "Email generation and delivery are handled "
                    "automatically by the LeadFlow workflow."
                )

            else:

                st.info("No readable email content available.")

        else:

            st.info(
                "Email has not been generated for this lead yet."
            )

else:

    st.info("No lead details available.")

st.divider()


# ==================================================
# 6. AUDIT HISTORY
# ==================================================

st.subheader("📜 Lead Activity History")

if leads:

    selected_history_id = st.selectbox(
        "Select Lead for Activity History",
        [lead["id"] for lead in leads],
        key="history_lead",
    )

    history = get_audit_logs(selected_history_id)

    if history:

        history_df = pd.DataFrame(history)

        st.dataframe(
            history_df,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info("No activity history available for this lead.")

else:

    st.info("No lead history available.")

st.divider()


# ==================================================
# 7. SYSTEM INFORMATION
# ==================================================

st.subheader("⚙️ System Information")

col1, col2 = st.columns(2)

with col1:

    st.write("**Lead Acquisition:** FastAPI Customer Form")
    st.write("**AI Information Extraction:** Groq LLM")
    st.write("**Information Validation:** Pydantic")
    st.write("**Workflow Orchestration:** LangGraph")

with col2:

    st.write("**CRM Database:** SQLite")
    st.write("**Email Generation:** Groq LLM")
    st.write("**Email Provider:** Gmail SMTP")
    st.write("**Dashboard:** Streamlit")
    st.write("**Workflow Persistence:** SQLite Checkpointing")
