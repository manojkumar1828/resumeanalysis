import streamlit as st
import pandas as pd
import altair as alt
import json
import re
from supabase import create_client, Client

# --- THIS MUST BE THE FIRST STREAMLIT COMMAND ---
st.set_page_config(layout="wide", page_title="AI Resume Analyzer")

# Import functions from your new utility and AI files
from utils import get_pdf_text, get_job_description_skills
from ai_model import get_gemini_response

# --- Supabase Connection and Session State Initialization ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error connecting to Supabase: {e}. Please check your .streamlit/secrets.toml file.")
        return None

supabase = init_connection()

# Initialize session state
if 'history' not in st.session_state:
    st.session_state.history = []
if 'job_skills' not in st.session_state:
    st.session_state.job_skills = []
if 'user' not in st.session_state:
    st.session_state.user = None
if 'show_login' not in st.session_state:
    st.session_state.show_login = True

# --- Main Page Login & Registration UI ---
def show_login_page():
    st.markdown("<h1 style='text-align: center;'>AI Resume Analyzer</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>Accelerate Your Hiring Process with Data-Driven Insights</h3>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        with st.container(border=True):
            if st.session_state.show_login:
                st.header("Login")
                username = st.text_input("Username", key="login_username")
                password = st.text_input("Password", type="password", key="login_password")
                
                login_button = st.button("Log In", use_container_width=True)

                st.markdown("---")
                if st.button("Not a user? Register here.", key="go_to_register"):
                    st.session_state.show_login = False
                    st.rerun()

                if login_button:
                    if supabase:
                        response = supabase.table('users').select('password_hash').eq('username', username).execute()
                        if response.data and response.data[0]['password_hash'] == password:
                            st.session_state.user = username
                            st.success(f"Welcome back, {username}!")
                            history_response = supabase.table('analysis_history').select('*').eq('username', username).execute()
                            st.session_state.history = history_response.data if history_response.data else []
                            st.rerun()
                        else:
                            st.error("Invalid username or password.")
                    else:
                        st.warning("Could not connect to the database. Please check your credentials.")
            else:
                st.header("Register")
                new_username = st.text_input("New Username", key="register_username")
                new_password = st.text_input("New Password", type="password", key="register_password")
                
                register_button = st.button("Create Account", use_container_width=True)

                st.markdown("---")
                if st.button("Already a user? Log In.", key="go_to_login"):
                    st.session_state.show_login = True
                    st.rerun()

                if register_button:
                    if supabase:
                        try:
                            supabase.table('users').insert({"username": new_username, "password_hash": new_password}).execute()
                            st.success("Registration successful! You can now log in.")
                        except Exception as e:
                            st.error("Username already exists. Please choose another one.")
                    else:
                        st.warning("Could not connect to the database. Please check your credentials.")

# --- Main Application UI (Hidden until login) ---
def show_main_app():
    # --- Sidebar Content ---
    with st.sidebar:
        st.header("Navigation")
        with st.expander("❓ How It Works"):
            st.markdown("1. 📝 Paste the job description.")
            st.markdown("2. 📄 Upload one or more PDF resumes.")
            st.markdown("3. ▶️ Click 'Analyze Resumes' to process candidates.")
            st.markdown("4. 📊 View detailed analysis and use filters to find the best fit.")
            st.write("---")
            st.markdown("### Technology Stack")
            st.info("Powered by Google's Gemini 1.5 Flash API and built with Streamlit.")
            
        st.header("Filters")
        score_range = st.slider(
            "Filter by Overall Score",
            0, 100, (0, 100)
        )
        selected_skills = st.multiselect(
            "Filter by Skills",
            options=st.session_state.job_skills,
            placeholder="Select skills..."
        )

        st.header("Analysis History")
        if st.session_state.user and st.session_state.history:
            if st.button("Clear History"):
                st.session_state.history = []
                st.session_state.job_skills = []
                st.rerun()
            for result in reversed(st.session_state.history):
                with st.expander(f"📚 {result.get('filename')} (Score: {result.get('overall_score', 'N/A')})"):
                    analysis_result = result.get('analysis_result')
                    if isinstance(analysis_result, str):
                        try:
                            analysis_result = json.loads(analysis_result)
                        except json.JSONDecodeError:
                            analysis_result = {}
                    if 'raw_response' in analysis_result:
                        st.warning("Failed to parse this entry.")
                        st.markdown(analysis_result['raw_response'])
                    else:
                        st.markdown(f"**Overall Score:** {analysis_result.get('overall_score', 0)}/100")
                        st.markdown(f"**Explanation:** {analysis_result.get('summary_highlights', 'No explanation provided.')}")
        else:
            st.info("No analysis history yet.")

        st.markdown("---")
        st.write(f"Logged in as **{st.session_state.user}**")
        if st.button("Log Out"):
            st.session_state.user = None
            st.rerun()

    # --- Main Page Content ---
    st.title("AI Resume Analyzer: Candidate Screening Tool 🤖")
    st.markdown("### Accelerate Your Hiring Process with Data-Driven Insights")
    st.write("Upload a job description and resumes to instantly screen candidates and find the perfect match.")
    st.write("---")
    with st.container(border=True):
        job_description = st.text_area("Enter the Job Description", height=250, help="Paste the full job description here.")
        uploaded_files = st.file_uploader("Upload Resumes (PDF)", type=["pdf"], accept_multiple_files=True, help="Select one or more resumes to analyze.")
        if st.button("Analyze Resumes"):
            if uploaded_files and job_description:
                st.session_state.job_skills = get_job_description_skills(job_description)
                with st.spinner("Analyzing resumes..."):
                    for file in uploaded_files:
                        try:
                            if any(r.get('filename') == file.name for r in st.session_state.history):
                                continue
                            resume_text = get_pdf_text(file)
                            if not resume_text:
                                continue
                            prompt = f"""
                            You are an experienced HR Manager. Your task is to compare the provided resume with the job description.
                            You will provide a detailed analysis in a structured JSON format. Your response MUST contain ONLY the JSON object and no other text.
                            The JSON object should have the following keys:
                            - "overall_score": An integer score out of 100 for the resume's suitability.
                            - "strengths": A list of strings detailing the resume's key strengths.
                            - "weaknesses": A list of strings detailing the resume's key weaknesses.
                            - "suggestions": A list of strings with actionable advice for the candidate to improve their resume.
                            - "found_skills": A list of skills from the job description that were found on the resume.
                            - "missing_skills": A list of strings of the top 5 missing skills from the resume that are present in the job description.
                            - "summary_highlights": A concise 3-4 line explanation of the overall score.
                            Here is the Resume: {resume_text}
                            Here is the Job Description: {job_description}
                            """
                            response_text = get_gemini_response(prompt, resume_text, job_description)
                            if response_text:
                                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                                if json_match:
                                    json_string = json_match.group(0)
                                else:
                                    json_string = response_text
                                try:
                                    analysis = json.loads(json_string)
                                    supabase.table('analysis_history').insert({
                                        'username': st.session_state.user,
                                        'filename': file.name,
                                        'job_description': job_description,
                                        'resume_text': resume_text,
                                        'analysis_result': json.dumps(analysis)
                                    }).execute()
                                    st.session_state.history.append({'filename': file.name, 'analysis_result': json.dumps(analysis)})
                                except json.JSONDecodeError:
                                    st.warning(f"Could not parse the JSON response for {file.name}. Displaying raw text.")
                                    raw_analysis = {
                                        'overall_score': 0,
                                        'raw_response': response_text
                                    }
                                    supabase.table('analysis_history').insert({
                                        'username': st.session_state.user,
                                        'filename': file.name,
                                        'job_description': job_description,
                                        'resume_text': resume_text,
                                        'analysis_result': json.dumps(raw_analysis)
                                    }).execute()
                                    st.session_state.history.append({'filename': file.name, 'analysis_result': json.dumps(raw_analysis)})
                        except Exception as e:
                            st.error(f"An error occurred with file {file.name}: {e}. Please ensure it's a readable PDF.")
            else:
                st.warning("Please upload at least one PDF resume and enter a job description.")
    if uploaded_files:
        current_results = []
        for file in uploaded_files:
            found_result = next((item for item in st.session_state.history if item.get('filename') == file.name), None)
            if found_result and isinstance(found_result.get('analysis_result'), str):
                try:
                    analysis_data = json.loads(found_result['analysis_result'])
                    analysis_data['filename'] = found_result['filename']
                    current_results.append(analysis_data)
                except json.JSONDecodeError:
                    st.warning(f"Could not parse JSON for {file.name} from history.")
                    continue
        if current_results:
            filtered_results = [
                res for res in current_results
                if res.get('overall_score', 0) >= score_range[0] and res.get('overall_score', 0) <= score_range[1]
            ]
            if selected_skills:
                filtered_results = [
                    res for res in filtered_results
                    if all(skill in res.get('found_skills', []) for skill in selected_skills)
                ]
            sorted_results = sorted(filtered_results, key=lambda x: x.get('overall_score', 0), reverse=True)
            st.success("Analysis Complete!")
            st.subheader("Analysis Results (Sorted by Score)")
            st.markdown("*(Use the filters in the sidebar to refine your results)*")
            st.write("---")
            if sorted_results:
                st.subheader("Candidate Score Ranking")
                df_scores = pd.DataFrame([
                    {'Candidate': res['filename'], 'Score': res.get('overall_score', 0)} 
                    for res in sorted_results
                ])
                chart = alt.Chart(df_scores).mark_bar().encode(
                    x=alt.X('Score', title='Overall Score'),
                    y=alt.Y('Candidate', sort='-x', title='Candidate'),
                    tooltip=['Candidate', 'Score']
                ).properties(
                    width=600
                )
                st.altair_chart(chart, use_container_width=True)
            for result in sorted_results:
                with st.container(border=True):
                    st.header(result['filename'])
                    col_score, col_details = st.columns([1, 2])
                    with col_score:
                        st.markdown(f"**Overall Score:**")
                        st.progress(result.get('overall_score', 0) / 100)
                        st.subheader(f"{result.get('overall_score', 0)}/100")
                        st.markdown("---")
                        st.markdown(f"**Highlights:** {result.get('summary_highlights', 'No highlights provided.')}")
                    with col_details:
                        with st.expander("Click for Detailed Analysis"):
                            if 'raw_response' in result:
                                st.warning("Could not parse JSON. Displaying raw output:")
                                st.markdown(result['raw_response'])
                            else:
                                st.markdown("### Strengths")
                                st.info("Here's where the candidate shines:")
                                for item in result.get('strengths', []):
                                    st.markdown(f"- **{item}**")
                                st.markdown("### Weaknesses")
                                st.warning("Gaps and areas for improvement:")
                                for item in result.get('weaknesses', []):
                                    st.markdown(f"- **{item}**")
                                st.markdown("### Missing Key Skills")
                                st.error("Crucial skills not found on the resume:")
                                if result.get('missing_skills'):
                                    df_skills = {'Missing Skills': result['missing_skills']}
                                    st.dataframe(df_skills, use_container_width=True)
                                else:
                                    st.info("No key skills were identified as missing.")
                                st.markdown("### Found Skills")
                                st.success("Skills found that match the job description:")
                                if result.get('found_skills'):
                                    found_skills_text = ", ".join(result['found_skills'])
                                    st.markdown(found_skills_text)
                                else:
                                    st.info("No matching skills were found.")
                                st.markdown("---")
                                st.markdown("### Suggestions for Improvement")
                                st.markdown("Actionable steps to improve this resume:")
                                for item in result.get('suggestions', []):
                                    st.markdown(f"- **{item}**")
            if len(sorted_results) >= 2:
                st.write("---")
                st.subheader("Candidate Comparison: Top 2 Candidates")
                col1, col2 = st.columns(2)
                candidate1 = sorted_results[0]
                candidate2 = sorted_results[1]
                with col1:
                    st.markdown(f"**{candidate1['filename']}**")
                    st.progress(candidate1.get('overall_score', 0) / 100)
                    st.markdown(f"**Score:** {candidate1.get('overall_score', 0)}/100")
                    st.info("Highlights:")
                    for item in candidate1.get('summary_highlights', []):
                        st.markdown(f"- {item}")
                with col2:
                    st.markdown(f"**{candidate2['filename']}**")
                    st.progress(candidate2.get('overall_score', 0) / 100)
                    st.markdown(f"**Score:** {candidate2.get('overall_score', 0)}/100")
                    st.info("Highlights:")
                    for item in candidate2.get('summary_highlights', []):
                        st.markdown(f"- {item}")

# --- Main app flow control ---
if st.session_state.user is None:
    show_login_page()
else:
    show_main_app()