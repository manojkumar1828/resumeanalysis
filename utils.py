# utils.py
from PyPDF2 import PdfReader
import streamlit as st
import json
import re

# We need to import the AI function to use it here
from ai_model import get_gemini_response

# Function to extract text from a PDF file
def get_pdf_text(pdf_file):
    """Extracts text from a single PDF file with improved error handling."""
    try:
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += str(page.extract_text())
        return text
    except Exception as e:
        st.error(f"Error reading PDF file: {e}. Please ensure it is not corrupted or password-protected.")
        return ""

# Function to get skills from the job description
def get_job_description_skills(job_description):
    """Extracts a list of key skills from a job description using the AI."""
    prompt = f"""
    You are a data extraction specialist. Your task is to extract a list of all key technical skills, programming languages, and tools mentioned in the job description.
    
    The output should be a single JSON list of strings. Do not include any other text.
    
    Job Description:
    {job_description}
    """
    try:
        response = get_gemini_response(prompt, "", "")
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            json_string = json_match.group(0)
            return json.loads(json_string)
        return []
    except Exception as e:
        st.error(f"Error extracting skills from job description: {e}")
        return []