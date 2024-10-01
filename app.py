from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import PyPDF2
import docx
import requests
import spacy

app = Flask(__name__)

# Load spaCy NLP model
nlp = spacy.load("en_core_web_sm")

# Directory to save uploaded CVs
UPLOAD_FOLDER = 'uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Allowed file extensions for CVs (PDF and DOCX)
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

# Careerjet API configuration
CAREERJET_API_URL = "http://public.api.careerjet.net/search"

# Function to check allowed file extension
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to extract text from PDF CV
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page].extract_text()
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
    return text

# Function to extract text from Word (docx) CV
def extract_text_from_word(docx_path):
    text = ""
    try:
        doc = docx.Document(docx_path)
        for para in doc.paragraphs:
            text += para.text + '\n'
    except Exception as e:
        print(f"Error extracting text from Word: {e}")
    return text

# Function to extract skills from CV text using NLP
# Function to extract skills from CV text using NLP
def extract_skills(cv_text):
    """
    This function uses NLP to dynamically extract potential skills from the CV text.
    We'll prioritize broad technical skills relevant to jobs in tech and data science.
    """
    doc = nlp(cv_text)
    skills = set()

    # List of broad technical keywords (you can expand this as needed)
    broad_keywords = {'python', 'data science', 'machine learning', 'software engineer',
                      'kubernetes', 'cloud', 'data visualization', 'api development',
                      'docker', 'flask', 'tensorflow', 'pytorch', 'javascript', 'node.js', 'react'}

    # Iterate through noun chunks and entities to extract skills
    for chunk in doc.noun_chunks:
        term = chunk.text.strip().lower()
        if len(term) > 2 and term not in nlp.Defaults.stop_words and term in broad_keywords:
            skills.add(term)

    # If we don't have enough broad skills, include a few specific ones
    if len(skills) < 3:
        for chunk in doc.ents:  # Named entities
            term = chunk.text.strip().lower()
            if len(term) > 2 and term not in nlp.Defaults.stop_words and term not in broad_keywords:
                skills.add(term)
            if len(skills) >= 5:
                break

    # Limit the number of keywords to 5 to avoid overloading the API
    skills_list = list(skills)[:5]  # Take the first 5 extracted skills

    return ', '.join(skills_list)



# Function to recommend jobs from Careerjet based on skills
def get_careerjet_jobs(skills, location="United States"):
    params = {
        'locale': 'en_US',
        'keywords': skills,
        'location': location,
        'page': 1,
        'user_ip': request.remote_addr,  # Get the user's IP address
        'user_agent': request.headers.get('User-Agent') or 'Mozilla/5.0'  # Set a default user agent if not provided
    }

    try:
        response = requests.get(CAREERJET_API_URL, params=params)

        # Print the request URL
        print("Careerjet API request URL:", response.url)
        print("Careerjet API response content:", response.content)


        # Check for non-200 response
        if response.status_code != 200:
            print(f"Error: API request failed with status code {response.status_code}")
            return []

        # Debugging: Print the raw API response
        print("Raw Careerjet API response:", response.content)

        response_json = response.json()

        # Extract job details
        jobs = response_json.get('jobs', [])
        if not jobs:
            print("No jobs returned by API.")
        job_list = []
        for job in jobs:
            job_list.append({
                'title': job.get('title', 'N/A'),
                'company': job.get('company', 'N/A'),
                'location': job.get('locations', 'N/A'),
                'description': job.get('description', 'N/A')
            })

        return job_list
    except Exception as e:
        print(f"Error fetching jobs from Careerjet: {e}")
        return []

# Route to upload CV and get job recommendations
@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if the request has a file
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']

    # Check if the file is allowed
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Extract text based on file type (PDF or DOCX)
        if filename.endswith('.pdf'):
            cv_text = extract_text_from_pdf(file_path)
        elif filename.endswith('.docx'):
            cv_text = extract_text_from_word(file_path)
        else:
            return jsonify({'error': 'Invalid file format'}), 400

        # Check if text extraction was successful
        if not cv_text:
            return jsonify({'error': 'Failed to extract text from the CV'}), 400

        # Debug: print extracted CV text
        print(f"Extracted CV text: {cv_text}")

        # Automatically extract skills from the CV text
        skills = extract_skills(cv_text)

        # Debug: print the refined extracted skills (this is where you put the print statement)
        print(f"Refined extracted skills: {skills}")

        # Get job recommendations based on extracted skills
        jobs = get_careerjet_jobs(skills)
        return jsonify({'jobs': jobs}), 200
    else:
        return jsonify({'error': 'Invalid file format. Only PDF and Word (docx) files are allowed.'}), 400


# Route to serve the frontend
@app.route('/')
def index():
    return render_template('index.html')

# Start the Flask app
if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)
