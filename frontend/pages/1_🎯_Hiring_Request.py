import streamlit as st

from ui import apply_styles, get_json, job_options, patch_json, post_json, safe_api, status_badge

apply_styles()

st.markdown('<div class="eyebrow">Phase 1 · position setup</div>', unsafe_allow_html=True)
st.title("Hiring Request")
st.caption("Shape the role, review the draft, then publish the job-specific application link.")
try:
    jobs = get_json("/api/v1/jobs") or []
except Exception as error:
    jobs = []
    st.error(str(error))

create_col, studio_col = st.columns([1, 1.25])
with create_col:
    st.subheader("New requisition")
    with st.form("create_job"):
        title = st.text_input("Role title", placeholder="Senior Data Engineer")
        stack = st.text_area("Technology stack", placeholder="Python, PostgreSQL, dbt")
        seniority = st.text_input("Seniority", placeholder="Senior")
        min_comp = st.number_input("Minimum compensation", min_value=0, step=5000, value=0)
        max_comp = st.number_input("Maximum compensation", min_value=0, step=5000, value=0)
        submitted = st.form_submit_button("Create requisition", type="primary", use_container_width=True)
    if submitted:
        payload = {"title": title, "tech_stack": stack, "seniority": seniority}
        if min_comp:
            payload["compensation_min"] = min_comp
        if max_comp:
            payload["compensation_max"] = max_comp
        if safe_api(lambda: post_json("/api/v1/jobs", payload), success="Requisition created"):
            st.rerun()

with studio_col:
    st.subheader("Requisition studio")
    options = job_options(jobs)
    if not options:
        st.info("Create your first requisition to begin.")
        st.stop()
    job = options[st.selectbox("Select requisition", list(options))]
    st.markdown(f"{status_badge(job['status'])}  **{job['title']}**", unsafe_allow_html=True)
    tabs = st.tabs(["Criteria", "Job description", "Application link", "LinkedIn post"])
    with tabs[0]:
        st.write(f"**Stack**  {job['tech_stack']}")
        st.write(f"**Seniority**  {job['seniority']}")
        st.write(f"**Compensation**  {job.get('compensation_min') or '—'} – {job.get('compensation_max') or '—'}")
        new_status = st.selectbox("Status", ["draft", "posted", "closed"], index=["draft", "posted", "closed"].index(job["status"]), key=f"status-{job['id']}")
        if st.button("Save status", key=f"save-status-{job['id']}"):
            if safe_api(lambda: patch_json(f"/api/v1/jobs/{job['id']}", {"status": new_status}), success="Status saved"):
                st.rerun()
    with tabs[1]:
        jd = st.text_area("Editable Markdown", value=job.get("jd_markdown") or "", height=330, key=f"jd-{job['id']}")
        a, b = st.columns(2)
        if a.button("Generate with Gemini", key=f"generate-{job['id']}", type="primary"):
            if safe_api(lambda: post_json(f"/api/v1/jobs/{job['id']}/generate-jd"), success="Draft generated"):
                st.rerun()
        if b.button("Save edits", key=f"save-jd-{job['id']}"):
            safe_api(lambda: patch_json(f"/api/v1/jobs/{job['id']}", {"jd_markdown": jd}), success="Job description saved")
    with tabs[2]:
        questions_key = f"form-questions-{job['id']}"
        result_key = f"form-result-{job['id']}"
        if st.button("Create questions with Gemini", key=f"questions-{job['id']}", type="primary"):
            generated = safe_api(lambda: post_json(f"/api/v1/jobs/{job['id']}/generate-form-questions"), success="Questions created")
            if generated:
                st.session_state[questions_key] = generated["questions"]
                st.rerun()

        questions = st.session_state.get(questions_key, [])
        if questions:
            st.markdown("**Review and edit questions**")
            remove_index = None
            reviewed_questions = []
            for index, question in enumerate(questions):
                with st.expander(f"Question {index + 1}", expanded=True):
                    title_value = st.text_input("Question text", value=question["title"], key=f"question-title-{job['id']}-{index}")
                    type_options = ["short_text", "paragraph", "multiple_choice", "checkbox"]
                    type_value = st.selectbox("Answer type", type_options, index=type_options.index(question["question_type"]), key=f"question-type-{job['id']}-{index}")
                    required_value = st.checkbox("Required", value=question.get("required", True), key=f"question-required-{job['id']}-{index}")
                    options_value = []
                    if type_value in {"multiple_choice", "checkbox"}:
                        options_text = st.text_area("Options, one per line", value="\n".join(question.get("options", [])), key=f"question-options-{job['id']}-{index}")
                        options_value = [item.strip() for item in options_text.splitlines() if item.strip()]
                    reviewed_questions.append({"title": title_value, "question_type": type_value, "options": options_value, "required": required_value})
                    if st.button("Remove question", key=f"remove-question-{job['id']}-{index}"):
                        remove_index = index
            if remove_index is not None:
                if len(questions) <= 2:
                    st.warning("A form needs at least two questions.")
                else:
                    st.session_state[questions_key].pop(remove_index)
                    st.rerun()
            if st.button("Add question", key=f"add-question-{job['id']}"):
                st.session_state[questions_key].append({"title": "", "question_type": "short_text", "options": [], "required": True})
                st.rerun()
            if st.button("Create Google Form", key=f"create-form-{job['id']}", type="primary"):
                result = safe_api(lambda: post_json(f"/api/v1/jobs/{job['id']}/clone-form", {"questions": reviewed_questions}), success="Google Form created")
                if result:
                    st.session_state[result_key] = result
                    st.rerun()

        form_result = st.session_state.get(result_key)
        responder_url = (form_result or {}).get("responder_url") or job.get("google_form_url")
        form_id = (form_result or {}).get("form_id") or job.get("google_form_id")
        editor_url = (form_result or {}).get("editor_url") or (f"https://docs.google.com/forms/d/{form_id}/edit" if form_id else None)
        if responder_url:
            st.success("Form ready")
            st.markdown(f'<a href="{responder_url}" target="_blank">Open applicant form ↗</a>', unsafe_allow_html=True)
            if editor_url:
                st.markdown(f'<a href="{editor_url}" target="_blank">Open form editor ↗</a>', unsafe_allow_html=True)
            st.caption(f"Form ID: {form_id or 'not returned'}")
        elif not questions:
            st.info("Create questions to begin.")
    with tabs[3]:
        blurb = st.text_area("Reviewed post copy", value=job.get("linkedin_blurb") or "", height=260, key=f"blurb-{job['id']}")
        a, b = st.columns(2)
        if a.button("Generate post", key=f"blurb-generate-{job['id']}", type="primary"):
            if safe_api(lambda: post_json(f"/api/v1/jobs/{job['id']}/linkedin-blurb"), success="Post draft generated"):
                st.rerun()
        if b.button("Save post edits", key=f"blurb-save-{job['id']}"):
            safe_api(lambda: patch_json(f"/api/v1/jobs/{job['id']}", {"linkedin_blurb": blurb}), success="Post copy saved")
