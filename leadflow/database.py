
import sqlite3
import json
from datetime import datetime, timezone

from leadflow.config import settings


# ==================================================
# 1. DATABASE CONNECTION
# ==================================================

def get_connection():

    settings.database_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        settings.database_file,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


# ==================================================
# 2. DATABASE INITIALIZATION & MIGRATION
# ==================================================

def initialize_database():

    with get_connection() as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT,
                company TEXT,
                business_type TEXT,
                requirement TEXT,
                additional_details TEXT,
                budget TEXT,
                timeline TEXT,
                intent TEXT,
                lead_status TEXT DEFAULT 'NEW',
                workflow_id TEXT,
                email_draft_json TEXT,
                approval_status TEXT DEFAULT 'not_required',
                email_send_status TEXT DEFAULT 'NOT_STARTED',
                workflow_status TEXT DEFAULT 'RUNNING',
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS email_send_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                workflow_id TEXT NOT NULL,
                recipient TEXT NOT NULL,
                status TEXT NOT NULL,
                provider_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(lead_id, workflow_id),
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            )
        """)

        # Safely migrate existing databases.
        existing_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(leads)"
            ).fetchall()
        }

        migrations = {
            "additional_details": "TEXT",
            "workflow_id": "TEXT",
            "email_draft_json": "TEXT",
            "approval_status": "TEXT DEFAULT 'not_required'",
            "email_send_status": "TEXT DEFAULT 'NOT_STARTED'",
            "workflow_status": "TEXT DEFAULT 'RUNNING'",
            "completed_at": "TEXT",
        }

        for column, definition in migrations.items():

            if column not in existing_columns:

                connection.execute(
                    f"ALTER TABLE leads ADD COLUMN {column} {definition}"
                )

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_leads_email
            ON leads(email)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_leads_workflow_id
            ON leads(workflow_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_lead_id
            ON audit_logs(lead_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_email_attempt_status
            ON email_send_attempts(status)
        """)


# ==================================================
# 3. LEAD RETRIEVAL
# ==================================================

def get_lead_by_email(email):

    if not email:
        return None

    with get_connection() as connection:

        lead = connection.execute("""
            SELECT *
            FROM leads
            WHERE LOWER(email) = LOWER(?)
            ORDER BY id DESC
            LIMIT 1
        """, (email.strip(),)).fetchone()

    return dict(lead) if lead else None


def get_lead_by_id(lead_id):

    with get_connection() as connection:

        lead = connection.execute(
            "SELECT * FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()

    if not lead:
        return None

    result = dict(lead)

    draft_json = result.get("email_draft_json")

    result["email_draft"] = (
        json.loads(draft_json)
        if draft_json
        else None
    )

    return result


def get_all_leads():

    with get_connection() as connection:

        rows = connection.execute("""
            SELECT *
            FROM leads
            ORDER BY created_at DESC
        """).fetchall()

    return [dict(row) for row in rows]


# ==================================================
# 4. SAVE OR UPDATE LEAD
# ==================================================

def save_lead(lead_data):

    email = lead_data.get("email")
    existing_lead = get_lead_by_email(email)

    now = current_timestamp()

    # Scoring fields are intentionally excluded.
    fields = [
        "name",
        "email",
        "company",
        "business_type",
        "requirement",
        "additional_details",
        "budget",
        "timeline",
        "intent",
    ]

    if existing_lead:

        updates = {}

        for field in fields:

            new_value = lead_data.get(field)

            updates[field] = (
                new_value
                if new_value is not None
                else existing_lead.get(field)
            )

        with get_connection() as connection:

            connection.execute("""
                UPDATE leads
                SET name = ?,
                    email = ?,
                    company = ?,
                    business_type = ?,
                    requirement = ?,
                    additional_details = ?,
                    budget = ?,
                    timeline = ?,
                    intent = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                updates["name"],
                updates["email"],
                updates["company"],
                updates["business_type"],
                updates["requirement"],
                updates["additional_details"],
                updates["budget"],
                updates["timeline"],
                updates["intent"],
                now,
                existing_lead["id"],
            ))

        log_action(
            existing_lead["id"],
            "LEAD_UPDATED",
            "Existing lead information updated.",
        )

        return existing_lead["id"], "updated"

    values = [lead_data.get(field) for field in fields]

    with get_connection() as connection:

        cursor = connection.execute("""
            INSERT INTO leads (
                name,
                email,
                company,
                business_type,
                requirement,
                additional_details,
                budget,
                timeline,
                intent,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (*values, now, now))

        lead_id = cursor.lastrowid

    log_action(
        lead_id,
        "LEAD_CREATED",
        "New lead created.",
    )

    return lead_id, "created"


# ==================================================
# 5. WORKFLOW TRACKING
# ==================================================

def update_lead_workflow(
    lead_id,
    workflow_id,
    approval_status="not_required",
    email_send_status="NOT_STARTED",
    workflow_status="RUNNING",
):
    """Store the latest workflow and clear any previous workflow draft."""

    now = current_timestamp()

    with get_connection() as connection:

        cursor = connection.execute("""
            UPDATE leads
            SET email_draft_json =
                    CASE
                        WHEN workflow_id IS NULL OR workflow_id != ?
                        THEN NULL
                        ELSE email_draft_json
                    END,
                workflow_id = ?,
                approval_status = ?,
                email_send_status = ?,
                workflow_status = ?,
                completed_at = NULL,
                updated_at = ?
            WHERE id = ?
        """, (
            workflow_id,
            workflow_id,
            approval_status,
            email_send_status,
            workflow_status,
            now,
            lead_id,
        ))

        if cursor.rowcount == 0:
            raise ValueError(f"Lead ID {lead_id} not found.")

    log_action(
        lead_id,
        "WORKFLOW_STARTED",
        f"Workflow ID: {workflow_id}",
    )


def get_lead_by_workflow_id(workflow_id):

    with get_connection() as connection:

        lead = connection.execute("""
            SELECT *
            FROM leads
            WHERE workflow_id = ?
            LIMIT 1
        """, (workflow_id,)).fetchone()

    return dict(lead) if lead else None


def update_workflow_status(
    lead_id,
    workflow_status,
    completed=False,
):
    """Update workflow execution status."""

    allowed_statuses = {
        "RUNNING",
        "WAITING_FOR_INFORMATION",
        "WAITING_FOR_CUSTOMER",
        "COMPLETED",
        "DRY_RUN_COMPLETED",
        "DUPLICATE_BLOCKED",
        "FAILED",
    }

    if workflow_status not in allowed_statuses:
        raise ValueError(
            f"Invalid workflow status: {workflow_status}"
        )

    now = current_timestamp()
    completed_at = now if completed else None

    with get_connection() as connection:

        cursor = connection.execute("""
            UPDATE leads
            SET workflow_status = ?,
                completed_at = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            workflow_status,
            completed_at,
            now,
            lead_id,
        ))

        if cursor.rowcount == 0:
            raise ValueError(f"Lead ID {lead_id} not found.")

    log_action(
        lead_id,
        "WORKFLOW_STATUS_UPDATED",
        f"Workflow status: {workflow_status}",
    )


# ==================================================
# 6. EMAIL DRAFT PERSISTENCE
# ==================================================

def save_email_draft(lead_id, workflow_id, draft):

    if not isinstance(draft, dict):
        raise ValueError("Email draft must be a dictionary.")

    for field in ["recipient", "subject", "body"]:

        if not draft.get(field):
            raise ValueError(f"Email draft is missing {field}.")

    draft_json = json.dumps(
        draft,
        ensure_ascii=False,
    )

    now = current_timestamp()

    with get_connection() as connection:

        cursor = connection.execute("""
            UPDATE leads
            SET workflow_id = ?,
                email_draft_json = ?,
                approval_status = 'not_required',
                email_send_status = 'PENDING',
                workflow_status = 'RUNNING',
                updated_at = ?
            WHERE id = ?
        """, (
            workflow_id,
            draft_json,
            now,
            lead_id,
        ))

        if cursor.rowcount == 0:
            raise ValueError(f"Lead ID {lead_id} not found.")

    log_action(
        lead_id,
        "EMAIL_DRAFT_SAVED",
        "Personalized email draft saved.",
    )


def get_email_draft(lead_id):

    with get_connection() as connection:

        row = connection.execute("""
            SELECT email_draft_json
            FROM leads
            WHERE id = ?
        """, (lead_id,)).fetchone()

    if not row or not row["email_draft_json"]:
        return None

    return json.loads(row["email_draft_json"])


def get_pending_email_approvals():
    """Legacy compatibility; autonomous workflows do not use approvals."""

    with get_connection() as connection:

        rows = connection.execute("""
            SELECT *
            FROM leads
            WHERE approval_status = 'pending'
            ORDER BY updated_at DESC
        """).fetchall()

    results = []

    for row in rows:

        lead = dict(row)

        lead["email_draft"] = (
            json.loads(lead["email_draft_json"])
            if lead.get("email_draft_json")
            else None
        )

        results.append(lead)

    return results


# ==================================================
# 7. EMAIL SEND IDEMPOTENCY
# ==================================================

def claim_email_send(
    lead_id,
    workflow_id,
    recipient,
):
    """
    Atomically claim one email send attempt per lead/workflow.

    Returns False if the workflow was already claimed.
    """

    now = current_timestamp()

    with get_connection() as connection:

        connection.execute("BEGIN IMMEDIATE")

        cursor = connection.execute("""
            INSERT OR IGNORE INTO email_send_attempts (
                lead_id,
                workflow_id,
                recipient,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'SENDING', ?, ?)
        """, (
            lead_id,
            workflow_id,
            recipient,
            now,
            now,
        ))

        claimed = cursor.rowcount == 1

    if not claimed:

        log_action(
            lead_id,
            "DUPLICATE_EMAIL_BLOCKED",
            f"Workflow already attempted email send: {workflow_id}",
        )

    return claimed


def complete_email_send(
    lead_id,
    workflow_id,
    status,
    provider_message="",
):
    """Record the outcome of a claimed email send."""

    allowed_statuses = {
        "SENT",
        "FAILED",
        "UNKNOWN",
    }

    if status not in allowed_statuses:
        raise ValueError("Invalid email attempt status.")

    now = current_timestamp()

    with get_connection() as connection:

        cursor = connection.execute("""
            UPDATE email_send_attempts
            SET status = ?,
                provider_message = ?,
                updated_at = ?
            WHERE lead_id = ?
              AND workflow_id = ?
              AND status = 'SENDING'
        """, (
            status,
            provider_message,
            now,
            lead_id,
            workflow_id,
        ))

        if cursor.rowcount == 0:
            raise ValueError("No active email send attempt found.")


def get_email_send_attempts(lead_id):

    with get_connection() as connection:

        rows = connection.execute("""
            SELECT *
            FROM email_send_attempts
            WHERE lead_id = ?
            ORDER BY created_at DESC
        """, (lead_id,)).fetchall()

    return [dict(row) for row in rows]


# ==================================================
# 8. EMAIL STATUS MANAGEMENT
# ==================================================

def update_email_workflow_status(
    lead_id,
    approval_status=None,
    email_send_status=None,
):

    updates = []
    values = []

    if approval_status is not None:

        updates.append("approval_status = ?")
        values.append(approval_status)

    if email_send_status is not None:

        updates.append("email_send_status = ?")
        values.append(email_send_status)

    if not updates:
        return

    updates.append("updated_at = ?")
    values.append(current_timestamp())
    values.append(lead_id)

    with get_connection() as connection:

        cursor = connection.execute(
            f"""
            UPDATE leads
            SET {", ".join(updates)}
            WHERE id = ?
            """,
            values,
        )

        if cursor.rowcount == 0:
            raise ValueError(f"Lead ID {lead_id} not found.")


# ==================================================
# 9. AUDIT LOGGING
# ==================================================

def log_action(lead_id, action, details=""):

    now = current_timestamp()

    with get_connection() as connection:

        connection.execute("""
            INSERT INTO audit_logs (
                lead_id,
                action,
                details,
                created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            lead_id,
            action,
            details,
            now,
        ))


def get_audit_logs(lead_id):

    with get_connection() as connection:

        rows = connection.execute("""
            SELECT *
            FROM audit_logs
            WHERE lead_id = ?
            ORDER BY created_at DESC
        """, (lead_id,)).fetchall()

    return [dict(row) for row in rows]


def get_email_history(lead_id):

    email_actions = (
        "EMAIL_DRAFT_SAVED",
        "EMAIL_DRAFT_GENERATED",
        "CUSTOMER_EMAIL_SENT",
        "CUSTOMER_EMAIL_FAILED",
        "EMAIL_EXECUTION_RESULT",
        "EMAIL_EXECUTION_FAILED",
        "DUPLICATE_EMAIL_BLOCKED",
    )

    placeholders = ",".join("?" for _ in email_actions)

    with get_connection() as connection:

        rows = connection.execute(
            f"""
            SELECT *
            FROM audit_logs
            WHERE lead_id = ?
              AND action IN ({placeholders})
            ORDER BY created_at DESC
            """,
            (lead_id, *email_actions),
        ).fetchall()

    return [dict(row) for row in rows]


# ==================================================
# 10. LEAD STATUS MANAGEMENT
# ==================================================

def update_lead_status(lead_id, status):

    allowed_statuses = {
        "NEW",
        "NEEDS_INFORMATION",
        "QUALIFIED",
    }

    if status not in allowed_statuses:
        raise ValueError("Invalid lead status.")

    now = current_timestamp()

    with get_connection() as connection:

        cursor = connection.execute("""
            UPDATE leads
            SET lead_status = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            status,
            now,
            lead_id,
        ))

        if cursor.rowcount == 0:
            raise ValueError(f"Lead ID {lead_id} not found.")

    log_action(
        lead_id,
        "STATUS_UPDATED",
        f"Lead status changed to {status}.",
    )
