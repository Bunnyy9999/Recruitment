import streamlit as st

from ui import apply_styles, fmt_status, get_json, post_json, safe_api


APPLICANTS_PER_PAGE = 20
FILTERS = {
    "All applicants": "all",
    "Passed Stage 1": "stage_one",
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
) -> dict:
    params = {
        "decision_filter": decision_filter,
        "search": search or None,
        "offset": offset,
        "limit": APPLICANTS_PER_PAGE,
    }
    return get_json(
        f"/api/v1/jobs/{job_id}/dashboard-applicants",
        params={key: value for key, value in params.items() if value is not None},
    )


apply_styles()
st.markdown('<div class="eyebrow">Dashboard · job applicants</div>', unsafe_allow_html=True)
if st.button("Back to job selection", icon="📋"):
    st.switch_page("pages/5_🔎_Dashboard_Drilldown.py")

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
if requested_filter is None:
    requested_filter = st.session_state.pop("candidate_detail_return_filter", None)
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
    selected_application = applicants[selected_rows[0]]
    if selected_application["id"] != st.session_state.get(selected_key):
        st.session_state[selected_key] = selected_application["id"]
        st.rerun()

selected_application = next(
    (item for item in applicants if item["id"] == st.session_state.get(selected_key)),
    None,
)
if selected_application:
    st.divider()
    action_filter = FILTERS[selected_filter]
    info_tab, action_tab = st.tabs(["Applicant info", "Next action"])
    with info_tab:
        st.markdown('<div class="eyebrow">Selected applicant</div>', unsafe_allow_html=True)
        st.subheader(selected_application.get("candidate_name") or "Applicant")
        info_col, stage_col, decision_col = st.columns(3)
        with info_col:
            st.caption("Email")
            st.write(selected_application.get("email") or "Not recorded")
            st.caption("Phone")
            st.write(selected_application.get("phone") or "Not recorded")
        with stage_col:
            st.caption("Pipeline")
            st.write(fmt_status(selected_application.get("pipeline_status")))
            st.caption("Screening")
            st.write(fmt_status(selected_application.get("agent_decision")))
        with decision_col:
            st.caption("Final decision")
            st.write(fmt_status(selected_application.get("final_decision")))
            st.caption("Application")
            st.write(f"{selected_application['id'][:8]}…")
        st.markdown("**Screening summary**")
        st.write(selected_application.get("screening_summary") or "No screening summary recorded.")
    with action_tab:
        action_col, profile_col = st.columns([2.2, 1], gap="medium")
        with action_col:
            if action_filter == "stage_one":
                if st.button("Schedule interview", type="primary", icon="📅", use_container_width=True):
                    st.session_state[f"interview-applicant-{job_id}"] = selected_application["id"]
                    st.session_state["interview-applicant-info"] = selected_application
                    st.session_state["interview-job"] = f"{job['title']} · {job['status'].title()}"
                    st.session_state["interview-job-data"] = job
                    st.switch_page("pages/3_Interviews.py")
            elif action_filter in {"first_interview_scheduled", "second_interview"}:
                schedule_col, ceo_col = st.columns(2)
                with schedule_col:
                    if st.button("Schedule next interview", type="primary", icon="📅", use_container_width=True):
                        st.session_state[f"interview-applicant-{job_id}"] = selected_application["id"]
                        st.session_state["interview-applicant-info"] = selected_application
                        st.session_state["interview-job"] = f"{job['title']} · {job['status'].title()}"
                        st.session_state["interview-job-data"] = job
                        st.switch_page("pages/3_Interviews.py")
                with ceo_col:
                    if st.button("Move to CEO review", icon="➡️", use_container_width=True):
                        result = safe_api(
                            lambda: post_json(
                                f"/api/v1/applications/{selected_application['id']}/move-to-ceo"
                            ),
                            success="Applicant moved to CEO review",
                        )
                        if result:
                            st.session_state.pop(selected_key, None)
                            st.rerun()
            elif action_filter == "ceo_review":
                if st.button("Open CEO review", type="primary", icon="💼", use_container_width=True):
                    st.session_state[f"executive-applicant-{job_id}"] = selected_application["id"]
                    st.session_state["executive-job"] = f"{job['title']} · {job['status'].title()}"
                    st.session_state["executive-job-data"] = job
                    st.switch_page("pages/4_ceo_review.py")
            else:
                st.caption("Select a pipeline stage to see its next action.")
        with profile_col:
            st.session_state["candidate_detail_return_filter"] = action_filter
            st.session_state["candidate_detail_application"] = selected_application
            if st.button("View applicant profile", icon="👤", use_container_width=True):
                st.switch_page("pages/7_👤_Candidate_Detail.py")

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

