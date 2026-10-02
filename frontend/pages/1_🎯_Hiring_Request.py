import streamlit as st

from ui import apply_styles, get_json, job_options, patch_json, post_json, safe_api, status_badge


@st.cache_data(ttl=30, show_spinner=False)
def load_jobs():
    return get_json("/api/v1/jobs") or []


apply_styles()

st.markdown('<div class="eyebrow">Phase 1 · position setup</div>', unsafe_allow_html=True)
st.title("Hiring Request")
st.caption("Shape the role, review the draft, then publish the job-specific application link.")
try:
    jobs = load_jobs()
except Exception as error:
    jobs = []
    st.error(str(error))

create_col, studio_col = st.columns([1, 1.25])
with create_col:
    st.subheader("New requisition")
    st.caption(":red[*] Required")
    with st.form("create_job"):
        title = st.text_input("Role title :red[*]", placeholder="Senior Data Engineer")
        stack = st.text_area("Technology stack :red[*]", placeholder="Python, PostgreSQL, dbt")
        seniority = st.text_input("Seniority :red[*]", placeholder="Senior")
        required_experience = st.text_input("Required experience :red[*]", placeholder="5+ years building production data systems")
        salary = st.text_input("Salary (optional)", placeholder="$120,000-$160,000 or competitive")
        location = st.text_input("Location (optional)", placeholder="New York, NY")
        work_type = st.text_input("Work type (optional)", placeholder="Remote, hybrid, or on-site")
        university = st.text_input("University (optional)", placeholder="Preferred universities, if applicable")
        submitted = st.form_submit_button("Create requisition", type="primary", use_container_width=True)
    if submitted:
        payload = {
            "title": title,
            "tech_stack": stack,
            "seniority": seniority,
            "required_experience": required_experience,
            "salary": salary or None,
            "location": location or None,
            "work_type": work_type or None,
            "university": university or None,
        }
        if safe_api(lambda: post_json("/api/v1/jobs", payload), success="Requisition created"):
            load_jobs.clear()
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
        st.write(f"**Required experience**  {job['required_experience']}")
        st.write(f"**Salary**  {job.get('salary') or '—'}")
        st.write(f"**Location**  {job.get('location') or '—'}")
        st.write(f"**Work type**  {job.get('work_type') or '—'}")
        st.write(f"**University**  {job.get('university') or '—'}")
        new_status = st.selectbox("Status", ["draft", "posted", "closed"], index=["draft", "posted", "closed"].index(job["status"]), key=f"status-{job['id']}")
        if st.button("Save status", key=f"save-status-{job['id']}"):
            if safe_api(lambda: patch_json(f"/api/v1/jobs/{job['id']}", {"status": new_status}), success="Status saved"):
                load_jobs.clear()
                st.rerun()
    with tabs[1]:
        jd_key = f"jd-{job['id']}"
        pending_jd_key = f"pending-jd-{job['id']}"
        if pending_jd_key in st.session_state:
            st.session_state[jd_key] = st.session_state.pop(pending_jd_key)
        elif jd_key not in st.session_state:
            st.session_state[jd_key] = job.get("jd_markdown") or ""
        jd = st.text_area("Editable Markdown", key=jd_key, height=330)
        a, b = st.columns(2)
        if a.button("Generate with Gemini", key=f"generate-{job['id']}", type="primary"):
            generated_job = safe_api(lambda: post_json(f"/api/v1/jobs/{job['id']}/generate-jd"), success="Draft generated")
            if generated_job:
                load_jobs.clear()
                st.session_state[pending_jd_key] = generated_job["jd_markdown"]
                st.rerun()
        if b.button("Save edits", key=f"save-jd-{job['id']}"):
            if safe_api(lambda: patch_json(f"/api/v1/jobs/{job['id']}", {"jd_markdown": jd}), success="Job description saved"):
                load_jobs.clear()
    with tabs[2]:
        questions_key = f"form-questions-{job['id']}"
        result_key = f"form-result-{job['id']}"
        if st.button("Create questions with Gemini", key=f"questions-{job['id']}", type="primary"):
            generated = safe_api(lambda: post_json(f"/api/v1/jobs/{job['id']}/generate-form-questions"), success="Questions created")
            if generated:
                st.session_state[questions_key] = generated["questions"]
                for index, question in enumerate(generated["questions"]):
                    st.session_state[f"question-title-{job['id']}-{index}"] = question["title"]
                    st.session_state[f"question-type-{job['id']}-{index}"] = question["question_type"]
                    st.session_state[f"question-required-{job['id']}-{index}"] = question.get("required", True)
                    st.session_state[f"question-options-{job['id']}-{index}"] = "\n".join(question.get("options", []))
                st.rerun()

        questions = st.session_state.get(questions_key, [])
        if questions:
            st.markdown("**Review and edit questions**")
            remove_index = None
            reviewed_questions = []
            for index, question in enumerate(questions):
                with st.expander(f"Question {index + 1}", expanded=True):
                    title_key = f"question-title-{job['id']}-{index}"
                    type_key = f"question-type-{job['id']}-{index}"
                    required_key = f"question-required-{job['id']}-{index}"
                    options_key = f"question-options-{job['id']}-{index}"
                    st.session_state.setdefault(title_key, question["title"])
                    st.session_state.setdefault(type_key, question["question_type"])
                    st.session_state.setdefault(required_key, question.get("required", True))
                    st.session_state.setdefault(options_key, "\n".join(question.get("options", [])))

                    title_value = st.text_input("Question text", key=title_key)
                    type_options = ["short_text", "paragraph", "multiple_choice", "checkbox"]
                    type_value = st.selectbox("Answer type", type_options, key=type_key)
                    required_value = st.checkbox("Required", key=required_key)
                    options_value = []
                    if type_value in {"multiple_choice", "checkbox"}:
                        options_text = st.text_area("Options, one per line", key=options_key)
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
                    load_jobs.clear()
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
        blurb_key = f"blurb-{job['id']}"
        pending_blurb_key = f"pending-blurb-{job['id']}"
        if pending_blurb_key in st.session_state:
            st.session_state[blurb_key] = st.session_state.pop(pending_blurb_key)
        elif blurb_key not in st.session_state:
            st.session_state[blurb_key] = job.get("linkedin_blurb") or ""
        blurb = st.text_area("Reviewed post copy", key=blurb_key, height=260)
        a, b = st.columns(2)
        if a.button("Generate post", key=f"blurb-generate-{job['id']}", type="primary"):
            generated_job = safe_api(lambda: post_json(f"/api/v1/jobs/{job['id']}/linkedin-blurb"), success="Post draft generated")
            if generated_job:
                load_jobs.clear()
                st.session_state[pending_blurb_key] = generated_job["linkedin_blurb"]
                st.rerun()
        if b.button("Save post edits", key=f"blurb-save-{job['id']}"):
            if safe_api(lambda: patch_json(f"/api/v1/jobs/{job['id']}", {"linkedin_blurb": blurb}), success="Post copy saved"):
                load_jobs.clear()
