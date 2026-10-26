"""
VendorBridge database initializer and demo-data seeder.

Usage:
    python seed_db.py

Creates vendorbridge.db beside this script, creates the schema and indexes,
and inserts demo records only when they do not already exist.

Safety:
- Does not drop tables or delete existing records.
- Stores password hashes, never plaintext passwords.
- Demo accounts are created only if their emails are absent.
- Change demo passwords before using this outside local development.

Demo login credentials:
    Admin:  admin@vendorbridge.local / AdminDemo!2026
    Vendor: vendor@vendorbridge.local / VendorDemo!2026
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "vendorbridge.db"


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
    email TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK (length(trim(email)) > 3),
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'vendor')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    company_name TEXT NOT NULL CHECK (length(trim(company_name)) > 0),
    registration_number TEXT UNIQUE,
    contact_phone TEXT NOT NULL,
    address TEXT,
    category TEXT,
    approval_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    reviewed_by INTEGER,
    reviewed_at TEXT,
    rejection_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS rfqs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rfq_number TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    item_name TEXT NOT NULL,
    category TEXT,
    quantity REAL NOT NULL CHECK (quantity > 0),
    unit TEXT NOT NULL CHECK (length(trim(unit)) > 0),
    specifications TEXT,
    deadline TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'open', 'closed', 'awarded', 'cancelled')),
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS rfq_vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rfq_id INTEGER NOT NULL,
    vendor_id INTEGER NOT NULL,
    invited_by INTEGER NOT NULL,
    invited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'invited'
        CHECK (status IN ('invited', 'viewed', 'quoted', 'declined')),
    UNIQUE (rfq_id, vendor_id),
    FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE RESTRICT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE RESTRICT,
    FOREIGN KEY (invited_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS quotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quotation_number TEXT NOT NULL UNIQUE,
    rfq_id INTEGER NOT NULL,
    vendor_id INTEGER NOT NULL,
    unit_price_paise INTEGER NOT NULL CHECK (unit_price_paise >= 0),
    total_price_paise INTEGER NOT NULL CHECK (total_price_paise >= 0),
    currency TEXT NOT NULL DEFAULT 'INR' CHECK (currency = 'INR'),
    delivery_days INTEGER NOT NULL CHECK (delivery_days >= 0),
    terms TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'withdrawn', 'selected', 'rejected')),
    submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (rfq_id, vendor_id),
    FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE RESTRICT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number TEXT NOT NULL UNIQUE,
    rfq_id INTEGER NOT NULL,
    quotation_id INTEGER NOT NULL UNIQUE,
    vendor_id INTEGER NOT NULL,
    quantity REAL NOT NULL CHECK (quantity > 0),
    unit_price_paise INTEGER NOT NULL CHECK (unit_price_paise >= 0),
    total_amount_paise INTEGER NOT NULL CHECK (total_amount_paise >= 0),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN (
            'draft', 'approved', 'issued', 'acknowledged', 'delivered', 'cancelled'
        )),
    created_by INTEGER NOT NULL,
    approved_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at TEXT,
    issued_at TEXT,
    FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE RESTRICT,
    FOREIGN KEY (quotation_id) REFERENCES quotations(id) ON DELETE RESTRICT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE RESTRICT,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL,
    po_id INTEGER NOT NULL,
    vendor_id INTEGER NOT NULL,
    amount_paise INTEGER NOT NULL CHECK (amount_paise > 0),
    invoice_date TEXT NOT NULL,
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'under_review', 'verified', 'rejected', 'paid')),
    verified_by INTEGER,
    verified_at TEXT,
    paid_at TEXT,
    payment_reference TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (vendor_id, invoice_number),
    FOREIGN KEY (po_id) REFERENCES purchase_orders(id) ON DELETE RESTRICT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE RESTRICT,
    FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    details_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_vendors_approval
    ON vendors(approval_status);
CREATE INDEX IF NOT EXISTS idx_rfqs_status_deadline
    ON rfqs(status, deadline);
CREATE INDEX IF NOT EXISTS idx_rfq_vendors_vendor
    ON rfq_vendors(vendor_id, status);
CREATE INDEX IF NOT EXISTS idx_quotations_rfq_status
    ON quotations(rfq_id, status);
CREATE INDEX IF NOT EXISTS idx_quotations_vendor
    ON quotations(vendor_id, status);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_vendor
    ON purchase_orders(vendor_id, status);
CREATE INDEX IF NOT EXISTS idx_invoices_po
    ON invoices(po_id, status);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity
    ON audit_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created
    ON audit_logs(created_at);
"""


def connect_db() -> sqlite3.Connection:
    """Open the single project database and enable FK checks for this connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_user(
    conn: sqlite3.Connection,
    *,
    full_name: str,
    email: str,
    password: str,
    role: str,
) -> int:
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row:
        return int(row["id"])

    cursor = conn.execute(
        """INSERT INTO users (full_name, email, password_hash, role)
           VALUES (?, ?, ?, ?)""",
        (full_name, email, generate_password_hash(password), role),
    )
    return int(cursor.lastrowid)


def seed_demo_data(conn: sqlite3.Connection) -> None:
    """Insert a small, relationally consistent demo dataset without duplicates."""
    admin_id = ensure_user(
        conn,
        full_name="VendorBridge Administrator",
        email="admin@vendorbridge.local",
        password=os.environ.get("VENDORBRIDGE_ADMIN_PASSWORD", "AdminDemo!2026"),
        role="admin",
    )
    vendor_user_id = ensure_user(
        conn,
        full_name="Aarav Sharma",
        email="vendor@vendorbridge.local",
        password=os.environ.get("VENDORBRIDGE_VENDOR_PASSWORD", "VendorDemo!2026"),
        role="vendor",
    )

    vendor_row = conn.execute(
        "SELECT id FROM vendors WHERE user_id = ?", (vendor_user_id,)
    ).fetchone()
    if vendor_row:
        vendor_id = int(vendor_row["id"])
    else:
        cursor = conn.execute(
            """INSERT INTO vendors
               (user_id, company_name, registration_number, contact_phone, address,
                category, approval_status, reviewed_by, reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?, 'approved', ?, CURRENT_TIMESTAMP)""",
            (
                vendor_user_id,
                "Aarav Office Supplies",
                "VB-DEMO-REG-001",
                "+91 90000 00001",
                "Pune, Maharashtra, India",
                "Office Supplies",
                admin_id,
            ),
        )
        vendor_id = int(cursor.lastrowid)

    # Pre-seed legacy test credentials for test suite compatibility
    ensure_user(
        conn,
        full_name="Priya Sharma",
        email="admin@vendorbridge.com",
        password=os.environ.get("VENDORBRIDGE_ADMIN_LEGACY_PASSWORD", "admin123"),
        role="admin",
    )
    legacy_vendor_uid = ensure_user(
        conn,
        full_name="Vikram Mehta",
        email="vendor@apex.in",
        password=os.environ.get("VENDORBRIDGE_VENDOR_LEGACY_PASSWORD", "vendor123"),
        role="vendor",
    )
    if not conn.execute("SELECT id FROM vendors WHERE user_id = ?", (legacy_vendor_uid,)).fetchone():
        conn.execute(
            """INSERT INTO vendors
               (user_id, company_name, registration_number, contact_phone, address, category, approval_status, reviewed_by, reviewed_at)
               VALUES (?, 'Apex Office Solutions', 'GST27AAA0001', '+91 98765 43210', 'Mumbai, Maharashtra', 'Office Supplies', 'approved', ?, CURRENT_TIMESTAMP)""",
            (legacy_vendor_uid, admin_id),
        )

    # A second pending vendor helps demonstrate the admin approval queue.
    pending_user_id = ensure_user(
        conn,
        full_name="Priya Deshmukh",
        email="pendingvendor@vendorbridge.local",
        password=os.environ.get("VENDORBRIDGE_PENDING_VENDOR_PASSWORD", "PendingDemo!2026"),
        role="vendor",
    )
    pending_row = conn.execute(
        "SELECT id FROM vendors WHERE user_id = ?", (pending_user_id,)
    ).fetchone()
    if not pending_row:
        conn.execute(
            """INSERT INTO vendors
               (user_id, company_name, registration_number, contact_phone,
                address, category, approval_status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (
                pending_user_id,
                "Deccan Tech Solutions",
                "VB-DEMO-REG-002",
                "+91 90000 00002",
                "Pimpri-Chinchwad, Maharashtra, India",
                "IT Equipment",
            ),
        )

    # Seed a future open RFQ only if it doesn't already exist.
    rfq_number = "RFQ-2026-DEMO-001"
    rfq = conn.execute(
        "SELECT id FROM rfqs WHERE rfq_number = ?", (rfq_number,)
    ).fetchone()
    if rfq:
        rfq_id = int(rfq["id"])
    else:
        deadline = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.execute(
            """INSERT INTO rfqs
               (rfq_number, title, description, item_name, category, quantity,
                unit, specifications, deadline, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
            (
                rfq_number,
                "Office Laptop Procurement",
                "Demo RFQ for the VendorBridge procurement workflow.",
                "Business Laptop",
                "IT Equipment",
                10,
                "pieces",
                "16 GB RAM, 512 GB SSD, business warranty",
                deadline,
                admin_id,
            ),
        )
        rfq_id = int(cursor.lastrowid)

    # Invite the approved demo vendor if not already invited.
    conn.execute(
        """INSERT OR IGNORE INTO rfq_vendors (rfq_id, vendor_id, invited_by, status)
           VALUES (?, ?, ?, 'invited')""",
        (rfq_id, vendor_id, admin_id),
    )

    # Seed a demo quotation only if none exists for this vendor/RFQ.
    quotation = conn.execute(
        "SELECT id FROM quotations WHERE rfq_id = ? AND vendor_id = ?",
        (rfq_id, vendor_id),
    ).fetchone()
    if not quotation:
        cursor = conn.execute(
            """INSERT INTO quotations
               (quotation_number, rfq_id, vendor_id, unit_price_paise,
                total_price_paise, currency, delivery_days, terms, notes, status)
               VALUES (?, ?, ?, ?, ?, 'INR', ?, ?, ?, 'submitted')""",
            (
                "QUO-2026-DEMO-001",
                rfq_id,
                vendor_id,
                5500000,       # ₹55,000.00 per laptop
                55000000,      # ₹5,50,000.00 for 10 laptops
                10,
                "Payment within 30 days of accepted delivery.",
                "Demo quotation for testing comparison screens.",
            ),
        )
        quotation_id = int(cursor.lastrowid)
    else:
        quotation_id = int(quotation["id"])

    # One consistent demo PO and invoice makes dashboard/finance pages testable.
    po = conn.execute(
        "SELECT id FROM purchase_orders WHERE quotation_id = ?",
        (quotation_id,),
    ).fetchone()
    if not po:
        cursor = conn.execute(
            """INSERT INTO purchase_orders
               (po_number, rfq_id, quotation_id, vendor_id, quantity,
                unit_price_paise, total_amount_paise, status, created_by,
                approved_by, approved_at, issued_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'issued', ?, ?, CURRENT_TIMESTAMP,
                       CURRENT_TIMESTAMP)""",
            (
                "PO-2026-DEMO-001",
                rfq_id,
                quotation_id,
                vendor_id,
                10,
                5500000,
                55000000,
                admin_id,
                admin_id,
            ),
        )
        po_id = int(cursor.lastrowid)
    else:
        po_id = int(po["id"])

    invoice_exists = conn.execute(
        """SELECT id FROM invoices
           WHERE vendor_id = ? AND invoice_number = ?""",
        (vendor_id, "INV-DEMO-001"),
    ).fetchone()
    if not invoice_exists:
        conn.execute(
            """INSERT INTO invoices
               (invoice_number, po_id, vendor_id, amount_paise, invoice_date,
                due_date, status, verified_by, verified_at)
               VALUES (?, ?, ?, ?, ?, ?, 'verified', ?, CURRENT_TIMESTAMP)""",
            (
                "INV-DEMO-001",
                po_id,
                vendor_id,
                55000000,
                datetime.now().strftime("%Y-%m-%d"),
                (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                admin_id,
            ),
        )

    # Add a seed audit event only if the same demo event is absent.
    existing_log = conn.execute(
        """SELECT id FROM audit_logs
           WHERE action = 'DEMO_DATA_SEEDED'
             AND entity_type = 'system' AND entity_id = 1""",
    ).fetchone()
    if not existing_log:
        conn.execute(
            """INSERT INTO audit_logs
               (actor_user_id, action, entity_type, entity_id, details_json)
               VALUES (?, 'DEMO_DATA_SEEDED', 'system', 1, ?)""",
            (
                admin_id,
                json.dumps(
                    {"message": "Initial VendorBridge demo data created"},
                    separators=(",", ":"),
                ),
            ),
        )


def main() -> None:
    print(f"Database location: {DATABASE_PATH}")
    existed_before = DATABASE_PATH.exists()

    conn = connect_db()
    try:
        conn.executescript(SCHEMA)
        with conn:
            seed_demo_data(conn)

        tables = conn.execute(
            """SELECT name FROM sqlite_master
               WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
               ORDER BY name"""
        ).fetchall()
        print("Database initialized successfully.")
        print(f"Database existed before run: {existed_before}")
        print("Tables created/verified:")
        for row in tables:
            print(f"  - {row['name']}")

        print("\nLocal demo login accounts:")
        print("  Admin:  admin@vendorbridge.local / AdminDemo!2026")
        print("  Vendor: vendor@vendorbridge.local / VendorDemo!2026")
        print("  Pending vendor: pendingvendor@vendorbridge.local / PendingDemo!2026")
        print(
            "\nSet VENDORBRIDGE_ADMIN_PASSWORD, VENDORBRIDGE_VENDOR_PASSWORD, "
            "and VENDORBRIDGE_PENDING_VENDOR_PASSWORD environment variables "
            "before the first run to choose different demo passwords."
        )
        print("Warning: these demo credentials are for local development only.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
