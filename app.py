"""
VendorBridge — Flask Application
Procurement Management System
"""
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'vendorbridge-enterprise-hackathon-2026-key'
app.permanent_session_lifetime = timedelta(days=7)

def verify_password(stored_password, provided_password):
    """Safely verify passwords supporting both hashed and legacy plain text."""
    if not stored_password or not provided_password:
        return False
    if stored_password.startswith(('pbkdf2:', 'scrypt:', 'argon2:')):
        return check_password_hash(stored_password, provided_password)
    return stored_password == provided_password

# ── User Accounts ──
USERS = {
    'admin@vendorbridge.com': {
        'id': 1,
        'name': 'Priya Sharma',
        'email': 'admin@vendorbridge.com',
        'password': generate_password_hash('admin123'),
        'role': 'admin',
        'role_title': 'Procurement Officer & System Admin',
        'department': 'Central Procurement & Strategic Sourcing',
        'phone': '+91 98765 00001',
        'address': 'VendorBridge HQ, Floor 4, Technology Park, Mumbai',
        'status': 'Active',
        'joined': 'January 2025',
        'bio': 'Overseeing corporate procurement, vendor approvals, and purchase order lifecycles.'
    },
    'vendor@apex.in': {
        'id': 2,
        'name': 'Vikram Mehta',
        'company': 'Apex Office Solutions',
        'email': 'vendor@apex.in',
        'password': generate_password_hash('vendor123'),
        'role': 'vendor',
        'role_title': 'Authorized Vendor Partner',
        'department': 'Apex Office Solutions — Sales & Enterprise Bids',
        'phone': '+91 98765 43210',
        'address': 'Apex Tower, Andheri East, Mumbai, Maharashtra',
        'status': 'Approved',
        'joined': 'September 2026',
        'bio': 'Primary contact for Apex Office Solutions enterprise tenders and supply bids.'
    }
}

def get_current_user():
    """Retrieve the currently logged-in user or None."""
    email = session.get('user_email')
    if email and email in USERS:
        return USERS[email]
    return None

# ── Sample Data for Procurement & Finance ──
SAMPLE_VENDORS = [
    {'id': 1, 'name': 'Apex Office Solutions', 'contact_name': 'Vikram Mehta', 'company': 'Apex Corp',
     'email': 'vendor@apex.in', 'phone': '+91 98765 43210', 'category': 'supplies', 'status': 'approved',
     'address': 'Apex Tower, Andheri East, Mumbai, Maharashtra', 'tax_id': 'GST27AAA0001', 'created_at': '2026-09-15', 'notes': 'Preferred corporate supplier'},
    {'id': 2, 'name': 'TechNova IT Services', 'contact_name': 'Rahul Nair', 'company': 'TechNova Pvt Ltd',
     'email': 'sales@technova.io', 'phone': '+91 87654 32109', 'category': 'it', 'status': 'approved',
     'address': 'Tech Park, Whitefield, Bangalore, Karnataka', 'tax_id': 'GST29BBB0002', 'created_at': '2026-09-20', 'notes': 'Tier 1 Network Infrastructure'},
    {'id': 3, 'name': 'GreenBuild Construction', 'contact_name': 'Anita Deshmukh', 'company': 'GreenBuild LLC',
     'email': 'info@greenbuild.com', 'phone': '+91 76543 21098', 'category': 'construction', 'status': 'pending',
     'address': 'Shivaji Nagar, Pune, Maharashtra', 'tax_id': 'GST27CCC0003', 'created_at': '2026-10-10', 'notes': 'Awaiting trade license verification'},
    {'id': 4, 'name': 'LogiTrack Shipping', 'contact_name': 'Suresh Patel', 'company': 'LogiTrack Freight',
     'email': 'ops@logitrack.in', 'phone': '+91 65432 10987', 'category': 'logistics', 'status': 'rejected',
     'address': 'Harbour Road, Chennai, Tamil Nadu', 'tax_id': 'GST33DDD0004', 'created_at': '2026-10-05',
     'rejection_reason': 'Incomplete documentation and unverifiable references.', 'notes': 'Non-compliant with mandatory ISO audit'},
    {'id': 5, 'name': 'ClearView Consulting', 'contact_name': 'Devendra Rao', 'company': 'ClearView Group',
     'email': 'hello@clearview.co', 'phone': '+91 54321 09876', 'category': 'consulting', 'status': 'pending',
     'address': 'HITEC City, Hyderabad, Telangana', 'tax_id': 'GST36EEE0005', 'created_at': '2026-10-22', 'notes': 'Self-registered vendor partner application'},
]

SAMPLE_RFQS = [
    {'id': 1, 'number': 'RFQ-2026-001', 'title': 'Office Furniture Procurement Q4',
     'description': 'Ergonomic desks, chairs, and storage cabinets for the new wing.',
     'budget': '₹5,00,000', 'budget_value': 500000, 'deadline': '2026-11-15', 'status': 'open', 'bid_count': 2,
     'created_at': '2026-10-01', 'is_overdue': False,
     'invited_vendors': ['Apex Office Solutions', 'TechNova IT Services'],
     'line_items': [
         {'name': 'Ergonomic Desk', 'quantity': 25, 'unit': 'pcs', 'spec': 'Height adjustable, 120x60cm'},
         {'name': 'Office Chair', 'quantity': 25, 'unit': 'pcs', 'spec': 'Lumbar support, mesh back'},
         {'name': 'Storage Cabinet', 'quantity': 10, 'unit': 'pcs', 'spec': '4-drawer, steel'}
     ]},
    {'id': 2, 'number': 'RFQ-2026-002', 'title': 'Network Infrastructure Upgrade',
     'description': 'Switches, access points, and cabling for campus-wide network upgrade.',
     'budget': '₹12,00,000', 'budget_value': 1200000, 'deadline': '2026-11-30', 'status': 'open', 'bid_count': 1,
     'created_at': '2026-10-12', 'is_overdue': False,
     'invited_vendors': ['TechNova IT Services'],
     'line_items': [
         {'name': 'Core Switch 48-Port', 'quantity': 4, 'unit': 'pcs', 'spec': 'Managed PoE+ Gigabit'},
         {'name': 'Wireless Access Point', 'quantity': 16, 'unit': 'pcs', 'spec': 'Wi-Fi 6 Dual Band'},
         {'name': 'Cat6 Shielded Cable Reel', 'quantity': 8, 'unit': 'reels', 'spec': '305m low-smoke halogen'}
     ]},
    {'id': 3, 'number': 'RFQ-2026-003', 'title': 'Annual Stationery Supply',
     'description': 'Pens, paper, folders, binders, and miscellaneous office supplies for FY2027.',
     'budget': '₹1,50,000', 'budget_value': 150000, 'deadline': '2026-10-25', 'status': 'closed', 'bid_count': 1,
     'is_overdue': True, 'created_at': '2026-09-28',
     'invited_vendors': ['Apex Office Solutions'],
     'line_items': [
         {'name': 'A4 Copier Paper (Cartons)', 'quantity': 100, 'unit': 'cartons', 'spec': '75 GSM high brightness'},
         {'name': 'Ballpoint Pens Box', 'quantity': 50, 'unit': 'boxes', 'spec': 'Blue / Black assortment'}
     ]},
    {'id': 4, 'number': 'RFQ-2026-004', 'title': 'Building Maintenance Contract',
     'description': 'Comprehensive annual maintenance for HVAC, plumbing, and electrical systems.',
     'budget': '₹8,00,000', 'budget_value': 800000, 'deadline': '2026-12-01', 'status': 'draft', 'bid_count': 0,
     'created_at': '2026-10-24', 'is_overdue': False,
     'invited_vendors': [],
     'line_items': []},
]

SAMPLE_QUOTATIONS = [
    {'id': 1, 'number': 'QT-001', 'rfq_id': 1, 'rfq_number': 'RFQ-2026-001', 'vendor_name': 'Apex Office Solutions',
     'vendor_email': 'vendor@apex.in', 'total_price': '₹4,75,000', 'price_value': 475000,
     'delivery_days': 21, 'submitted_at': '2026-10-18', 'status': 'submitted',
     'notes': 'Includes free on-site assembly, placement, and 2-year enterprise warranty.'},
    {'id': 2, 'number': 'QT-002', 'rfq_id': 1, 'rfq_number': 'RFQ-2026-001', 'vendor_name': 'TechNova IT Services',
     'vendor_email': 'sales@technova.io', 'total_price': '₹5,10,000', 'price_value': 510000,
     'delivery_days': 14, 'submitted_at': '2026-10-19', 'status': 'submitted',
     'notes': 'Premium ergonomic range, express 14-day delivery with replacement guarantee.'},
    {'id': 3, 'number': 'QT-003', 'rfq_id': 2, 'rfq_number': 'RFQ-2026-002', 'vendor_name': 'TechNova IT Services',
     'vendor_email': 'sales@technova.io', 'total_price': '₹11,40,000', 'price_value': 1140000,
     'delivery_days': 30, 'submitted_at': '2026-10-20', 'status': 'under_review',
     'notes': 'Cisco enterprise hardware with 3-year OEM SLA support.'},
]

SAMPLE_APPROVALS = [
    {'id': 1, 'rfq_number': 'RFQ-2026-003', 'rfq_title': 'Annual Stationery Supply',
     'selected_vendor': 'Apex Office Solutions', 'bid_amount': '₹1,32,000',
     'delivery_days': 7, 'requested_by': 'Priya Sharma'},
]

SAMPLE_POS = [
    {'id': 1, 'number': 'PO-2026-001', 'rfq_number': 'RFQ-2026-003', 'vendor_name': 'Apex Office Solutions',
     'total': '₹1,32,000', 'date': '2026-10-20', 'status': 'confirmed', 'line_items': []},
    {'id': 2, 'number': 'PO-2026-002', 'rfq_number': 'RFQ-2026-001', 'vendor_name': 'TechNova IT Services',
     'total': '₹5,10,000', 'date': '2026-10-23', 'status': 'draft', 'line_items': []},
]

SAMPLE_INVOICES = [
    {'id': 1, 'number': 'INV-2026-001', 'vendor_name': 'Apex Office Solutions',
     'po_number': 'PO-2026-001', 'amount': '₹1,32,000', 'po_amount': '₹1,32,000',
     'date': '2026-10-22', 'verification_status': 'verified', 'payment_status': 'paid',
     'has_mismatch': False},
    {'id': 2, 'number': 'INV-2026-002', 'vendor_name': 'TechNova IT Services',
     'po_number': 'PO-2026-002', 'amount': '₹5,25,000', 'po_amount': '₹5,10,000',
     'date': '2026-10-25', 'verification_status': 'pending', 'payment_status': 'unpaid',
     'has_mismatch': True,
     'mismatch_reason': 'Invoice amount (₹5,25,000) exceeds PO value (₹5,10,000) by ₹15,000.'},
    {'id': 3, 'number': 'INV-2026-003', 'vendor_name': 'Apex Office Solutions',
     'po_number': 'PO-2026-001', 'amount': '₹45,000', 'po_amount': '₹1,32,000',
     'date': '2026-10-24', 'verification_status': 'verified', 'payment_status': 'partial',
     'has_mismatch': False, 'amount_paid': '20000'},
]

SAMPLE_PAYMENTS = [
    {'invoice_id': 2, 'invoice_number': 'INV-2026-002', 'vendor_name': 'TechNova IT Services',
     'amount': '₹5,25,000', 'amount_paid': '₹0', 'balance': '₹5,25,000',
     'due_date': '2026-11-25', 'status': 'unpaid', 'is_overdue': False},
    {'invoice_id': 3, 'invoice_number': 'INV-2026-003', 'vendor_name': 'Apex Office Solutions',
     'amount': '₹45,000', 'amount_paid': '₹20,000', 'balance': '₹25,000',
     'due_date': '2026-11-10', 'status': 'partial', 'is_overdue': False},
    {'invoice_id': 1, 'invoice_number': 'INV-2026-001', 'vendor_name': 'Apex Office Solutions',
     'amount': '₹1,32,000', 'amount_paid': '₹1,32,000', 'balance': '₹0',
     'due_date': '2026-11-01', 'status': 'paid', 'is_overdue': False},
]

SAMPLE_AUDIT = [
    {'timestamp': '2026-10-26 14:32', 'user_name': 'Priya Sharma', 'action': 'Verified Invoice',
     'record_type': 'Invoice', 'record_id': 'INV-2026-001', 'details': 'Amount matched PO-2026-001.'},
    {'timestamp': '2026-10-25 16:10', 'user_name': 'Priya Sharma', 'action': 'Registered Invoice',
     'record_type': 'Invoice', 'record_id': 'INV-2026-002', 'details': 'Mismatch flagged with PO-2026-002.'},
    {'timestamp': '2026-10-24 11:45', 'user_name': 'System', 'action': 'Generated PO',
     'record_type': 'PO', 'record_id': 'PO-2026-002', 'details': 'Created from approved RFQ-2026-001.'},
    {'timestamp': '2026-10-23 09:20', 'user_name': 'Priya Sharma', 'action': 'Approved Vendor',
     'record_type': 'Vendor', 'record_id': 'TechNova IT Services', 'details': 'Compliance documents verified.'},
    {'timestamp': '2026-10-22 17:00', 'user_name': 'Priya Sharma', 'action': 'Recorded Payment',
     'record_type': 'Invoice', 'record_id': 'INV-2026-001', 'details': 'Full payment of ₹1,32,000.'},
    {'timestamp': '2026-10-20 10:30', 'user_name': 'System', 'action': 'Generated PO',
     'record_type': 'PO', 'record_id': 'PO-2026-001', 'details': 'Created from approved RFQ-2026-003.'},
]

SAMPLE_ACTIVITY = [
    {'user': 'Priya Sharma', 'action': 'verified invoice', 'record': 'INV-2026-001',
     'time': '2 hours ago', 'color': 'green'},
    {'user': 'TechNova IT', 'action': 'submitted quotation for', 'record': 'RFQ-2026-002',
     'time': '5 hours ago', 'color': 'blue'},
    {'user': 'System', 'action': 'flagged amount mismatch on', 'record': 'INV-2026-002',
     'time': 'Yesterday', 'color': 'amber'},
    {'user': 'Priya Sharma', 'action': 'rejected vendor', 'record': 'LogiTrack Shipping',
     'time': '3 days ago', 'color': 'red'},
]

SAMPLE_TASKS = [
    {'description': 'Review vendor registration: ClearView Consulting',
     'due': 'Due today', 'priority_color': 'amber',
     'link': '/vendors?status=pending'},
    {'description': 'Verify invoice INV-2026-002 — mismatch flagged',
     'due': 'Due today', 'priority_color': 'red',
     'link': '/finance?tab=invoices'},
    {'description': 'Approve bid for RFQ-2026-003',
     'due': 'Due tomorrow', 'priority_color': 'amber',
     'link': '/procurement?tab=approvals'},
]

# ── Authentication Protection Hook ──
@app.before_request
def require_login():
    """Ensure unauthenticated users are redirected to login for protected pages."""
    public_endpoints = {'login', 'register', 'static'}
    if request.endpoint and request.endpoint not in public_endpoints:
        if not get_current_user():
            if request.endpoint != 'index':
                flash('Please sign in to access VendorBridge.', 'warning')
            return redirect(url_for('login'))

# ── Root Route ──
@app.route('/')
def index():
    if get_current_user():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# ── Authentication Routes ──
@app.route('/login', methods=['GET', 'POST'])
def login():
    if get_current_user():
        return redirect(url_for('dashboard'))

    form_errors = {}
    mode = request.args.get('mode', 'login')

    if request.method == 'POST':
        action = request.form.get('action', 'login')
        if action == 'register':
            return handle_registration()

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = USERS.get(email)
        if user and verify_password(user['password'], password):
            session.clear()
            session['user_email'] = email
            if remember:
                session.permanent = True
            
            if user.get('status') == 'Pending':
                flash(f"Welcome, {user['name']}. Your vendor application is currently awaiting administrator review.", 'warning')
            elif user.get('status') == 'Rejected':
                flash(f"Notice: Your account application was rejected. Please contact procurement support.", 'error')
            else:
                flash(f"Welcome back, {user['name']}!", 'success')
            return redirect(url_for('dashboard'))
        else:
            form_errors['general'] = 'Invalid email or password. Please verify your credentials.'
            flash('Invalid email or password. Please check your credentials.', 'error')

    return render_template('login.html', form_errors=form_errors, mode=mode)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Vendor Self-Registration route."""
    if get_current_user():
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        return handle_registration()

    return render_template('login.html', mode='register', form_errors={})

def handle_registration():
    """Processes vendor registration with strict validation and secure hashing."""
    form_errors = {}
    name = request.form.get('name', '').strip()
    company = request.form.get('company', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    # Validations
    if not name:
        form_errors['name'] = "Contact person's name is required."
    if not company:
        form_errors['company'] = 'Business/company name is required.'
    if not email:
        form_errors['email'] = 'Business email address is required.'
    elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        form_errors['email'] = 'Please provide a valid business email address.'
    elif email in USERS or any(v['email'].lower() == email for v in SAMPLE_VENDORS):
        form_errors['email'] = 'An account or vendor profile with this email already exists.'

    if not phone:
        form_errors['phone'] = 'Contact phone number is required.'
    if not password:
        form_errors['password'] = 'Password is required.'
    elif len(password) < 6:
        form_errors['password'] = 'Password must be at least 6 characters.'
    if password != confirm_password:
        form_errors['confirm_password'] = 'Passwords do not match.'

    if form_errors:
        flash('Please correct the errors in the registration form below.', 'error')
        return render_template('login.html', mode='register', form_errors=form_errors, form_data=request.form)

    # 1. Create vendor user account with strictly 'vendor' role and 'Pending' status
    user_id = max(u['id'] for u in USERS.values()) + 1 if USERS else 1
    USERS[email] = {
        'id': user_id,
        'name': name,
        'company': company,
        'email': email,
        'password': generate_password_hash(password),
        'role': 'vendor',
        'role_title': 'Vendor Partner (Pending Approval)',
        'department': f"{company} — Sales & Bid Team",
        'phone': phone,
        'address': 'Submitted during self-registration',
        'status': 'Pending',
        'joined': datetime.now().strftime('%B %Y'),
        'bio': f'Self-registered vendor partner representative for {company}.'
    }

    # 2. Create corresponding vendor profile with Pending status
    vendor_id = max(v['id'] for v in SAMPLE_VENDORS) + 1 if SAMPLE_VENDORS else 1
    SAMPLE_VENDORS.append({
        'id': vendor_id,
        'name': company,
        'contact_name': name,
        'company': company,
        'email': email,
        'phone': phone,
        'category': 'supplies',
        'status': 'pending',
        'address': 'Address to be verified upon approval',
        'tax_id': 'Pending Verification',
        'created_at': datetime.now().strftime('%Y-%m-%d'),
        'notes': f'Self-registered vendor applicant. Contact: {name} ({phone})'
    })

    # 3. Log audit trail entry
    SAMPLE_AUDIT.insert(0, {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'user_name': name,
        'action': 'Vendor Registration Submitted',
        'record_type': 'Vendor',
        'record_id': company,
        'details': f"New vendor application submitted by {name} ({email}). Initial status set to Pending approval."
    })

    flash(
        'Your vendor registration was submitted successfully and awaits review by our procurement administration. '
        'You may log in to monitor your application status.',
        'success'
    )
    return redirect(url_for('login'))

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('You have been signed out successfully.', 'info')
    return redirect(url_for('login'))

# ── Dashboard & Profile ──
@app.route('/dashboard')
def dashboard():
    user = get_current_user()
    is_vendor = user and user.get('role') == 'vendor'
    vendor_name = user.get('company') or user.get('name')

    if is_vendor:
        # Vendor-specific scoped stats
        vendor_rfqs = [r for r in SAMPLE_RFQS if vendor_name in r.get('invited_vendors', []) or r['status'] == 'open']
        vendor_quotes = [q for q in SAMPLE_QUOTATIONS if q.get('vendor_name') == vendor_name or q.get('vendor_email') == user.get('email')]
        vendor_pos = [p for p in SAMPLE_POS if p.get('vendor_name') == vendor_name]
        vendor_invoices = [i for i in SAMPLE_INVOICES if i.get('vendor_name') == vendor_name]

        stats = {
            'total_vendors': 1,
            'active_rfqs': len([r for r in vendor_rfqs if r['status'] == 'open']),
            'pending_approvals': len([q for q in vendor_quotes if q['status'] == 'submitted']),
            'purchase_orders': len(vendor_pos),
            'unpaid_invoices': sum(1 for i in vendor_invoices if i['payment_status'] != 'paid'),
        }
        recent_rfqs = vendor_rfqs[:4]
        recent_orders = vendor_pos
    else:
        stats = {
            'total_vendors': len(SAMPLE_VENDORS),
            'active_rfqs': sum(1 for r in SAMPLE_RFQS if r['status'] == 'open'),
            'pending_approvals': len(SAMPLE_APPROVALS),
            'purchase_orders': len(SAMPLE_POS),
            'unpaid_invoices': sum(1 for i in SAMPLE_INVOICES if i['payment_status'] != 'paid'),
        }
        recent_rfqs = SAMPLE_RFQS[:4]
        recent_orders = SAMPLE_POS

    return render_template('dashboard.html',
        active_page='dashboard',
        current_user=user,
        stats=stats,
        recent_activity=SAMPLE_ACTIVITY if not is_vendor else [a for a in SAMPLE_ACTIVITY if vendor_name in str(a)],
        pending_tasks=SAMPLE_TASKS if not is_vendor else [],
        recent_rfqs=recent_rfqs,
        recent_orders=recent_orders,
        pending_vendor_count=sum(1 for v in SAMPLE_VENDORS if v['status'] == 'pending'),
        active_rfq_count=sum(1 for r in SAMPLE_RFQS if r['status'] == 'open'),
        pending_approval_count=len(SAMPLE_APPROVALS),
    )

@app.route('/profile')
def profile():
    user = get_current_user()
    return render_template('dashboard.html',
        active_page='profile',
        current_user=user,
        pending_vendor_count=sum(1 for v in SAMPLE_VENDORS if v['status'] == 'pending'),
        active_rfq_count=sum(1 for r in SAMPLE_RFQS if r['status'] == 'open'),
        pending_approval_count=len(SAMPLE_APPROVALS),
    )

@app.route('/profile/update', methods=['POST'])
def update_profile():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    user['name'] = request.form.get('name', user['name']).strip()
    user['phone'] = request.form.get('phone', user.get('phone', '')).strip()
    user['department'] = request.form.get('department', user.get('department', '')).strip()
    user['address'] = request.form.get('address', user.get('address', '')).strip()
    user['bio'] = request.form.get('bio', user.get('bio', '')).strip()

    flash('Your profile changes have been saved successfully.', 'success')
    return redirect(url_for('profile'))

# ── Vendors Management & Filtering ──
@app.route('/vendors', methods=['GET'])
def vendors():
    user = get_current_user()

    # Vendor isolation: Vendors can only view their own profile/status
    if user and user.get('role') == 'vendor':
        v_email = user.get('email', '').lower()
        v_name = user.get('company') or user.get('name')
        vendor_data = [v for v in SAMPLE_VENDORS if v['email'].lower() == v_email or v['name'] == v_name]
        return render_template('vendors.html',
            active_page='vendors',
            current_user=user,
            vendors=vendor_data,
            total_vendors=len(vendor_data),
            page=1,
            total_pages=1,
            pending_vendor_count=0,
            active_rfq_count=sum(1 for r in SAMPLE_RFQS if r['status'] == 'open'),
            pending_approval_count=0,
        )

    # Admin filtering: Combined search (q) and status and category filters
    q = request.args.get('q', '').strip().lower()
    status_filter = request.args.get('status', '').strip().lower()
    category_filter = request.args.get('category', '').strip().lower()

    filtered = SAMPLE_VENDORS

    if status_filter:
        filtered = [v for v in filtered if v.get('status', '').lower() == status_filter]

    if category_filter:
        filtered = [v for v in filtered if v.get('category', '').lower() == category_filter]

    if q:
        filtered = [
            v for v in filtered
            if q in v.get('name', '').lower()
            or q in v.get('company', '').lower()
            or q in v.get('contact_name', '').lower()
            or q in v.get('email', '').lower()
            or q in v.get('phone', '').lower()
            or q in v.get('tax_id', '').lower()
        ]

    return render_template('vendors.html',
        active_page='vendors',
        current_user=user,
        vendors=filtered,
        total_vendors=len(SAMPLE_VENDORS),
        page=1,
        total_pages=1,
        pending_vendor_count=sum(1 for v in SAMPLE_VENDORS if v['status'] == 'pending'),
        active_rfq_count=sum(1 for r in SAMPLE_RFQS if r['status'] == 'open'),
        pending_approval_count=len(SAMPLE_APPROVALS),
    )

@app.route('/vendors/register', methods=['POST'])
def register_vendor():
    """Admin-initiated vendor creation."""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only administrators can register vendors directly.', 'error')
        return redirect(url_for('vendors'))

    name = request.form.get('name', '').strip()
    company = request.form.get('company', '').strip() or name
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    category = request.form.get('category', 'supplies')
    tax_id = request.form.get('tax_id', '').strip()

    if not name or not email:
        flash('Vendor name and email address are required.', 'error')
        return redirect(url_for('vendors'))

    vendor_id = max(v['id'] for v in SAMPLE_VENDORS) + 1 if SAMPLE_VENDORS else 1
    SAMPLE_VENDORS.append({
        'id': vendor_id,
        'name': name,
        'contact_name': name,
        'company': company,
        'email': email,
        'phone': phone,
        'category': category,
        'status': 'pending',
        'address': request.form.get('address', '').strip(),
        'tax_id': tax_id,
        'created_at': datetime.now().strftime('%Y-%m-%d'),
        'notes': request.form.get('notes', '').strip()
    })

    SAMPLE_AUDIT.insert(0, {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'user_name': user['name'],
        'action': 'Added Vendor Record',
        'record_type': 'Vendor',
        'record_id': name,
        'details': f"Vendor {name} ({email}) registered by administrator. Status: Pending approval."
    })

    flash(f"Vendor '{name}' registered successfully. Awaiting approval.", 'success')
    return redirect(url_for('vendors'))

@app.route('/vendors/<int:vendor_id>/approve', methods=['POST'])
def approve_vendor(vendor_id):
    """Admin approves a pending vendor registration."""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only administrators can approve vendor registrations.', 'error')
        return redirect(url_for('vendors'))

    vendor = next((v for v in SAMPLE_VENDORS if v['id'] == vendor_id), None)
    if not vendor:
        flash('Vendor not found.', 'error')
        return redirect(url_for('vendors'))

    vendor['status'] = 'approved'
    vendor.pop('rejection_reason', None)

    # Also update associated user account status
    v_email = vendor.get('email', '').lower()
    if v_email in USERS:
        USERS[v_email]['status'] = 'Active'
        USERS[v_email]['role_title'] = 'Authorized Vendor Partner'

    SAMPLE_AUDIT.insert(0, {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'user_name': user['name'],
        'action': 'Approved Vendor Registration',
        'record_type': 'Vendor',
        'record_id': vendor['name'],
        'details': f"Vendor registration for {vendor['name']} ({vendor['email']}) approved by {user['name']}."
    })

    flash(f"Vendor '{vendor['name']}' has been officially approved. Account is now active.", 'success')
    return redirect(url_for('vendors'))

@app.route('/vendors/<int:vendor_id>/reject', methods=['POST'])
def reject_vendor(vendor_id):
    """Admin rejects a vendor registration with recorded reason."""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only administrators can reject vendor registrations.', 'error')
        return redirect(url_for('vendors'))

    vendor = next((v for v in SAMPLE_VENDORS if v['id'] == vendor_id), None)
    if not vendor:
        flash('Vendor not found.', 'error')
        return redirect(url_for('vendors'))

    reason = request.form.get('reason', '').strip() or 'Registration criteria not met upon review.'
    vendor['status'] = 'rejected'
    vendor['rejection_reason'] = reason

    v_email = vendor.get('email', '').lower()
    if v_email in USERS:
        USERS[v_email]['status'] = 'Rejected'
        USERS[v_email]['rejection_reason'] = reason

    SAMPLE_AUDIT.insert(0, {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'user_name': user['name'],
        'action': 'Rejected Vendor Registration',
        'record_type': 'Vendor',
        'record_id': vendor['name'],
        'details': f"Vendor registration rejected by {user['name']}. Reason: {reason}"
    })

    flash(f"Vendor registration for '{vendor['name']}' was rejected.", 'warning')
    return redirect(url_for('vendors'))

# ── Procurement Workspace & Dynamic Quotation Comparison ──
@app.route('/procurement')
def procurement():
    user = get_current_user()
    is_vendor = user and user.get('role') == 'vendor'
    vendor_name = user.get('company') or user.get('name') if user else ''
    active_tab = request.args.get('tab', 'rfqs')

    # Security: Vendors cannot access bid comparison or administrative approvals
    if is_vendor and active_tab in ['comparison', 'approvals']:
        flash('Restricted: Vendors cannot access comparative bidding analysis or administrative approvals.', 'warning')
        return redirect(url_for('procurement', tab='rfqs'))

    # RFQ filtering based on role
    if is_vendor:
        # Vendor only sees RFQs they are invited to or public open tenders
        visible_rfqs = [
            r for r in SAMPLE_RFQS
            if vendor_name in r.get('invited_vendors', []) or r['status'] == 'open'
        ]
        # Vendor only sees their own quotations
        visible_quotations = [
            q for q in SAMPLE_QUOTATIONS
            if q.get('vendor_name') == vendor_name or q.get('vendor_email') == user.get('email')
        ]
        # Vendor only sees their own purchase orders
        visible_pos = [p for p in SAMPLE_POS if p.get('vendor_name') == vendor_name]
    else:
        visible_rfqs = SAMPLE_RFQS
        visible_quotations = SAMPLE_QUOTATIONS
        visible_pos = SAMPLE_POS

    # Dynamic Bid Comparison for selected RFQ
    compare_rfq_id = request.args.get('compare_rfq')
    selected_rfq = None
    comparison_data = None

    if compare_rfq_id and not is_vendor:
        try:
            rfq_num_id = int(compare_rfq_id)
            selected_rfq = next((r for r in SAMPLE_RFQS if r['id'] == rfq_num_id), None)
        except ValueError:
            selected_rfq = next((r for r in SAMPLE_RFQS if r['number'] == compare_rfq_id), None)
    elif active_tab == 'comparison' and not is_vendor and SAMPLE_RFQS:
        selected_rfq = next((r for r in SAMPLE_RFQS if r.get('bid_count', 0) > 0), SAMPLE_RFQS[0])

    if selected_rfq and not is_vendor:
        # Gather all submitted quotes for this RFQ
        quotes = [
            q for q in SAMPLE_QUOTATIONS
            if q.get('rfq_id') == selected_rfq['id'] or q.get('rfq_number') == selected_rfq['number']
        ]
        if quotes:
            # Find the lowest numeric price
            min_price = min(q.get('price_value', 999999999) for q in quotes)
            comparison_data = []
            for q in quotes:
                item = dict(q)
                item['is_lowest'] = (item.get('price_value') == min_price)
                item['quotation_id'] = q['id']
                comparison_data.append(item)
        else:
            comparison_data = []

    return render_template('procurement.html',
        active_page='procurement',
        active_tab=active_tab,
        current_user=user,
        rfqs=visible_rfqs,
        invitations=[],
        quotations=visible_quotations,
        comparison_data=comparison_data,
        selected_rfq=selected_rfq,
        pending_approvals=SAMPLE_APPROVALS if not is_vendor else [],
        purchase_orders=visible_pos,
        procurement_history=[],
        approved_vendors=[v for v in SAMPLE_VENDORS if v['status'] == 'approved'],
        pending_vendor_count=sum(1 for v in SAMPLE_VENDORS if v['status'] == 'pending'),
        active_rfq_count=sum(1 for r in SAMPLE_RFQS if r['status'] == 'open'),
        pending_approval_count=len(SAMPLE_APPROVALS),
    )

@app.route('/procurement/rfq/create', methods=['POST'])
def create_rfq():
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only procurement officers can create RFQs.', 'error')
        return redirect(url_for('procurement', tab='rfqs'))

    title = request.form.get('title', '').strip()
    budget = request.form.get('budget', '').strip()
    deadline = request.form.get('deadline', '').strip()
    description = request.form.get('description', '').strip()

    if not title:
        flash('RFQ title is required.', 'error')
        return redirect(url_for('procurement', tab='rfqs'))

    rfq_id = max(r['id'] for r in SAMPLE_RFQS) + 1 if SAMPLE_RFQS else 1
    rfq_num = f"RFQ-2026-{rfq_id:03d}"

    SAMPLE_RFQS.insert(0, {
        'id': rfq_id,
        'number': rfq_num,
        'title': title,
        'description': description,
        'budget': f"₹{budget}" if not budget.startswith('₹') else budget,
        'budget_value': int(re.sub(r'[^\d]', '', budget)) if budget else 0,
        'deadline': deadline,
        'status': 'open',
        'bid_count': 0,
        'is_overdue': False,
        'created_at': datetime.now().strftime('%Y-%m-%d'),
        'invited_vendors': [],
        'line_items': []
    })

    SAMPLE_AUDIT.insert(0, {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'user_name': user['name'],
        'action': 'Created RFQ Tender',
        'record_type': 'RFQ',
        'record_id': rfq_num,
        'details': f"New tender published: {title}. Budget: {budget}, Deadline: {deadline}."
    })

    flash(f"Request for Quotation {rfq_num} created successfully.", 'success')
    return redirect(url_for('procurement', tab='rfqs'))

@app.route('/procurement/invitation/send', methods=['POST'])
def send_invitation():
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only administrators can send vendor invitations.', 'error')
        return redirect(url_for('procurement', tab='invitations'))

    rfq_id = request.form.get('rfq_id')
    vendor_name = request.form.get('vendor_name', '').strip()

    rfq = next((r for r in SAMPLE_RFQS if str(r['id']) == str(rfq_id)), None)
    if rfq and vendor_name:
        if vendor_name not in rfq.get('invited_vendors', []):
            rfq.setdefault('invited_vendors', []).append(vendor_name)

        SAMPLE_AUDIT.insert(0, {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'user_name': user['name'],
            'action': 'Sent RFQ Invitation',
            'record_type': 'RFQ',
            'record_id': rfq['number'],
            'details': f"Vendor {vendor_name} invited to bid on {rfq['number']}."
        })
        flash(f"Invitation sent to {vendor_name} for tender {rfq['number']}.", 'success')
    else:
        flash('Please select a valid RFQ and approved vendor partner.', 'error')

    return redirect(url_for('procurement', tab='invitations'))

@app.route('/procurement/quotation/submit', methods=['POST'])
def submit_quotation():
    """Allows eligible approved vendors to submit quotation bids before deadline."""
    user = get_current_user()
    if not user or user.get('role') != 'vendor':
        flash('Unauthorized: Only authorized vendors can submit quotation bids.', 'error')
        return redirect(url_for('procurement', tab='quotations'))

    if user.get('status') != 'Active' and user.get('status') != 'Approved':
        flash('Your vendor account is pending verification. You cannot submit quotations until approved.', 'error')
        return redirect(url_for('procurement', tab='quotations'))

    rfq_id_str = request.form.get('rfq_id', '')
    rfq = next((r for r in SAMPLE_RFQS if str(r['id']) == rfq_id_str or r['number'] == rfq_id_str), None)

    if not rfq:
        flash('Selected RFQ tender does not exist.', 'error')
        return redirect(url_for('procurement', tab='quotations'))

    # Check deadline
    if rfq.get('is_overdue') or rfq.get('status') != 'open':
        flash('Quotation submission closed: The deadline for this RFQ has already passed.', 'error')
        return redirect(url_for('procurement', tab='quotations'))

    # Check eligibility (must be invited or open)
    vendor_name = user.get('company') or user.get('name')
    if rfq.get('invited_vendors') and vendor_name not in rfq['invited_vendors']:
        flash('Your organization has not been invited to submit bids for this specific RFQ.', 'error')
        return redirect(url_for('procurement', tab='quotations'))

    price_str = request.form.get('total_price', '').strip()
    delivery_days = request.form.get('delivery_days', '').strip()
    notes = request.form.get('notes', '').strip()

    if not price_str or not delivery_days:
        flash('Quoted price and delivery days are required.', 'error')
        return redirect(url_for('procurement', tab='quotations'))

    numeric_price = int(re.sub(r'[^\d]', '', price_str)) if price_str else 0
    formatted_price = f"₹{numeric_price:,}" if numeric_price else price_str

    quote_id = max(q['id'] for q in SAMPLE_QUOTATIONS) + 1 if SAMPLE_QUOTATIONS else 1
    quote_num = f"QT-{quote_id:03d}"

    SAMPLE_QUOTATIONS.append({
        'id': quote_id,
        'number': quote_num,
        'rfq_id': rfq['id'],
        'rfq_number': rfq['number'],
        'vendor_name': vendor_name,
        'vendor_email': user.get('email'),
        'total_price': formatted_price,
        'price_value': numeric_price,
        'delivery_days': int(delivery_days) if delivery_days.isdigit() else 14,
        'submitted_at': datetime.now().strftime('%Y-%m-%d'),
        'status': 'submitted',
        'notes': notes or 'Standard enterprise terms and warranty included.'
    })

    rfq['bid_count'] = rfq.get('bid_count', 0) + 1

    SAMPLE_AUDIT.insert(0, {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'user_name': user['name'],
        'action': 'Submitted Quotation Bid',
        'record_type': 'Quotation',
        'record_id': quote_num,
        'details': f"Bid of {formatted_price} submitted for {rfq['number']} by {vendor_name}."
    })

    flash(f"Quotation {quote_num} submitted successfully for tender {rfq['number']}.", 'success')
    return redirect(url_for('procurement', tab='quotations'))

@app.route('/procurement/quotation/select', methods=['POST'])
def select_quotation():
    """Procurement admin selects a quotation from comparison to submit for approval."""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only procurement officers can select quotations for approval.', 'error')
        return redirect(url_for('procurement', tab='rfqs'))

    quote_id = request.form.get('quotation_id')
    rfq_id = request.form.get('rfq_id')

    quote = next((q for q in SAMPLE_QUOTATIONS if str(q['id']) == str(quote_id)), None)
    rfq = next((r for r in SAMPLE_RFQS if str(r['id']) == str(rfq_id)), None)

    if not quote or not rfq:
        flash('Selected quotation or RFQ tender could not be found.', 'error')
        return redirect(url_for('procurement', tab='comparison'))

    quote['status'] = 'selected'

    # Create approval queue entry
    approval_id = max(a['id'] for a in SAMPLE_APPROVALS) + 1 if SAMPLE_APPROVALS else 1
    # Check if already in queue
    if not any(a['rfq_number'] == rfq['number'] for a in SAMPLE_APPROVALS):
        SAMPLE_APPROVALS.append({
            'id': approval_id,
            'rfq_number': rfq['number'],
            'rfq_title': rfq['title'],
            'selected_vendor': quote['vendor_name'],
            'bid_amount': quote['total_price'],
            'delivery_days': quote['delivery_days'],
            'requested_by': user['name']
        })

    SAMPLE_AUDIT.insert(0, {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'user_name': user['name'],
        'action': 'Selected Bid for Approval',
        'record_type': 'Quotation',
        'record_id': quote['number'],
        'details': f"Vendor {quote['vendor_name']} selected for {rfq['number']} at {quote['total_price']}. Advanced to approval queue."
    })

    flash(f"Quotation from {quote['vendor_name']} ({quote['total_price']}) submitted to the approval queue.", 'success')
    return redirect(url_for('procurement', tab='approvals'))

@app.route('/procurement/approve', methods=['POST'])
def approve_procurement():
    """Authorizes procurement proposal and generates official Purchase Order."""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only administrators can authorize procurement proposals.', 'error')
        return redirect(url_for('procurement', tab='approvals'))

    action = request.form.get('action', 'approve')
    approval_id = request.form.get('approval_id')

    approval = next((a for a in SAMPLE_APPROVALS if str(a['id']) == str(approval_id)), None)

    if action == 'approve':
        if approval:
            # Generate official Purchase Order
            po_id = max(p['id'] for p in SAMPLE_POS) + 1 if SAMPLE_POS else 1
            po_num = f"PO-2026-{po_id:03d}"

            SAMPLE_POS.insert(0, {
                'id': po_id,
                'number': po_num,
                'rfq_number': approval['rfq_number'],
                'vendor_name': approval['selected_vendor'],
                'total': approval['bid_amount'],
                'date': datetime.now().strftime('%Y-%m-%d'),
                'status': 'confirmed',
                'line_items': []
            })

            # Update RFQ status to awarded
            rfq = next((r for r in SAMPLE_RFQS if r['number'] == approval['rfq_number']), None)
            if rfq:
                rfq['status'] = 'awarded'

            SAMPLE_APPROVALS.remove(approval)

            SAMPLE_AUDIT.insert(0, {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'user_name': user['name'],
                'action': 'Authorized Purchase Order',
                'record_type': 'PO',
                'record_id': po_num,
                'details': f"Purchase Order {po_num} generated for {approval['selected_vendor']} for {approval['bid_amount']}."
            })

            flash(f"Procurement proposal authorized! Purchase Order {po_num} generated successfully.", 'success')
        else:
            flash('Approval record could not be found.', 'error')
        return redirect(url_for('procurement', tab='orders'))
    else:
        if approval:
            SAMPLE_APPROVALS.remove(approval)
            SAMPLE_AUDIT.insert(0, {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'user_name': user['name'],
                'action': 'Rejected Procurement Bid',
                'record_type': 'RFQ',
                'record_id': approval['rfq_number'],
                'details': f"Procurement proposal for {approval['selected_vendor']} was rejected by {user['name']}."
            })
            flash('Procurement proposal rejected.', 'warning')
        return redirect(url_for('procurement', tab='approvals'))

# ── Finance & Invoice Verification ──
@app.route('/finance')
def finance():
    user = get_current_user()
    is_vendor = user and user.get('role') == 'vendor'
    vendor_name = user.get('company') or user.get('name') if user else ''
    active_tab = request.args.get('tab', 'invoices')

    # Security: Vendors cannot access administrative audit trails
    if is_vendor and active_tab == 'audit':
        flash('Restricted: Audit trail records are reserved for internal accounting administration.', 'warning')
        return redirect(url_for('finance', tab='invoices'))

    if is_vendor:
        invoices = [i for i in SAMPLE_INVOICES if i.get('vendor_name') == vendor_name]
        payments = [p for p in SAMPLE_PAYMENTS if p.get('vendor_name') == vendor_name]
        orders = [p for p in SAMPLE_POS if p.get('vendor_name') == vendor_name]
        audit_records = []
    else:
        invoices = SAMPLE_INVOICES
        payments = SAMPLE_PAYMENTS
        orders = SAMPLE_POS
        audit_records = SAMPLE_AUDIT

    return render_template('finance.html',
        active_page='finance',
        active_tab=active_tab,
        current_user=user,
        finance_stats={
            'total_invoices': len(invoices),
            'pending_verification': sum(1 for i in invoices if i['verification_status'] == 'pending'),
            'unpaid': sum(1 for i in invoices if i['payment_status'] != 'paid'),
            'total_paid': sum(1 for i in invoices if i['payment_status'] == 'paid'),
        },
        invoices=invoices,
        payment_records=payments,
        audit_logs=audit_records,
        purchase_orders=orders,
        approved_vendors=[v for v in SAMPLE_VENDORS if v['status'] == 'approved'],
        pending_vendor_count=sum(1 for v in SAMPLE_VENDORS if v['status'] == 'pending'),
        active_rfq_count=sum(1 for r in SAMPLE_RFQS if r['status'] == 'open'),
        pending_approval_count=len(SAMPLE_APPROVALS),
    )

@app.route('/finance/invoice/register', methods=['POST'])
def register_invoice():
    user = get_current_user()
    inv_num = request.form.get('invoice_number', '').strip()
    po_num = request.form.get('po_number', '').strip()
    vendor_name = request.form.get('vendor_name', '').strip()
    amount_str = request.form.get('amount', '').strip()

    po = next((p for p in SAMPLE_POS if p['number'] == po_num), None)
    po_amount = po['total'] if po else amount_str

    # Automatic mismatch detection between Invoice and PO amounts
    numeric_inv = int(re.sub(r'[^\d]', '', amount_str)) if amount_str else 0
    numeric_po = int(re.sub(r'[^\d]', '', po_amount)) if po_amount else 0

    has_mismatch = (numeric_inv > numeric_po)
    mismatch_reason = ""
    if has_mismatch:
        diff = numeric_inv - numeric_po
        mismatch_reason = f"Invoice amount (₹{numeric_inv:,}) exceeds authorized PO value (₹{numeric_po:,}) by ₹{diff:,}."

    inv_id = max(i['id'] for i in SAMPLE_INVOICES) + 1 if SAMPLE_INVOICES else 1

    SAMPLE_INVOICES.insert(0, {
        'id': inv_id,
        'number': inv_num or f"INV-2026-{inv_id:03d}",
        'vendor_name': vendor_name or (po['vendor_name'] if po else 'Unknown Vendor'),
        'po_number': po_num,
        'amount': f"₹{numeric_inv:,}" if numeric_inv else amount_str,
        'po_amount': po_amount,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'verification_status': 'pending',
        'payment_status': 'unpaid',
        'has_mismatch': has_mismatch,
        'mismatch_reason': mismatch_reason
    })

    # Also register payment balance tracker
    SAMPLE_PAYMENTS.insert(0, {
        'invoice_id': inv_id,
        'invoice_number': inv_num or f"INV-2026-{inv_id:03d}",
        'vendor_name': vendor_name or (po['vendor_name'] if po else 'Unknown Vendor'),
        'amount': f"₹{numeric_inv:,}" if numeric_inv else amount_str,
        'amount_paid': '₹0',
        'balance': f"₹{numeric_inv:,}" if numeric_inv else amount_str,
        'due_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
        'status': 'unpaid',
        'is_overdue': False
    })

    SAMPLE_AUDIT.insert(0, {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'user_name': user['name'] if user else 'System',
        'action': 'Registered Invoice',
        'record_type': 'Invoice',
        'record_id': inv_num,
        'details': f"Registered against {po_num}. {'MISMATCH FLAGGED: ' + mismatch_reason if has_mismatch else 'Amounts aligned.'}"
    })

    if has_mismatch:
        flash(f"Invoice {inv_num} registered with warning: PO mismatch detected! Awaiting review.", 'warning')
    else:
        flash(f"Invoice {inv_num} registered successfully and matched against {po_num}.", 'success')

    return redirect(url_for('finance', tab='invoices'))

@app.route('/finance/invoice/verify', methods=['POST'])
def verify_invoice():
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only finance officers can verify supplier invoices.', 'error')
        return redirect(url_for('finance', tab='invoices'))

    action = request.form.get('action', 'verify')
    inv_id = request.form.get('invoice_id')
    inv = next((i for i in SAMPLE_INVOICES if str(i['id']) == str(inv_id)), None)

    if not inv:
        flash('Invoice record not found.', 'error')
        return redirect(url_for('finance', tab='invoices'))

    if action == 'verify':
        inv['verification_status'] = 'verified'
        SAMPLE_AUDIT.insert(0, {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'user_name': user['name'],
            'action': 'Verified Invoice',
            'record_type': 'Invoice',
            'record_id': inv['number'],
            'details': f"Invoice verified against Purchase Order {inv['po_number']} by {user['name']}."
        })
        flash(f"Invoice {inv['number']} verified successfully against Purchase Order {inv['po_number']}.", 'success')
    else:
        inv['verification_status'] = 'rejected'
        reason = request.form.get('rejection_reason', 'Invoice items or pricing did not match signed Purchase Order.')
        inv['mismatch_reason'] = reason
        SAMPLE_AUDIT.insert(0, {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'user_name': user['name'],
            'action': 'Rejected Invoice',
            'record_type': 'Invoice',
            'record_id': inv['number'],
            'details': f"Invoice {inv['number']} rejected by {user['name']}. Reason: {reason}"
        })
        flash(f"Invoice {inv['number']} rejected. Discrepancy noted.", 'warning')

    return redirect(url_for('finance', tab='invoices'))

@app.route('/finance/payment/update', methods=['POST'])
def update_payment():
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        flash('Unauthorized: Only finance officers can record payment updates.', 'error')
        return redirect(url_for('finance', tab='payments'))

    inv_id = request.form.get('invoice_id')
    amount_paid_str = request.form.get('amount_paid', '').strip()
    status = request.form.get('status', 'paid')

    inv = next((i for i in SAMPLE_INVOICES if str(i['id']) == str(inv_id)), None)
    pay = next((p for p in SAMPLE_PAYMENTS if str(p['invoice_id']) == str(inv_id)), None)

    if inv:
        inv['payment_status'] = status
    if pay:
        pay['status'] = status
        if amount_paid_str:
            numeric_paid = int(re.sub(r'[^\d]', '', amount_paid_str))
            numeric_total = int(re.sub(r'[^\d]', '', pay['amount']))
            pay['amount_paid'] = f"₹{numeric_paid:,}"
            pay['balance'] = f"₹{max(0, numeric_total - numeric_paid):,}"
        elif status == 'paid':
            pay['amount_paid'] = pay['amount']
            pay['balance'] = '₹0'

    inv_num = inv['number'] if inv else 'Invoice'
    SAMPLE_AUDIT.insert(0, {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'user_name': user['name'],
        'action': 'Recorded Payment',
        'record_type': 'Payment',
        'record_id': inv_num,
        'details': f"Payment status updated to '{status.title()}' for {inv_num} by {user['name']}."
    })

    flash(f"Payment record for {inv_num} updated to {status.title()}.", 'success')
    return redirect(url_for('finance', tab='payments'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
