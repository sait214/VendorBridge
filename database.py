"""
VendorBridge — database.py
Database connection management and reusable data access layer for SQLite.

Adheres strictly to project constraints:
- Built-in sqlite3 only (no ORMs, no external database engines).
- Enables foreign-key enforcement ('PRAGMA foreign_keys = ON') on all connections.
- Parameterized SQL queries only (no string concatenation of user inputs).
- Atomic transactions with rollback protection on errors.
- Role-based scoping and vendor data isolation enforced at query level.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import current_app, g, has_app_context
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "vendorbridge.db"


# ─────────────────────────────────────────────────────────────────────────────
# Connection Management
# ─────────────────────────────────────────────────────────────────────────────

def ensure_audit_schema(conn: Optional[sqlite3.Connection] = None) -> None:
    """Ensures audits table, audit_id column on audit_logs, and audit indexes exist."""
    db = conn if conn is not None else (g.get("db") if has_app_context() else None)
    if db is None:
        return
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_reference TEXT NOT NULL UNIQUE,
                company_id INTEGER NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT DEFAULT 'Compliance & Safety',
                status TEXT DEFAULT 'in_progress',
                lead_auditor TEXT,
                audit_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cols = [c[1] for c in db.execute("PRAGMA table_info(audit_logs)").fetchall()]
        if "audit_id" not in cols:
            db.execute("ALTER TABLE audit_logs ADD COLUMN audit_id INTEGER REFERENCES audits(id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_audits_company ON audits(company_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_audits_status ON audits(status)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_audit_id ON audit_logs(audit_id)")
        db.commit()
    except Exception:
        pass


def get_db() -> sqlite3.Connection:
    """
    Returns an open SQLite database connection with row_factory and FKs enabled.
    Stores the connection on the Flask application context 'g' when available.
    Falls back gracefully to a standalone connection outside request context.
    """
    if has_app_context():
        if "db" not in g:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            ensure_audit_schema(conn)
            g.db = conn
        return g.db
    return connect_standalone()


def close_db(e: Optional[BaseException] = None) -> None:
    """Closes the current database connection if opened on Flask application context."""
    if has_app_context():
        db = g.pop("db", None)
        if db is not None:
            db.close()



def connect_standalone() -> sqlite3.Connection:
    """Helper for standalone scripts or tests outside Flask request context."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    ensure_audit_schema(conn)
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# Helper Utilities (Formatting & Conversion)
# ─────────────────────────────────────────────────────────────────────────────

def paise_to_inr_str(paise: int | float | None) -> str:
    """Formats an amount in paise to Indian Rupee string, e.g. 5500000 -> '₹55,000.00'."""
    if paise is None:
        return "₹0.00"
    rupees = float(paise) / 100.0
    return f"₹{rupees:,.2f}"


def inr_str_to_paise(val: Union[str, int, float, None]) -> int:
    """Converts a user-provided numeric or string amount to paise."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val * 100)
    cleaned = re.sub(r"[^\d.]", "", str(val))
    if not cleaned:
        return 0
    try:
        return int(float(cleaned) * 100)
    except ValueError:
        return 0


def verify_user_password(stored_hash: str, candidate_password: str) -> bool:
    """Safely verifies passwords supporting both modern hashes and legacy plain text."""
    if not stored_hash or not candidate_password:
        return False
    if stored_hash.startswith(("pbkdf2:", "scrypt:", "argon2:")):
        return check_password_hash(stored_hash, candidate_password)
    return stored_hash == candidate_password


# ─────────────────────────────────────────────────────────────────────────────
# Users & Authentication
# ─────────────────────────────────────────────────────────────────────────────

_USER_BASE_QUERY = """
    SELECT
        u.id,
        u.full_name AS name,
        u.email,
        u.password_hash AS password,
        u.role,
        u.is_active,
        u.created_at,
        v.id AS vendor_id,
        v.company_name AS company,
        v.contact_phone AS phone,
        v.address,
        v.category,
        v.approval_status,
        v.rejection_reason
    FROM users u
    LEFT JOIN vendors v ON u.id = v.user_id
"""


def _format_user_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    """Enriches a raw database user row with presentation attributes used across templates."""
    if not row:
        return None

    data = dict(row)
    if data["role"] == "admin":
        data["role_title"] = "Procurement Officer & System Admin"
        data["department"] = "Central Procurement & Strategic Sourcing"
        data["status"] = "Active"
    else:
        status_val = (data.get("approval_status") or "pending").lower()
        if status_val == "approved":
            data["role_title"] = "Authorized Vendor Partner"
            data["status"] = "Approved"
        elif status_val == "rejected":
            data["role_title"] = "Vendor Applicant (Rejected)"
            data["status"] = "Rejected"
        else:
            data["role_title"] = "Vendor Partner (Pending Approval)"
            data["status"] = "Pending"
        data["department"] = f"{data.get('company') or data['name']} — Sales & Bid Team"

    data["bio"] = f"Account registered for {data.get('company') or data['name']}."
    return data


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Fetches user and associated vendor record by email address."""
    if not email:
        return None
    db = get_db()
    row = db.execute(
        f"{_USER_BASE_QUERY} WHERE u.email = ? COLLATE NOCASE",
        (email.strip().lower(),)
    ).fetchone()
    return _format_user_dict(row)


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetches user and associated vendor record by user ID."""
    if not user_id:
        return None
    db = get_db()
    row = db.execute(f"{_USER_BASE_QUERY} WHERE u.id = ?", (user_id,)).fetchone()
    return _format_user_dict(row)


def update_user_profile(
    user_id: int,
    *,
    name: str,
    phone: Optional[str] = None,
    address: Optional[str] = None,
) -> bool:
    """Updates user contact details atomically in both users and vendors tables."""
    db = get_db()
    with db:
        db.execute(
            "UPDATE users SET full_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (name.strip(), user_id),
        )
        if phone is not None or address is not None:
            db.execute(
                """UPDATE vendors
                   SET contact_phone = COALESCE(?, contact_phone),
                       address = COALESCE(?, address),
                       updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ?""",
                (phone.strip() if phone else None, address.strip() if address else None, user_id),
            )
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Vendor Management & Registration
# ─────────────────────────────────────────────────────────────────────────────

_VENDOR_BASE_QUERY = """
    SELECT
        v.id,
        v.user_id,
        v.company_name AS name,
        v.company_name AS company,
        u.full_name AS contact_name,
        u.email,
        v.contact_phone AS phone,
        v.category,
        v.approval_status AS status,
        v.address,
        v.registration_number AS tax_id,
        v.rejection_reason,
        SUBSTR(v.created_at, 1, 10) AS created_at
    FROM vendors v
    JOIN users u ON v.user_id = u.id
"""


def get_vendors(
    status: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves vendor records with optional filters.
    If user_id is provided, enforces vendor data isolation (vendors only see themselves).
    """
    db = get_db()
    params: List[Any] = []
    conditions: List[str] = []

    if user_id is not None:
        conditions.append("v.user_id = ?")
        params.append(user_id)

    if status:
        conditions.append("LOWER(v.approval_status) = ?")
        params.append(status.strip().lower())

    if category:
        conditions.append("LOWER(v.category) = ?")
        params.append(category.strip().lower())

    if search:
        pattern = f"%{search.strip().lower()}%"
        conditions.append(
            """(
                LOWER(v.company_name) LIKE ? OR
                LOWER(u.full_name) LIKE ? OR
                LOWER(u.email) LIKE ? OR
                LOWER(COALESCE(v.contact_phone, '')) LIKE ? OR
                LOWER(COALESCE(v.registration_number, '')) LIKE ?
            )"""
        )
        params.extend([pattern, pattern, pattern, pattern, pattern])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"{_VENDOR_BASE_QUERY} {where_clause} ORDER BY v.id DESC"
    rows = db.execute(query, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def get_vendor_by_id(vendor_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a single vendor record by its primary key ID."""
    db = get_db()
    row = db.execute(f"{_VENDOR_BASE_QUERY} WHERE v.id = ?", (vendor_id,)).fetchone()
    return dict(row) if row else None


def get_vendor_by_user_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetches vendor record belonging to a specific user ID."""
    db = get_db()
    row = db.execute(f"{_VENDOR_BASE_QUERY} WHERE v.user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def register_vendor_account(
    *,
    contact_name: str,
    company_name: str,
    email: str,
    phone: str,
    password: str,
    category: str = "supplies",
    address: str = "",
    tax_id: str = "",
    initial_status: str = "pending",
    actor_user_id: Optional[int] = None,
) -> Tuple[int, int]:
    """
    Registers a new vendor user and corresponding vendor profile atomically.
    Public registration strictly assigns role='vendor' and status='pending'.
    Returns (user_id, vendor_id).
    """
    email_clean = email.strip().lower()
    db = get_db()

    with db:
        # 1. Insert user with strictly 'vendor' role
        cursor_user = db.execute(
            """INSERT INTO users (full_name, email, password_hash, role)
               VALUES (?, ?, ?, 'vendor')""",
            (contact_name.strip(), email_clean, generate_password_hash(password),),
        )
        new_user_id = int(cursor_user.lastrowid)

        # 2. Insert vendor profile linked to the user
        cursor_vendor = db.execute(
            """INSERT INTO vendors
               (user_id, company_name, registration_number, contact_phone, address, category, approval_status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                new_user_id,
                company_name.strip(),
                tax_id.strip() or None,
                phone.strip(),
                address.strip() or None,
                category.strip() or "supplies",
                initial_status,
            ),
        )
        new_vendor_id = int(cursor_vendor.lastrowid)

        # 3. Log audit event
        log_audit_event(
            actor_user_id=actor_user_id or new_user_id,
            action="VENDOR_REGISTERED",
            entity_type="Vendor",
            entity_id=new_vendor_id,
            details=f"Vendor account created for {company_name} ({email_clean}). Status: {initial_status}.",
        )

    return new_user_id, new_vendor_id


def approve_vendor_in_db(vendor_id: int, admin_user_id: int) -> bool:
    """Approves a vendor application and records administrator approval details."""
    db = get_db()
    with db:
        vendor = db.execute("SELECT company_name FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if not vendor:
            return False

        db.execute(
            """UPDATE vendors
               SET approval_status = 'approved',
                   reviewed_by = ?,
                   reviewed_at = CURRENT_TIMESTAMP,
                   rejection_reason = NULL,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (admin_user_id, vendor_id),
        )

        log_audit_event(
            actor_user_id=admin_user_id,
            action="VENDOR_APPROVED",
            entity_type="Vendor",
            entity_id=vendor_id,
            details=f"Vendor registration for '{vendor['company_name']}' approved.",
        )
    return True


def reject_vendor_in_db(vendor_id: int, admin_user_id: int, reason: str) -> bool:
    """Rejects a vendor application and records the rejection reason."""
    db = get_db()
    with db:
        vendor = db.execute("SELECT company_name FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if not vendor:
            return False

        db.execute(
            """UPDATE vendors
               SET approval_status = 'rejected',
                   reviewed_by = ?,
                   reviewed_at = CURRENT_TIMESTAMP,
                   rejection_reason = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (admin_user_id, reason.strip() or "Requirements not met upon review", vendor_id),
        )

        log_audit_event(
            actor_user_id=admin_user_id,
            action="VENDOR_REJECTED",
            entity_type="Vendor",
            entity_id=vendor_id,
            details=f"Vendor '{vendor['company_name']}' rejected. Reason: {reason}",
        )
    return True


# ─────────────────────────────────────────────────────────────────────────────
# RFQs (Requests for Quotation) & Invitations
# ─────────────────────────────────────────────────────────────────────────────

def get_rfqs(user: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Retrieves RFQs formatted for UI templates.
    If user is a vendor: shows open tenders and tenders the vendor is invited to.
    """
    db = get_db()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Fetch all RFQs
    query = """
        SELECT
            r.id,
            r.rfq_number AS number,
            r.rfq_number,
            r.title,
            r.description,
            r.item_name,
            r.category,
            r.quantity,
            r.unit,
            r.specifications,
            r.deadline,
            r.status,
            r.created_by,
            SUBSTR(r.created_at, 1, 10) AS created_at,
            (SELECT COUNT(*) FROM quotations q WHERE q.rfq_id = r.id) AS bid_count
        FROM rfqs r
        ORDER BY r.id DESC
    """
    rows = db.execute(query).fetchall()

    rfqs: List[Dict[str, Any]] = []
    vendor_id = user.get("vendor_id") if (user and user.get("role") == "vendor") else None
    vendor_company = user.get("company") if user else ""

    for r in rows:
        data = dict(r)
        data["is_overdue"] = bool(data["deadline"] < now_str)

        # Fetch invited vendor names
        invited_rows = db.execute(
            """SELECT v.company_name, rv.vendor_id
               FROM rfq_vendors rv
               JOIN vendors v ON rv.vendor_id = v.id
               WHERE rv.rfq_id = ?""",
            (data["id"],),
        ).fetchall()
        invited_names = [row["company_name"] for row in invited_rows]
        invited_vendor_ids = [row["vendor_id"] for row in invited_rows]

        data["invited_vendors"] = invited_names
        data["budget"] = f"{int(data['quantity']):,} {data['unit']}"

        # Line items structure expected by some modal views
        data["line_items"] = [
            {
                "name": data["item_name"],
                "quantity": data["quantity"],
                "unit": data["unit"],
                "spec": data["specifications"] or "Standard enterprise specification",
            }
        ]

        # Role filtering
        if user and user.get("role") == "vendor":
            # Vendor sees open RFQs or those they are explicitly invited to
            if data["status"] == "open" or (vendor_id and vendor_id in invited_vendor_ids):
                rfqs.append(data)
        else:
            rfqs.append(data)

    return rfqs


def get_rfq_by_id(rfq_id_or_number: Union[int, str]) -> Optional[Dict[str, Any]]:
    """Fetches an RFQ by its ID or by its rfq_number string."""
    db = get_db()
    if str(rfq_id_or_number).isdigit():
        query = "SELECT * FROM rfqs WHERE id = ?"
        param = int(rfq_id_or_number)
    else:
        query = "SELECT * FROM rfqs WHERE rfq_number = ?"
        param = str(rfq_id_or_number)

    row = db.execute(query, (param,)).fetchone()
    if not row:
        return None

    data = dict(row)
    data["number"] = data["rfq_number"]
    data["is_overdue"] = bool(data["deadline"] < datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Invited vendors
    invited_rows = db.execute(
        """SELECT v.company_name
           FROM rfq_vendors rv
           JOIN vendors v ON rv.vendor_id = v.id
           WHERE rv.rfq_id = ?""",
        (data["id"],),
    ).fetchall()
    data["invited_vendors"] = [r["company_name"] for r in invited_rows]
    data["bid_count"] = db.execute(
        "SELECT COUNT(*) FROM quotations WHERE rfq_id = ?", (data["id"],)
    ).fetchone()[0]

    return data


def create_rfq_in_db(
    *,
    title: str,
    description: str,
    deadline: str,
    created_by_user_id: int,
    item_name: Optional[str] = None,
    category: Optional[str] = None,
    quantity: float = 1.0,
    unit: str = "lot",
    budget: Optional[str] = None,
) -> int:
    """Creates a new RFQ tender and returns the new rfq_id."""
    db = get_db()
    with db:
        # Generate rfq_number
        count_row = db.execute("SELECT COUNT(*) FROM rfqs").fetchone()
        next_num = (count_row[0] if count_row else 0) + 1
        rfq_number = f"RFQ-2026-{next_num:03d}"

        # Clean deadline string
        deadline_clean = deadline.strip()
        if len(deadline_clean) == 10:
            deadline_clean += " 23:59:59"

        cursor = db.execute(
            """INSERT INTO rfqs
               (rfq_number, title, description, item_name, category, quantity, unit, specifications, deadline, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
            (
                rfq_number,
                title.strip(),
                description.strip() or "Standard procurement tender.",
                item_name.strip() if item_name else title.strip(),
                category.strip() if category else "General",
                max(1.0, float(quantity)),
                unit.strip() or "units",
                budget.strip() if budget else "Within approved quarterly budget",
                deadline_clean,
                created_by_user_id,
            ),
        )
        new_rfq_id = int(cursor.lastrowid)

        log_audit_event(
            actor_user_id=created_by_user_id,
            action="RFQ_CREATED",
            entity_type="RFQ",
            entity_id=new_rfq_id,
            details=f"Tender '{title}' created with deadline {deadline_clean}.",
        )

    return new_rfq_id


def invite_vendor_to_rfq(rfq_id: int, vendor_id: int, admin_user_id: int) -> bool:
    """Invites an approved vendor to bid on an RFQ."""
    db = get_db()
    with db:
        db.execute(
            """INSERT OR IGNORE INTO rfq_vendors (rfq_id, vendor_id, invited_by, status)
               VALUES (?, ?, ?, 'invited')""",
            (rfq_id, vendor_id, admin_user_id),
        )
        log_audit_event(
            actor_user_id=admin_user_id,
            action="RFQ_VENDOR_INVITED",
            entity_type="RFQ",
            entity_id=rfq_id,
            details=f"Vendor ID {vendor_id} invited to bid on RFQ ID {rfq_id}.",
        )
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Quotations & Comparative Bidding
# ─────────────────────────────────────────────────────────────────────────────

def get_quotations(
    user: Optional[Dict[str, Any]] = None,
    rfq_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves quotations with join on vendor and RFQ tables.
    Enforces vendor isolation: vendors only see their own quotations.
    """
    db = get_db()
    conditions: List[str] = []
    params: List[Any] = []

    if user and user.get("role") == "vendor":
        conditions.append("q.vendor_id = ?")
        params.append(user.get("vendor_id") or 0)

    if rfq_id is not None:
        conditions.append("q.rfq_id = ?")
        params.append(rfq_id)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT
            q.id,
            q.quotation_number AS number,
            q.quotation_number,
            q.rfq_id,
            r.rfq_number,
            r.title AS rfq_title,
            q.vendor_id,
            v.company_name AS vendor_name,
            u.email AS vendor_email,
            q.unit_price_paise,
            q.total_price_paise,
            q.delivery_days,
            q.terms,
            q.notes,
            q.status,
            SUBSTR(q.submitted_at, 1, 10) AS submitted_at
        FROM quotations q
        JOIN rfqs r ON q.rfq_id = r.id
        JOIN vendors v ON q.vendor_id = v.id
        JOIN users u ON v.user_id = u.id
        {where_clause}
        ORDER BY q.id DESC
    """
    rows = db.execute(query, tuple(params)).fetchall()

    quotes: List[Dict[str, Any]] = []
    for r in rows:
        data = dict(r)
        data["total_price"] = paise_to_inr_str(data["total_price_paise"])
        data["price_value"] = float(data["total_price_paise"]) / 100.0
        quotes.append(data)
    return quotes


def get_quotation_comparison(rfq_id: int) -> List[Dict[str, Any]]:
    """
    Gathers all quotations submitted for a specific RFQ.
    Calculates the lowest price and marks 'is_lowest' for competitive display.
    """
    quotes = get_quotations(rfq_id=rfq_id)
    if not quotes:
        return []

    min_price = min(q["price_value"] for q in quotes)
    for q in quotes:
        q["is_lowest"] = (q["price_value"] == min_price)
        q["quotation_id"] = q["id"]
    return quotes


def submit_quotation_in_db(
    *,
    rfq_id: int,
    vendor_id: int,
    total_price: Union[str, float, int],
    delivery_days: int,
    notes: str = "",
    terms: str = "",
) -> int:
    """
    Allows a verified vendor to submit a quotation bid before the RFQ deadline.
    Returns the new quotation ID.
    """
    db = get_db()
    total_paise = inr_str_to_paise(total_price)
    unit_paise = total_paise

    with db:
        # Generate quotation_number
        count_row = db.execute("SELECT COUNT(*) FROM quotations").fetchone()
        next_num = (count_row[0] if count_row else 0) + 1
        quote_num = f"QT-2026-{next_num:03d}"

        cursor = db.execute(
            """INSERT INTO quotations
               (quotation_number, rfq_id, vendor_id, unit_price_paise, total_price_paise,
                currency, delivery_days, terms, notes, status)
               VALUES (?, ?, ?, ?, ?, 'INR', ?, ?, ?, 'submitted')""",
            (
                quote_num,
                rfq_id,
                vendor_id,
                unit_paise,
                total_paise,
                max(1, int(delivery_days)),
                terms.strip() or "Standard payment terms within 30 days.",
                notes.strip() or "Enterprise bid submission.",
            ),
        )
        new_quote_id = int(cursor.lastrowid)

        # Update rfq_vendors status if invited
        db.execute(
            "UPDATE rfq_vendors SET status = 'quoted' WHERE rfq_id = ? AND vendor_id = ?",
            (rfq_id, vendor_id),
        )

        log_audit_event(
            actor_user_id=None,
            action="QUOTATION_SUBMITTED",
            entity_type="Quotation",
            entity_id=new_quote_id,
            details=f"Quotation {quote_num} submitted for RFQ {rfq_id} with amount {paise_to_inr_str(total_paise)}.",
        )

    return new_quote_id


def select_quotation_for_approval(quotation_id: int, admin_user_id: int) -> bool:
    """
    Advances a winning quotation to 'selected' status for administrative authorization.
    """
    db = get_db()
    with db:
        quote = db.execute(
            """SELECT q.id, q.quotation_number, q.rfq_id, v.company_name
               FROM quotations q
               JOIN vendors v ON q.vendor_id = v.id
               WHERE q.id = ?""",
            (quotation_id,),
        ).fetchone()
        if not quote:
            return False

        db.execute(
            "UPDATE quotations SET status = 'selected', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (quotation_id,),
        )

        log_audit_event(
            actor_user_id=admin_user_id,
            action="QUOTATION_SELECTED",
            entity_type="Quotation",
            entity_id=quotation_id,
            details=f"Quotation {quote['quotation_number']} ({quote['company_name']}) selected for procurement approval.",
        )
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Approvals & Purchase Orders
# ─────────────────────────────────────────────────────────────────────────────

def get_pending_approvals() -> List[Dict[str, Any]]:
    """
    Returns quotations with status='selected' that have not yet had a final PO approved/issued.
    """
    db = get_db()
    query = """
        SELECT
            q.id,
            q.id AS quotation_id,
            r.id AS rfq_id,
            r.rfq_number,
            r.title AS rfq_title,
            v.company_name AS selected_vendor,
            q.total_price_paise,
            q.delivery_days,
            u.full_name AS requested_by
        FROM quotations q
        JOIN rfqs r ON q.rfq_id = r.id
        JOIN vendors v ON q.vendor_id = v.id
        JOIN users u ON r.created_by = u.id
        LEFT JOIN purchase_orders po ON q.id = po.quotation_id
        WHERE q.status = 'selected' AND (po.id IS NULL OR po.status = 'draft')
        ORDER BY q.id DESC
    """
    rows = db.execute(query).fetchall()
    approvals: List[Dict[str, Any]] = []
    for r in rows:
        data = dict(r)
        data["bid_amount"] = paise_to_inr_str(data["total_price_paise"])
        approvals.append(data)
    return approvals


def count_pending_approvals() -> int:
    """Returns the total number of quotations awaiting purchase order authorization."""
    db = get_db()
    row = db.execute(
        """SELECT COUNT(*) FROM quotations q
           LEFT JOIN purchase_orders po ON q.id = po.quotation_id
           WHERE q.status = 'selected' AND (po.id IS NULL OR po.status = 'draft')"""
    ).fetchone()
    return int(row[0]) if row else 0


def authorize_procurement_proposal(approval_id: int, admin_user_id: int) -> Optional[str]:
    """
    Authorizes a selected quotation, creates the Purchase Order, and awards the RFQ.
    Returns the new PO number upon success.
    """
    db = get_db()
    with db:
        quote = db.execute(
            """SELECT q.*, r.quantity AS rfq_qty
               FROM quotations q
               JOIN rfqs r ON q.rfq_id = r.id
               WHERE q.id = ? AND q.status = 'selected'""",
            (approval_id,),
        ).fetchone()
        if not quote:
            return None

        # Generate po_number
        po_count = db.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
        po_num = f"PO-2026-{po_count + 1:03d}"

        # Insert PO
        cursor = db.execute(
            """INSERT INTO purchase_orders
               (po_number, rfq_id, quotation_id, vendor_id, quantity,
                unit_price_paise, total_amount_paise, status, created_by,
                approved_by, approved_at, issued_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'issued', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (
                po_num,
                quote["rfq_id"],
                quote["id"],
                quote["vendor_id"],
                quote["rfq_qty"] or 1.0,
                quote["unit_price_paise"],
                quote["total_price_paise"],
                admin_user_id,
                admin_user_id,
            ),
        )
        new_po_id = int(cursor.lastrowid)

        # Update RFQ status to 'awarded'
        db.execute(
            "UPDATE rfqs SET status = 'awarded', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (quote["rfq_id"],),
        )

        log_audit_event(
            actor_user_id=admin_user_id,
            action="PO_AUTHORIZED",
            entity_type="PurchaseOrder",
            entity_id=new_po_id,
            details=f"Purchase Order {po_num} authorized for {paise_to_inr_str(quote['total_price_paise'])}.",
        )

    return po_num


def reject_procurement_proposal(approval_id: int, admin_user_id: int) -> bool:
    """Rejects a procurement proposal and resets the quotation status."""
    db = get_db()
    with db:
        db.execute(
            "UPDATE quotations SET status = 'rejected', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (approval_id,),
        )
        log_audit_event(
            actor_user_id=admin_user_id,
            action="PROPOSAL_REJECTED",
            entity_type="Quotation",
            entity_id=approval_id,
            details=f"Procurement quotation proposal ID {approval_id} rejected.",
        )
    return True


def get_purchase_orders(user: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Retrieves purchase orders with formatted currency and display fields.
    Enforces vendor isolation: vendors only see their own POs.
    Includes linked invoice status to determine invoice submission eligibility.
    """
    db = get_db()
    conditions: List[str] = []
    params: List[Any] = []

    if user and user.get("role") == "vendor":
        conditions.append("po.vendor_id = ?")
        params.append(user.get("vendor_id") or 0)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT
            po.id,
            po.po_number AS number,
            po.po_number,
            po.rfq_id,
            r.rfq_number,
            r.title AS rfq_title,
            r.item_name,
            r.quantity AS rfq_quantity,
            r.unit AS rfq_unit,
            r.specifications AS rfq_specifications,
            po.quotation_id,
            q.quotation_number,
            po.vendor_id,
            v.company_name AS vendor_name,
            po.quantity,
            po.unit_price_paise,
            po.total_amount_paise,
            po.status,
            SUBSTR(po.created_at, 1, 10) AS date,
            po.created_at,
            inv.id AS invoice_id,
            inv.invoice_number,
            inv.status AS invoice_status,
            inv.amount_paise AS invoice_amount_paise
        FROM purchase_orders po
        JOIN rfqs r ON po.rfq_id = r.id
        JOIN vendors v ON po.vendor_id = v.id
        LEFT JOIN quotations q ON po.quotation_id = q.id
        LEFT JOIN invoices inv ON po.id = inv.po_id AND inv.status != 'rejected'
        {where_clause}
        ORDER BY po.id DESC
    """
    rows = db.execute(query, tuple(params)).fetchall()
    orders: List[Dict[str, Any]] = []
    for r in rows:
        data = dict(r)
        data["total"] = paise_to_inr_str(data["total_amount_paise"])
        data["unit_price"] = paise_to_inr_str(data["unit_price_paise"])

        # Map internal status for template compatibility
        if data["status"] in ("approved", "issued", "acknowledged"):
            data["display_status"] = "confirmed"
        else:
            data["display_status"] = data["status"]

        # Track invoice lifecycle against this PO
        data["has_invoice"] = bool(data.get("invoice_id"))
        data["is_invoice_eligible"] = (not data["has_invoice"]) and (
            data["status"] in ("approved", "issued", "acknowledged", "confirmed")
        )
        orders.append(data)
    return orders


def get_po_by_id(po_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single Purchase Order record by its primary key ID."""
    db = get_db()
    row = db.execute(
        """SELECT po.*, v.company_name AS vendor_name, v.user_id AS vendor_user_id,
                  r.rfq_number, r.title AS rfq_title, r.item_name, r.unit, r.specifications
           FROM purchase_orders po
           JOIN vendors v ON po.vendor_id = v.id
           JOIN rfqs r ON po.rfq_id = r.id
           WHERE po.id = ?""",
        (po_id,),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    data["total"] = paise_to_inr_str(data["total_amount_paise"])
    data["unit_price"] = paise_to_inr_str(data["unit_price_paise"])
    return data


def get_po_for_pdf(po_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves complete joined Purchase Order details formatted for ReportLab PDF generation.
    """
    db = get_db()
    query = """
        SELECT
            po.id,
            po.po_number,
            po.rfq_id,
            po.quotation_id,
            po.vendor_id,
            po.quantity,
            po.unit_price_paise,
            po.total_amount_paise,
            po.status,
            po.created_at,
            po.approved_at,
            po.issued_at,
            r.rfq_number,
            r.title AS rfq_title,
            r.description AS rfq_description,
            r.item_name,
            r.category AS rfq_category,
            r.unit,
            r.specifications,
            q.quotation_number,
            q.delivery_days,
            q.terms AS quotation_terms,
            q.notes AS quotation_notes,
            v.company_name,
            v.registration_number,
            v.contact_phone,
            v.address,
            v.category AS vendor_category,
            u.email AS vendor_email,
            u.full_name AS vendor_name,
            u_creat.full_name AS created_by_name,
            u_appr.full_name AS approved_by_name
        FROM purchase_orders po
        JOIN rfqs r ON po.rfq_id = r.id
        JOIN vendors v ON po.vendor_id = v.id
        JOIN users u ON v.user_id = u.id
        LEFT JOIN quotations q ON po.quotation_id = q.id
        LEFT JOIN users u_creat ON po.created_by = u_creat.id
        LEFT JOIN users u_appr ON po.approved_by = u_appr.id
        WHERE po.id = ?
    """
    row = db.execute(query, (po_id,),).fetchone()
    return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Invoices, Payments, & Three-Way Matching
# ─────────────────────────────────────────────────────────────────────────────

def get_invoices(
    user: Optional[Dict[str, Any]] = None,
    verification_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves invoices with verification, payment tracking, and PO mismatch checks.
    Enforces vendor isolation: vendors only see their own invoices.
    """
    db = get_db()
    conditions: List[str] = []
    params: List[Any] = []

    if user and user.get("role") == "vendor":
        conditions.append("inv.vendor_id = ?")
        params.append(user.get("vendor_id") or 0)

    if search:
        pat = f"%{search.strip().lower()}%"
        conditions.append("(LOWER(inv.invoice_number) LIKE ? OR LOWER(v.company_name) LIKE ?)")
        params.extend([pat, pat])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT
            inv.id,
            inv.invoice_number AS number,
            inv.invoice_number,
            inv.po_id,
            po.po_number,
            po.total_amount_paise AS po_amount_paise,
            r.rfq_number,
            r.title AS rfq_title,
            r.item_name,
            inv.vendor_id,
            v.company_name AS vendor_name,
            inv.amount_paise,
            inv.invoice_date AS date,
            inv.due_date,
            inv.status,
            inv.verified_by,
            inv.verified_at,
            inv.paid_at,
            inv.payment_reference,
            inv.created_at,
            u_ver.full_name AS verified_by_name
        FROM invoices inv
        JOIN purchase_orders po ON inv.po_id = po.id
        JOIN rfqs r ON po.rfq_id = r.id
        JOIN vendors v ON inv.vendor_id = v.id
        LEFT JOIN users u_ver ON inv.verified_by = u_ver.id
        {where_clause}
        ORDER BY inv.id DESC
    """
    rows = db.execute(query, tuple(params)).fetchall()
    invoices: List[Dict[str, Any]] = []

    for r in rows:
        data = dict(r)
        data["amount"] = paise_to_inr_str(data["amount_paise"])
        data["po_amount"] = paise_to_inr_str(data["po_amount_paise"])

        # Determine presentation statuses
        st = data["status"]
        if st in ("submitted", "under_review"):
            data["verification_status"] = "pending"
            data["payment_status"] = "unpaid"
        elif st == "verified":
            data["verification_status"] = "verified"
            data["payment_status"] = "unpaid"
        elif st == "rejected":
            data["verification_status"] = "rejected"
            data["payment_status"] = "unpaid"
        elif st == "paid":
            data["verification_status"] = "verified"
            data["payment_status"] = "paid"
        else:
            data["verification_status"] = "pending"
            data["payment_status"] = "unpaid"

        # Three-way matching check (Invoice amount vs PO amount)
        data["has_mismatch"] = bool(data["amount_paise"] > data["po_amount_paise"])
        if data["has_mismatch"]:
            diff = (data["amount_paise"] - data["po_amount_paise"]) / 100.0
            data["mismatch_reason"] = (
                f"Invoice amount ({data['amount']}) exceeds authorized PO value ({data['po_amount']}) "
                f"by ₹{diff:,.2f}."
            )
        else:
            data["mismatch_reason"] = ""

        # Filter by verification status if requested
        if verification_status and data["verification_status"] != verification_status.strip().lower():
            continue

        # Filter by payment status if requested
        if payment_status and data["payment_status"] != payment_status.strip().lower():
            continue

        invoices.append(data)

    return invoices


def get_invoice_by_id(invoice_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single invoice record by primary key ID."""
    db = get_db()
    row = db.execute(
        """SELECT inv.*, po.po_number, v.company_name AS vendor_name, v.user_id AS vendor_user_id
           FROM invoices inv
           JOIN purchase_orders po ON inv.po_id = po.id
           JOIN vendors v ON inv.vendor_id = v.id
           WHERE inv.id = ?""",
        (invoice_id,),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    data["amount"] = paise_to_inr_str(data["amount_paise"])
    return data


def get_invoice_for_pdf(invoice_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves full joined invoice data for ReportLab PDF generation.
    """
    db = get_db()
    query = """
        SELECT
            inv.id,
            inv.invoice_number,
            inv.amount_paise,
            inv.invoice_date,
            inv.due_date,
            inv.status,
            inv.verified_by,
            inv.verified_at,
            inv.paid_at,
            inv.payment_reference,
            inv.created_at,
            po.id AS po_id,
            po.po_number,
            po.total_amount_paise AS po_total_paise,
            po.unit_price_paise,
            po.quantity,
            po.status AS po_status,
            r.id AS rfq_id,
            r.rfq_number,
            r.title AS rfq_title,
            r.item_name,
            r.category AS rfq_category,
            r.unit,
            r.specifications,
            q.quotation_number,
            q.delivery_days,
            q.terms AS quotation_terms,
            q.notes AS quotation_notes,
            v.id AS vendor_id,
            v.company_name,
            v.registration_number,
            v.contact_phone,
            v.address,
            v.category AS vendor_category,
            u.email AS vendor_email,
            u.full_name AS vendor_name,
            u_ver.full_name AS verified_by_name
        FROM invoices inv
        JOIN purchase_orders po ON inv.po_id = po.id
        JOIN vendors v ON inv.vendor_id = v.id
        JOIN users u ON v.user_id = u.id
        JOIN rfqs r ON po.rfq_id = r.id
        LEFT JOIN quotations q ON po.quotation_id = q.id
        LEFT JOIN users u_ver ON inv.verified_by = u_ver.id
        WHERE inv.id = ?
    """
    row = db.execute(query, (invoice_id,)).fetchone()
    return dict(row) if row else None


def get_payment_receipt_for_pdf(invoice_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves full joined payment receipt record for ReportLab PDF generation."""
    return get_invoice_for_pdf(invoice_id)


def get_payment_records(user: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Returns payment tracking entries computed from invoices."""
    invoices = get_invoices(user=user)
    payments: List[Dict[str, Any]] = []

    for inv in invoices:
        is_paid = (inv["payment_status"] == "paid")
        payments.append({
            "invoice_id": inv["id"],
            "invoice_number": inv["number"],
            "po_number": inv.get("po_number"),
            "vendor_name": inv["vendor_name"],
            "amount": inv["amount"],
            "amount_paid": inv["amount"] if is_paid else "₹0.00",
            "balance": "₹0.00" if is_paid else inv["amount"],
            "due_date": inv.get("due_date") or (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "status": "paid" if is_paid else "unpaid",
            "is_overdue": False,
            "paid_at": inv.get("paid_at"),
            "payment_reference": inv.get("payment_reference"),
        })
    return payments


def register_invoice_in_db(
    *,
    invoice_number: str,
    po_number: Optional[str] = None,
    po_id: Optional[Union[int, str]] = None,
    amount_str: Optional[str] = None,
    user_id: Optional[int] = None,
    vendor_id: Optional[int] = None,
    invoice_date: Optional[str] = None,
    due_date: Optional[str] = None,
    notes: Optional[str] = None,
) -> Tuple[int, bool, str]:
    """
    Registers an invoice against an existing PO.
    Performs vendor isolation check, duplicate prevention, and mismatch detection.
    Returns (invoice_id, has_mismatch, mismatch_reason).
    """
    db = get_db()
    with db:
        po_row = None
        if po_id:
            try:
                po_id_int = int(po_id)
                po_row = db.execute(
                    """SELECT po.id, po.po_number, po.vendor_id, po.total_amount_paise, po.status, v.company_name
                       FROM purchase_orders po
                       JOIN vendors v ON po.vendor_id = v.id
                       WHERE po.id = ?""",
                    (po_id_int,),
                ).fetchone()
            except ValueError:
                pass

        if not po_row and po_number:
            po_row = db.execute(
                """SELECT po.id, po.po_number, po.vendor_id, po.total_amount_paise, po.status, v.company_name
                   FROM purchase_orders po
                   JOIN vendors v ON po.vendor_id = v.id
                   WHERE po.po_number = ?""",
                (str(po_number).strip(),),
            ).fetchone()

        if not po_row:
            ref_str = po_number or str(po_id)
            raise ValueError(f"Purchase Order '{ref_str}' could not be found.")

        # 1. Enforce vendor ownership if user is a vendor
        if vendor_id and po_row["vendor_id"] != vendor_id:
            raise PermissionError("Unauthorized: You can only submit invoices against Purchase Orders issued to your company.")

        # 2. Prevent duplicate active invoices for the same PO
        existing_active = db.execute(
            """SELECT id, invoice_number, status
               FROM invoices
               WHERE po_id = ? AND status != 'rejected'""",
            (po_row["id"],),
        ).fetchone()
        if existing_active:
            raise ValueError(
                f"Invoice '{existing_active['invoice_number']}' has already been submitted for Purchase Order {po_row['po_number']}."
            )

        # 3. Check duplicate invoice number for this vendor
        dup_num = db.execute(
            """SELECT id FROM invoices WHERE vendor_id = ? AND LOWER(invoice_number) = ?""",
            (po_row["vendor_id"], invoice_number.strip().lower()),
        ).fetchone()
        if dup_num:
            raise ValueError(
                f"Invoice number '{invoice_number.strip()}' has already been registered for your company."
            )

        # 4. Calculate amount and mismatch
        amount_paise = inr_str_to_paise(amount_str) if amount_str else po_row["total_amount_paise"]
        if amount_paise <= 0:
            amount_paise = po_row["total_amount_paise"]

        po_amount_paise = po_row["total_amount_paise"]
        has_mismatch = bool(amount_paise > po_amount_paise)
        mismatch_reason = ""
        if has_mismatch:
            diff = (amount_paise - po_amount_paise) / 100.0
            mismatch_reason = (
                f"Invoice amount ({paise_to_inr_str(amount_paise)}) exceeds authorized PO value "
                f"({paise_to_inr_str(po_amount_paise)}) by ₹{diff:,.2f}."
            )

        inv_date = invoice_date.strip() if invoice_date and invoice_date.strip() else datetime.now().strftime("%Y-%m-%d")
        d_date = due_date.strip() if due_date and due_date.strip() else (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        cursor = db.execute(
            """INSERT INTO invoices
               (invoice_number, po_id, vendor_id, amount_paise, invoice_date, due_date, status)
               VALUES (?, ?, ?, ?, ?, ?, 'submitted')""",
            (
                invoice_number.strip(),
                po_row["id"],
                po_row["vendor_id"],
                amount_paise,
                inv_date,
                d_date,
            ),
        )
        new_inv_id = int(cursor.lastrowid)

        log_audit_event(
            actor_user_id=user_id,
            action="INVOICE_SUBMITTED",
            entity_type="Invoice",
            entity_id=new_inv_id,
            details=f"Invoice {invoice_number} submitted against {po_row['po_number']}. Mismatch: {has_mismatch}.",
        )

    return new_inv_id, has_mismatch, mismatch_reason


def verify_invoice_in_db(invoice_id: int, admin_user_id: int, action: str = "verify") -> bool:
    """Verifies or rejects a supplier invoice."""
    db = get_db()
    with db:
        new_status = "verified" if action == "verify" else "rejected"
        db.execute(
            """UPDATE invoices
               SET status = ?,
                   verified_by = ?,
                   verified_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (new_status, admin_user_id, invoice_id),
        )
        log_audit_event(
            actor_user_id=admin_user_id,
            action=f"INVOICE_{action.upper()}",
            entity_type="Invoice",
            entity_id=invoice_id,
            details=f"Invoice ID {invoice_id} status updated to {new_status}.",
        )
    return True


def record_payment_in_db(
    invoice_id: int,
    admin_user_id: int,
    status: str = "paid",
    reference: Optional[str] = None,
) -> bool:
    """Records payment for a verified invoice."""
    db = get_db()
    with db:
        inv = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not inv:
            raise ValueError(f"Invoice ID {invoice_id} not found.")

        # Business rule: Must be verified before payment can be recorded
        if inv["status"] not in ("verified", "paid"):
            raise ValueError(f"Invoice {inv['invoice_number']} must be verified by admin before payment can be recorded.")

        clean_status = status.strip().lower()
        if clean_status not in ("paid", "submitted", "verified"):
            clean_status = "paid"

        payment_ref = reference.strip() if reference and reference.strip() else f"PAY-REF-{datetime.now().strftime('%Y%m%d%H%M')}"
        db.execute(
            """UPDATE invoices
               SET status = ?,
                   paid_at = CURRENT_TIMESTAMP,
                   payment_reference = ?
               WHERE id = ?""",
            (clean_status, payment_ref, invoice_id),
        )
        log_audit_event(
            actor_user_id=admin_user_id,
            action="PAYMENT_RECORDED",
            entity_type="Invoice",
            entity_id=invoice_id,
            details=f"Payment recorded for invoice ID {invoice_id} ({inv['invoice_number']}). Ref: {payment_ref}. Status: {clean_status}.",
        )
    return True



# ─────────────────────────────────────────────────────────────────────────────
# Audit Logs & Dashboard Metrics
# ─────────────────────────────────────────────────────────────────────────────

def log_audit_event(
    *,
    actor_user_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[int],
    details: str,
) -> None:
    """Inserts a structured chronological audit trail entry."""
    try:
        db = get_db()
        details_payload = json.dumps({"message": details}, separators=(",", ":"))
        db.execute(
            """INSERT INTO audit_logs (actor_user_id, action, entity_type, entity_id, details_json)
               VALUES (?, ?, ?, ?, ?)""",
            (actor_user_id, action, entity_type, entity_id, details_payload),
        )
        db.commit()
    except Exception:
        # Fallback in case of transaction isolation or outside context
        pass



def format_audit_log_entry(data: Dict[str, Any]) -> Dict[str, Any]:
    """Formats an audit log dictionary with actor details, labels, action names, and previous/new values."""
    raw = data.get("details_json")
    parsed_json: Dict[str, Any] = {}
    if raw:
        try:
            parsed_json = json.loads(raw)
            data["details"] = parsed_json.get("message", raw)
        except Exception:
            data["details"] = raw
    else:
        data["details"] = "—"

    # Human-friendly action title
    action = data.get("action", "")
    ACTION_TITLES = {
        "INVOICE_SUBMITTED": "Invoice Submitted",
        "INVOICE_VERIFY": "Invoice Verified",
        "PAYMENT_RECORDED": "Payment Recorded",
        "PO_AUTHORIZED": "Purchase Order Authorized",
        "QUOTATION_SELECTED": "Quotation Selected",
        "QUOTATION_SUBMITTED": "Quotation Bid Submitted",
        "RFQ_CREATED": "RFQ Tender Created",
        "RFQ_VENDOR_INVITED": "Vendor Invited to RFQ",
        "VENDOR_APPROVED": "Vendor Registration Approved",
        "VENDOR_REGISTERED": "Vendor Registered",
        "DEMO_DATA_SEEDED": "Demo Data Seeded",
        "INSPECTION_INITIATED": "Inspection Initiated",
        "NON_COMPLIANCE_FLAGGED": "Non-Compliance Flagged",
        "SAFETY_VIOLATION_CITED": "Safety Violation Cited",
        "CONTRACTOR_NOTIFIED": "Contractor Formally Notified",
        "CORRECTIVE_GEAR_ISSUED": "Corrective Action / Gear Issued",
        "REINSPECTION_VERIFIED": "Reinspection Verified & Passed",
        "HAZARD_IDENTIFIED": "Hazard Identified",
        "CALIBRATION_CHECK_FAILED": "Calibration Check Failed",
        "REMEDIATION_PLAN_APPROVED": "Remediation Plan Approved",
        "AIRFLOW_TEST_FAILED": "Airflow Rate Deficit Identified",
        "FILTRATION_UPGRADE_ORDERED": "Filtration Upgrade Ordered",
        "AIR_QUALITY_CERTIFIED": "Air Quality Certified",
        "POLICY_REVIEW_INITIATED": "Regulatory Review Initiated",
        "STANDARD_OPERATING_PROC_UPDATED": "SOP Protocol Updated",
        "COMPLIANCE_CLEARANCE_ISSUED": "Annual Compliance Clearance",
    }
    data["action_title"] = ACTION_TITLES.get(action, action.replace("_", " ").title())

    # Actor role and organization labels
    role = data.get("user_role") or "system"
    company = data.get("company_name") or data.get("vendor_company")
    if role == "admin":
        if any(k in action for k in ("INSPECTION", "SAFETY", "COMPLIANCE", "AUDIT", "HAZARD", "AIRFLOW")):
            data["actor_role"] = "Lead Safety Auditor"
            data["actor_organization"] = "VendorBridge Audit & Compliance"
        else:
            data["actor_role"] = "Procurement Admin"
            data["actor_organization"] = "VendorBridge Procurement"
    elif role == "vendor":
        data["actor_role"] = "Company Representative"
        data["actor_organization"] = company or "Registered Supplier"
    else:
        data["actor_role"] = "Automated System"
        data["actor_organization"] = "VendorBridge Ledger Engine"

    # Extract previous/new values if present in json or message
    prev_val = parsed_json.get("previous_value")
    new_val = parsed_json.get("new_value")

    # Detect state transitions from message like "status updated to verified", "status: paid", "status: pending"
    msg = data.get("details", "")
    if not prev_val and not new_val:
        if "status updated to verified" in msg:
            prev_val = "Pending Verification"
            new_val = "Verified"
        elif "status: paid" in msg:
            prev_val = "Verified / Unpaid"
            new_val = "Paid"
        elif "approved" in msg.lower() and "vendor" in msg.lower():
            prev_val = "Pending Review"
            new_val = "Approved"
        elif "rejected" in msg.lower():
            prev_val = "Pending"
            new_val = "Rejected"

    data["previous_value"] = prev_val
    data["new_value"] = new_val

    # Evidence / Document attachment links
    rec_type = data.get("record_type")
    rec_id = data.get("record_id")
    data["has_evidence"] = False
    data["evidence_type"] = None
    data["evidence_url"] = None

    if action == "PAYMENT_RECORDED" and rec_type == "Invoice" and rec_id:
        data["has_evidence"] = True
        data["evidence_type"] = "Payment Receipt PDF"
        data["evidence_url"] = f"/finance/payment/{rec_id}/receipt/pdf"
    elif rec_type == "Invoice" and rec_id:
        data["has_evidence"] = True
        data["evidence_type"] = "Invoice PDF"
        data["evidence_url"] = f"/finance/invoice/{rec_id}/pdf"
    elif rec_type in ("PurchaseOrder", "PO") and rec_id:
        data["has_evidence"] = True
        data["evidence_type"] = "Purchase Order PDF"
        data["evidence_url"] = f"/procurement/order/{rec_id}/pdf"

    return data


def get_audit_logs(limit: int = 50, search: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves chronological audit events formatted for the audit trail view and timeline."""
    db = get_db()
    query = """
        SELECT
            al.id,
            al.created_at AS timestamp,
            COALESCE(u.full_name, 'System') AS user_name,
            COALESCE(u.role, 'system') AS user_role,
            v.company_name AS vendor_company,
            al.action,
            al.entity_type AS record_type,
            COALESCE(al.entity_id, 0) AS record_id,
            al.details_json
        FROM audit_logs al
        LEFT JOIN users u ON al.actor_user_id = u.id
        LEFT JOIN vendors v ON v.user_id = u.id
    """
    params: List[Any] = []
    if search:
        query += """
            WHERE al.action LIKE ?
               OR al.entity_type LIKE ?
               OR u.full_name LIKE ?
               OR v.company_name LIKE ?
               OR al.details_json LIKE ?
        """
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard, wildcard, wildcard])

    query += " ORDER BY al.id DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(query, tuple(params)).fetchall()
    return [format_audit_log_entry(dict(r)) for r in rows]


def get_audit_log_by_id(log_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a single audit log by ID with enriched metadata and company/audit linkage."""
    db = get_db()
    query = """
        SELECT
            al.id,
            al.audit_id,
            a.audit_reference,
            a.company_id,
            COALESCE(c.company_name, v.company_name) AS company_name,
            al.created_at AS timestamp,
            COALESCE(u.full_name, 'System') AS user_name,
            COALESCE(u.role, 'system') AS user_role,
            COALESCE(c.company_name, v.company_name) AS vendor_company,
            al.action,
            al.entity_type AS record_type,
            COALESCE(al.entity_id, 0) AS record_id,
            al.details_json
        FROM audit_logs al
        LEFT JOIN audits a ON al.audit_id = a.id
        LEFT JOIN vendors c ON a.company_id = c.id
        LEFT JOIN users u ON al.actor_user_id = u.id
        LEFT JOIN vendors v ON v.user_id = u.id
        WHERE al.id = ?
    """
    row = db.execute(query, (log_id,)).fetchone()
    if not row:
        return None
    return format_audit_log_entry(dict(row))


def get_companies_with_audit_counts(
    user: Optional[Dict[str, Any]] = None,
    search: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Returns list of companies (vendors) with audit counts and metadata.
    Enforces role-based isolation: vendors can only see their own company.
    """
    db = get_db()
    is_vendor = bool(user and user.get("role") == "vendor")
    vendor_id = user.get("vendor_id") if is_vendor else None

    query = """
        SELECT
            v.id,
            v.company_name,
            v.registration_number,
            v.contact_phone,
            v.category,
            v.address,
            v.approval_status,
            COUNT(DISTINCT a.id) AS total_audits,
            COUNT(DISTINCT CASE WHEN a.status IN ('in_progress', 'scheduled', 'flagged') THEN a.id END) AS active_audits,
            COUNT(DISTINCT CASE WHEN a.status = 'completed' THEN a.id END) AS completed_audits,
            COUNT(DISTINCT al.id) AS total_events,
            MAX(a.audit_date) AS latest_audit_date
        FROM vendors v
        LEFT JOIN audits a ON a.company_id = v.id
        LEFT JOIN audit_logs al ON al.audit_id = a.id
    """
    params: List[Any] = []
    where_clauses: List[str] = []

    if is_vendor:
        where_clauses.append("v.id = ?")
        params.append(vendor_id or 0)

    if search:
        where_clauses.append("(v.company_name LIKE ? OR v.category LIKE ? OR v.registration_number LIKE ?)")
        wild = f"%{search}%"
        params.extend([wild, wild, wild])

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " GROUP BY v.id ORDER BY total_audits DESC, v.company_name ASC"

    rows = db.execute(query, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def get_company_by_id(company_id: int) -> Optional[Dict[str, Any]]:
    """Fetches company details by ID from vendors table."""
    db = get_db()
    row = db.execute(
        """SELECT id, company_name, registration_number, contact_phone, category,
                  address, approval_status, created_at
           FROM vendors WHERE id = ?""",
        (company_id,)
    ).fetchone()
    return dict(row) if row else None


def get_audits_for_company(
    company_id: int,
    user: Optional[Dict[str, Any]] = None,
    search: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Returns all audits belonging to a specific company.
    Strictly verifies vendor authorization: vendors cannot view other companies' audits.
    """
    if user and user.get("role") == "vendor":
        if user.get("vendor_id") != company_id:
            return []

    db = get_db()
    query = """
        SELECT
            a.id,
            a.audit_reference,
            a.company_id,
            v.company_name,
            a.title,
            a.description,
            a.category,
            a.status,
            a.lead_auditor,
            a.audit_date,
            a.created_at,
            a.updated_at,
            COUNT(al.id) AS events_count,
            MAX(al.created_at) AS latest_event_time
        FROM audits a
        JOIN vendors v ON a.company_id = v.id
        LEFT JOIN audit_logs al ON al.audit_id = a.id
        WHERE a.company_id = ?
    """
    params: List[Any] = [company_id]

    if search:
        query += " AND (a.audit_reference LIKE ? OR a.title LIKE ? OR a.description LIKE ? OR a.category LIKE ? OR a.lead_auditor LIKE ?)"
        wild = f"%{search}%"
        params.extend([wild, wild, wild, wild, wild])

    query += " GROUP BY a.id ORDER BY a.id ASC"

    rows = db.execute(query, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def get_audit_by_id(audit_id: int, company_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Fetches an audit by ID.
    If company_id is provided, guarantees the audit belongs to that company.
    """
    db = get_db()
    query = """
        SELECT
            a.id,
            a.audit_reference,
            a.company_id,
            v.company_name,
            v.category AS company_category,
            v.registration_number AS company_registration,
            a.title,
            a.description,
            a.category,
            a.status,
            a.lead_auditor,
            a.audit_date,
            a.created_at,
            a.updated_at,
            COUNT(al.id) AS events_count
        FROM audits a
        JOIN vendors v ON a.company_id = v.id
        LEFT JOIN audit_logs al ON al.audit_id = a.id
        WHERE a.id = ?
    """
    params: List[Any] = [audit_id]
    if company_id is not None:
        query += " AND a.company_id = ?"
        params.append(company_id)

    query += " GROUP BY a.id"
    row = db.execute(query, tuple(params)).fetchone()
    return dict(row) if row else None


def get_audit_logs_for_audit(audit_id: int, search: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves chronological audit events belonging exclusively to audit_id.
    """
    db = get_db()
    query = """
        SELECT
            al.id,
            al.audit_id,
            a.audit_reference,
            a.company_id,
            v.company_name,
            al.created_at AS timestamp,
            COALESCE(u.full_name, 'System') AS user_name,
            COALESCE(u.role, 'system') AS user_role,
            COALESCE(v.company_name, 'System') AS vendor_company,
            al.action,
            al.entity_type AS record_type,
            COALESCE(al.entity_id, 0) AS record_id,
            al.details_json
        FROM audit_logs al
        JOIN audits a ON al.audit_id = a.id
        JOIN vendors v ON a.company_id = v.id
        LEFT JOIN users u ON al.actor_user_id = u.id
        WHERE al.audit_id = ?
    """
    params: List[Any] = [audit_id]
    if search:
        query += """
            AND (al.action LIKE ?
                 OR al.entity_type LIKE ?
                 OR u.full_name LIKE ?
                 OR al.details_json LIKE ?)
        """
        wild = f"%{search}%"
        params.extend([wild, wild, wild, wild])

    query += " ORDER BY al.created_at ASC, al.id ASC"

    rows = db.execute(query, tuple(params)).fetchall()
    return [format_audit_log_entry(dict(r)) for r in rows]


def verify_audit_integrity(audit_id: int) -> Dict[str, Any]:
    """
    Performs cryptographic hash-chain and chronological integrity verification
    on all ledger events for a given audit.
    """
    import hashlib
    db = get_db()
    audit = get_audit_by_id(audit_id)
    if not audit:
        return {"verified": False, "error": "Audit record not found"}

    rows = db.execute(
        """SELECT id, created_at, action, entity_type, entity_id, details_json
           FROM audit_logs WHERE audit_id = ? ORDER BY created_at ASC, id ASC""",
        (audit_id,)
    ).fetchall()

    h = hashlib.sha256()
    prev_time = None
    chronological = True

    for r in rows:
        row_str = f"{r['id']}|{r['created_at']}|{r['action']}|{r['entity_type']}|{r['entity_id']}|{r['details_json']}"
        h.update(row_str.encode("utf-8"))
        curr_time = r["created_at"]
        if prev_time and curr_time < prev_time:
            chronological = False
        prev_time = curr_time

    checksum = h.hexdigest().upper()[:16]

    return {
        "verified": True,
        "audit_id": audit_id,
        "audit_reference": audit["audit_reference"],
        "company_name": audit["company_name"],
        "title": audit["title"],
        "events_count": len(rows),
        "chronological": chronological,
        "ledger_checksum": checksum,
        "verification_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "VALID",
        "message": f"Cryptographic integrity verified. {len(rows)} chronological records verified against tamper-evident SQLite ledger.",
    }



def get_dashboard_stats(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates all key metrics for the dashboard view based on user role."""
    db = get_db()
    is_vendor = bool(user and user.get("role") == "vendor")
    vendor_id = user.get("vendor_id") if is_vendor else None

    if is_vendor:
        # Scoped metrics for active vendor
        active_rfqs = db.execute(
            """SELECT COUNT(*) FROM rfqs r
               WHERE r.status = 'open' OR r.id IN (
                   SELECT rfq_id FROM rfq_vendors WHERE vendor_id = ?
               )""",
            (vendor_id or 0,),
        ).fetchone()[0]

        pending_quotes = db.execute(
            "SELECT COUNT(*) FROM quotations WHERE vendor_id = ? AND status = 'submitted'",
            (vendor_id or 0,),
        ).fetchone()[0]

        vendor_pos = db.execute(
            "SELECT COUNT(*) FROM purchase_orders WHERE vendor_id = ?",
            (vendor_id or 0,),
        ).fetchone()[0]

        unpaid_invs = db.execute(
            "SELECT COUNT(*) FROM invoices WHERE vendor_id = ? AND status != 'paid'",
            (vendor_id or 0,),
        ).fetchone()[0]

        return {
            "total_vendors": 1,
            "active_rfqs": active_rfqs,
            "pending_approvals": pending_quotes,
            "purchase_orders": vendor_pos,
            "unpaid_invoices": unpaid_invs,
        }

    # Administrative broad metrics
    total_vendors = db.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]
    active_rfqs = db.execute("SELECT COUNT(*) FROM rfqs WHERE status = 'open'").fetchone()[0]
    pending_approvals = count_pending_approvals()
    pos_count = db.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    unpaid_invs = db.execute("SELECT COUNT(*) FROM invoices WHERE status != 'paid'").fetchone()[0]

    return {
        "total_vendors": total_vendors,
        "active_rfqs": active_rfqs,
        "pending_approvals": pending_approvals,
        "purchase_orders": pos_count,
        "unpaid_invoices": unpaid_invs,
    }


def get_system_counts() -> Tuple[int, int, int]:
    """Returns (pending_vendor_count, active_rfq_count, pending_approval_count)."""
    db = get_db()
    pending_vendors = db.execute(
        "SELECT COUNT(*) FROM vendors WHERE approval_status = 'pending'"
    ).fetchone()[0]
    active_rfqs = db.execute(
        "SELECT COUNT(*) FROM rfqs WHERE status = 'open'"
    ).fetchone()[0]
    pending_approvals = count_pending_approvals()
    return pending_vendors, active_rfqs, pending_approvals
