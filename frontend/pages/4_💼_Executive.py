import streamlit as st

from ui import apply_styles, fmt_status, get_json, job_options, post_json, safe_api, status_badge

apply_styles()
st.markdown('<div class="eyebrow">Phase 4 · executive decision</div>', unsafe_allow_html=True)
st.title("Executive Review")
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
applications = safe_api(lambda: get_json(f"/api/v1/jobs/{job['id']}/applications")) or []
eligible = [item for item in applications if item.get("pipeline_status") in {"active_pipeline", "pending_ceo_decision"}]
if not eligible:
    st.info("No candidates are ready for executive review.")
    st.stop()
app = eligible[st.selectbox("Applicant", eligible, format_func=lambda item: item["id"])]
dossier = safe_api(lambda: get_json(f"/api/v1/applications/{app['id']}/dossier"))
if dossier:
    application = dossier["application"]
    st.markdown(f"{status_badge(application.get('pipeline_status'))}  **Application {application['id'][:8]}…**", unsafe_allow_html=True)
    st.markdown(f"**Screening:** {fmt_status(application.get('agent_decision'))}  ·  {application.get('screening_summary') or 'No summary'}")
    st.subheader("Interview evidence")
    for round_ in dossier.get("interviews", []):
        st.markdown(f"**Round {round_['sequence_order']}** · {fmt_status(round_['status'])} · {round_.get('feedback') or 'No feedback'}")
        if round_.get("local_audio_path"):
            st.caption(f"Verified local recording: {round_['local_audio_path']}")
    if application.get("pipeline_status") == "active_pipeline" and st.button("Move to CEO review", type="primary"):
        safe_api(lambda: post_json(f"/api/v1/applications/{app['id']}/move-to-ceo"), success="Application moved to CEO review")
    st.divider()
    decision = st.radio("Final decision", ["pass", "fail"], horizontal=True)
    remarks = st.text_area("CEO remarks", placeholder="Decision rationale")
    if st.button("Lock final decision", type="primary"):
        safe_api(lambda: post_json(f"/api/v1/applications/{app['id']}/final-decision", {"final_decision": decision, "remarks": remarks or None}), success="Final decision saved")
