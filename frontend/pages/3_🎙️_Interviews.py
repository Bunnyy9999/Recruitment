from datetime import date, datetime, time, timezone

import streamlit as st

from ui import api_request, apply_styles, get_json, job_options, patch_json, post_json, safe_api, status_badge

apply_styles()
st.markdown('<div class="eyebrow">Phase 3 · technical interviews</div>', unsafe_allow_html=True)
st.title("Interviews")
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
applications = safe_api(lambda: get_json(f"/api/v1/jobs/{job['id']}/applications?pipeline_status=active_pipeline")) or []
if not applications:
    st.info("No active applicants are ready for interviews.")
    st.stop()
app = applications[st.selectbox("Applicant", applications, format_func=lambda item: item["id"])]
rounds = safe_api(lambda: get_json(f"/api/v1/applications/{app['id']}/interviews")) or []
left, right = st.columns([1.35, 1])
with left:
    st.subheader("Interview rounds")
    for round_ in rounds:
        st.markdown(f'<div class="record"><div class="record-title">Technical interview {round_["sequence_order"]} {status_badge(round_["status"])}</div><div class="record-meta">Scheduled: {round_.get("scheduled_at") or "—"} · Date: {round_.get("interview_date") or "—"}</div><div class="record-meta">{round_.get("feedback") or "No interviewer notes yet."}</div></div>', unsafe_allow_html=True)
        with st.expander(f"Manage round {round_['sequence_order']}"):
            feedback = st.text_area("Feedback", value=round_.get("feedback") or "", key=f"feedback-{round_['id']}")
            state = st.selectbox("Round status", ["pending", "complete"], index=0 if round_["status"] == "pending" else 1, key=f"state-{round_['id']}")
            if st.button("Save round", key=f"save-round-{round_['id']}"):
                safe_api(lambda: patch_json(f"/api/v1/interviews/{round_['id']}", {"feedback": feedback, "status": state}), success="Round updated")
            recording = st.file_uploader("MP3 recording", type=["mp3"], key=f"recording-{round_['id']}")
            recording_date = st.date_input("Interview date", value=date.today(), key=f"date-{round_['id']}")
            if recording and st.button("Store recording", key=f"upload-{round_['id']}", type="primary"):
                result = safe_api(lambda: api_request("POST", f"/api/v1/interviews/{round_['id']}/recording", params={"interview_date": recording_date.isoformat()}, files={"recording": (recording.name, recording.getvalue(), "audio/mpeg")}), success="Recording verified and linked")
                if result:
                    st.rerun()
with right:
    st.subheader("Schedule next round")
    with st.form("schedule-round"):
        schedule_date = st.date_input("Date", value=date.today())
        schedule_time = st.time_input("Time", value=time(10, 0))
        schedule = st.form_submit_button("Schedule round", type="primary", use_container_width=True)
    if schedule:
        scheduled_at = datetime.combine(schedule_date, schedule_time, tzinfo=timezone.utc).isoformat()
        result = safe_api(lambda: post_json(f"/api/v1/applications/{app['id']}/interviews", {"scheduled_at": scheduled_at}), success="Next round scheduled")
        if result:
            st.rerun()
