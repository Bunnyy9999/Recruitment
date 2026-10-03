import streamlit as st

from ui import apply_styles, fmt_status, get_json, job_options, post_json, safe_api, status_badge


@st.cache_data(ttl=30, show_spinner=False)
def load_jobs():
    return get_json("/api/v1/jobs") or []


apply_styles()


@st.cache_data(ttl=10, show_spinner=False)
def load_executive_workspace(job_id: str, application_id: str | None):
    params = {"application_id": application_id} if application_id else {}
    return get_json(
        f"/api/v1/jobs/{job_id}/executive-workspace",
        params=params,
    )


apply_styles()
st.markdown('<div class="eyebrow">Pipeline · final gate</div>', unsafe_allow_html=True)
st.title("Executive Review")
st.caption("Review the complete interview record, then make the final hiring decision for this applicant.")
try:
    routed_job = st.session_state.pop("executive-job-data", None)
    jobs = [routed_job] if isinstance(routed_job, dict) and routed_job.get("id") else load_jobs()
except Exception as error:
    jobs = []
    st.error(str(error))
options = job_options(jobs)
if not options:
    st.info("Create a requisition first.")
    st.stop()
job_labels = list(options)
requested_job = st.session_state.pop("executive-job", None)
job_picker_key = "executive-job-picker"
if requested_job in options:
    st.session_state[job_picker_key] = requested_job
job_choices = ["Select a requisition"] + job_labels
selected_job = st.selectbox("Requisition", job_choices, key=job_picker_key)
if selected_job == "Select a requisition":
    st.info("Select a requisition to view candidates ready for CEO review.")
    st.stop()
job = options[selected_job]
applicant_key = f"executive-applicant-{job['id']}"
selected_applicant_id = st.session_state.get(applicant_key)
workspace = safe_api(
    lambda: load_executive_workspace(str(job["id"]), selected_applicant_id)
) or {}
eligible = workspace.get("eligible_applicants", [])
if not eligible:
    st.info("No candidates are ready for executive review.")
    st.stop()

eligible_by_id = {item["id"]: item for item in eligible}
applicant_choices = [None] + list(eligible_by_id)
applicant_id = st.selectbox(
    "Applicant",
    options=applicant_choices,
    format_func=lambda item_id: (
        "Select an applicant"
        if item_id is None
        else (
        f"{eligible_by_id[item_id].get('candidate_name') or 'Unknown'} — "
        f"{eligible_by_id[item_id].get('email') or 'no email'}"
        )
    ),
    key=applicant_key,
)
if applicant_id is None:
    st.info("Select an applicant to review the interview evidence and record a final decision.")
    st.stop()
workspace = safe_api(
    lambda: load_executive_workspace(str(job["id"]), applicant_id)
) or workspace
app = eligible_by_id[applicant_id]
dossier = workspace.get("dossier")
if dossier:
    application = dossier["application"]
    st.markdown(
        f'<div class="workspace-panel"><div class="eyebrow">Decision dossier</div>'
        f'<h3>{app.get("candidate_name") or "Unknown applicant"}</h3>'
        f'<div class="record-meta">{app.get("email") or "No email recorded"} · {status_badge(application.get("pipeline_status"))} · Application {application["id"][:8]}…</div></div>',
        unsafe_allow_html=True,
    )
    screening_col, stage_col = st.columns(2)
    with screening_col:
        st.markdown('<div class="workspace-stat"><div class="workspace-stat-label">AI screening</div><div class="workspace-stat-value">' + fmt_status(application.get("agent_decision")) + '</div></div>', unsafe_allow_html=True)
    with stage_col:
        st.markdown('<div class="workspace-stat"><div class="workspace-stat-label">Pipeline stage</div><div class="workspace-stat-value">' + fmt_status(application.get("current_stage")) + '</div></div>', unsafe_allow_html=True)
    st.markdown("**Screening summary**")
    st.write(application.get("screening_summary") or "No summary recorded.")
    st.markdown('<div class="workspace-panel">', unsafe_allow_html=True)
    st.subheader("Interview evidence")
    for round_ in dossier.get("interviews", []):
        st.markdown(f'<div class="round-card {round_["status"]}"><div class="round-title">Round {round_["sequence_order"]} · {fmt_status(round_["status"])}</div><div class="round-meta">{round_.get("feedback") or "No feedback"}</div></div>', unsafe_allow_html=True)
        if round_.get("local_audio_path"):
            st.caption(f"Verified local recording ")
    st.markdown('</div>', unsafe_allow_html=True)
    decision = st.radio("Final decision", ["pass", "fail"], horizontal=True)
    remarks = st.text_area("CEO remarks", placeholder="Decision rationale")
    if st.button("Lock final decision", type="primary"):
        result = safe_api(
            lambda: post_json(
                f"/api/v1/applications/{app['id']}/final-decision",
                {"final_decision": decision, "remarks": remarks or None},
            ),
            success="Final decision saved",
        )
        if result:
            load_executive_workspace.clear()
            st.session_state.pop(applicant_key, None)
            st.rerun()
