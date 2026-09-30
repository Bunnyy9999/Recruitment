import streamlit as st

from ui import apply_styles, fmt_status, get_json, safe_api, status_badge

apply_styles()
st.markdown('<div class="eyebrow">Portfolio overview</div>', unsafe_allow_html=True)
st.title("Jobs Dashboard")

try:
    jobs = get_json("/api/v1/jobs") or []
except Exception as error:
    jobs = []
    st.error(str(error))

if not jobs:
    st.info("No jobs have been created yet.")
    st.stop()

selected_job_id = st.session_state.get("selected_job_id")
if selected_job_id not in {job["id"] for job in jobs}:
    selected_job_id = jobs[0]["id"]
    st.session_state["selected_job_id"] = selected_job_id

job_columns = st.columns(3)
for index, job in enumerate(jobs):
    with job_columns[index % 3]:
        container = st.container(border=True)
        with container:
            st.markdown(f"**{job.get('title', 'Untitled job')}**")
            st.caption(f"{job.get('seniority', 'Unspecified')} · {job.get('tech_stack', 'No stack data')}")
            st.markdown(status_badge(job.get("status")), unsafe_allow_html=True)
            if st.button("Open", key=f"open-job-{job['id']}", use_container_width=True):
                st.session_state["selected_job_id"] = job["id"]
                st.rerun()

selected_job = next((job for job in jobs if job["id"] == selected_job_id), jobs[0])
st.divider()
selected_job_title = selected_job.get("title", "Selected role")
selected_job_status = selected_job.get("status", "draft")
st.subheader(f"{selected_job_title}")
st.markdown(f"{status_badge(selected_job_status)} · {selected_job.get('seniority', 'Unspecified')} · {selected_job.get('tech_stack', 'No stack data')}", unsafe_allow_html=True)

applications = safe_api(lambda: get_json(f"/api/v1/jobs/{selected_job['id']}/applications")) or []
filter_options = ["All", "Pass", "Fail", "Pending"]
selected_filter = st.segmented_control("Applicant filter", options=filter_options, default="All")
search = st.text_input("Search applicants", placeholder="Name, email, or application ID")

if selected_filter == "Pass":
    applications = [item for item in applications if item.get("agent_decision") == "pass"]
elif selected_filter == "Fail":
    applications = [item for item in applications if item.get("agent_decision") == "fail"]
elif selected_filter == "Pending":
    applications = [
        item
        for item in applications
        if item.get("agent_decision") in {None, "pending"} or item.get("final_decision") == "pending"
    ]

if search.strip():
    needle = search.strip().casefold()
    applications = [
        item
        for item in applications
        if needle in " ".join([item.get("candidate_name", ""), item.get("email", ""), item.get("id", "")]).casefold()
    ]

if not applications:
    st.info("No applicants match this job and filter combination.")
    st.stop()

app_rows = [
    {
        "Applicant": item.get("candidate_name") or "Unknown applicant",
        "Email": item.get("email") or "",
        "Phone": item.get("phone") or "",
        "Screening": fmt_status(item.get("agent_decision")),
        "Pipeline": fmt_status(item.get("pipeline_status")),
        "Final": fmt_status(item.get("final_decision")),
        "Summary": item.get("screening_summary") or "No summary",
    }
    for item in applications
]

st.dataframe(app_rows, hide_index=True, use_container_width=True)

selected_application_id = st.selectbox(
    "Open applicant details",
    options=[item["id"] for item in applications],
    format_func=lambda item_id: next(
        (item.get("candidate_name") or "Unknown applicant" for item in applications if item["id"] == item_id),
        "Unknown applicant",
    ),
)
selected_application = next((item for item in applications if item["id"] == selected_application_id), applications[0])

with st.container(border=True):
    st.subheader(selected_application.get("candidate_name") or "Applicant details")
    st.caption(selected_application.get("email") or "No email")
    st.write(f"Pipeline: {fmt_status(selected_application.get('pipeline_status'))}")
    st.write(f"Screening: {fmt_status(selected_application.get('agent_decision'))}")
    st.write(f"Final decision: {fmt_status(selected_application.get('final_decision'))}")
    st.write(selected_application.get("screening_summary") or "No screening summary recorded.")

    if selected_application.get("form_responses"):
        st.markdown("**Form responses**")
        for question, answer in selected_application["form_responses"].items():
            st.markdown(f"**{question}**")
            st.write(answer)
