import streamlit as st

from ui import apply_styles, get_json


apply_styles()
st.markdown('<div class="eyebrow">Dashboard · details</div>', unsafe_allow_html=True)
st.link_button("Back to Dashboard", url="/", icon="📊")

selection = st.session_state.get("dashboard_drilldown", "jobs-total")
try:
    summary = get_json("/api/v1/dashboard/summary") or {}
except Exception as error:
    summary = {}
    st.error(str(error))

jobs = summary.get("jobs", [])
job_status_cards = [
    ("draft", "Draft", summary.get("draft_job_count", 0)),
    ("posted", "Posted", summary.get("posted_job_count", summary.get("open_job_count", 0))),
    ("closed", "Closed", summary.get("closed_job_count", 0)),
]
applicant_filters = {
    "applicants": ("Total Applicants", "application_count", "all"),
    "stage-one": ("Passed Stage 1", "stage1_pass_count", "pass"),
    "first-interview": ("1st Interview Scheduled", "first_interview_scheduled_count", "first_interview_scheduled"),
    "second-interview": ("Moved to 2nd Interview", "second_interview_count", "second_interview"),
    "ceo-review": ("At CEO Review", "ceo_decision_count", "ceo_review"),
    "successful": ("Successful Applicants", "successful_applicant_count", "hired"),
    "ceo-failed": ("Failed at CEO Review", "ceo_failed_applicant_count", "failed_at_ceo"),
}

if selection == "jobs-total":
    st.title("Total Jobs")
    st.caption(f"{summary.get('total_job_count', len(jobs))} jobs across every status")
    status_columns = st.columns(3, gap="medium")
    for column, (status, label, count) in zip(status_columns, job_status_cards):
        with column:
            if st.button(f"{label} Jobs\n\n{count}\n\nOpen {label.lower()} requisitions", key=f"job-status-{status}", use_container_width=True):
                st.session_state["dashboard_job_status"] = status
                st.session_state["dashboard_drilldown"] = f"jobs-{status}"
                st.rerun()
    selected_status = None
elif selection in {"jobs-draft", "jobs-open", "jobs-posted", "jobs-closed"}:
    selected_status = {
        "jobs-draft": "draft",
        "jobs-open": "posted",
        "jobs-posted": "posted",
        "jobs-closed": "closed",
    }[selection]
else:
    selected_status = None

if selected_status:
    status_label = selected_status.title()
    status_jobs = [job for job in jobs if job.get("status") == selected_status]
    count = next((value for status, _, value in job_status_cards if status == selected_status), 0)
    st.title(f"{status_label} Jobs")
    st.caption(f"{count} {selected_status} requisitions")
    if not status_jobs:
        st.info(f"There are no {selected_status} jobs yet.")
    else:
        selected_job = st.selectbox(
            "Search and select a job to continue",
            options=status_jobs,
            index=None,
            placeholder="Type a job title, seniority, or location",
            format_func=lambda job: (
                f"{job['title']} · {job.get('seniority') or 'Unspecified seniority'} · "
                f"{job.get('location') or 'Location not set'}"
            ),
            key=f"dashboard-job-picker-{selected_status}",
        )
        if selected_job:
            st.session_state["selected_job_id"] = selected_job["id"]
            if selected_status == "draft":
                st.session_state["hiring-selected-job"] = f"{selected_job['title']} · {selected_job['status'].title()}"
                st.switch_page("pages/1_🎯_Hiring_Request.py")
            else:
                st.session_state["dashboard_applicant_filter"] = "all"
                st.switch_page("pages/6_📋_Dashboard_Job_Applicants.py")
elif selection in applicant_filters:
    title, count_key, decision_filter = applicant_filters[selection]
    st.title(title)
    st.metric("Applicants", summary.get(count_key, 0))
    st.caption("Choose a job to review its matching applicant records and open an applicant profile.")
    if not jobs:
        st.info("No jobs are available yet.")
    else:
        selected_job = st.selectbox(
            "Search and select a job to continue",
            options=jobs,
            index=None,
            placeholder="Type a job title",
            format_func=lambda job: f"{job['title']} · {job['status'].title()}",
            key=f"dashboard-applicant-job-{selection}",
        )
        if selected_job:
            st.session_state["selected_job_id"] = selected_job["id"]
            st.session_state["dashboard_applicant_filter"] = decision_filter
            st.switch_page("pages/6_📋_Dashboard_Job_Applicants.py")
elif selection != "jobs-total":
    st.title("Dashboard Details")
    st.info("Choose a dashboard card to open its details.")