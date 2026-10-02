import streamlit as st

from ui import apply_styles, fmt_status, get_json, safe_api, status_badge


APPLICANTS_PER_PAGE = 20
FILTERS = {
    "All applicants": "all",
    "Sync pass": "pass",
    "Sync fail": "fail",
    "Active pipeline": "active_pipeline",
    "CEO review": "ceo_review",
    "Hired": "hired",
    "Failed at CEO": "failed_at_ceo",
    "1st interview scheduled": "first_interview_scheduled",
    "2nd interview": "second_interview",
}


def load_applicant_page(
    job_id: str,
    decision_filter: str,
    search: str,
    offset: int,
    selected_application_id: str | None,
) -> dict:
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
st.markdown('<div class="eyebrow">Dashboard · job applicants</div>', unsafe_allow_html=True)
st.link_button("Back to job selection", url="/dashboard-details", icon="📋")

job_id = st.session_state.get("selected_job_id")
if not job_id:
    st.info("Select a job from the Dashboard to view applicants.")
    st.stop()

try:
    jobs = get_json("/api/v1/jobs") or []
except Exception as error:
    st.error(str(error))
    st.stop()

job = next((item for item in jobs if item["id"] == job_id), None)
if not job:
    st.error("The selected job could not be found.")
    st.stop()

st.title(job["title"])
st.caption(" · ".join(value for value in [job.get("seniority"), job.get("tech_stack"), job.get("location"), job.get("work_type")] if value))
with st.expander("Job details", expanded=False):
    st.markdown("**Required experience**")
    st.write(job.get("required_experience") or "—")
    st.markdown("**Compensation**")
    st.write(job.get("salary") or "—")
    st.markdown("**University criteria**")
    st.write(job.get("university") or "—")
    st.markdown("**Job description**")
    st.markdown(job.get("jd_markdown") or "No job description saved.")
    if job.get("google_form_url"):
        st.link_button("Application form", job["google_form_url"])
    if job.get("linkedin_blurb"):
        st.markdown("**LinkedIn post**")
        st.write(job["linkedin_blurb"])

filter_key = f"dashboard-job-applicant-filter-{job_id}"
requested_filter = st.session_state.pop("dashboard_applicant_filter", None)
if requested_filter in FILTERS.values():
    st.session_state[filter_key] = next(label for label, value in FILTERS.items() if value == requested_filter)
selected_filter = st.selectbox(
    "Applicant stage",
    options=list(FILTERS),
    index=0,
    key=filter_key,
)
search = st.text_input("Search applicants", placeholder="Name, email, or application ID", max_chars=200)
query_signature = (FILTERS[selected_filter], search.strip())
query_key = f"dashboard-job-applicant-query-{job_id}"
page_key = f"dashboard-job-applicant-page-{job_id}"
selected_key = f"dashboard-job-applicant-selected-{job_id}"
if st.session_state.get(query_key) != query_signature:
    st.session_state[query_key] = query_signature
    st.session_state[page_key] = 0
    st.session_state.pop(selected_key, None)

page_index = max(st.session_state.get(page_key, 0), 0)
page_result = safe_api(
    lambda: load_applicant_page(
        str(job_id),
        FILTERS[selected_filter],
        search.strip(),
        page_index * APPLICANTS_PER_PAGE,
        st.session_state.get(selected_key),
    )
) or {}
applicants = page_result.get("applicants", [])
total_count = page_result.get("total_count", 0)
st.metric("Applicants in this view", total_count)

if total_count == 0:
    st.info("No applicants match this stage and search.")
    st.stop()

page_count = (total_count + APPLICANTS_PER_PAGE - 1) // APPLICANTS_PER_PAGE
if page_index >= page_count:
    st.session_state[page_key] = page_count - 1
    st.session_state.pop(selected_key, None)
    st.rerun()

table_rows = [
    {
        "Applicant": item.get("candidate_name") or "Unknown applicant",
        "Email": item.get("email") or "",
        "Screening": fmt_status(item.get("agent_decision")),
        "Pipeline": fmt_status(item.get("pipeline_status")),
        "Final decision": fmt_status(item.get("final_decision")),
    }
    for item in applicants
]
table_event = st.dataframe(
    table_rows,
    hide_index=True,
    use_container_width=True,
    on_select="rerun",
    selection_mode="single-row",
    key=f"dashboard-job-applicants-table-{job_id}-{page_index}-{selected_filter}-{search.strip()}",
)
selected_rows = table_event.selection.rows
if selected_rows:
    clicked_application_id = applicants[selected_rows[0]]["id"]
    if clicked_application_id != st.session_state.get(selected_key):
        st.session_state[selected_key] = clicked_application_id
        st.rerun()

previous_col, page_info_col, next_col = st.columns([1, 2, 1])
with previous_col:
    if st.button("Previous", disabled=page_index == 0, key=f"dashboard-applicants-prev-{job_id}", use_container_width=True):
        st.session_state[page_key] = page_index - 1
        st.session_state.pop(selected_key, None)
        st.rerun()
with page_info_col:
    st.caption(f"Page {page_index + 1} of {page_count}")
with next_col:
    if st.button("Next", disabled=page_index >= page_count - 1, key=f"dashboard-applicants-next-{job_id}", use_container_width=True):
        st.session_state[page_key] = page_index + 1
        st.session_state.pop(selected_key, None)
        st.rerun()

selected_id = st.session_state.get(selected_key)
selected_summary = next((item for item in applicants if item["id"] == selected_id), None)
selected_details = page_result.get("selected_application") if selected_summary else None
if selected_summary and selected_details:
    st.divider()
    st.subheader(selected_summary.get("candidate_name") or "Applicant details")
    st.caption(selected_summary.get("email") or "")
    st.markdown(f"**Screening:** {fmt_status(selected_summary.get('agent_decision'))}")
    st.markdown(f"**Pipeline:** {status_badge(selected_summary.get('pipeline_status'))}", unsafe_allow_html=True)
    st.markdown(f"**Final decision:** {fmt_status(selected_summary.get('final_decision'))}")
    st.write(selected_summary.get("screening_summary") or "No screening summary recorded.")
    if selected_details.get("remarks"):
        st.markdown("**Remarks**")
        st.write(selected_details["remarks"])
    if selected_details.get("form_responses"):
        st.markdown("**Application responses**")
        for question, answer in selected_details["form_responses"].items():
            with st.expander(question):
                st.write(answer)