import streamlit as st

from ui import apply_styles, fmt_status, get_json, job_options, post_json, safe_api, status_badge

APPLICANTS_PER_PAGE = 20

apply_styles()


@st.cache_data(ttl=30, show_spinner=False)
def load_jobs():
    return get_json("/api/v1/jobs") or []


@st.cache_data(ttl=15, show_spinner=False)
def load_applicant_page(
    job_id: str,
    selected_filter: str,
    history_filter: str,
    search: str,
    offset: int,
):
    params = {
        "agent_decision": {"Pass": "pass", "Fail": "fail"}.get(selected_filter),
        "has_other_applications": {
            "Has applications for other jobs": True,
            "No applications for other jobs": False,
        }.get(history_filter),
        "search": search or None,
        "offset": offset,
        "limit": APPLICANTS_PER_PAGE,
    }
    return get_json(
        f"/api/v1/jobs/{job_id}/applicants",
        params={key: value for key, value in params.items() if value is not None},
    )


@st.cache_data(ttl=30, show_spinner=False)
def load_candidate_history(candidate_id: str):
    return get_json(f"/api/v1/candidates/{candidate_id}/history") or []


def applicant_phone(application):
    phone = application.get("phone")
    if phone:
        return phone
    for question, answer in (application.get("form_responses") or {}).items():
        normalized_question = question.casefold()
        if any(label in normalized_question for label in ("phone", "mobile", "contact number")):
            return answer
    return ""


st.markdown('<div class="eyebrow">Phase 2 · sync and screening</div>', unsafe_allow_html=True)
st.title("Sync & Screen")
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

sync_col, filter_col = st.columns([1, 2])
with sync_col:
    st.subheader("Form sync")
    st.caption("Fetch new submissions, screen each résumé and answer set, and skip responses already processed.")
    if st.button("Sync all applicants", type="primary", use_container_width=True):
        result = safe_api(lambda: post_json(f"/api/v1/jobs/{job['id']}/sync"))
        if result is not None:
            load_applicant_page.clear()
            st.success(
                f"Checked {result['total_responses']} responses: "
                f"{result['synced']} synced, {result['skipped_duplicates']} duplicates, "
                f"{result['errors']} errors."
            )
            new_applications = [
                item for item in result.get("items", [])
                if item.get("status") == "synced"
            ]
            if new_applications:
                st.dataframe(
                    [
                        {
                            "Applicant": item.get("candidate_name") or "Unknown applicant",
                            "Email": item.get("email") or "",
                            "Screening": fmt_status(item.get("agent_decision")),
                            "Summary": item.get("screening_summary") or "",
                        }
                        for item in new_applications
                    ],
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info("No new applications were added in this sync.")

with filter_col:
    st.subheader("Applicant results")
    selected_filter = st.segmented_control(
        "Screening outcome",
        options=["All", "Pass", "Fail"],
        default="All",
        key=f"screening-filter-{job['id']}",
    )
    history_filter = st.selectbox(
        "Other job applications",
        options=[
            "All applicants",
            "Has applications for other jobs",
            "No applications for other jobs",
        ],
        key=f"application-history-filter-{job['id']}",
    )
    search = st.text_input(
        "Search applicants",
        placeholder="Name, email, or application ID",
        max_chars=200,
    )

page_state_key = f"applicant-page-{job['id']}"
query_signature = (selected_filter, history_filter, search.strip())
signature_key = f"applicant-query-{job['id']}"
if st.session_state.get(signature_key) != query_signature:
    st.session_state[signature_key] = query_signature
    st.session_state[page_state_key] = 0
page_index = max(st.session_state.get(page_state_key, 0), 0)
st.session_state[page_state_key] = page_index
page_result = safe_api(
    lambda: load_applicant_page(
        str(job["id"]),
        selected_filter,
        history_filter,
        search.strip(),
        page_index * APPLICANTS_PER_PAGE,
    )
) or {}
applications = page_result.get("items", [])
total_count = page_result.get("total_count", 0)
if total_count == 0:
    st.info("No applicants match this view.")
    st.stop()

page_count = (total_count + APPLICANTS_PER_PAGE - 1) // APPLICANTS_PER_PAGE
if page_index >= page_count:
    st.session_state[page_state_key] = page_count - 1
    st.rerun()

previous_col, page_info_col, next_col = st.columns([1, 2, 1])
with previous_col:
    if st.button(
        "Previous",
        disabled=page_index == 0,
        key=f"applicants-previous-{job['id']}",
        use_container_width=True,
    ):
        st.session_state[page_state_key] = page_index - 1
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
        key=f"applicants-next-{job['id']}",
        use_container_width=True,
    ):
        st.session_state[page_state_key] = page_index + 1
        st.rerun()

page_applications = applications
table_rows = [
    {
        "Applicant": item.get("candidate_name", "Unknown applicant"),
        "Email": item.get("email", ""),
        "Phone": applicant_phone(item),
        "Screening": fmt_status(item.get("agent_decision")),
        "Pipeline": fmt_status(item.get("pipeline_status")),
        "Other jobs": "Yes" if item.get("has_other_applications") else "No",
        "Summary": item.get("screening_summary") or "No screening summary",
    }
    for item in page_applications
]
table_event = st.dataframe(
    table_rows,
    hide_index=True,
    use_container_width=True,
    on_select="rerun",
    selection_mode="single-row",
    key=f"applicant-table-{job['id']}-{page_index}-{selected_filter}-{history_filter}-{search.strip()}",
)
selected_rows = table_event.selection.rows
selected_application = page_applications[selected_rows[0]] if selected_rows else None

if selected_application:
    st.divider()
    st.subheader(selected_application.get("candidate_name", "Applicant details"))
    st.caption(selected_application.get("email", ""))
    st.markdown(f"**Screening:** {fmt_status(selected_application.get('agent_decision'))}")
    st.write(selected_application.get("screening_summary") or "No screening explanation saved.")
    if selected_application.get("form_responses"):
        st.markdown("**Application answers**")
        for question, answer in selected_application["form_responses"].items():
            with st.container(border=True):
                st.markdown(f"**{question}**")
                st.write(answer)

    history = safe_api(
        lambda: load_candidate_history(str(selected_application["candidate_id"]))
    ) or []
    previous_applications = [
        item for item in history
        if item["application_id"] != selected_application["id"]
    ]
    if previous_applications:
        st.markdown("**Previous applications**")
        st.dataframe(
            [
                {
                    "Job": item["job_title"],
                    "Stage": fmt_status(item["current_stage"]),
                    "Status": fmt_status(item["pipeline_status"]),
                    "Decision": fmt_status(item["final_decision"]),
                    "Screening summary": item.get("screening_summary") or "",
                    "Remarks": item.get("remarks") or "",
                }
                for item in previous_applications
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.caption("No previous applications for this candidate.")

    if selected_application.get("pipeline_status") == "failed_at_sync":
        username = st.text_input("HR username", key=f"override-user-{selected_application['id']}")
        if st.button("Restore to active pipeline", type="primary"):
            if safe_api(
                lambda: post_json(
                    f"/api/v1/applications/{selected_application['id']}/hr-override",
                    {"hr_username": username},
                ),
                success="Application restored",
            ):
                load_applicant_page.clear()
                load_candidate_history.clear()
                st.rerun()
