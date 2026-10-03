from datetime import date, datetime, time, timezone

import streamlit as st

from ui import api_request, apply_styles, get_json, job_options, patch_json, post_json, safe_api, status_badge


def delete_interview_round(interview_id: str) -> bool:
    api_request("DELETE", f"/api/v1/interviews/{interview_id}")
    return True


apply_styles()


@st.cache_data(ttl=30, show_spinner=False)
def load_jobs():
    return get_json("/api/v1/jobs") or []


@st.cache_data(ttl=10, show_spinner=False)
def load_interview_workspace(job_id: str, application_id: str | None):
    params = {"application_id": application_id} if application_id else {}
    return get_json(
        f"/api/v1/jobs/{job_id}/interview-workspace",
        params=params,
    )


apply_styles()
st.markdown('<div class="eyebrow">Pipeline · interview workspace</div>', unsafe_allow_html=True)
st.title("Interview Workspace")
st.caption("Schedule the next conversation, capture interviewer feedback, and keep every round attached to the applicant record.")
try:
    routed_job = st.session_state.pop("interview-job-data", None)
    jobs = [routed_job] if isinstance(routed_job, dict) and routed_job.get("id") else load_jobs()
except Exception as error:
    jobs = []
    st.error(str(error))
options = job_options(jobs)
if not options:
    st.info("Create a requisition first.")
    st.stop()
job_labels = list(options)
requested_job = st.session_state.pop("interview-job", None)
job_picker_key = "interview-job-picker"
if requested_job in options:
    st.session_state[job_picker_key] = requested_job
if st.session_state.get(job_picker_key) not in options:
    st.session_state[job_picker_key] = job_labels[0]
job = options[st.selectbox("Requisition", job_labels, key=job_picker_key)]
applicant_key = f"interview-applicant-{job['id']}"
selected_applicant_id = st.session_state.get(applicant_key)
workspace = safe_api(
    lambda: load_interview_workspace(str(job["id"]), selected_applicant_id)
) or {}
applications = workspace.get("applicants", [])
if not applications:
    st.info("No active applicants are ready for interviews.")
    st.stop()
applicants_by_id = {item["id"]: item for item in applications}
if st.session_state.get(applicant_key) not in applicants_by_id:
    st.session_state[applicant_key] = applications[0]["id"]
    workspace = safe_api(
        lambda: load_interview_workspace(str(job["id"]), applications[0]["id"])
    ) or workspace
app = st.selectbox(
    "Applicant",
    options=list(applicants_by_id),
    format_func=lambda applicant_id: (
        f"{applicants_by_id[applicant_id].get('candidate_name') or 'Unknown'} — "
        f"{applicants_by_id[applicant_id].get('email') or 'no email'}"
    ),
    key=applicant_key,
)
app = applicants_by_id[app]
rounds = workspace.get("rounds", [])
route_info = st.session_state.get("interview-applicant-info") or {}
application_info = route_info if route_info.get("id") == app["id"] else app
st.markdown(
    f'<div class="workspace-panel"><div class="eyebrow">Selected applicant</div>'
    f'<h3>{app.get("candidate_name") or "Unknown applicant"}</h3>'
    f'<div class="record-meta">{app.get("email") or "No email recorded"} · {application_info.get("phone") or "No phone recorded"} · {status_badge(app.get("pipeline_status"))}</div>'
    f'<div class="record-meta">Screening: {application_info.get("screening_summary") or "No screening summary recorded."}</div></div>',
    unsafe_allow_html=True,
)
st.markdown("<div class='action-strip'>Use the controls below to schedule the next round or complete the CEO hand-off when every recorded round is complete.</div>", unsafe_allow_html=True)
left, right = st.columns([1.35, 1])
with left:
    st.markdown('<div class="workspace-panel">', unsafe_allow_html=True)
    st.subheader("Interview rounds")
    if not rounds:
        st.info("No interview rounds yet. Schedule the first round from the panel on the right.")
    for round_ in rounds:
        st.markdown(f'<div class="round-card {round_["status"]}"><div class="round-title">Round {round_["sequence_order"]} · Technical interview {status_badge(round_["status"])}</div><div class="round-meta">Scheduled: {round_.get("scheduled_at") or "—"} · Date: {round_.get("interview_date") or "—"}</div><div class="round-meta">{round_.get("feedback") or "No interviewer notes yet."}</div></div>', unsafe_allow_html=True)
        with st.expander(f"Manage round {round_['sequence_order']}"):
            with st.form(f"manage-round-{round_['id']}"):
                feedback = st.text_area("Feedback", value=round_.get("feedback") or "", key=f"feedback-{round_['id']}")
                state = st.selectbox("Round status", ["pending", "complete"], index=0 if round_["status"] == "pending" else 1, key=f"state-{round_['id']}")
                recording = st.file_uploader("Recording (optional)", type=["mp3", "m4a"], key=f"recording-{round_['id']}")
                recording_date = st.date_input("Interview date", value=round_.get("interview_date") or date.today(), key=f"date-{round_['id']}")
                save_round = st.form_submit_button("Save round", type="primary")

            if save_round:
                recording_saved = True
                if recording:
                    recording_saved = safe_api(
                        lambda: api_request(
                            "POST",
                            f"/api/v1/interviews/{round_['id']}/recording",
                            params={"interview_date": recording_date.isoformat()},
                            files={"recording": (recording.name, recording.getvalue(), "audio/mpeg")},
                        )
                    ) is not None

                if recording_saved:
                    result = safe_api(
                        lambda: patch_json(
                            f"/api/v1/interviews/{round_['id']}",
                            {"feedback": feedback, "status": state},
                        ),
                        success="Round saved",
                    )
                    if result:
                        load_interview_workspace.clear()
                        st.rerun()

            if st.button("Remove round", key=f"delete-round-{round_['id']}", type="secondary"):
                result = safe_api(
                    lambda: delete_interview_round(str(round_["id"])),
                    success="Round removed",
                )
                if result:
                    load_interview_workspace.clear()
                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    if (
        rounds
        and all(round_["status"] == "complete" for round_ in rounds)
        and app.get("pipeline_status") == "active_pipeline"
        and st.button(
            "Move to CEO review",
            key=f"move-to-ceo-{app['id']}",
            type="primary",
            use_container_width=True,
        )
    ):
        result = safe_api(
            lambda: post_json(f"/api/v1/applications/{app['id']}/move-to-ceo"),
            success="Application moved to CEO review",
        )
        if result:
            load_interview_workspace.clear()
            st.rerun()
with right:
    st.markdown('<div class="workspace-panel">', unsafe_allow_html=True)
    st.subheader("Schedule next round")
    st.caption(f"This will create Technical Interview {len(rounds) + 1} for the selected applicant.")
    with st.form("schedule-round"):
        schedule_date = st.date_input("Date", value=date.today())
        schedule_time = st.time_input("Time", value=time(10, 0))
        schedule = st.form_submit_button("Schedule round", type="primary", use_container_width=True)
    if schedule:
        scheduled_at = datetime.combine(schedule_date, schedule_time, tzinfo=timezone.utc).isoformat()
        result = safe_api(lambda: post_json(f"/api/v1/applications/{app['id']}/interviews", {"scheduled_at": scheduled_at}), success="Next round scheduled")
        if result:
            load_interview_workspace.clear()
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
