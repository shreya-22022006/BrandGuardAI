import re
from io import BytesIO
from xml.sax.saxutils import escape

import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
)

st.set_page_config(
    page_title="BrandGuard AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------- DESIGN --------------------
st.markdown(r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] {font-family:Inter,sans-serif}
.stApp {background:radial-gradient(ellipse at 85% 10%,#25245a55,transparent 32%),#06142b;color:#edf3ff}
[data-testid="stHeader"] {background:transparent}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#07132b,#081a37);border-right:1px solid #263c66}
.block-container {padding-top:1.1rem;max-width:1600px}
.brand-logo {display:flex;align-items:center;gap:12px;padding:8px 0 25px}
.brand-shield {width:44px;height:48px;display:flex;align-items:center;justify-content:center;font-size:28px;border-radius:14px;background:linear-gradient(145deg,#6d55ff,#163ed1);box-shadow:0 0 25px #6654ff55}
.brand-name {font-size:21px;font-weight:800;color:#f5f7ff}
.brand-name span {color:#9274ff}
.brand-sub {font-size:10px;color:#a5b8df;margin-top:3px}
.sidebar-bottom {margin-top:100px;padding:22px 14px;text-align:center;border-radius:15px;border:1px solid #4a7ee233;background:linear-gradient(150deg,#0a234ddd,#071631);color:#a9bfff;font-size:12px;line-height:1.8}
.online {text-align:right;color:#c4d9ff;font-size:12px;margin:0 4px 12px}
.online span {color:#30e0aa;font-size:16px}
.hero {border:1px solid #556ced55;border-radius:17px;padding:27px 24px;min-height:174px;background:radial-gradient(ellipse at 90% 100%,#8f2ae477,transparent 32%),linear-gradient(110deg,#102e7c,#061b3d 58%,#071d42);position:relative;overflow:hidden}
.hero h1 {font-size:clamp(27px,2.7vw,38px);font-weight:800;letter-spacing:-1px;margin:0 0 10px;color:#f5f7ff}
.hero h1 span {background:linear-gradient(90deg,#5ba5ff,#a56cff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero p {font-size:16px;line-height:1.75;color:#d1e0ff;max-width:690px;margin:0}
.hero-art {position:absolute;right:35px;top:24px;font-size:88px;filter:drop-shadow(0 0 18px #785cffbb)}
.hero-quote {position:absolute;right:205px;top:44px;color:#e4eaff;font-style:italic;font-size:18px;transform:rotate(-7deg);text-align:center}
.metric {border:1px solid #597dd535;border-radius:15px;padding:17px;min-height:90px;display:flex;align-items:center;gap:13px;background:linear-gradient(135deg,#0c264e,#091c3a)}
.metric-icon {width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:24px;flex-shrink:0}
.metric-title {font-weight:600;font-size:14px;color:#e6efff;margin-bottom:7px}
.metric-sub {font-size:11px;color:#9eb5df}
.panel {border:1px solid #5b82da40;border-radius:16px;padding:20px 21px;background:linear-gradient(145deg,#091d3a,#071832)}
.panel-title {font-size:16px;font-weight:700;color:#c9c8ff;margin:0 0 5px}
.panel-sub {font-size:11px;color:#a9bee4;line-height:1.7;margin-bottom:17px}
.side-card {border:1px solid #5b82da40;border-radius:16px;padding:24px;background:linear-gradient(145deg,#091d3a,#111849);position:relative;overflow:hidden}
.side-card h3 {font-size:19px;line-height:1.7;color:#d6d1ff;margin:0 0 12px}
.side-card p {font-size:12px;line-height:1.9;color:#c1d1ef;max-width:280px}
.activity {border-bottom:1px solid #6b89cc22;padding:13px 0;font-size:12px;color:#d7e3ff}
.activity small {float:right;color:#6f8cbd}
.stTextInput label,.stNumberInput label,.stTextArea label,.stSelectbox label {color:#d9e6ff!important;font-size:12px!important}
.stTextInput input,.stNumberInput input,.stTextArea textarea {background:#10294b!important;color:#eaf2ff!important;border:1px solid #5a7ec94a!important;border-radius:9px!important}
.stButton button,.stFormSubmitButton button {border:0!important;border-radius:10px!important;color:white!important;font-weight:700!important;background:linear-gradient(100deg,#4e4df4,#3989ff)!important;min-height:43px;box-shadow:0 7px 20px #345bee33}
.stButton button:hover,.stFormSubmitButton button:hover {filter:brightness(1.12)}
div.stDownloadButton > button {background:linear-gradient(100deg,#4e4df4,#3989ff)!important;color:#fff!important;border-radius:10px!important;font-weight:700!important;min-height:46px!important}
hr {border-color:#5e80cb40!important}
footer,#MainMenu {visibility:hidden}
div[data-testid="stExpander"] {background:#f4f6fc!important;border:1px solid #d8dff0!important;border-radius:10px!important}
div[data-testid="stExpander"] summary,div[data-testid="stExpander"] summary p,div[data-testid="stExpander"] summary span {color:#17213d!important}
div[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p {color:#17213d!important}
@media(max-width:900px) {.hero-art,.hero-quote {display:none}.sidebar-bottom {margin-top:30px}}
</style>
""", unsafe_allow_html=True)

# -------------------- SESSION STATE --------------------
if "page" not in st.session_state:
    st.session_state.page = "Home"
if "rules" not in st.session_state:
    st.session_state.rules = {
        "product": "Eco Bottle",
        "price": 999.0,
        "banned": "best ever, guaranteed",
        "claims": "Reusable and refillable",
    }
if "history" not in st.session_state:
    st.session_state.history = []
if "latest" not in st.session_state:
    st.session_state.latest = None

# -------------------- SIDEBAR --------------------
with st.sidebar:
    st.markdown("""
    <div class="brand-logo">
      <div class="brand-shield">✓</div>
      <div><div class="brand-name">BrandGuard <span>AI</span></div>
      <div class="brand-sub">Smarter Checks. Stronger Brands.</div></div>
    </div>
    """, unsafe_allow_html=True)
    pages = [
        ("⌂  Home", "Home", "home_btn"),
        ("♧  Brand Rules", "Brand Rules", "rules_btn"),
        ("▤  Content Audit", "Content Audit", "audit_btn"),
        ("◷  History", "History", "history_btn"),
        ("⚙  Settings", "Settings", "settings_btn"),
    ]
    for label, page_name, key in pages:
        if st.button(label, key=key, use_container_width=True):
            st.session_state.page = page_name
            st.rerun()
    st.markdown("""
    <div class="sidebar-bottom"><div style="font-size:48px">🛡️</div>
    Protecting your brand<br>one check at a time.
    <div style="margin-top:14px;color:#718fca">BrandGuard AI</div></div>
    """, unsafe_allow_html=True)

def online():
    st.markdown('<div class="online"><span>●</span> Online &nbsp;&nbsp; ☼</div>', unsafe_allow_html=True)

def run_audit(draft):
    r = st.session_state.rules
    findings = []
    low = draft.lower()

    for word in [x.strip() for x in r["banned"].split(",") if x.strip()]:
        if word.lower() in low:
            findings.append((
                "High", f'Banned phrase found: “{word}”',
                f'The draft contains “{word}”.',
                f'Remove “{word}” or replace it with an approved, evidence-backed statement.'
            ))

    for price_text in re.findall(r'(?:₹|rs\.?\s*)(\d+(?:,\d{3})*(?:\.\d{1,2})?)', draft, re.I):
        try:
            value = float(price_text.replace(",", ""))
            if value != float(r["price"]):
                findings.append((
                    "High",
                    f'Price mismatch: INR {value:,.0f} shown; approved price is INR {r["price"]:,.0f}.',
                    "The price in the draft differs from the saved brand price.",
                    f'Change the price to INR {r["price"]:,.0f} or verify the approved price.'
                ))
        except ValueError:
            pass

    if r["product"] and r["product"].lower() not in low:
        findings.append((
            "Medium", f'Approved product name “{r["product"]}” is missing.',
            "The draft does not contain the configured product name.",
            f'Add the approved name “{r["product"]}” where appropriate.'
        ))

    approved = [x.strip().lower() for x in re.split(r"[,\n;]", r["claims"]) if x.strip()]
    for phrase in ["100%", "plastic free", "eco-friendly", "sustainable", "number one"]:
        if phrase in low and not any(phrase in x for x in approved):
            findings.append((
                "Medium", f'Promotional claim needs verification: “{phrase}”.',
                "This claim is not listed in the approved claims field.",
                "Provide supporting evidence and approve the claim, or remove/rephrase it."
            ))

    if not findings:
        findings = [(
            "Low", "No configured rule violations detected.",
            "The draft passed the current basic rule checks.",
            "Complete a human review before publishing; this checker does not verify every brand or legal requirement."
        )]

    record = {
        "content": draft,
        "findings": findings,
        "status": "Needs review" if any(f[0] in ("High", "Medium") for f in findings) else "Review required",
        "decision": "Pending",
    }
    st.session_state.history.insert(0, record)
    st.session_state.latest = record
    return record

def create_pdf(record):
    buffer = BytesIO()
    navy = colors.HexColor("#101A38")
    purple = colors.HexColor("#7657E8")
    muted = colors.HexColor("#65708A")
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BGTitle", parent=styles["Title"], fontName="Helvetica-Bold",
                              fontSize=22, leading=26, textColor=navy, alignment=TA_LEFT, spaceAfter=4))
    styles.add(ParagraphStyle(name="BGSubtitle", parent=styles["Normal"], fontSize=9,
                              leading=13, textColor=muted))
    styles.add(ParagraphStyle(name="BGSection", parent=styles["Heading2"], fontSize=13,
                              leading=17, textColor=navy, spaceBefore=10, spaceAfter=7))
    styles.add(ParagraphStyle(name="BGBody", parent=styles["BodyText"], fontSize=9,
                              leading=13, textColor=navy, spaceAfter=4))
    styles.add(ParagraphStyle(name="BGSmall", parent=styles["BodyText"], fontSize=8,
                              leading=11, textColor=muted))
    story = []
    header = Table([[
        Paragraph('<font color="#7657E8" size="25"><b>✓</b></font>', styles["BGTitle"]),
        [Paragraph("BRANDGUARD AI", styles["BGTitle"]),
         Paragraph("SMARTER CHECKS. STRONGER BRANDS.", styles["BGSubtitle"])]
    ]], colWidths=[18*mm, 142*mm])
    header.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#F0EEFF")),
        ("BOX",(0,0),(-1,-1),0.8,colors.HexColor("#D8D2FA")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),12),("TOPPADDING",(0,0),(-1,-1),12),
        ("BOTTOMPADDING",(0,0),(-1,-1),12)
    ]))
    story += [header, Spacer(1, 7*mm), Paragraph("CONTENT AUDIT REPORT", styles["BGSection"]),
              Paragraph("Brand compliance review and recommended corrections", styles["BGSubtitle"]),
              Spacer(1, 4*mm)]
    status = escape(str(record.get("status", "Needs review")))
    decision = escape(str(record.get("decision", "Pending")))
    summary = Table([
        [Paragraph("<b>AUDIT STATUS</b>", styles["BGSmall"]), Paragraph("<b>REVIEWER DECISION</b>", styles["BGSmall"])],
        [Paragraph(f"<b>{status}</b>", styles["BGBody"]), Paragraph(f"<b>{decision}</b>", styles["BGBody"])]
    ], colWidths=[80*mm, 80*mm])
    summary.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#F3F5FC")),
        ("BOX",(0,0),(-1,-1),0.7,colors.HexColor("#D8DFF0")),
        ("INNERGRID",(0,0),(-1,-1),0.5,colors.HexColor("#D8DFF0")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),10),
        ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)
    ]))
    story += [summary, Spacer(1, 4*mm), Paragraph("AUDIT FINDINGS", styles["BGSection"])]
    for idx, (severity, issue, evidence, fix) in enumerate(record.get("findings", []), start=1):
        sev_color = colors.HexColor("#C0394A") if severity == "High" else (
            colors.HexColor("#B86B18") if severity == "Medium" else colors.HexColor("#16856B"))
        # Use INR in the PDF for reliable font support.
        issue, evidence, fix = [str(x).replace("₹", "INR ") for x in (issue, evidence, fix)]
        parts = [
            Paragraph(f'<font color="{sev_color.hexval()}"><b>{escape(severity.upper())}</b></font>', styles["BGBody"]),
            Paragraph(f"<b>{idx}. {escape(issue)}</b>", styles["BGBody"]),
            Spacer(1, 1.5*mm),
            Paragraph(f"<b>Evidence:</b> {escape(evidence)}", styles["BGBody"]),
            Paragraph(f"<b>Suggested fix:</b> {escape(fix)}", styles["BGBody"])
        ]
        card = Table([[parts]], colWidths=[160*mm])
        card.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),colors.white),("BOX",(0,0),(-1,-1),0.7,colors.HexColor("#D8DFF0")),
            ("LINEBEFORE",(0,0),(0,-1),3,sev_color),("LEFTPADDING",(0,0),(-1,-1),11),
            ("RIGHTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),8),
            ("BOTTOMPADDING",(0,0),(-1,-1),7)
        ]))
        story.append(KeepTogether([card, Spacer(1, 3*mm)]))
    story += [Spacer(1, 3*mm), Paragraph(
        "<b>Review note:</b> This report uses configured rule checks. Verify claims and complete human review before publication.",
        styles["BGSmall"])]
    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D8DFF0"))
        canvas.line(20*mm, 14*mm, 190*mm, 14*mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(muted)
        canvas.drawString(20*mm, 9*mm, "BRANDGUARD AI | CONFIDENTIAL REVIEW")
        canvas.drawRightString(190*mm, 9*mm, f"Page {doc_obj.page}")
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()

# -------------------- PAGE CONTENT --------------------
page = st.session_state.page
online()

if page == "Home":
    st.markdown("""<div class="hero"><div class="hero-art">🛡️</div>
    <div class="hero-quote">Better Content<br>Builds Stronger Brands</div>
    <h1>Welcome to <span>BrandGuard AI</span></h1>
    <p>Your intelligent brand governance partner. Check your content<br>
    against approved brand rules before publishing.</p></div>""", unsafe_allow_html=True)
    st.write("")
    cols = st.columns(4)
    for col, (ico, title, sub, color) in zip(cols, [
        ("🛡", "Brand Safety", "Keep your content on track", "#2379e8"),
        ("▤", "Policy Compliance", "Follow approved guidelines", "#12bca0"),
        ("♧", "Rule-Based Checks", "Detect risks & violations", "#b64bb9"),
        ("ϟ", "Faster Approvals", "Save time, reduce rework", "#bf833b"),
    ]):
        with col:
            st.markdown(f'<div class="metric"><div class="metric-icon" style="background:{color}33;color:{color}">{ico}</div><div><div class="metric-title">{title}</div><div class="metric-sub">{sub}</div></div></div>', unsafe_allow_html=True)
    st.write("")
    left, right = st.columns([1.55, .95], gap="large")
    with left:
        st.markdown('<div class="panel-title">✦ &nbsp; Quick Start</div><div class="panel-sub">Choose a section from the sidebar to configure rules or review content.</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel"><div class="panel-title">Your brand workspace</div><p style="color:#c1d1ef">Save approved product details, run a content audit, then approve or reject the latest result.</p></div>', unsafe_allow_html=True)
        if st.button("▤  Start a Content Audit", use_container_width=True):
            st.session_state.page = "Content Audit"
            st.rerun()
    with right:
        st.markdown('<div class="side-card"><h3>🛡️ Protect your brand voice</h3><p>Catch banned phrases, price mismatches and claims that need verification before content is published.</p></div>', unsafe_allow_html=True)
        st.write("")
        st.markdown('<div class="panel-title">Recent activity</div>', unsafe_allow_html=True)
        if st.session_state.history:
            for item in st.session_state.history[:3]:
                st.markdown(f'<div class="activity">{escape(item.get("decision","Pending"))}<small>{escape(item.get("status","Needs review"))}</small></div>', unsafe_allow_html=True)
        else:
            st.caption("No audits yet. Your recent activity will appear here.")

elif page == "Brand Rules":
    st.title("♧ Brand Rules")
    st.caption("Set the approved details and phrases used by the preliminary checker.")
    r = st.session_state.rules
    with st.form("rules_page_form"):
        product = st.text_input("Approved product name", value=r["product"])
        price = st.number_input("Approved price (INR)", min_value=0.0, value=float(r["price"]), step=1.0)
        banned = st.text_input("Banned words (comma-separated)", value=r["banned"])
        claims = st.text_area("Approved promotional claims", value=r["claims"], height=110)
        saved = st.form_submit_button("▣  Save Brand Rules", use_container_width=True)
    if saved:
        st.session_state.rules = {"product": product.strip(), "price": price, "banned": banned, "claims": claims}
        st.success("Brand rules saved for this session!")
    st.info("These rules remain available while this Streamlit session is active.")

elif page == "Content Audit":
    st.title("▤ Content Audit")
    st.caption("Paste content below to check it against the saved brand rules.")
    with st.form("audit_page_form"):
        draft = st.text_area("Content draft", placeholder="Example: Grab our Eco Bottle for just ₹799. Best ever! 100% plastic free!", height=160)
        submitted = st.form_submit_button("⌕  Run Brand Audit", use_container_width=True)
    if submitted:
        if not draft.strip():
            st.warning("Please enter some content first.")
        else:
            run_audit(draft.strip())
            st.success("Audit completed. Review the findings below.")
    latest = st.session_state.latest
    if latest:
        st.markdown("---")
        st.subheader("Audit Report")
        st.caption("Rule-based preliminary check · Human review required before publication")
        for sev, issue, evidence, fix in latest["findings"]:
            with st.expander(f"{sev} · {issue}", expanded=True):
                st.write("**Evidence:** " + evidence)
                st.write("**Suggested fix:** " + fix)
        st.info("Status: " + latest["status"])
        st.markdown("---")
        st.subheader("Reviewer Decision")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Approve Content", use_container_width=True, key="approve_content"):
                latest["decision"] = "Approved"
                latest["status"] = "Approved"
                st.session_state.latest = latest
                st.rerun()
        with col2:
            if st.button("❌ Reject Content", use_container_width=True, key="reject_content"):
                latest["decision"] = "Rejected"
                latest["status"] = "Rejected"
                st.session_state.latest = latest
                st.rerun()
        st.write("Current decision: **" + latest.get("decision", "Pending") + "**")
        if latest.get("decision") == "Approved":
            st.success("Content approved by reviewer!")
        elif latest.get("decision") == "Rejected":
            st.warning("Content rejected. Please revise it before publishing.")
        else:
            st.info("Waiting for reviewer decision.")
        st.markdown("---")
        st.subheader("Download Report")
        try:
            pdf_data = create_pdf(latest)
            st.download_button(
                "⬇️ Download Branded PDF Report",
                data=pdf_data,
                file_name="BrandGuard_Audit_Report.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="branded_pdf_download",
            )
        except Exception as exc:
            st.error("PDF report could not be generated. Check the ReportLab installation.")
            st.caption(str(exc))
    else:
        st.info("Run an audit to view findings, make a reviewer decision, and download the PDF.")

elif page == "History":
    st.title("◷ Audit History")
    st.caption("Previous content audits and reviewer decisions")
    if st.session_state.history:
        for i, item in enumerate(st.session_state.history):
            decision = item.get("decision", "Pending")
            with st.expander(f"Audit #{i + 1} — {decision}"):
                st.write("**Content:**", item.get("content", ""))
                st.write("**Status:**", item.get("status", "Needs review"))
                st.write("**Reviewer decision:**", decision)
                for sev, issue, evidence, fix in item.get("findings", []):
                    st.write(f"**{sev}:** {issue}")
                    st.caption("Evidence: " + evidence)
                    st.write("Suggested fix: " + fix)
    else:
        st.info("No audit history yet. Run a brand audit first.")

elif page == "Settings":
    st.title("⚙ Settings")
    st.caption("Basic application information")
    st.markdown('<div class="panel"><div class="panel-title">BrandGuard AI</div><p style="color:#c1d1ef">A preliminary brand-governance dashboard for checking configured phrases, product names, prices and promotional claims.</p><p style="color:#a9bee4">Current checker: rule-based · Final publication decision should be made by a human reviewer.</p></div>', unsafe_allow_html=True)
    if st.button("Clear Audit History", use_container_width=False):
        st.session_state.history = []
        st.session_state.latest = None
        st.success("Audit history cleared for this session.")
