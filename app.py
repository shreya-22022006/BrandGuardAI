import streamlit as st
import pytesseract
from PIL import Image
import requests
import re
import sqlite3
import hashlib
import hmac
import secrets
import json
from datetime import datetime
from io import BytesIO
from pypdf import PdfReader
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

# -------------------- CONFIGURATION --------------------

st.set_page_config(page_title="BrandGuard AI", page_icon="🛡️", layout="wide")

DB_PATH = "brandguard.db"
# Change this path only if Tesseract is installed somewhere else.
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

DEFAULT_RULES = {
    "product": "Eco Bottle",
    "price": 999.0,
    "banned": "best ever, guaranteed",
    "claims": "Reusable and refillable",
}

# -------------------- DATABASE --------------------

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('Admin','Reviewer','Creator')),
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                findings TEXT NOT NULL,
                ai_analysis TEXT,
                status TEXT NOT NULL,
                decision TEXT NOT NULL DEFAULT 'Pending',
                source_file TEXT,
                source_image TEXT,
                created_by TEXT NOT NULL,
                reviewed_by TEXT,
                created_at TEXT NOT NULL,
                reviewed_at TEXT
            )
        """)
        existing = conn.execute("SELECT value FROM settings WHERE key='brand_rules'").fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES('brand_rules', ?)",
                (json.dumps(DEFAULT_RULES),)
            )

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 300000)
    return digest.hex(), salt

def verify_password(password, stored_hash, salt):
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, stored_hash)

def user_count():
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

def create_user(username, password, role):
    password_hash, salt = hash_password(password)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO users(username, password_hash, salt, role, created_at) VALUES(?,?,?,?,?)",
            (username.strip(), password_hash, salt, role, datetime.now().isoformat(timespec="seconds"))
        )

def authenticate(username, password):
    with get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE username=?", (username.strip(),)).fetchone()
    if user and verify_password(password, user["password_hash"], user["salt"]):
        return {"username": user["username"], "role": user["role"]}
    return None

def load_rules():
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='brand_rules'").fetchone()
    return json.loads(row["value"]) if row else DEFAULT_RULES.copy()

def save_rules(rules):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO settings(key,value) VALUES('brand_rules',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps(rules),)
        )

def save_audit(record, created_by):
    created_at = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO audits(content, findings, ai_analysis, status, decision,
                               source_file, source_image, created_by, created_at)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (
            record["content"], json.dumps(record["findings"]), record.get("ai_analysis", ""),
            record["status"], record.get("decision", "Pending"),
            record.get("source_file"), record.get("source_image"), created_by, created_at
        ))
        return cur.lastrowid

def update_audit_decision(audit_id, decision, reviewer):
    status = "Approved" if decision == "Approved" else "Rejected"
    with get_connection() as conn:
        conn.execute("""
            UPDATE audits SET decision=?, status=?, reviewed_by=?, reviewed_at=?
            WHERE id=?
        """, (decision, status, reviewer, datetime.now().isoformat(timespec="seconds"), audit_id))

def get_audit(audit_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM audits WHERE id=?", (audit_id,)).fetchone()
    if not row:
        return None
    record = dict(row)
    record["findings"] = json.loads(record["findings"])
    record["decision"] = record["decision"]
    return record

def get_audits():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM audits ORDER BY id DESC").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["findings"] = json.loads(item["findings"])
        result.append(item)
    return result

def delete_audit_history():
    with get_connection() as conn:
        conn.execute("DELETE FROM audits")

init_db()

# -------------------- DESIGN --------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] {font-family:Inter,sans-serif}
.stApp {background:radial-gradient(ellipse at 85% 10%,#25245a55,transparent 32%),#06142b;color:#edf3ff}
[data-testid="stHeader"] {background:transparent}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#07132b,#081a37);border-right:1px solid #263c66}
.block-container {padding-top:1.1rem;max-width:1600px}
.stTextInput label,.stNumberInput label,.stTextArea label,.stSelectbox label,.stRadio label {color:#d9e6ff!important}
.stTextInput input,.stNumberInput input,.stTextArea textarea {background:#10294b!important;color:#eaf2ff!important;border:1px solid #5a7ec94a!important;border-radius:9px!important}
.stButton button,.stFormSubmitButton button {border:0!important;border-radius:10px!important;color:white!important;font-weight:700!important;background:linear-gradient(100deg,#4e4df4,#3989ff)!important;min-height:43px}
div.stDownloadButton > button {background:linear-gradient(100deg,#4e4df4,#3989ff)!important;color:#fff!important;border-radius:10px!important;font-weight:700!important}
.hero {border:1px solid #556ced55;border-radius:17px;padding:27px 24px;background:linear-gradient(110deg,#102e7c,#061b3d 58%,#071d42)}
.hero h1 {font-size:34px;font-weight:800;color:#f5f7ff;margin:0 0 8px}
.hero p {font-size:15px;color:#d1e0ff;margin:0}
.panel {border:1px solid #5b82da40;border-radius:16px;padding:20px;background:linear-gradient(145deg,#091d3a,#071832)}
hr {border-color:#5e80cb40!important}
footer,#MainMenu {visibility:hidden}
</style>
""", unsafe_allow_html=True)

# -------------------- AUTHENTICATION --------------------

def login_screen():
    st.markdown('<div class="hero"><h1>🛡️ BrandGuard AI</h1><p>Secure brand governance and content review workspace.</p></div>', unsafe_allow_html=True)
    st.write("")
    if user_count() == 0:
        st.subheader("Create the first Admin account")
        st.info("First-time setup: create your administrator login. Keep the password safe.")
        with st.form("first_admin_form"):
            username = st.text_input("Admin username")
            password = st.text_input("Password", type="password")
            confirm = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create Admin account", use_container_width=True)
        if submitted:
            if not username.strip() or len(password) < 8:
                st.error("Enter a username and a password with at least 8 characters.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                try:
                    create_user(username, password, "Admin")
                    st.success("Admin account created. Please log in.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("This username already exists.")
    else:
        st.subheader("Login")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state.user = user
                st.session_state.page = "Home"
                st.rerun()
            else:
                st.error("Incorrect username or password.")

if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "Home"
if "latest_audit_id" not in st.session_state:
    st.session_state.latest_audit_id = None

if not st.session_state.user:
    login_screen()
    st.stop()

user = st.session_state.user
role = user["role"]
username = user["username"]

# -------------------- IMAGE / PDF TEXT EXTRACTION --------------------

def extract_image_text(uploaded_image):
    try:
        uploaded_image.seek(0)
        image = Image.open(uploaded_image).convert("RGB")
        return pytesseract.image_to_string(image).strip(), None
    except Exception as exc:
        return None, f"Could not extract text from image: {exc}"

def extract_pdf_text(uploaded_file):
    try:
        reader = PdfReader(uploaded_file)
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if not extracted:
            return None, "No selectable text was found. Scanned PDF OCR is not included."
        return extracted, None
    except Exception as exc:
        return None, f"Could not read this PDF: {exc}"

# -------------------- AI + AUDIT --------------------

def analyze_with_ai(draft, rules):
    prompt = f"""
You are an AI brand compliance assistant for BrandGuard AI.
Use ONLY the information provided below.

BRAND RULES:
Product: {rules['product']}
Approved price: INR {rules['price']}
Banned phrases: {rules['banned']}
Approved claims: {rules['claims']}

CONTENT TO ANALYZE:
{draft}

Analyze:
1. BRAND TONE: Does it sound professional and trustworthy?
2. MISLEADING CLAIMS: Identify unsupported or misleading claims and explain why verification is needed.
3. CONTEXTUAL RISKS: Identify other brand-related risks.
4. SUGGESTED REWRITE: Rewrite using only verified information from the rules and original draft.

Never invent product features, certifications, discounts, materials or claims.
Use only claims explicitly listed in Approved claims. If information is missing, write
"Requires human verification". Human review is required before publication.
Keep the response simple, professional and structured.
"""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3.2:3b", "prompt": prompt, "stream": False},
            timeout=180
        )
        response.raise_for_status()
        return response.json().get("response", "AI analysis could not generate a response.")
    except requests.exceptions.RequestException:
        return ("AI analysis is currently unavailable. Make sure Ollama is running "
                "and the llama3.2:3b model is installed. Rule-based audit is still available.")

def run_audit(draft, rules):
    findings = []
    low = draft.lower()

    for word in [x.strip() for x in rules["banned"].split(",") if x.strip()]:
        if word.lower() in low:
            findings.append(("High", f'Banned phrase found: “{word}”',
                             f'The draft contains “{word}”.',
                             f'Remove “{word}” or replace it with an approved statement.'))

    for price_text in re.findall(r'(?:₹|rs\.?\s*)(\d+(?:,\d{3})*(?:\.\d{1,2})?)', draft, re.I):
        value = float(price_text.replace(",", ""))
        if value != float(rules["price"]):
            findings.append(("High",
                f'Price mismatch: INR {value:,.0f} shown; approved price is INR {rules["price"]:,.0f}.',
                "The price in the draft differs from the saved brand price.",
                f'Change the price to INR {rules["price"]:,.0f} or verify the approved price.'))

    if rules["product"] and rules["product"].lower() not in low:
        findings.append(("Medium", f'Approved product name “{rules["product"]}” is missing.',
                         "The draft does not contain the configured product name.",
                         f'Add the approved name “{rules["product"]}” where appropriate.'))

    approved = [x.strip().lower() for x in re.split(r"[,;\n]", rules["claims"]) if x.strip()]
    for phrase in ["100%", "plastic free", "eco-friendly", "sustainable", "number one"]:
        if phrase in low and not any(phrase in claim for claim in approved):
            findings.append(("Medium", f'Promotional claim needs verification: “{phrase}”.',
                             "This claim is not listed in the approved claims field.",
                             "Provide supporting evidence and approve the claim, or remove/rephrase it."))

    if not findings:
        findings = [("Low", "No configured rule violations detected.",
                     "The draft passed the current basic rule checks.",
                     "Complete human review before publishing; this checker does not verify every requirement.")]

    return {
        "content": draft,
        "findings": findings,
        "status": "Needs review" if any(f[0] in ("High", "Medium") for f in findings) else "Review required",
        "decision": "Pending",
    }

# -------------------- PDF REPORT --------------------

def create_pdf(record):
    buffer = BytesIO()
    navy = colors.HexColor("#101A38")
    muted = colors.HexColor("#65708A")
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BGTitle", parent=styles["Title"], fontName="Helvetica-Bold",
                              fontSize=21, leading=25, textColor=navy, alignment=TA_LEFT, spaceAfter=4))
    styles.add(ParagraphStyle(name="BGSubtitle", parent=styles["Normal"], fontSize=9,
                              leading=13, textColor=muted))
    styles.add(ParagraphStyle(name="BGSection", parent=styles["Heading2"], fontSize=13,
                              leading=17, textColor=navy, spaceBefore=10, spaceAfter=7))
    styles.add(ParagraphStyle(name="BGBody", parent=styles["BodyText"], fontSize=9,
                              leading=13, textColor=navy, spaceAfter=4))
    styles.add(ParagraphStyle(name="BGSmall", parent=styles["BodyText"], fontSize=8,
                              leading=11, textColor=muted))
    story = [
        Paragraph("BRANDGUARD AI", styles["BGTitle"]),
        Paragraph("SMARTER CHECKS. STRONGER BRANDS.", styles["BGSubtitle"]),
        Spacer(1, 5*mm),
        Paragraph("CONTENT AUDIT REPORT", styles["BGSection"]),
        Paragraph(f"<b>Status:</b> {escape(str(record.get('status','Needs review')))}"
                  f" &nbsp;&nbsp; <b>Decision:</b> {escape(str(record.get('decision','Pending')))}",
                  styles["BGBody"]),
        Paragraph("AUDIT FINDINGS", styles["BGSection"])
    ]
    for index, (severity, issue, evidence, fix) in enumerate(record.get("findings", []), 1):
        parts = [
            Paragraph(f"<b>{escape(severity.upper())}</b> — {index}. {escape(issue)}", styles["BGBody"]),
            Paragraph(f"<b>Evidence:</b> {escape(evidence)}", styles["BGBody"]),
            Paragraph(f"<b>Suggested fix:</b> {escape(fix)}", styles["BGBody"])
        ]
        card = Table([[parts]], colWidths=[160*mm])
        card.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),colors.white),
            ("BOX",(0,0),(-1,-1),0.7,colors.HexColor("#D8DFF0")),
            ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
            ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),7)
        ]))
        story.append(KeepTogether([card, Spacer(1, 3*mm)]))
    ai = record.get("ai_analysis", "")
    if ai:
        story.extend([Paragraph("AI-POWERED ANALYSIS", styles["BGSection"]),
                      Paragraph(escape(ai).replace("\n", "<br/>"), styles["BGBody"])])
    story.append(Paragraph("<b>Review note:</b> AI and rule checks are preliminary. Human review is required.",
                           styles["BGSmall"]))
    doc.build(story)
    return buffer.getvalue()

# -------------------- SIDEBAR / NAVIGATION --------------------

with st.sidebar:
    st.markdown("## 🛡️ BrandGuard **AI**")
    st.caption("Smarter Checks. Stronger Brands.")
    st.write(f"**User:** {username}")
    st.write(f"**Role:** {role}")
    st.divider()

    pages = [("Home", "⌂ Home")]
    if role == "Admin":
        pages.append(("Brand Rules", "♧ Brand Rules"))
    if role in ("Admin", "Creator"):
        pages.append(("Content Audit", "▤ Content Audit"))
    pages.append(("History", "◷ Audit History"))
    if role == "Admin":
        pages.append(("User Management", "♙ User Management"))
        pages.append(("Settings", "⚙ Settings"))

    for page_name, label in pages:
        if st.button(label, key=f"nav_{page_name}", use_container_width=True):
            st.session_state.page = page_name
            st.rerun()

    st.divider()
    if st.button("Log out", use_container_width=True):
        st.session_state.user = None
        st.session_state.latest_audit_id = None
        st.session_state.page = "Home"
        st.rerun()

page = st.session_state.page
st.markdown('<div style="text-align:right;color:#c4d9ff;font-size:12px">🟢 Secure session active</div>',
            unsafe_allow_html=True)

# -------------------- HOME --------------------

if page == "Home":
    st.markdown("""
    <div class="hero">
      <h1>Welcome to BrandGuard AI</h1>
      <p>Your intelligent brand governance partner. Check content against approved brand rules before publishing.</p>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    audits = get_audits()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Audits", len(audits))
    c2.metric("Pending Review", sum(1 for a in audits if a["decision"] == "Pending"))
    c3.metric("Approved", sum(1 for a in audits if a["decision"] == "Approved"))
    st.subheader("Recent activity")
    if audits:
        for item in audits[:5]:
            st.write(f"**Audit #{item['id']}** · {item['status']} · submitted by {item['created_by']} · {item['created_at']}")
    else:
        st.info("No audits yet. Submit content to get started.")
    if role == "Creator":
        st.caption("You can submit content audits and view their status.")
    elif role == "Reviewer":
        st.caption("You can review submitted audits and approve or reject them from Audit History.")

# -------------------- BRAND RULES --------------------

elif page == "Brand Rules" and role == "Admin":
    st.title("♧ Brand Rules")
    st.caption("These settings are stored in the database and remain after restarting the app.")
    rules = load_rules()
    with st.form("rules_form"):
        product = st.text_input("Approved product name", value=rules["product"])
        price = st.number_input("Approved price (INR)", min_value=0.0, value=float(rules["price"]), step=1.0)
        banned = st.text_input("Banned words (comma-separated)", value=rules["banned"])
        claims = st.text_area("Approved promotional claims", value=rules["claims"], height=110)
        saved = st.form_submit_button("Save Brand Rules", use_container_width=True)
    if saved:
        save_rules({"product": product.strip(), "price": price, "banned": banned, "claims": claims})
        st.success("Brand rules saved permanently.")

# -------------------- CONTENT AUDIT --------------------

elif page == "Content Audit" and role in ("Admin", "Creator"):
    st.title("▤ Content Audit")
    st.caption("Submit text, PDF or image for brand checking.")
    input_method = st.radio("Choose input method", ["Paste Text", "Upload PDF", "Upload Image"], horizontal=True)
    draft = ""
    uploaded_pdf = None
    uploaded_image = None
    if input_method == "Paste Text":
        draft = st.text_area("Content draft", placeholder="Paste your content here...", height=180)
    elif input_method == "Upload PDF":
        uploaded_pdf = st.file_uploader("Choose PDF file", type=["pdf"])
    else:
        uploaded_image = st.file_uploader("Choose image", type=["png", "jpg", "jpeg"])
        if uploaded_image:
            st.image(uploaded_image, caption="Uploaded image preview", use_container_width=True)

    if st.button("Run Brand Audit", use_container_width=True):
        audit_text = draft.strip()
        source_file = None
        source_image = None
        if input_method == "Upload PDF":
            if uploaded_pdf is None:
                st.warning("Please upload a PDF file first.")
                st.stop()
            source_file = uploaded_pdf.name
            audit_text, error = extract_pdf_text(uploaded_pdf)
            if error:
                st.error(error)
                st.stop()
        elif input_method == "Upload Image":
            if uploaded_image is None:
                st.warning("Please upload an image first.")
                st.stop()
            source_image = uploaded_image.name
            with st.spinner("Extracting image text using OCR..."):
                audit_text, error = extract_image_text(uploaded_image)
            if error:
                st.error(error)
                st.stop()
            if not audit_text:
                st.warning("No readable text found. Please upload a clearer image.")
                st.stop()
            st.success("Text extracted successfully using OCR.")
            with st.expander("View extracted text"):
                st.write(audit_text)

        if not audit_text:
            st.warning("Please enter or upload content first.")
            st.stop()

        rules = load_rules()
        with st.spinner("Running brand rules and AI analysis..."):
            record = run_audit(audit_text, rules)
            record["ai_analysis"] = analyze_with_ai(audit_text, rules)
            record["source_file"] = source_file
            record["source_image"] = source_image
            audit_id = save_audit(record, username)
        st.session_state.latest_audit_id = audit_id
        st.success(f"Audit #{audit_id} saved to database. You can find it in Audit History.")
        st.rerun()

# -------------------- AUDIT HISTORY / REVIEW --------------------

elif page == "History":
    st.title("◷ Audit History")
    st.caption("Audit records are stored in SQLite and remain available after app restart.")
    audits = get_audits()
    if role == "Creator":
        audits = [a for a in audits if a["created_by"] == username]
    if not audits:
        st.info("No audit records available.")
    for item in audits:
        heading = f"Audit #{item['id']} · {item['decision']} · {item['created_at']}"
        with st.expander(heading):
            st.write("**Submitted by:**", item["created_by"])
            st.write("**Content:**", item["content"])
            st.write("**Status:**", item["status"])
            st.write("**Reviewer decision:**", item["decision"])
            if item.get("reviewed_by"):
                st.write("**Reviewed by:**", item["reviewed_by"])
            if item.get("source_file"):
                st.write("**PDF:**", item["source_file"])
            if item.get("source_image"):
                st.write("**Image:**", item["source_image"], "· OCR text was checked; logo matching is not included.")
            st.markdown("**Findings**")
            for severity, issue, evidence, fix in item["findings"]:
                st.markdown(f"**{severity}: {issue}**")
                st.write("Evidence:", evidence)
                st.write("Suggested fix:", fix)
            if item.get("ai_analysis"):
                st.markdown("**AI-Powered Analysis**")
                st.write(item["ai_analysis"])

            can_review = role in ("Admin", "Reviewer") and item["decision"] == "Pending"
            if can_review:
                left, right = st.columns(2)
                if left.button("✅ Approve", key=f"approve_{item['id']}", use_container_width=True):
                    update_audit_decision(item["id"], "Approved", username)
                    st.success("Audit approved.")
                    st.rerun()
                if right.button("❌ Reject", key=f"reject_{item['id']}", use_container_width=True):
                    update_audit_decision(item["id"], "Rejected", username)
                    st.warning("Audit rejected.")
                    st.rerun()

            pdf_record = dict(item)
            pdf_bytes = create_pdf(pdf_record)
            st.download_button("Download PDF report", data=pdf_bytes,
                               file_name=f"BrandGuard_Audit_{item['id']}.pdf",
                               mime="application/pdf", key=f"pdf_{item['id']}")

# -------------------- USER MANAGEMENT --------------------

elif page == "User Management" and role == "Admin":
    st.title("♙ User Management")
    st.caption("Only Admin can create user accounts.")
    with st.form("create_user_form"):
        new_username = st.text_input("New username")
        new_password = st.text_input("Temporary password (minimum 8 characters)", type="password")
        new_role = st.selectbox("Role", ["Reviewer", "Creator"])
        create = st.form_submit_button("Create User", use_container_width=True)
    if create:
        if not new_username.strip() or len(new_password) < 8:
            st.error("Enter a username and a password with at least 8 characters.")
        else:
            try:
                create_user(new_username, new_password, new_role)
                st.success(f"{new_role} account created for {new_username}. Share the login details securely.")
            except sqlite3.IntegrityError:
                st.error("That username already exists.")
    st.subheader("Existing accounts")
    with get_connection() as conn:
        users = conn.execute("SELECT username, role, created_at FROM users ORDER BY id").fetchall()
    st.dataframe([dict(u) for u in users], use_container_width=True, hide_index=True)

# -------------------- SETTINGS --------------------

elif page == "Settings" and role == "Admin":
    st.title("⚙ Settings")
    st.markdown("""
    <div class="panel">
      <b>BrandGuard AI</b>
      <p>Secure login, role-based access and persistent audit history are enabled.</p>
      <p>Passwords are stored as salted PBKDF2 hashes. Audit history and brand rules are stored in a local SQLite database.</p>
    </div>
    """, unsafe_allow_html=True)
    st.warning("Clearing history permanently deletes all audit records from the local database.")
    confirm_clear = st.checkbox("I understand that this cannot be undone.")
    if st.button("Clear Audit History", disabled=not confirm_clear):
        delete_audit_history()
        st.success("Audit history cleared from the database.")
        st.rerun()
