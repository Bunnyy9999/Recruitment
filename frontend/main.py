from pathlib import Path

import streamlit as st

from ui import get_json, setup_page


setup_page("Dashboard")


def command_center() -> None:
    logo_column, brand_column = st.columns([0.75, 5], vertical_alignment="center")
    with logo_column:
        st.image(Path(__file__).parent / "Pictures" / "DataRopes.jpg", width=76)
    with brand_column:
        st.markdown(
            '<div class="dashboard-header"><div class="dashboard-brand-name">DataRopes.ai</div>'
            '<div class="dashboard-title">Dashboard</div></div>',
            unsafe_allow_html=True,
        )
    try:
        summary = get_json("/api/v1/dashboard/summary") or {}
    except Exception as error:
        summary = {}
        st.error(str(error))

    cards = [
        ("jobs-total", "Total Jobs", "total_job_count", "Across all statuses"),
        ("jobs-draft", "Draft Jobs", "draft_job_count", "Not yet posted"),
        ("jobs-open", "Posted Jobs", "posted_job_count", "Accepting applicants"),
        ("jobs-closed", "Closed Jobs", "closed_job_count", "No longer open"),
        ("applicants", "Total Applicants", "application_count", "Across all jobs"),
        ("stage-one", "Passed Stage 1", "stage1_pass_count", "Sync screening passed"),
        ("first-interview", "1st Interview Scheduled", "first_interview_scheduled_count", "Awaiting completion"),
        ("second-interview", "Moved to 2nd Interview", "second_interview_count", "Round one complete"),
        ("ceo-review", "At CEO Review", "ceo_decision_count", "Awaiting final decision"),
        ("successful", "Successful Applicants", "successful_applicant_count", "Hired by CEO"),
        ("ceo-failed", "Failed at CEO Review", "ceo_failed_applicant_count", "Rejected by CEO"),
    ]
    for row_start in range(0, len(cards), 3):
        cols = st.columns(3, gap="medium")
        for col, (tone, label, key, note) in zip(cols, cards[row_start : row_start + 3]):
            value = summary.get(key, "—")
            with col:
                with st.container(key=f"dashboard-card-wrap-{tone}"):
                    if st.button(
                        f"{label}\n\n{value}\n\n{note}",
                        key=f"dashboard-card-{tone}",
                        help=f"Open {label.lower()} details",
                        use_container_width=True,
                    ):
                        st.session_state["dashboard_drilldown"] = tone
                        st.switch_page("pages/5_🔎_Dashboard_Drilldown.py")


pages = {
    "Dashboard": st.Page(command_center, title="Dashboard", icon="📊", url_path="dashboard"),
    "Jobs Dashboard": st.Page("pages/0_🏢_Jobs_Dashboard.py", title="Jobs Dashboard", icon="🏢"),
    "Hiring Request": st.Page("pages/1_🎯_Hiring_Request.py", title="Hiring Request", icon="🎯"),
    "Sync & Screen": st.Page("pages/2_🔄_Sync_&_Screen.py", title="Sync & Screen", icon="🔄"),
    "Interviews": st.Page("pages/3_🎙️_Interviews.py", title="Interviews", icon="🎙️"),
    "Executive Review": st.Page("pages/4_💼_Executive.py", title="Executive Review", icon="💼"),
    "Dashboard Details": st.Page("pages/5_🔎_Dashboard_Drilldown.py", title="Dashboard Details", url_path="dashboard-details", visibility="hidden"),
    "Job Applicant Details": st.Page("pages/6_📋_Dashboard_Job_Applicants.py", title="Job Applicant Details", url_path="dashboard-job-applicants", visibility="hidden"),
}

st.navigation(list(pages.values())).run()
