import streamlit as st

from ui import apply_styles, fmt_status, get_json, job_options, post_json, safe_api, status_badge

apply_styles()


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
    jobs = get_json("/api/v1/jobs") or []
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
            st.success(
                f"Checked {result['total_responses']} responses: "
                f"{result['synced']} synced, {result['skipped_duplicates']} duplicates, "
                f"{result['errors']} errors."
            )
            if result.get("items"):
                st.dataframe(
                    [
                        {
                            "Applicant": item.get("candidate_name") or "Unknown applicant",
                            "Email": item.get("email") or "",
                            "Result": fmt_status(item.get("agent_decision")),
                            "Sync": fmt_status(item.get("status")),
                            "Details": item.get("detail") or item.get("screening_summary") or "",
                        }
                        for item in result["items"]
                    ],
                    hide_index=True,
                    use_container_width=True,
                )

with filter_col:
    st.subheader("Applicant results")
    selected_filter = st.segmented_control(
        "Screening outcome",
        options=["All", "Pass", "Fail"],
        default="All",
        key=f"screening-filter-{job['id']}",
    )
    search = st.text_input("Search applicants", placeholder="Name, email, or application ID")

applications = safe_api(lambda: get_json(f"/api/v1/jobs/{job['id']}/applications")) or []
if selected_filter == "Pass":
    applications = [item for item in applications if item.get("agent_decision") == "pass"]
elif selected_filter == "Fail":
    applications = [item for item in applications if item.get("agent_decision") == "fail"]
if search.strip():
    needle = search.strip().casefold()
    applications = [
        item
        for item in applications
        if needle in " ".join(
            [
                item.get("candidate_name", ""),
                item.get("email", ""),
                item.get("id", ""),
            ]
        ).casefold()
    ]

if not applications:
    st.info("No applicants match this view.")
    st.stop()

table_rows = [
    {
        "Applicant": item.get("candidate_name", "Unknown applicant"),
        "Email": item.get("email", ""),
        "Phone": applicant_phone(item),
        "Screening": fmt_status(item.get("agent_decision")),
        "Pipeline": fmt_status(item.get("pipeline_status")),
        "Summary": item.get("screening_summary") or "No screening summary",
    }
    for item in applications
]
table_event = st.dataframe(
    table_rows,
    hide_index=True,
    use_container_width=True,
    on_select="rerun",
    selection_mode="single-row",
)
selected_rows = table_event.selection.rows
selected_application = applications[selected_rows[0]] if selected_rows else None

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
        lambda: get_json(
            f"/api/v1/candidates/{selected_application['candidate_id']}/history"
        )
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
                st.rerun()
