import streamlit as st

from ui import apply_styles, fmt_status, get_json, job_options, post_json, safe_api, status_badge


@st.cache_data(ttl=30, show_spinner=False)
def load_jobs():
    return get_json("/api/v1/jobs") or []


@st.cache_data(ttl=10, show_spinner=False)
def load_executive_workspace(job_id: str, application_id: str | None):
    params = {"application_id": application_id} if application_id else {}
    return get_json(
        f"/api/v1/jobs/{job_id}/executive-workspace",
        params=params,
    )


apply_styles()
st.markdown('<div class="eyebrow">Phase 4 · executive decision</div>', unsafe_allow_html=True)
st.title("Executive Review")
try:
    jobs = load_jobs()
except Exception as error:
    jobs = []
    st.error(str(error))
options = job_options(jobs)
if not options:
    st.info("Create a requisition first.")
    st.stop()
job = options[st.selectbox("Requisition", list(options))]
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
if st.session_state.get(applicant_key) not in eligible_by_id:
    st.session_state[applicant_key] = eligible[0]["id"]
    workspace = safe_api(
        lambda: load_executive_workspace(str(job["id"]), eligible[0]["id"])
    ) or workspace

applicant_id = st.selectbox(
    "Applicant",
    options=list(eligible_by_id),
    format_func=lambda item_id: (
        f"{eligible_by_id[item_id].get('candidate_name') or 'Unknown'} — "
        f"{eligible_by_id[item_id].get('email') or 'no email'}"
    ),
    key=applicant_key,
)
app = eligible_by_id[applicant_id]
dossier = workspace.get("dossier")
if dossier:
    application = dossier["application"]
    st.markdown(f"{status_badge(application.get('pipeline_status'))}  **Application {application['id'][:8]}…**", unsafe_allow_html=True)
    st.markdown(f"**Screening:** {fmt_status(application.get('agent_decision'))}  ·  {application.get('screening_summary') or 'No summary'}")
    st.subheader("Interview evidence")
    for round_ in dossier.get("interviews", []):
        st.markdown(f"**Round {round_['sequence_order']}** · {fmt_status(round_['status'])} · {round_.get('feedback') or 'No feedback'}")
        if round_.get("local_audio_path"):
            st.caption(f"Verified local recording: {round_['local_audio_path']}")
    st.divider()
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
