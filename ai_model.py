# ai_model.py
import os
import google.generativeai as genai
import streamlit as st

# Configure the Gemini API using Streamlit's secrets
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# Function to get the structured response from Gemini
def get_gemini_response(input_prompt, resume_text, job_description):
    """Generates a structured response from the Gemini API."""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(
            f"""{input_prompt}\n\nResume: {resume_text}\n\nJob Description: {job_description}"""
        )
        return response.text
    except Exception as e:
        st.error(f"Error generating content from Gemini: {e}")
        return ""