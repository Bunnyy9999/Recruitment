import streamlit as st

from ui import apply_styles, fmt_status, get_json, status_badge


apply_styles()
if st.button("Back to applicants", icon="📋"):
    return_filter = st.session_state.pop("candidate_detail_return_filter", None)
    if return_filter:
        st.session_state["dashboard_applicant_filter"] = return_filter
    st.switch_page("pages/6_📋_Dashboard_Job_Applicants.py")

application = st.session_state.get("candidate_detail_application")
if not application:
    st.info("Select an applicant from the job applicant list first.")
    st.stop()

if application.get("id"):
    try:
        dossier = get_json(f"/api/v1/applications/{application['id']}/dossier") or {}
        application = {**application, **(dossier.get("application") or {})}
    except Exception as error:
        st.warning(f"Full application details are unavailable: {error}")

candidate_name = application.get("candidate_name") or "Applicant details"
st.markdown('<div class="eyebrow">Candidate profile</div>', unsafe_allow_html=True)
st.title(candidate_name)
st.caption(application.get("email") or "No email recorded")

status_col, decision_col, stage_col = st.columns(3)
with status_col:
    st.caption("Pipeline")
    st.markdown(status_badge(application.get("pipeline_status")), unsafe_allow_html=True)
with decision_col:
    st.caption("Final decision")
    st.write(fmt_status(application.get("final_decision")))
with stage_col:
    st.caption("Current stage")
    st.write(fmt_status(application.get("current_stage")))

contact_col, phone_col, examiner_col = st.columns(3)
with contact_col:
    st.caption("Email")
    st.write(application.get("email") or "Not recorded")
with phone_col:
    st.caption("Phone")
    st.write(application.get("phone") or "Not recorded")
with examiner_col:
    st.caption("Examiner")
    st.write(application.get("examiner") or "Not recorded")

st.divider()
st.markdown("**Screening**")
st.markdown(f"**Decision:** {fmt_status(application.get('agent_decision'))}")
st.write(application.get("screening_summary") or "No screening summary recorded.")

if application.get("remarks"):
    st.markdown("**Remarks**")
    st.write(application["remarks"])

form_responses = application.get("form_responses") or {}
if form_responses:
    st.markdown("**Application responses**")
    for question, answer in form_responses.items():
        with st.expander(question):
            st.write(answer or "Answer not provided")
else:
    st.caption("No application responses were saved.")
