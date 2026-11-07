import os
import streamlit as st
from google import genai
from google.genai import types
import chess.pgn
import io
import json
import re

# Page Configuration
st.set_page_config(
    page_title="FlexiDoc AI - Smart Workspace",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Gemini Client
api_key = None
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
elif os.environ.get("GEMINI_API_KEY"):
    api_key = os.environ.get("GEMINI_API_KEY")

client = None
if api_key:
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"Failed to initialize Gemini Client: {e}")

# Sidebar
with st.sidebar:
    st.title("📄 FlexiDoc AI")
    st.markdown("---")
    st.markdown("### Workspace Options")
    
    action_choice = st.radio(
        "Choose Transformation:",
        [
            "Interactive Quiz & Hints",
            "Readable / Clean Version",
            "Summarize & Key Insights",
            "Translate Language",
            "Chess PGN Breakdown"
        ]
    )
    
    target_lang = "English"
    batch_size = 10
    if action_choice == "Translate Language":
        target_lang = st.selectbox("Target Language", ["Bengali (বাংলা)", "English", "Hindi (हिंदी)"])
    elif action_choice == "Interactive Quiz & Hints":
        batch_size = st.slider("Questions per batch:", min_value=5, max_value=25, value=10, step=5)
        st.caption("Extracts exact questions directly from your PDF/document.")
        
    st.markdown("---")
    st.markdown(
        f"<div style='text-align: center; color: #64748b; font-size: 0.85rem; padding: 10px; background: #f1f5f9; border-radius: 8px;'>"
        f"<b>Owner:</b> NilanjanC<br>Powered by Gemini 3.5 Flash-Lite"
        f"</div>",
        unsafe_allow_html=True
    )

st.title("FlexiDoc AI Workspace")
st.markdown("Upload any PDF, DOCX, TXT, or PGN file to extract questions, summarize, translate, or clean up content.")

uploaded_file = st.file_uploader(
    "Drop your document or game file here",
    type=["pdf", "docx", "txt", "pgn", "csv"]
)

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    file_size_kb = len(file_bytes) / 1024
    
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.success(f"**File Loaded:** {uploaded_file.name}")
    with col2:
        st.info(f"**Size:** {file_size_kb:.1f} KB")
    with col3:
        if st.button("Clear File"):
            for key in ["quiz_data", "quiz_submitted", "asked_questions", "user_answers"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
            
    if "asked_questions" not in st.session_state:
        st.session_state["asked_questions"] = []

    def generate_quiz_batch():
        if not client:
            st.error("Gemini API key is missing!")
            return
        
        with st.spinner(f"Reading PDF and extracting exact questions using Gemini native vision..."):
            try:
                excluded_list = "\n".join([f"- {q}" for q in st.session_state["asked_questions"][-50:]])
                
                prompt = f"""You are an expert exam parser. Read the attached document carefully.
EXTRACT the EXACT next {batch_size} consecutive questions directly from the document as they appear.

CRITICAL RULES:
1. Do NOT invent new questions. Extract the real questions from the file (e.g. Physics Q1, Q2, etc.).
2. Do NOT re-extract any of these previously extracted question titles:
{excluded_list if excluded_list else "None yet."}
3. Preserve the exact question text and choices (Option 1, 2, 3, 4 or A, B, C, D).
4. For each question, solve it to determine the correct answer letter, provide a helpful hint, and write a step-by-step explanation.

Return the output STRICTLY as a valid JSON array of objects with no markdown outside:
[
  {{
    "question": "Exact question text from PDF",
    "options": ["(1) ...", "(2) ...", "(3) ...", "(4) ..."],
    "answer": "1",  // or "A", matching the correct option
    "hint": "Clue to solve it",
    "explanation": "Detailed step by step solution"
  }}
]"""

                # Pass raw PDF bytes directly to Gemini so it reads images/scanned tables
                mime_type = "application/pdf" if uploaded_file.name.endswith(".pdf") else "text/plain"
                
                if uploaded_file.name.endswith(".pdf"):
                    contents = [
                        types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"),
                        prompt
                    ]
                else:
                    contents = [file_bytes.decode("utf-8", errors="ignore"), prompt]

                response = client.models.generate_content(
                    model='gemini-3.5-flash-lite',
                    contents=contents,
                )
                
                response_text = response.text
                match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
                json_str = match.group(1) if match else response_text
                
                quiz_json = json.loads(json_str)
                
                for q in quiz_json:
                    st.session_state["asked_questions"].append(q["question"])

                st.session_state["quiz_data"] = quiz_json
                st.session_state["quiz_submitted"] = False
                st.session_state["user_answers"] = {}
            except Exception as e:
                st.error(f"Error parsing PDF questions: {e}")

    if action_choice != "Interactive Quiz & Hints":
        if st.button("Generate AI Output", type="primary", use_container_width=True):
            if not client:
                st.error("Gemini API key is missing!")
            else:
                with st.spinner("Processing content..."):
                    try:
                        mime_type = "application/pdf" if uploaded_file.name.endswith(".pdf") else "text/plain"
                        if action_choice == "Readable / Clean Version":
                            prompt = "Clean up and format the text in this file into a clean readable version."
                        elif action_choice == "Summarize & Key Insights":
                            prompt = "Provide a comprehensive summary and key takeaways from this document."
                        elif action_choice == "Translate Language":
                            prompt = f"Translate the contents of this document into {target_lang}."
                        elif action_choice == "Chess PGN Breakdown":
                            prompt = "Analyze this chess PGN notation, highlighting tactics and key moves."

                        if uploaded_file.name.endswith(".pdf"):
                            contents = [types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"), prompt]
                        else:
                            contents = [file_bytes.decode("utf-8", errors="ignore"), prompt]

                        response = client.models.generate_content(
                            model='gemini-3.5-flash-lite',
                            contents=contents,
                        )
                        st.markdown("### 📊 Result Workspace")
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        if "quiz_data" not in st.session_state:
            if st.button("Extract & Start Quiz from PDF", type="primary", use_container_width=True):
                generate_quiz_batch()
                st.rerun()
        
        if "quiz_data" in st.session_state:
            quiz_data = st.session_state["quiz_data"]
            st.markdown(f"### 🧠 Extracted Exam Questions (Batch Size: {len(quiz_data)})")
            
            with st.form("quiz_form"):
                user_answers = {}
                for idx, q in enumerate(quiz_data):
                    st.markdown(f"#### Question {idx + 1}: {q['question']}")
                    
                    with st.expander(f"💡 Show Hint for Question {idx + 1}"):
                        st.write(q['hint'])
                    
                    user_choice = st.radio(
                        f"Select your answer for Q{idx + 1}:",
                        q['options'],
                        key=f"q_{idx}_{len(st.session_state['asked_questions'])}_{idx}"
                    )
                    user_answers[idx] = user_choice
                    st.markdown("---")
                
                submitted = st.form_submit_button("Submit Answers & Check Results", type="primary")
                
            if submitted:
                st.session_state["quiz_submitted"] = True
                st.session_state["user_answers"] = user_answers

            if st.session_state.get("quiz_submitted", False):
                st.markdown("### 📋 Quiz Evaluation & Solutions")
                score = 0
                user_answers = st.session_state.get("user_answers", {})
                
                for idx, q in enumerate(quiz_data):
                    selected = user_answers.get(idx, "")
                    correct_ans = str(q['answer']).strip()
                    
                    is_correct = correct_ans in selected
                    if is_correct:
                        score += 1
                    
                    st.markdown(f"**Question {idx + 1}:** {q['question']}")
                    st.markdown(f"Your Answer: `{selected}`")
                    
                    if is_correct:
                        st.success("✅ Correct!")
                    else:
                        st.error(f"❌ Incorrect. The correct choice is **{correct_ans}**.")
                    
                    st.info(f"**Step-by-Step Explanation:** {q['explanation']}")
                    st.markdown("---")
                
                st.metric(label="Final Score", value=f"{score} / {len(quiz_data)}")
                
                st.markdown("---")
                if st.button("➡️ Load Next Batch of Questions", type="primary"):
                    generate_quiz_batch()
                    st.rerun()
else:
    st.markdown(
        """
        <div style='border: 2px dashed #cbd5e1; border-radius: 12px; padding: 40px; text-align: center; color: #64748b;'>
            <h4>Upload a file using the sidebar or drag-and-drop above to get started.</h4>
        </div>
        """,
        unsafe_allow_html=True
    )
