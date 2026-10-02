import streamlit as st

from ui import apply_styles, fmt_status, get_json, safe_api, status_badge

APPLICANTS_PER_PAGE = 20


@st.cache_data(ttl=30, show_spinner=False)
def load_jobs():
    return get_json("/api/v1/jobs") or []


@st.cache_data(ttl=15, show_spinner=False)
def load_job_dashboard_page(
    job_id: str,
    decision_filter: str,
    search: str,
    offset: int,
    selected_application_id: str | None,
):
    params = {
        "decision_filter": decision_filter,
        "search": search or None,
        "offset": offset,
        "limit": APPLICANTS_PER_PAGE,
        "selected_application_id": selected_application_id,
    }
    return get_json(
        f"/api/v1/jobs/{job_id}/dashboard-applicants",
        params={key: value for key, value in params.items() if value is not None},
    )

apply_styles()
st.markdown('<div class="eyebrow">Portfolio overview</div>', unsafe_allow_html=True)
st.title("Jobs Dashboard")

try:
    jobs = load_jobs()
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
            details = " · ".join(
                value
                for value in [job.get("location"), job.get("work_type"), job.get("salary")]
                if value
            )
            if details:
                st.caption(details)
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
st.caption(
    " · ".join(
        value
        for value in [
            selected_job.get("required_experience"),
            selected_job.get("salary"),
            selected_job.get("location"),
            selected_job.get("work_type"),
            selected_job.get("university"),
        ]
        if value
    )
)

filter_options = {
    "All": "all",
    "Sync pass": "pass",
    "Sync fail": "fail",
    "Active pipeline": "active_pipeline",
    "CEO review": "ceo_review",
    "Hired": "hired",
    "Failed at CEO": "failed_at_ceo",
    "1st interview scheduled": "first_interview_scheduled",
    "2nd interview": "second_interview",
}
filter_key = f"job-dashboard-filter-{selected_job['id']}"
requested_filter = st.session_state.pop("dashboard_applicant_filter", None)
if requested_filter in filter_options.values():
    st.session_state[filter_key] = next(label for label, value in filter_options.items() if value == requested_filter)
selected_filter = st.selectbox(
    "Applicant filter",
    options=list(filter_options),
    index=0,
    key=filter_key,
)
search_state_key = f"job-dashboard-search-{selected_job['id']}"
with st.form(f"job-dashboard-search-form-{selected_job['id']}"):
    search_input = st.text_input(
        "Search applicants",
        placeholder="Name, email, or application ID",
        value=st.session_state.get(search_state_key, ""),
        max_chars=200,
    )
    search_submitted = st.form_submit_button("Search")
if search_submitted:
    st.session_state[search_state_key] = search_input.strip()
search = st.session_state.get(search_state_key, "")

page_state_key = f"job-dashboard-page-{selected_job['id']}"
query_state_key = f"job-dashboard-query-{selected_job['id']}"
selected_application_key = f"job-dashboard-applicant-{selected_job['id']}"
query_signature = (filter_options[selected_filter], search)
if st.session_state.get(query_state_key) != query_signature:
    st.session_state[query_state_key] = query_signature
    st.session_state[page_state_key] = 0
    st.session_state.pop(selected_application_key, None)

page_index = max(st.session_state.get(page_state_key, 0), 0)
page_result = safe_api(
    lambda: load_job_dashboard_page(
        str(selected_job["id"]),
        filter_options[selected_filter],
        search,
        page_index * APPLICANTS_PER_PAGE,
        st.session_state.get(selected_application_key),
    )
) or {}
applicants = page_result.get("applicants", [])
total_count = page_result.get("total_count", 0)

if total_count == 0:
    st.info("No applicants match this job and filter combination.")
    st.stop()

page_count = (total_count + APPLICANTS_PER_PAGE - 1) // APPLICANTS_PER_PAGE
if page_index >= page_count:
    st.session_state[page_state_key] = page_count - 1
    st.session_state.pop(selected_application_key, None)
    st.rerun()

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
    for item in applicants
]

table_event = st.dataframe(
    app_rows,
    hide_index=True,
    use_container_width=True,
    on_select="rerun",
    selection_mode="single-row",
    key=f"job-dashboard-applicants-{selected_job['id']}-{page_index}-{selected_filter}-{search}",
)
selected_rows = table_event.selection.rows
if selected_rows:
    clicked_application_id = applicants[selected_rows[0]]["id"]
    if clicked_application_id != st.session_state.get(selected_application_key):
        st.session_state[selected_application_key] = clicked_application_id
        st.rerun()

previous_col, page_info_col, next_col = st.columns([1, 2, 1])
with previous_col:
    if st.button(
        "Previous",
        disabled=page_index == 0,
        key=f"job-dashboard-previous-{selected_job['id']}",
        use_container_width=True,
    ):
        st.session_state[page_state_key] = page_index - 1
        st.session_state.pop(selected_application_key, None)
        st.rerun()
with page_info_col:
    first_applicant = page_index * APPLICANTS_PER_PAGE + 1
    last_applicant = min((page_index + 1) * APPLICANTS_PER_PAGE, total_count)
    st.caption(
        f"Applicants {first_applicant}-{last_applicant} of {total_count} · "
        f"Page {page_index + 1} of {page_count}"
    )
with next_col:
    if st.button(
        "Next",
        disabled=page_index >= page_count - 1,
        key=f"job-dashboard-next-{selected_job['id']}",
        use_container_width=True,
    ):
        st.session_state[page_state_key] = page_index + 1
        st.session_state.pop(selected_application_key, None)
        st.rerun()

selected_application = page_result.get("selected_application")

if selected_application:
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
