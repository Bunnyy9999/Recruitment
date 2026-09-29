import streamlit as st

from ui import apply_styles, fmt_status, get_json, job_options, post_json, safe_api, status_badge

apply_styles()
st.markdown('<div class="eyebrow">Phase 2 · sync and screening</div>', unsafe_allow_html=True)
st.title("Sync & Screen")
try:
    jobs = get_json("/api/v1/jobs") or []
except Exception as error:
    jobs = []
    st.error(str(error))
options = job_options(jobs)
if not options:
    st.info("Create a requisition first.")
    st.stop()
job = options[st.selectbox("Requisition", list(options))]
sync_col, pool_col = st.columns([1, 1.4])
with sync_col:
    st.subheader("Sync applicant")
    with st.form("sync-applicant"):
        full_name = st.text_input("Full name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        linkedin = st.text_input("LinkedIn URL")
        age = st.number_input("Age", min_value=0, max_value=120, value=0)
        gender = st.text_input("Gender")
        resume = st.text_area("Resume text", height=180)
        responses = st.text_area("Form responses", placeholder="Question: answer", height=120)
        sync = st.form_submit_button("Run sync", type="primary", use_container_width=True)
    if sync:
        form_responses = {}
        for line in responses.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                form_responses[key.strip()] = value.strip()
        payload = {"full_name": full_name, "email": email, "resume_text": resume, "form_responses": form_responses}
        for key, value in {"phone": phone, "linkedin_url": linkedin, "gender": gender}.items():
            if value:
                payload[key] = value
        if age:
            payload["age"] = age
        result = safe_api(lambda: post_json(f"/api/v1/jobs/{job['id']}/sync", payload), success="Applicant evaluated")
        if result:
            st.json({"decision": result.get("agent_decision"), "status": result.get("pipeline_status"), "summary": result.get("screening_summary")})
with pool_col:
    st.subheader("Applicant pool")
    filter_value = st.selectbox("Filter", ["all", "active_pipeline", "failed_at_sync", "pending_ceo_decision"], format_func=fmt_status)
    path = f"/api/v1/jobs/{job['id']}/applications"
    if filter_value != "all":
        path += f"?pipeline_status={filter_value}"
    applications = safe_api(lambda: get_json(path)) or []
    if not applications:
        st.info("No applications in this view.")
    for application in applications:
        st.markdown(f'<div class="record"><div class="record-title">Application {application["id"][:8]}…</div><div class="record-meta">{status_badge(application.get("pipeline_status"))} · screening: {fmt_status(application.get("agent_decision"))}</div><div class="record-meta">{application.get("screening_summary") or "No screening summary"}</div></div>', unsafe_allow_html=True)
    failed = [item for item in applications if item.get("pipeline_status") == "failed_at_sync"]
    if failed:
        chosen = st.selectbox("Failed application", [item["id"] for item in failed])
        username = st.text_input("HR username")
        if st.button("Restore to active pipeline", type="primary"):
            safe_api(lambda: post_json(f"/api/v1/applications/{chosen}/hr-override", {"hr_username": username}), success="Application restored")
