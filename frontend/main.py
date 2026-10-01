import streamlit as st

from ui import get_json, setup_page, status_badge


setup_page("Command Center")


def command_center() -> None:
    st.markdown('<div class="eyebrow">Recruitment operations</div>', unsafe_allow_html=True)
    st.markdown("<div class='hero'><h1>Make the next great hire feel inevitable.</h1><p>A calm, evidence-led workspace for job setup, applicant decisions, interviews, and the final call.</p></div>", unsafe_allow_html=True)
    try:
        jobs = get_json("/api/v1/jobs") or []
    except Exception as error:
        jobs = []
        st.error(str(error))

    applications = []
    for job in jobs:
        try:
            applications.extend(get_json(f"/api/v1/jobs/{job['id']}/applications") or [])
        except Exception:
            continue

    active = sum(item.get("pipeline_status") == "active_pipeline" for item in applications)
    ceo = sum(item.get("pipeline_status") == "pending_ceo_decision" for item in applications)
    cols = st.columns(4)
    for col, value, label in zip(cols, [len(jobs), len(applications), active, ceo], ["Open requisitions", "Applications", "Active pipeline", "CEO decisions"]):
        with col:
            st.markdown(f'<div class="metric"><div class="metric-value">{value}</div><div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="eyebrow">Live pulse</div>', unsafe_allow_html=True)
    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Your requisitions")
        if not jobs:
            st.info("No requisitions yet. Open the Hiring Request page to create one.")
        for job in jobs[:8]:
            metadata = [job.get("seniority"), job.get("tech_stack")]
            metadata.extend(
                value
                for value in [job.get("location"), job.get("work_type"), job.get("salary")]
                if value
            )
            metadata.append(status_badge(job["status"]))
            details = " · ".join(value for value in metadata if value)
            st.markdown(f'<div class="record"><div class="record-title">{job["title"]}</div><div class="record-meta">{details}</div></div>', unsafe_allow_html=True)
    with right:
        st.subheader("Pipeline signals")
        st.metric("Waiting on CEO", ceo)
        st.caption("Screening failures stay out of the active pipeline until HR restores them.")


pages = {
    "Command center": st.Page(command_center, title="Command center", icon="📊", url_path="command-center"),
    "Jobs Dashboard": st.Page("pages/0_🏢_Jobs_Dashboard.py", title="Jobs Dashboard", icon="🏢"),
    "Hiring Request": st.Page("pages/1_🎯_Hiring_Request.py", title="Hiring Request", icon="🎯"),
    "Sync & Screen": st.Page("pages/2_🔄_Sync_&_Screen.py", title="Sync & Screen", icon="🔄"),
    "Interviews": st.Page("pages/3_🎙️_Interviews.py", title="Interviews", icon="🎙️"),
    "Executive Review": st.Page("pages/4_💼_Executive.py", title="Executive Review", icon="💼"),
}

st.navigation(list(pages.values())).run()
