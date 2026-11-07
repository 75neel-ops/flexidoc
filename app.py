import os
import streamlit as st
from google import genai
import PyPDF2
import mammoth
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

# Initialize Gemini Client securely using Streamlit Secrets
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

# Sidebar - Branding & Owner Info
with st.sidebar:
    st.title("📄 FlexiDoc AI")
    st.markdown("---")
    st.markdown("### Workspace Options")
    
    # Action Selector
    action_choice = st.radio(
        "Choose Transformation:",
        [
            "Readable / Clean Version",
            "Interactive Quiz & Hints",
            "Summarize & Key Insights",
            "Translate Language",
            "Chess PGN Breakdown"
        ]
    )
    
    target_lang = "English"
    if action_choice == "Translate Language":
        target_lang = st.selectbox("Target Language", ["Bengali (বাংলা)", "English", "Hindi (हिंदी)"])
        
    st.markdown("---")
    # Owner Badge
    st.markdown(
        f"<div style='text-align: center; color: #64748b; font-size: 0.85rem; padding: 10px; background: #f1f5f9; border-radius: 8px;'>"
        f"<b>Owner:</b> NilanjanC<br>Powered by Gemini 3.5 Flash-Lite"
        f"</div>",
        unsafe_allow_html=True
    )

# Main Application Header
st.title("FlexiDoc AI Workspace")
st.markdown("Upload any file (PDF, DOCX, TXT, PGN, etc.) and let AI transform, translate, summarize, or quiz you on its contents.")

# File Uploader
uploaded_file = st.file_uploader(
    "Drop your document or game file here",
    type=["pdf", "docx", "txt", "pgn", "csv"]
)

# Helper function to extract text based on file type
def extract_file_content(uploaded_file):
    file_extension = uploaded_file.name.split(".")[-1].lower()
    text_content = ""
    
    try:
        if file_extension == "pdf":
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_content += text + "\n"
        elif file_extension == "docx":
            result = mammoth.extract_raw_text(uploaded_file)
            text_content = result.value
        elif file_extension in ["txt", "csv"]:
            text_content = uploaded_file.getvalue().decode("utf-8")
        elif file_extension == "pgn":
            game = chess.pgn.read_game(io.StringIO(uploaded_file.getvalue().decode("utf-8")))
            if game:
                text_content = str(game)
            else:
                text_content = uploaded_file.getvalue().decode("utf-8")
        else:
            text_content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    except Exception as e:
        st.error(f"Error parsing file: {e}")
        
    return text_content

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    file_size_kb = len(file_bytes) / 1024
    
    # File Info Preview Box
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.success(f"**File Loaded:** {uploaded_file.name}")
    with col2:
        st.info(f"**Size:** {file_size_kb:.1f} KB")
    with col3:
        if st.button("Clear File"):
            if "quiz_data" in st.session_state:
                del st.session_state["quiz_data"]
            st.rerun()
            
    # Extract text content
    raw_text = extract_file_content(uploaded_file)
    
    if st.button("Generate AI Output", type="primary", use_container_width=True):
        if not client:
            st.error("Gemini API key is missing! Please configure your secrets.toml.")
        elif not raw_text.strip():
            st.warning("The uploaded file appears to be empty or unreadable.")
        else:
            with st.spinner("Processing content with Gemini 3.5 Flash-Lite..."):
                try:
                    # Construct prompt based on chosen action
                    if action_choice == "Interactive Quiz & Hints":
                        prompt = f"""Based on the following text, generate a comprehensive set of multiple-choice questions covering all key sections. 
Return the output STRICTLY as a valid JSON array of objects. Do not include any extra text outside the JSON block.
Each object must have the following keys:
- "question": string
- "options": list of 4 strings (e.g. ["A) ...", "B) ...", "C) ...", "D) ..."])
- "answer": string representing the correct option letter only ("A", "B", "C", or "D")
- "hint": string providing a helpful clue without giving away the direct answer
- "explanation": string explaining why the answer is correct

Text to use:
{raw_text[:20000]}"""
                    else:
                        if action_choice == "Readable / Clean Version":
                            prompt = f"Clean up this text, fix typos, correct broken line breaks, and present a structured, easy-to-read version:\n\n{raw_text[:15000]}"
                        elif action_choice == "Summarize & Key Insights":
                            prompt = f"Provide a comprehensive executive summary, key bullet points, and main takeaways from this text:\n\n{raw_text[:15000]}"
                        elif action_choice == "Translate Language":
                            prompt = f"Translate the following document accurately into {target_lang}:\n\n{raw_text[:15000]}"
                        elif action_choice == "Chess PGN Breakdown":
                            prompt = f"Analyze this chess PGN or game notation. Highlight key turning points, tactical themes, mistakes, and strategic plans in plain language:\n\n{raw_text[:15000]}"

                    response = client.models.generate_content(
                        model='gemini-3.5-flash-lite',
                        contents=prompt,
                    )
                    
                    if action_choice == "Interactive Quiz & Hints":
                        response_text = response.text
                        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
                        if match:
                            json_str = match.group(1)
                        else:
                            json_str = response_text
                        
                        quiz_json = json.loads(json_str)
                        st.session_state["quiz_data"] = quiz_json
                        st.session_state["quiz_submitted"] = False
                    else:
                        st.session_state.pop("quiz_data", None)
                        st.markdown("### 📊 Result Workspace")
                        st.markdown(response.text)
                        
                        st.download_button(
                            label="Download Result as Text",
                            data=response.text,
                            file_name=f"flexidoc_output_{uploaded_file.name}.txt",
                            mime="text/plain"
                        )
                    
                except Exception as e:
                    st.error(f"An error occurred during generation: {e}")

    # Render Interactive Quiz Workspace if quiz data is loaded
    if action_choice == "Interactive Quiz & Hints" and "quiz_data" in st.session_state:
        st.markdown("### 🧠 Interactive Quiz Workspace")
        st.markdown("Test your knowledge! Review the questions, use hints if needed, select your 4 choices, and submit your answers.")
        
        quiz_data = st.session_state["quiz_data"]
        
        with st.form("quiz_form"):
            user_answers = {}
            for idx, q in enumerate(quiz_data):
                st.markdown(f"#### Question {idx + 1}: {q['question']}")
                
                # On-demand Hint Expander
                with st.expander(f"💡 Show Hint for Question {idx + 1}"):
                    st.write(q['hint'])
                
                # 4 choices via radio buttons
                user_choice = st.radio(
                    f"Select your answer for Q{idx + 1}:",
                    q['options'],
                    key=f"q_{idx}"
                )
                user_answers[idx] = user_choice
                st.markdown("---")
            
            submitted = st.form_submit_button("Submit Answers & Check Results", type="primary")
            
        if submitted:
            st.session_state["quiz_submitted"] = True
            st.session_state["user_answers"] = user_answers

        if st.session_state.get("quiz_submitted", False):
            st.markdown("### 📋 Quiz Evaluation & Explanations")
            score = 0
            user_answers = st.session_state.get("user_answers", {})
            
            for idx, q in enumerate(quiz_data):
                selected = user_answers.get(idx, "")
                selected_letter = selected[0].upper() if selected else ""
                correct_letter = q['answer'].strip().upper()
                
                is_correct = (selected_letter == correct_letter)
                if is_correct:
                    score += 1
                
                st.markdown(f"**Question {idx + 1}:** {q['question']}")
                st.markdown(f"Your Answer: `{selected}`")
                
                if is_correct:
                    st.success("✅ Correct!")
                else:
                    st.error(f"❌ Incorrect. The correct answer is **Option {correct_letter}**.")
                
                st.info(f"**Explanation:** {q['explanation']}")
                st.markdown("---")
            
            st.metric(label="Final Score", value=f"{score} / {len(quiz_data)}")
else:
    st.markdown(
        """
        <div style='border: 2px dashed #cbd5e1; border-radius: 12px; padding: 40px; text-align: center; color: #64748b;'>
            <h4>Upload a file using the sidebar or drag-and-drop above to get started.</h4>
        </div>
        """,
        unsafe_allow_html=True
    )
