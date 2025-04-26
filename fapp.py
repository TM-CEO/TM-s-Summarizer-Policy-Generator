from flask import Flask, render_template, request, jsonify
import os
import pdfplumber
import docx
import json
from PIL import Image
import pytesseract
from werkzeug.utils import secure_filename
import openai  # OpenAI API instead of Google Gemini
import time

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure OpenAI API
OPENAI_API_KEY = "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"  # Replace with your OpenAI API key
openai.api_key = OPENAI_API_KEY

# Basic fallback summarization function
def basic_summarize(text, max_length=1000):
    """Provide a basic summarization when API fails"""
    # Simple extractive summarization - first few paragraphs
    paragraphs = text.split('\n\n')
    intro = ' '.join(paragraphs[:3])
    
    # Add a basic overview of document structure
    structure = f"\n\nDocument contains {len(paragraphs)} paragraphs, approximately {len(text.split())} words."
    
    # Add a note about API limitation
    note = "\n\nNote: This is a basic summary created without AI due to API limitations. For better results, try again later."
    
    return intro[:max_length] + structure + note

def extract_text_from_file(filepath, filetype):
    """Extracts text from different file formats"""
    text = ""
    try:
        if filetype == 'pdf':
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
        elif filetype == 'docx':
            doc = docx.Document(filepath)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif filetype == 'json':
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                text = json.dumps(data, indent=2)
        elif filetype in ['png', 'jpg', 'jpeg']:
            image = Image.open(filepath)
            text = pytesseract.image_to_string(image)
        else:  # Plain text
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
    except Exception as e:
        return str(e)
    return text

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/summarize', methods=['POST'])
def summarize():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    text = extract_text_from_file(file_path, file_ext)
    
    if not text.strip():
        return jsonify({"error": "Could not extract text from the document"}), 400
    
    try:
        # Limit text length to avoid API limits
        max_tokens = 4000  # OpenAI has token limits
        if len(text.split()) > max_tokens:
            limited_text = ' '.join(text.split()[:max_tokens])
            text_limit_warning = "Document was truncated due to length."
        else:
            limited_text = text
            text_limit_warning = None
            
        # Attempt to use OpenAI API with retry
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",  # Can switch to "gpt-4" for more advanced capabilities
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that summarizes documents accurately and thoroughly."},
                        {"role": "user", "content": f"Provide a detailed summary (at least 300 words) of the following document:\n{limited_text}"}
                    ],
                    max_tokens=1000
                )
                summary = response.choices[0].message.content
                
                # Add warning about truncated text if applicable
                if text_limit_warning:
                    summary = text_limit_warning + "\n\n" + summary
                    
                return jsonify({"summary": summary})
            except Exception as e:
                error_msg = str(e).lower()
                if ("rate" in error_msg or "limit" in error_msg) and attempt < max_retries - 1:
                    # If it's a rate limit error and not the last attempt, wait and retry
                    time.sleep(2)  # Wait 2 seconds before retrying
                    continue
                else:
                    # If it's the last attempt or not a rate limit error, use fallback
                    raise e
        
        # If we reach here, all retries failed
        raise Exception("API rate limit exceeded after multiple attempts")
        
    except Exception as e:
        # Use fallback summarization if API fails
        if "rate" in str(e).lower() or "limit" in str(e).lower() or "quota" in str(e).lower():
            fallback_summary = basic_summarize(text)
            return jsonify({
                "summary": fallback_summary,
                "warning": "API rate limit exceeded. This is a basic summary generated without AI. Please try again later for a better summary."
            })
        else:
            return jsonify({"error": f"AI generation failed: {str(e)}"}), 500

@app.route('/generate_policy', methods=['POST'])
def generate_policy():
    data = request.json
    prompt_text = data.get('prompt', '').strip()
    
    if not prompt_text:
        return jsonify({"error": "Prompt text is required"}), 400
    
    try:
        # Similar approach with retry and fallback
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that generates detailed and well-structured policies."},
                        {"role": "user", "content": f"Generate a detailed policy covering at least 10 key points based on the following scenario:\n{prompt_text}"}
                    ],
                    max_tokens=1500
                )
                policy = response.choices[0].message.content
                return jsonify({"policy": policy})
            except Exception as e:
                error_msg = str(e).lower()
                if ("rate" in error_msg or "limit" in error_msg) and attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    raise e
        
        # If we reach here, all retries failed
        raise Exception("API rate limit exceeded after multiple attempts")
        
    except Exception as e:
        if "rate" in str(e).lower() or "limit" in str(e).lower() or "quota" in str(e).lower():
            # Fallback basic policy generator
            fallback_policy = f"""
# Basic Policy Framework for: {prompt_text}

Due to API limitations, we're providing a basic policy framework:

1. **Purpose and Scope**: Define the purpose of this policy and who it applies to.
2. **Key Definitions**: Define important terms used in the policy.
3. **Roles and Responsibilities**: Outline who is responsible for implementing different aspects.
4. **Core Requirements**: List the main rules or procedures.
5. **Compliance and Monitoring**: Explain how compliance will be monitored.
6. **Exceptions**: Detail any exceptions to the policy.
7. **Consequences of Non-compliance**: Explain repercussions for violations.
8. **Related Policies and Documents**: Reference related materials.
9. **Review and Updates**: State how often the policy will be reviewed.
10. **Contact Information**: Provide details on whom to contact with questions.

Note: This is a basic framework generated without AI due to API limitations. For a complete policy, please try again later.
"""
            return jsonify({
                "policy": fallback_policy,
                "warning": "API rate limit exceeded. This is a basic framework generated without AI. Please try again later for a complete policy."
            })
        else:
            return jsonify({"error": f"AI generation failed: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)