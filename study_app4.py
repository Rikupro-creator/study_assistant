import streamlit as st
import json
from openai import OpenAI
from datetime import datetime, timedelta
import re
import PyPDF2
import io
import os
from pathlib import Path
import random
import hashlib
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from pypdf import PdfReader, PdfWriter
import string
import pandas as pd

# Page configuration
st.set_page_config(
    page_title="AI Study Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    /* Main theme colors */
    :root {
        --primary-color: #1f77b4;
        --secondary-color: #ff7f0e;
        --success-color: #2ca02c;
        --danger-color: #d62728;
    }
    
    /* Improve sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #5e84a6 0%, #6a849c 100%);
    }
    
    /* Card-like containers */
    .stExpander {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Better buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* Metrics styling */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: bold;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 600;
    }
    
    /* Success/Error messages */
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    /* Progress bars */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #4CAF50 0%, #8BC34A 100%);
    }
    
    /* File info cards */
    .file-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Question cards */
    .question-card {
        background: #f8f9fa;
        border-left: 4px solid #1f77b4;
        border-radius: 4px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    /* Answer feedback */
    .correct-answer {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
    }
    
    .incorrect-answer {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Improve spacing */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'api_key' not in st.session_state:
    st.session_state.api_key = ""
if 'document_content' not in st.session_state:
    st.session_state.document_content = ""
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'generated_content' not in st.session_state:
    st.session_state.generated_content = {}
if 'study_progress' not in st.session_state:
    st.session_state.study_progress = {}
if 'selected_folder' not in st.session_state:
    st.session_state.selected_folder = None
if 'selected_file' not in st.session_state:
    st.session_state.selected_file = None
if 'available_files' not in st.session_state:
    st.session_state.available_files = []
if 'available_folders' not in st.session_state:
    st.session_state.available_folders = []
if 'use_all_files' not in st.session_state:
    st.session_state.use_all_files = False
if 'loaded_files_info' not in st.session_state:
    st.session_state.loaded_files_info = []
if 'watermark_image' not in st.session_state:
    st.session_state.watermark_image = "the_coltap_logo.jpg"
if 'generation_count' not in st.session_state:
    st.session_state.generation_count = {}
if 'previous_generations' not in st.session_state:
    st.session_state.previous_generations = {}
if 'test_questions' not in st.session_state:
    st.session_state.test_questions = []
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {}
if 'test_submitted' not in st.session_state:
    st.session_state.test_submitted = False
if 'test_results' not in st.session_state:
    st.session_state.test_results = {}
if 'current_test_id' not in st.session_state:
    st.session_state.current_test_id = None
if 'test_detailed_results' not in st.session_state:
    st.session_state.test_detailed_results = {}

# Helper functions
def extract_letter_from_answer(answer):
    """Extract just the letter from an answer"""
    if not answer:
        return ""
    answer = str(answer).strip()
    if len(answer) == 1 and answer.isalpha():
        return answer.upper()
    if ')' in answer:
        letter_part = answer.split(')')[0].strip()
        if letter_part and letter_part[0].isalpha():
            return letter_part[0].upper()
    if answer and answer[0].isalpha():
        return answer[0].upper()
    return answer

def normalize_true_false(answer):
    """Normalize true/false answers"""
    if not answer:
        return ""
    answer = str(answer).strip().lower()
    true_variations = ['true', 't', 'yes', 'y', 'correct', 'right', '1']
    false_variations = ['false', 'f', 'no', 'n', 'incorrect', 'wrong', '0']
    if answer in true_variations:
        return "True"
    elif answer in false_variations:
        return "False"
    return answer.capitalize()

def is_answer_correct(user_answer, correct_answer, question_type):
    """Intelligently compare answers"""
    if user_answer is None or correct_answer is None:
        return False
    
    user_str = str(user_answer).strip()
    correct_str = str(correct_answer).strip()
    
    if not user_str:
        return False
    
    if question_type == "Multiple Choice":
        user_letter = extract_letter_from_answer(user_str)
        correct_letter = extract_letter_from_answer(correct_str)
        return user_letter == correct_letter
    
    elif question_type == "True/False":
        user_normalized = normalize_true_false(user_str)
        correct_normalized = normalize_true_false(correct_str)
        return user_normalized == correct_normalized
    
    else:  # Short Answer or Fill in the Blank
        user_clean = user_str.lower().translate(str.maketrans('', '', string.punctuation))
        correct_clean = correct_str.lower().translate(str.maketrans('', '', string.punctuation))
        user_clean = ' '.join(user_clean.split())
        correct_clean = ' '.join(correct_clean.split())
        
        if user_clean == correct_clean:
            return True
        
        user_words = set(user_clean.split())
        correct_words = set(correct_clean.split())
        
        if len(correct_words) > 0:
            overlap = user_words.intersection(correct_words)
            similarity = len(overlap) / len(correct_words)
            if similarity >= 0.6:
                return True
        
        return False

def normalize_answer_for_storage(answer, question_type):
    """Normalize answer for storage"""
    if answer is None:
        return ""
    answer_str = str(answer).strip()
    if question_type == "Multiple Choice":
        return extract_letter_from_answer(answer_str)
    elif question_type == "True/False":
        return normalize_true_false(answer_str)
    return answer_str

def discover_folders(base_path="."):
    """Discover all subfolders"""
    folders = []
    try:
        base = Path(base_path)
        for item in base.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                folders.append(str(item))
        folders.sort()
    except Exception as e:
        st.error(f"Error discovering folders: {str(e)}")
    return folders

def get_files_from_folder(folder_path):
    """Get list of supported files"""
    supported_extensions = ['.txt', '.md', '.pdf']
    files = []
    try:
        folder = Path(folder_path)
        for ext in supported_extensions:
            files.extend(list(folder.glob(f'*{ext}')))
        files.sort()
        return files
    except Exception as e:
        st.error(f"Error reading folder: {str(e)}")
        return []

def read_single_file(file_path):
    """Read content from a file"""
    try:
        file_path = Path(file_path)
        if file_path.suffix == '.pdf':
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                content = ""
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        content += text + "\n"
                return content, len(pdf_reader.pages)
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                return content, None
    except Exception as e:
        st.error(f"Error reading file: {str(e)}")
        return "", None

def read_all_files(file_list):
    """Read all files"""
    combined_content = ""
    files_info = []
    total_pages = 0
    total_words = 0
    
    for file_path in file_list:
        try:
            content, pages = read_single_file(file_path)
            if content:
                file_name = file_path.name
                combined_content += f"\n\n{'='*80}\n"
                combined_content += f"FILE: {file_name}\n"
                combined_content += f"{'='*80}\n\n"
                combined_content += content
                
                word_count = len(content.split())
                files_info.append({
                    'name': file_name,
                    'pages': pages if pages else 'N/A',
                    'words': word_count
                })
                
                if pages:
                    total_pages += pages
                total_words += word_count
        except Exception as e:
            st.warning(f"Could not read {file_path.name}: {str(e)}")
    
    return combined_content, files_info, total_pages, total_words

def create_test_results_pdf(test_data, user_answers_data, detailed_results, watermark_path=None):
    """Create a comprehensive PDF with test questions, user answers, and results"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                          rightMargin=72, leftMargin=72,
                          topMargin=72, bottomMargin=72)
    
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=30,
        alignment=1
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2c5aa0'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Title
    title = Paragraph("Practice Test Results", title_style)
    story.append(title)
    story.append(Spacer(1, 12))
    
    # Test info
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    info_text = f"Generated: {timestamp}<br/>Total Questions: {test_data['total_questions']}<br/>Score: {test_data['correct_answers']}/{test_data['total_questions']} ({test_data['score_percentage']:.1f}%)"
    story.append(Paragraph(info_text, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Summary table
    summary_data = [
        ['Metric', 'Value'],
        ['Total Questions', str(test_data['total_questions'])],
        ['Correct Answers', str(test_data['correct_answers'])],
        ['Incorrect Answers', str(test_data['total_questions'] - test_data['correct_answers'])],
        ['Score Percentage', f"{test_data['score_percentage']:.1f}%"],
        ['Difficulty Level', test_data.get('difficulty', 'N/A')]
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 3*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 30))
    story.append(PageBreak())
    
    # Detailed questions and answers
    story.append(Paragraph("Detailed Results", heading_style))
    story.append(Spacer(1, 20))
    
    for i, result in enumerate(detailed_results, 1):
        # Question header
        question_header = f"<b>Question {i}</b> [Type: {result['question_type']} | Status: {'✓ Correct' if result['is_correct'] else '✗ Incorrect'}]"
        story.append(Paragraph(question_header, heading_style))
        story.append(Spacer(1, 8))
        
        # Question text
        question_text = result['question'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        story.append(Paragraph(f"<b>Q:</b> {question_text}", styles['Normal']))
        story.append(Spacer(1, 8))
        
        # User answer
        user_answer_display = result['user_answer'] if result['user_answer'] else "No answer provided"
        user_answer_text = user_answer_display.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        if result['is_correct']:
            story.append(Paragraph(f"<b>Your Answer:</b> <font color='green'>{user_answer_text}</font>", styles['Normal']))
        else:
            story.append(Paragraph(f"<b>Your Answer:</b> <font color='red'>{user_answer_text}</font>", styles['Normal']))
        story.append(Spacer(1, 8))
        
        # Correct answer
        correct_answer_text = result['correct_answer'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        story.append(Paragraph(f"<b>Correct Answer:</b> {correct_answer_text}", styles['Normal']))
        story.append(Spacer(1, 8))
        
        # Explanation
        if result.get('explanation'):
            explanation_text = result['explanation'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(f"<b>Explanation:</b> {explanation_text}", styles['Normal']))
        
        story.append(Spacer(1, 20))
        
        # Page break every 3 questions for readability
        if i % 3 == 0 and i < len(detailed_results):
            story.append(PageBreak())
    
    # Build PDF
    doc.build(story)
    
    # Apply watermark if provided
    if watermark_path and os.path.exists(watermark_path):
        buffer.seek(0)
        watermark_buffer = io.BytesIO()
        c = canvas.Canvas(watermark_buffer, pagesize=letter)
        width, height = letter
        
        c.setFillAlpha(0.1)
        img_width = 200
        img_height = 200
        x = (width - img_width) / 2
        y = (height - img_height) / 2
        
        c.drawImage(watermark_path, x, y, width=img_width, height=img_height,
                   mask='auto', preserveAspectRatio=True)
        c.save()
        
        watermark_buffer.seek(0)
        watermark_pdf = PdfReader(watermark_buffer)
        content_pdf = PdfReader(buffer)
        
        writer = PdfWriter()
        for page in content_pdf.pages:
            page.merge_page(watermark_pdf.pages[0])
            writer.add_page(page)
        
        final_buffer = io.BytesIO()
        writer.write(final_buffer)
        final_buffer.seek(0)
        return final_buffer.getvalue()
    
    buffer.seek(0)
    return buffer.getvalue()

def create_pdf_with_watermark(text_content, filename, watermark_image_path=None):
    """Create a PDF with optional watermark"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                          rightMargin=72, leftMargin=72,
                          topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor='#1f4788',
        spaceAfter=30,
        alignment=1
    )
    
    heading2_style = ParagraphStyle(
        'CustomHeading2',
        parent=styles['Heading2'],
        fontSize=16,
        textColor='#2c5aa0',
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    heading3_style = ParagraphStyle(
        'CustomHeading3',
        parent=styles['Heading3'],
        fontSize=14,
        textColor='#4a7ba7',
        spaceAfter=10,
        spaceBefore=10,
        fontName='Helvetica-Bold'
    )
    
    bullet_style = ParagraphStyle(
        'BulletStyle',
        parent=styles['Normal'],
        leftIndent=20,
        spaceAfter=6,
        fontSize=11
    )
    
    story = []
    title = Paragraph("Study Material Summary", title_style)
    story.append(title)
    story.append(Spacer(1, 12))
    
    timestamp = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                         styles['Normal'])
    story.append(timestamp)
    story.append(Spacer(1, 20))
    
    lines = text_content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            story.append(Spacer(1, 6))
            i += 1
            continue
        
        if line.startswith('### '):
            heading_text = line[4:].strip()
            heading_text = heading_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            heading_text = heading_text.replace('**', '').replace('*', '')
            p = Paragraph(heading_text, heading3_style)
            story.append(p)
        
        elif line.startswith('## '):
            heading_text = line[3:].strip()
            heading_text = heading_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            heading_text = heading_text.replace('**', '').replace('*', '')
            p = Paragraph(heading_text, heading2_style)
            story.append(p)
        
        elif line.startswith('# '):
            heading_text = line[2:].strip()
            heading_text = heading_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            heading_text = heading_text.replace('**', '').replace('*', '')
            p = Paragraph(heading_text, heading2_style)
            story.append(p)
        
        elif line.startswith('- ') or line.startswith('* '):
            bullet_text = line[2:].strip()
            while '**' in bullet_text:
                start = bullet_text.find('**')
                end = bullet_text.find('**', start + 2)
                if end != -1:
                    before = bullet_text[:start]
                    bold_text = bullet_text[start+2:end]
                    after = bullet_text[end+2:]
                    bullet_text = before + '<b>' + bold_text + '</b>' + after
                else:
                    bullet_text = bullet_text.replace('**', '')
                    break
            
            bullet_text = bullet_text.replace('*', '')
            bullet_text = bullet_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            bullet_text = bullet_text.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
            p = Paragraph('• ' + bullet_text, bullet_style)
            story.append(p)
        
        else:
            para_text = line
            while '**' in para_text:
                start = para_text.find('**')
                end = para_text.find('**', start + 2)
                if end != -1:
                    before = para_text[:start]
                    bold_text = para_text[start+2:end]
                    after = para_text[end+2:]
                    para_text = before + '<b>' + bold_text + '</b>' + after
                else:
                    para_text = para_text.replace('**', '')
                    break
            
            para_text = para_text.replace('*', '')
            para_text = para_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            para_text = para_text.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
            
            p = Paragraph(para_text, styles['Normal'])
            story.append(p)
            story.append(Spacer(1, 8))
        
        i += 1
    
    doc.build(story)
    
    if watermark_image_path and os.path.exists(watermark_image_path):
        buffer.seek(0)
        watermark_buffer = io.BytesIO()
        c = canvas.Canvas(watermark_buffer, pagesize=letter)
        width, height = letter
        
        c.setFillAlpha(0.1)
        img_width = 200
        img_height = 200
        x = (width - img_width) / 2
        y = (height - img_height) / 2
        
        c.drawImage(watermark_image_path, x, y, width=img_width, height=img_height,
                   mask='auto', preserveAspectRatio=True)
        c.save()
        
        watermark_buffer.seek(0)
        watermark_pdf = PdfReader(watermark_buffer)
        content_pdf = PdfReader(buffer)
        
        writer = PdfWriter()
        for page in content_pdf.pages:
            page.merge_page(watermark_pdf.pages[0])
            writer.add_page(page)
        
        final_buffer = io.BytesIO()
        writer.write(final_buffer)
        final_buffer.seek(0)
        return final_buffer.getvalue()
    
    buffer.seek(0)
    return buffer.getvalue()

def get_ai_response(prompt, model="openrouter/free"):
    """Get response from OpenRouter API"""
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=st.session_state.api_key,
        )
        
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            extra_body={}
        )
        return completion.choices[0].message.content
    except Exception as e:
        st.error(f"Error communicating with API: {str(e)}")
        return None

def get_unique_generation_seed(content_type):
    """Generate unique seed"""
    if content_type not in st.session_state.generation_count:
        st.session_state.generation_count[content_type] = 0
    
    st.session_state.generation_count[content_type] += 1
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    random_num = random.randint(1000, 9999)
    count = st.session_state.generation_count[content_type]
    seed_string = f"{timestamp}_{random_num}_{count}"
    return hashlib.md5(seed_string.encode()).hexdigest()[:8]

def add_uniqueness_instructions(base_prompt, content_type):
    """Add uniqueness instructions"""
    seed = get_unique_generation_seed(content_type)
    uniqueness_instructions = f"""
IMPORTANT INSTRUCTIONS FOR UNIQUENESS (Generation ID: {seed}):
- This is generation #{st.session_state.generation_count.get(content_type, 1)} for this content type
- Create completely NEW and DIFFERENT content from any previous generations
- Use varied question formats, perspectives, and angles
- Focus on different aspects or sections of the material
- Avoid repeating similar questions or content patterns
- Be creative and explore the material from fresh angles
- Mix difficulty levels and question styles differently each time

"""
    return uniqueness_instructions + base_prompt

def analyze_test_performance():
    """Analyze test performance"""
    if not st.session_state.test_results:
        return None
    
    total_tests = len(st.session_state.test_results)
    total_questions = sum(r['total_questions'] for r in st.session_state.test_results.values())
    total_correct = sum(r['correct_answers'] for r in st.session_state.test_results.values())
    avg_score = (total_correct / total_questions * 100) if total_questions > 0 else 0
    
    question_types = {}
    difficulties = {}
    
    for test_id, result in st.session_state.test_results.items():
        for i, question in enumerate(result['questions']):
            q_type = question.get('type', 'Unknown')
            q_diff = question.get('difficulty', 'Unknown')
            is_correct = result['user_answers'].get(i) == question['correct_answer']
            
            if q_type not in question_types:
                question_types[q_type] = {'total': 0, 'correct': 0}
            question_types[q_type]['total'] += 1
            if is_correct:
                question_types[q_type]['correct'] += 1
            
            if q_diff not in difficulties:
                difficulties[q_diff] = {'total': 0, 'correct': 0}
            difficulties[q_diff]['total'] += 1
            if is_correct:
                difficulties[q_diff]['correct'] += 1
    
    insights = []
    insights.append(f"**Overall Performance**: {avg_score:.1f}% across {total_tests} tests")
    
    for q_type, stats in question_types.items():
        accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
        insights.append(f"**{q_type}**: {accuracy:.1f}% accuracy ({stats['correct']}/{stats['total']})")
    
    for diff, stats in difficulties.items():
        accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
        insights.append(f"**{diff} questions**: {accuracy:.1f}% accuracy")
    
    if question_types:
        lowest_type = min(question_types.items(), 
                         key=lambda x: (x[1]['correct']/x[1]['total']) if x[1]['total'] > 0 else 1)
        insights.append(f"**Focus Area**: Practice more {lowest_type[0]} questions")
    
    return insights

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/clouds/100/000000/book.png", width=80)
    st.title("⚙️ Settings")
    
    # API Key
    api_key_input = st.text_input(
        "🔑 OpenRouter API Key",
        type="password",
        value=st.session_state.api_key,
        help="Get your API key from https://openrouter.ai/",
        key="api_key_input"
    )
    if api_key_input:
        st.session_state.api_key = api_key_input
        st.success("✅ API Key saved!")
    
    st.divider()
    
    # Folder Selection
    st.header("📁 Study Materials")
    
    if st.button("🔍 Discover Folders", key="discover_modules", use_container_width=True):
        with st.spinner("Scanning for folders..."):
            st.session_state.available_folders = discover_folders(".")
            st.session_state.selected_folder = None
            st.session_state.available_files = []
            st.session_state.selected_file = None
            st.session_state.use_all_files = False
            st.session_state.loaded_files_info = []
            if st.session_state.available_folders:
                st.success(f"✅ Found {len(st.session_state.available_folders)} folder(s)")
            else:
                st.warning("⚠️ No subfolders found")
    
    if st.session_state.available_folders:
        folder_names = [Path(f).name for f in st.session_state.available_folders]
        
        selected_folder_name = st.selectbox(
            "📂 Select a folder",
            options=[""] + folder_names,
            key="folder_selector",
            help="Choose the folder containing your study materials"
        )
        
        if selected_folder_name and selected_folder_name != "":
            selected_folder_path = st.session_state.available_folders[
                folder_names.index(selected_folder_name)
            ]
            
            if selected_folder_path != st.session_state.selected_folder:
                st.session_state.selected_folder = selected_folder_path
                st.session_state.available_files = get_files_from_folder(selected_folder_path)
                st.session_state.selected_file = None
                st.session_state.document_content = ""
                st.session_state.use_all_files = False
                st.session_state.loaded_files_info = []
                
                if st.session_state.available_files:
                    st.info(f"📄 Found {len(st.session_state.available_files)} file(s)")
                else:
                    st.warning(f"⚠️ No supported files found")
    
    if st.session_state.available_files:
        st.divider()
        st.subheader("📖 Loading Options")
        
        load_method = st.radio(
            "Choose loading method:",
            ["📄 Single File", "📚 All Files"],
            key="load_method",
            help="Analyze one file or combine multiple files"
        )
        
        st.session_state.use_all_files = (load_method == "📚 All Files")
        
        if not st.session_state.use_all_files:
            file_names = [f.name for f in st.session_state.available_files]
            selected_file_name = st.selectbox(
                "Select file:",
                options=[""] + file_names,
                key="file_selector"
            )
            
            if selected_file_name and selected_file_name != "":
                selected_file_path = st.session_state.available_files[
                    file_names.index(selected_file_name)
                ]
                
                if st.button("📥 Load File", key="load_file", use_container_width=True):
                    st.session_state.selected_file = selected_file_path
                    with st.spinner(f"Reading {selected_file_name}..."):
                        content, pages = read_single_file(selected_file_path)
                        if content:
                            st.session_state.document_content = content
                            word_count = len(content.split())
                            st.session_state.loaded_files_info = [{
                                'name': selected_file_name,
                                'pages': pages if pages else 'N/A',
                                'words': word_count
                            }]
                            st.success(f"✅ Loaded successfully!")
                            st.balloons()
        else:
            st.info(f"📚 Ready to load {len(st.session_state.available_files)} files")
            
            if st.button("📥 Load All Files", key="load_all_files", use_container_width=True):
                with st.spinner("Reading all files..."):
                    combined_content, files_info, total_pages, total_words = read_all_files(
                        st.session_state.available_files
                    )
                    
                    if combined_content:
                        st.session_state.document_content = combined_content
                        st.session_state.loaded_files_info = files_info
                        st.session_state.selected_file = None
                        st.success(f"✅ Loaded {len(files_info)} files!")
                        st.balloons()
    
    # Current selection info
    if st.session_state.document_content:
        st.divider()
        word_count = len(st.session_state.document_content.split())
        
        if st.session_state.use_all_files:
            st.success(f"📚 **{len(st.session_state.loaded_files_info)} files loaded**")
            st.metric("Total Words", f"{word_count:,}")
            
            with st.expander("📋 File Details"):
                for file_info in st.session_state.loaded_files_info:
                    pages_info = f", {file_info['pages']} pages" if file_info['pages'] != 'N/A' else ""
                    st.write(f"📄 **{file_info['name']}**")
                    st.caption(f"{file_info['words']:,} words{pages_info}")
        else:
            st.success("📄 **File loaded**")
            st.metric("Words", f"{word_count:,}")
            if st.session_state.selected_file:
                st.caption(f"📝 {st.session_state.selected_file.name}")

# Main App
col1, col2, col3 = st.columns([1, 3, 1])
with col2:
    st.title("📚 AI Study Assistant")
    st.markdown("*Your intelligent companion for effective learning*")

if st.session_state.document_content:
    if st.session_state.use_all_files:
        st.info(f"📚 Currently analyzing **{len(st.session_state.loaded_files_info)} files** from your selected folder")
    else:
        file_name = st.session_state.selected_file.name if st.session_state.selected_file else "your document"
        st.info(f"📄 Currently analyzing: **{file_name}**")

# Create tabs
tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏠 Home",
    "📝 Analysis",
    "❓ Questions",
    "📋 Cheat Sheet",
    "💬 Q&A Chat",
    "🎯 Practice Tests",
    "🧠 Memory Aids",
    "📊 Study Plan"
])

# TAB 0: Welcome
with tab0:
    st.header("👋 Welcome!")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### Your Personal AI Study Trainer 🎓
        
        Welcome to your intelligent study companion! I'm here to help you master your materials through:
        
        #### 🌟 Key Features
        
        - **📝 Smart Analysis**: Get comprehensive summaries and extract key concepts
        - **❓ Question Generation**: Create unlimited practice questions with explanations
        - **📋 Cheat Sheets**: Generate one-page summaries and formula sheets
        - **💬 Interactive Chat**: Ask questions about your materials anytime
        - **🎯 Practice Tests**: Take realistic tests and track your progress
        - **🧠 Memory Aids**: Get mnemonics, analogies, and visual associations
        - **📊 Study Planning**: Create personalized study schedules
        - **📚 Multi-File Support**: Analyze single files or entire folders
        
        #### 🚀 Getting Started
        
        1. **Enter your API key** in the sidebar (get one at [openrouter.ai](https://openrouter.ai))
        2. **Discover and select** a folder with your study materials
        3. **Choose loading method**: single file or all files
        4. **Start generating** study materials with the tools above!
        
        #### 💡 Pro Tips
        
        - Each generation creates **completely unique content**
        - Download materials as **TXT or PDF** with watermarks
        - Track your progress with the **performance analyzer**
        - Use **all files mode** for comprehensive exam prep
        """)
    
    with col2:
        st.info("""
        **📊 Quick Stats**
        
        ✅ Unlimited Questions
        ✅ PDF Export
        ✅ Progress Tracking
        ✅ Multi-File Support
        ✅ Smart Comparisons
        ✅ 7 Study Tools
        ✅ Always Unique
        """)
        
        if st.session_state.api_key and st.session_state.document_content:
            st.success("""
            **✨ You're Ready!**
            
            Everything is set up.
            Start exploring the tabs above!
            """)
        elif not st.session_state.api_key:
            st.warning("""
            **⚠️ API Key Needed**
            
            Please enter your API key in the sidebar.
            """)
        else:
            st.warning("""
            **⚠️ Load Materials**
            
            Please load your study materials using the sidebar.
            """)

# Check setup for other tabs
if not st.session_state.api_key:
    for tab in [tab1, tab2, tab3, tab4, tab5, tab6, tab7]:
        with tab:
            st.warning("⚠️ Please enter your OpenRouter API key in the sidebar to get started.")
    st.stop()

if not st.session_state.document_content:
    for tab in [tab1, tab2, tab3, tab4, tab5, tab6, tab7]:
        with tab:
            st.info("👈 Please load your study materials using the sidebar.")
    st.stop()

# TAB 1: Document Analysis
with tab1:
    st.header("📝 Document Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📖 Summarization")
        summary_depth = st.select_slider(
            "Summary depth:",
            options=["Brief", "Detailed", "Comprehensive", "Academic"],
            key="tab1_summary_depth"
        )
        
        if st.button("✨ Generate Summary", key="summary_btn", use_container_width=True):
            with st.spinner("Analyzing document..."):
                depth_instructions = {
                    "Brief": "Provide a concise summary in 5-7 sentences focusing on the core concepts and main takeaways.",
                    "Detailed": "Provide a detailed summary in 2-3 paragraphs covering all key concepts, their relationships, and practical applications.",
                    "Comprehensive": "Provide an in-depth analysis covering: 1) Main themes and concepts 2) Key principles and theories 3) Important examples/case studies 4) Practical applications 5) Critical insights and takeaways",
                    "Academic": "Provide a scholarly summary with: 1) Abstract-style overview 2) Methodology/theoretical framework 3) Key findings and evidence 4) Implications and significance 5) Limitations and future directions"
                }
                
                base_prompt = f"""Analyze the following text and provide a {summary_depth.lower()} summary that captures the depth and nuance of the content. Never mention the course or the author.

{depth_instructions[summary_depth]}

Text: {st.session_state.document_content}"""
                
                prompt = add_uniqueness_instructions(base_prompt, "summary")
                summary = get_ai_response(prompt)
                
                if summary:
                    st.session_state.generated_content['summary'] = summary
                    generation_num = st.session_state.generation_count.get('summary', 1)
                    st.success(f"✅ Summary generated! (Generation #{generation_num})")
        
        if 'summary' in st.session_state.generated_content:
            st.markdown("### 📄 Summary")
            with st.container():
                st.write(st.session_state.generated_content['summary'])
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button(
                    "📄 Download TXT",
                    st.session_state.generated_content['summary'],
                    file_name="summary.txt",
                    key="download_summary_txt",
                    use_container_width=True
                )
            with col_b:
                pdf_data = create_pdf_with_watermark(
                    st.session_state.generated_content['summary'],
                    "summary.pdf",
                    st.session_state.watermark_image
                )
                st.download_button(
                    "📕 Download PDF",
                    pdf_data,
                    file_name="summary.pdf",
                    mime="application/pdf",
                    key="download_summary_pdf",
                    use_container_width=True
                )
    
    with col2:
        st.subheader("🔑 Key Concepts")
        
        if st.button("✨ Extract Key Concepts", key="concepts_btn", use_container_width=True):
            with st.spinner("Extracting key concepts..."):
                prompt = f"""Extract and define the key concepts from this text. 
Format as:
**Concept Name**: Definition

Text: {st.session_state.document_content}"""
                
                concepts = get_ai_response(prompt)
                if concepts:
                    st.session_state.generated_content['concepts'] = concepts
                    st.success("✅ Concepts extracted!")
        
        if 'concepts' in st.session_state.generated_content:
            st.markdown("### 🔑 Key Concepts")
            with st.container():
                st.write(st.session_state.generated_content['concepts'])
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button(
                    "📄 Download TXT",
                    st.session_state.generated_content['concepts'],
                    file_name="key_concepts.txt",
                    key="download_concepts_txt",
                    use_container_width=True
                )
            with col_b:
                pdf_data = create_pdf_with_watermark(
                    st.session_state.generated_content['concepts'],
                    "key_concepts.pdf",
                    st.session_state.watermark_image
                )
                st.download_button(
                    "📕 Download PDF",
                    pdf_data,
                    file_name="key_concepts.pdf",
                    mime="application/pdf",
                    key="download_concepts_pdf",
                    use_container_width=True
                )

# TAB 2: Question Generator
with tab2:
    st.header("❓ Question Generator")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        num_questions = st.slider("Number of questions:", 5, 50, 10, key="tab2_num_questions")
    
    with col2:
        difficulty = st.select_slider(
            "Difficulty:",
            options=["Easy", "Medium", "Hard", "Mixed"],
            key="tab2_question_difficulty"
        )
    
    with col3:
        question_type = st.selectbox(
            "Question type:",
            ["Multiple Choice", "True/False", "Short Answer", "Fill in the Blank", "Mixed"],
            key="tab2_question_type"
        )
    
    if st.button("✨ Generate Questions", key="gen_questions", use_container_width=True):
        with st.spinner(f"Generating {num_questions} {question_type} questions..."):
            base_prompt = f"""Generate {num_questions} {question_type} questions from this text.
Difficulty level: {difficulty}

Format each question clearly with:
- Question number
- The question
- Options (if applicable)
- Correct answer
- Brief explanation

Text: {st.session_state.document_content}"""
            
            prompt = add_uniqueness_instructions(base_prompt, "questions")
            questions = get_ai_response(prompt)
            
            if questions:
                st.session_state.generated_content['questions'] = questions
                generation_num = st.session_state.generation_count.get('questions', 1)
                st.success(f"✅ Questions generated! (Generation #{generation_num})")
                st.info(f"🎲 This is generation #{generation_num}. Each generation creates completely new questions!")
    
    if 'questions' in st.session_state.generated_content:
        st.markdown("### 📝 Generated Questions")
        with st.container():
            st.write(st.session_state.generated_content['questions'])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button(
                "📄 Download TXT",
                st.session_state.generated_content['questions'],
                file_name="study_questions.txt",
                key="download_questions_txt",
                use_container_width=True
            )
        with col2:
            pdf_data = create_pdf_with_watermark(
                st.session_state.generated_content['questions'],
                "study_questions.pdf",
                st.session_state.watermark_image
            )
            st.download_button(
                "📕 Download PDF",
                pdf_data,
                file_name="study_questions.pdf",
                mime="application/pdf",
                key="download_questions_pdf",
                use_container_width=True
            )
        with col3:
            st.download_button(
                "📇 Anki Format",
                st.session_state.generated_content['questions'],
                file_name="anki_cards.txt",
                key="download_anki_format",
                use_container_width=True
            )

# TAB 3: Cheat Sheet
with tab3:
    st.header("📋 Cheat Sheet Generator")
    
    cheat_sheet_format = st.selectbox(
        "Choose format:",
        ["One-Page Summary", "Flashcard Style", "Formula Sheet", "Timeline", "Comparison Table"],
        key="tab3_cheat_sheet_format"
    )
    
    if st.button("✨ Generate Cheat Sheet", key="cheat_sheet_btn", use_container_width=True):
        with st.spinner("Creating cheat sheet..."):
            prompts = {
                "One-Page Summary": f"Create a concise one-page cheat sheet with the most important information from this text. Use bullet points and clear sections.\n\nText: {st.session_state.document_content}",
                "Flashcard Style": f"Create flashcard-style content with questions on one side and answers on the other. Format as 'Q: [question]\nA: [answer]'\n\nText: {st.session_state.document_content}",
                "Formula Sheet": f"Extract all formulas, equations, and important calculations. Explain when to use each.\n\nText: {st.session_state.document_content}",
                "Timeline": f"Create a chronological timeline of events, developments, or processes mentioned in this text.\n\nText: {st.session_state.document_content}",
                "Comparison Table": f"Create a comparison table showing similarities and differences between key concepts.\n\nText: {st.session_state.document_content}"
            }
            
            prompt = add_uniqueness_instructions(prompts[cheat_sheet_format], "cheat_sheet")
            cheat_sheet = get_ai_response(prompt)
            
            if cheat_sheet:
                st.session_state.generated_content['cheat_sheet'] = cheat_sheet
                generation_num = st.session_state.generation_count.get('cheat_sheet', 1)
                st.success(f"✅ Cheat sheet created! (Generation #{generation_num})")
    
    if 'cheat_sheet' in st.session_state.generated_content:
        st.markdown("### 📋 Your Cheat Sheet")
        with st.container():
            st.write(st.session_state.generated_content['cheat_sheet'])
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📄 Download TXT",
                st.session_state.generated_content['cheat_sheet'],
                file_name=f"cheat_sheet_{cheat_sheet_format.lower().replace(' ', '_')}.txt",
                key="download_cheat_txt",
                use_container_width=True
            )
        with col2:
            pdf_data = create_pdf_with_watermark(
                st.session_state.generated_content['cheat_sheet'],
                "cheat_sheet.pdf",
                st.session_state.watermark_image
            )
            st.download_button(
                "📕 Download PDF",
                pdf_data,
                file_name=f"cheat_sheet_{cheat_sheet_format.lower().replace(' ', '_')}.pdf",
                mime="application/pdf",
                key="download_cheat_pdf",
                use_container_width=True
            )

# TAB 4: Q&A Chat
with tab4:
    st.header("💬 Interactive Q&A Chat")
    st.markdown("*Ask questions about your documents and get instant answers*")
    
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.write(chat["content"])
    
    user_question = st.chat_input("Ask a question about the documents...", key="chat_input")
    
    if user_question:
        st.session_state.chat_history.append({"role": "user", "content": user_question})
        
        with st.chat_message("user"):
            st.write(user_question)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                prompt = f"""Based on the following documents, answer this question: {user_question}

If the question cannot be answered from the documents, say so and provide general knowledge if helpful.

Documents: {st.session_state.document_content}"""
                
                response = get_ai_response(prompt)
                if response:
                    st.write(response)
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
    
    if st.button("🗑️ Clear Chat History", key="clear_chat"):
        st.session_state.chat_history = []
        st.rerun()

# TAB 5: Practice Tests (IMPROVED with download functionality)
with tab5:
    st.header("🎯 Practice Tests")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        test_length = st.slider("Number of questions:", 5, 50, 15, key="tab5_test_length")
        question_types = st.multiselect(
            "Question types:",
            ["Multiple Choice", "True/False", "Short Answer", "Fill in the Blank"],
            default=["Multiple Choice", "True/False"],
            key="tab5_question_types"
        )
    
    with col2:
        test_difficulty = st.select_slider(
            "Difficulty level:",
            options=["Easy", "Medium", "Hard", "Mixed"],
            key="tab5_test_difficulty"
        )
    
    with col3:
        shuffle_questions = st.checkbox("Shuffle questions", value=True, key="tab5_shuffle_questions")
    
    if st.button("🔄 Generate New Practice Test", key="generate_test", use_container_width=True):
        with st.spinner("Creating your personalized practice test..."):
            st.session_state.test_questions = []
            st.session_state.user_answers = {}
            st.session_state.test_submitted = False
            st.session_state.current_test_id = str(datetime.now().timestamp())
            
            base_prompt = f"""Create a practice test with EXACTLY {test_length} questions from this study material.

YOU MUST CREATE EXACTLY {test_length} QUESTIONS - NO MORE, NO LESS.

SPECIFIC FORMATTING REQUIREMENTS:
For EACH question, provide in this EXACT format:
==QUESTION START==
Question Type: [Multiple Choice/True/False/Short Answer/Fill in the Blank]
Difficulty: [Easy/Medium/Hard]
Question: [The question text]
Options: [For MC: "A) Option1 | B) Option2 | C) Option3 | D) Option4" | For TF: "True | False" | For others: "N/A"]
Correct Answer: [The exact correct answer]
Explanation: [Brief explanation of why this is correct]
==QUESTION END==

Additional requirements:
- Mix of question types: {', '.join(question_types)}
- Overall difficulty: {test_difficulty}
- Include questions that test conceptual understanding
- Vary the cognitive level (remember, understand, apply, analyze)
- CRITICAL: You must provide exactly {test_length} complete questions

Study Material: {st.session_state.document_content}"""
            
            prompt = add_uniqueness_instructions(base_prompt, "flashcard_test")
            
            max_attempts = 3
            attempt = 0
            
            while attempt < max_attempts:
                test_content = get_ai_response(prompt)
                
                if test_content:
                    questions = []
                    question_blocks = test_content.split("==QUESTION START==")[1:]
                    
                    for block in question_blocks:
                        if "==QUESTION END==" in block:
                            question_text = block.split("==QUESTION END==")[0].strip()
                            lines = question_text.split("\n")
                            
                            question_data = {}
                            for line in lines:
                                line = line.strip()
                                if line.startswith("Question Type:"):
                                    question_data['type'] = line.split("Question Type:")[1].strip()
                                elif line.startswith("Difficulty:"):
                                    question_data['difficulty'] = line.split("Difficulty:")[1].strip()
                                elif line.startswith("Question:"):
                                    question_data['question'] = line.split("Question:")[1].strip()
                                elif line.startswith("Options:"):
                                    question_data['options'] = line.split("Options:")[1].strip()
                                elif line.startswith("Correct Answer:"):
                                    question_data['correct_answer'] = line.split("Correct Answer:")[1].strip()
                                elif line.startswith("Explanation:"):
                                    question_data['explanation'] = line.split("Explanation:")[1].strip()
                            
                            if all(key in question_data for key in ['type', 'question', 'correct_answer']):
                                questions.append(question_data)
                    
                    # Check if we got the right number of questions
                    if len(questions) == test_length:
                        st.session_state.test_questions = questions
                        generation_num = st.session_state.generation_count.get('flashcard_test', 1)
                        st.success(f"✅ Test generated with {len(questions)} questions! (Generation #{generation_num})")
                        st.rerun()
                        break
                    elif len(questions) > test_length:
                        # Too many questions - trim to exact length
                        st.session_state.test_questions = questions[:test_length]
                        generation_num = st.session_state.generation_count.get('flashcard_test', 1)
                        st.success(f"✅ Test generated with {test_length} questions! (Generation #{generation_num})")
                        st.rerun()
                        break
                    else:
                        # Too few questions - try again
                        attempt += 1
                        if attempt < max_attempts:
                            st.warning(f"Only got {len(questions)} questions, retrying... (Attempt {attempt + 1}/{max_attempts})")
                        else:
                            # Last attempt failed - use what we got
                            st.session_state.test_questions = questions
                            st.warning(f"⚠️ Generated {len(questions)} questions instead of {test_length}. Try regenerating if you need exactly {test_length}.")
                            st.rerun()
                else:
                    attempt += 1
                    if attempt >= max_attempts:
                        st.error("Failed to generate test. Please try again.")
                        break
    
    if st.session_state.test_questions:
        st.divider()
        
        # Test stats header
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📝 Questions", len(st.session_state.test_questions))
        with col2:
            answered = len(st.session_state.user_answers)
            st.metric("✅ Answered", f"{answered}/{len(st.session_state.test_questions)}")
        with col3:
            if st.session_state.test_submitted:
                correct = 0
                for i, question in enumerate(st.session_state.test_questions):
                    user_answer = st.session_state.user_answers.get(i)
                    if user_answer and is_answer_correct(user_answer, question['correct_answer'], question['type']):
                        correct += 1
                st.metric("🎯 Score", f"{correct}/{len(st.session_state.test_questions)}")
        with col4:
            if not st.session_state.test_submitted:
                if st.button("📥 Submit Test", type="primary", use_container_width=True, key="submit_test_btn"):
                    st.session_state.test_submitted = True
                    
                    correct = 0
                    detailed_results = []
                    
                    for i, question in enumerate(st.session_state.test_questions):
                        user_answer = st.session_state.user_answers.get(i)
                        normalized_user_answer = normalize_answer_for_storage(user_answer, question['type'])
                        
                        if user_answer:
                            st.session_state.user_answers[i] = normalized_user_answer
                        
                        is_correct = is_answer_correct(user_answer, question['correct_answer'], question['type'])
                        
                        if is_correct:
                            correct += 1
                        
                        detailed_results.append({
                            'question_index': i,
                            'question': question['question'],
                            'question_type': question['type'],
                            'user_answer': user_answer,
                            'normalized_user_answer': normalized_user_answer,
                            'correct_answer': question['correct_answer'],
                            'is_correct': is_correct,
                            'explanation': question.get('explanation', '')
                        })
                    
                    st.session_state.test_detailed_results[st.session_state.current_test_id] = detailed_results
                    
                    st.session_state.test_results[st.session_state.current_test_id] = {
                        'timestamp': datetime.now().isoformat(),
                        'total_questions': len(st.session_state.test_questions),
                        'correct_answers': correct,
                        'score_percentage': (correct / len(st.session_state.test_questions)) * 100,
                        'difficulty': test_difficulty,
                        'questions': st.session_state.test_questions,
                        'user_answers': dict(st.session_state.user_answers),
                        'detailed_results': detailed_results
                    }
                    st.rerun()
        
        st.divider()
        
        # Display questions
        for i, question in enumerate(st.session_state.test_questions):
            with st.container():
                st.markdown(f"### Question {i+1}")
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{question['question']}**")
                with col2:
                    st.caption(f"Type: {question['type']}")
                    st.caption(f"Difficulty: {question['difficulty']}")
                
                if question['type'] == "Multiple Choice":
                    options = question['options'].split(" | ")
                    option_labels = [opt.split(")")[0] for opt in options]
                    option_texts = [opt.split(")")[1].strip() for opt in options]
                    
                    cols = st.columns(len(options))
                    for idx, (label, text) in enumerate(zip(option_labels, option_texts)):
                        with cols[idx]:
                            if st.button(f"{label}) {text}", key=f"q{i}_opt{label}", 
                                       use_container_width=True,
                                       disabled=st.session_state.test_submitted):
                                st.session_state.user_answers[i] = label
                                st.rerun()
                    
                    if i in st.session_state.user_answers:
                        current_answer = st.session_state.user_answers[i]
                        full_answer = ""
                        for label, text in zip(option_labels, option_texts):
                            if label == current_answer:
                                full_answer = f"{label}) {text}"
                                break
                        
                        if full_answer:
                            st.info(f"📝 Your answer: {full_answer}")
                        else:
                            st.info(f"📝 Your answer: {current_answer}")
                
                elif question['type'] == "True/False":
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ True", key=f"q{i}_true", 
                                   use_container_width=True,
                                   disabled=st.session_state.test_submitted):
                            st.session_state.user_answers[i] = "True"
                            st.rerun()
                    with col2:
                        if st.button("❌ False", key=f"q{i}_false", 
                                   use_container_width=True,
                                   disabled=st.session_state.test_submitted):
                            st.session_state.user_answers[i] = "False"
                            st.rerun()
                    
                    if i in st.session_state.user_answers:
                        st.info(f"📝 Your answer: {st.session_state.user_answers[i]}")
                
                else:
                    user_answer = st.text_input(
                        "Your answer:",
                        key=f"q{i}_text",
                        value=st.session_state.user_answers.get(i, ""),
                        disabled=st.session_state.test_submitted,
                        label_visibility="collapsed"
                    )
                    if user_answer and user_answer != st.session_state.user_answers.get(i):
                        st.session_state.user_answers[i] = user_answer
                
                if st.session_state.test_submitted:
                    st.divider()
                    
                    current_test_id = st.session_state.current_test_id
                    detailed_results = st.session_state.test_detailed_results.get(current_test_id, [])
                    
                    if i < len(detailed_results):
                        result = detailed_results[i]
                        
                        col1, col2 = st.columns([1, 3])
                        
                        with col1:
                            if result['is_correct']:
                                st.success("✅ Correct!")
                            else:
                                st.error("❌ Incorrect")
                        
                        with col2:
                            user_display = result['user_answer'] if result['user_answer'] else "No answer"
                            st.markdown(f"**Your answer:** {user_display}")
                            st.markdown(f"**Correct answer:** {result['correct_answer']}")
                            
                            if result['explanation']:
                                with st.expander("📖 Show explanation"):
                                    st.info(result['explanation'])
                
                st.divider()
        
        # Download test results
        if st.session_state.test_submitted:
            st.markdown("### 📥 Download Your Test Results")
            
            col1, col2, col3 = st.columns(3)
            
            current_test_id = st.session_state.current_test_id
            if current_test_id in st.session_state.test_results:
                test_data = st.session_state.test_results[current_test_id]
                detailed_results = st.session_state.test_detailed_results.get(current_test_id, [])
                
                with col1:
                    # Download as JSON
                    json_data = {
                        'test_id': current_test_id,
                        'timestamp': test_data['timestamp'],
                        'total_questions': test_data['total_questions'],
                        'correct_answers': test_data['correct_answers'],
                        'score_percentage': test_data['score_percentage'],
                        'difficulty': test_data['difficulty'],
                        'detailed_results': detailed_results
                    }
                    
                    json_str = json.dumps(json_data, indent=2)
                    st.download_button(
                        "📊 Download JSON",
                        json_str,
                        file_name=f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        key="download_test_json",
                        use_container_width=True
                    )
                
                with col2:
                    # Download as PDF
                    pdf_data = create_test_results_pdf(
                        test_data,
                        st.session_state.user_answers,
                        detailed_results,
                        st.session_state.watermark_image
                    )
                    
                    st.download_button(
                        "📕 Download PDF",
                        pdf_data,
                        file_name=f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        key="download_test_pdf",
                        use_container_width=True
                    )
                
                with col3:
                    # Download as TXT
                    txt_content = f"""PRACTICE TEST RESULTS
{'='*50}

Test Date: {datetime.fromisoformat(test_data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}
Total Questions: {test_data['total_questions']}
Correct Answers: {test_data['correct_answers']}
Score: {test_data['score_percentage']:.1f}%
Difficulty: {test_data['difficulty']}

{'='*50}
DETAILED RESULTS
{'='*50}

"""
                    
                    for i, result in enumerate(detailed_results, 1):
                        status = "✓ CORRECT" if result['is_correct'] else "✗ INCORRECT"
                        txt_content += f"\nQuestion {i} [{status}]\n"
                        txt_content += f"Type: {result['question_type']}\n"
                        txt_content += f"Q: {result['question']}\n"
                        txt_content += f"Your Answer: {result['user_answer'] if result['user_answer'] else 'No answer'}\n"
                        txt_content += f"Correct Answer: {result['correct_answer']}\n"
                        if result.get('explanation'):
                            txt_content += f"Explanation: {result['explanation']}\n"
                        txt_content += "\n" + "-"*50 + "\n"
                    
                    st.download_button(
                        "📄 Download TXT",
                        txt_content,
                        file_name=f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        key="download_test_txt",
                        use_container_width=True
                    )
    
    # Test history
    if st.session_state.test_results:
        st.divider()
        with st.expander("📊 Test History & Performance Analysis"):
            for test_id, result in st.session_state.test_results.items():
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                with col1:
                    test_time = datetime.fromisoformat(result['timestamp']).strftime('%Y-%m-%d %H:%M')
                    st.write(f"**Test on {test_time}**")
                with col2:
                    st.write(f"**Score:** {result['correct_answers']}/{result['total_questions']}")
                with col3:
                    st.write(f"**{result['score_percentage']:.1f}%**")
                with col4:
                    st.write(f"Diff: {result['difficulty']}")
            
            st.divider()
            st.subheader("📈 Performance Insights")
            
            insights = analyze_test_performance()
            if insights:
                for insight in insights:
                    st.write(insight)
                
                # Progress chart
                if len(st.session_state.test_results) > 1:
                    test_dates = []
                    test_scores = []
                    
                    for test_id, result in sorted(st.session_state.test_results.items()):
                        test_date = datetime.fromisoformat(result['timestamp']).strftime('%Y-%m-%d %H:%M')
                        test_dates.append(test_date)
                        test_scores.append(result['score_percentage'])
                    
                    chart_data = pd.DataFrame({
                        "Test": test_dates,
                        "Score (%)": test_scores
                    })
                    st.line_chart(chart_data, x="Test", y="Score (%)")

# TAB 6: Memory Aids
with tab6:
    st.header("🧠 Memory Aids")
    
    memory_tool = st.selectbox(
        "Choose a memory aid:",
        ["Mnemonics", "Analogies", "Visual Associations", "Acronyms", "Story Method"],
        key="tab6_memory_tool"
    )
    
    if st.button("✨ Generate Memory Aid", key="memory_aid_btn", use_container_width=True):
        with st.spinner(f"Creating {memory_tool.lower()}..."):
            prompts = {
                "Mnemonics": f"Create memorable mnemonics for the key concepts in this text. Explain each mnemonic.\n\nText: {st.session_state.document_content}",
                "Analogies": f"Create helpful analogies to explain difficult concepts in this text by relating them to everyday experiences.\n\nText: {st.session_state.document_content}",
                "Visual Associations": f"Suggest visual associations and mental images to help remember key information from this text.\n\nText: {st.session_state.document_content}",
                "Acronyms": f"Create acronyms to help remember lists and key points from this text.\n\nText: {st.session_state.document_content}",
                "Story Method": f"Create a memorable story that incorporates the key concepts from this text.\n\nText: {st.session_state.document_content}"
            }
            
            prompt = add_uniqueness_instructions(prompts[memory_tool], "memory_aid")
            memory_aid = get_ai_response(prompt)
            
            if memory_aid:
                st.session_state.generated_content['memory_aid'] = memory_aid
                generation_num = st.session_state.generation_count.get('memory_aid', 1)
                st.success(f"✅ {memory_tool} created! (Generation #{generation_num})")
    
    if 'memory_aid' in st.session_state.generated_content:
        st.markdown(f"### {memory_tool}")
        with st.container():
            st.write(st.session_state.generated_content['memory_aid'])
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📄 Download TXT",
                st.session_state.generated_content['memory_aid'],
                file_name=f"memory_aid_{memory_tool.lower().replace(' ', '_')}.txt",
                key="download_memory_txt",
                use_container_width=True
            )
        with col2:
            pdf_data = create_pdf_with_watermark(
                st.session_state.generated_content['memory_aid'],
                "memory_aid.pdf",
                st.session_state.watermark_image
            )
            st.download_button(
                "📕 Download PDF",
                pdf_data,
                file_name=f"memory_aid_{memory_tool.lower().replace(' ', '_')}.pdf",
                mime="application/pdf",
                key="download_memory_pdf",
                use_container_width=True
            )

# TAB 7: Study Planner
with tab7:
    st.header("📊 Study Planner")
    
    col1, col2 = st.columns(2)
    
    with col1:
        exam_date = st.date_input(
            "Exam/Deadline date:",
            min_value=datetime.now().date(),
            value=datetime.now().date() + timedelta(days=14),
            key="tab7_exam_date"
        )
    
    with col2:
        study_hours_per_day = st.slider("Study hours per day:", 1, 8, 2, key="tab7_study_hours")
    
    if st.button("✨ Generate Study Plan", key="study_plan_btn", use_container_width=True):
        days_until_exam = (exam_date - datetime.now().date()).days
        
        with st.spinner("Creating your personalized study plan..."):
            prompt = f"""Create a detailed study plan for this material with the following constraints:
- Days until exam: {days_until_exam}
- Study hours per day: {study_hours_per_day}
- Total study hours available: {days_until_exam * study_hours_per_day}

Include:
1. Daily breakdown of topics to cover
2. Recommended study techniques for each section
3. Review sessions
4. Practice test schedule
5. Rest days

Text to study: {st.session_state.document_content}"""
            
            study_plan = get_ai_response(prompt)
            if study_plan:
                st.session_state.generated_content['study_plan'] = study_plan
                st.success("✅ Study plan created!")
    
    if 'study_plan' in st.session_state.generated_content:
        st.markdown("### 📅 Your Study Plan")
        with st.container():
            st.write(st.session_state.generated_content['study_plan'])
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📄 Download TXT",
                st.session_state.generated_content['study_plan'],
                file_name="study_plan.txt",
                key="download_study_plan_txt",
                use_container_width=True
            )
        with col2:
            pdf_data = create_pdf_with_watermark(
                st.session_state.generated_content['study_plan'],
                "study_plan.pdf",
                st.session_state.watermark_image
            )
            st.download_button(
                "📕 Download PDF",
                pdf_data,
                file_name="study_plan.pdf",
                mime="application/pdf",
                key="download_study_plan_pdf",
                use_container_width=True
            )
    
    st.divider()
    
    # Progress tracking
    st.subheader("📈 Progress Tracker")
    
    topic_status = st.text_input("Enter topic name:", key="topic_status_input")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📖 Mark as Studying", key="mark_studying_btn", use_container_width=True):
            if topic_status:
                st.session_state.study_progress[topic_status] = "Studying"
                st.success(f"'{topic_status}' marked as Studying")
    
    with col2:
        if st.button("🔄 Mark as Review", key="mark_review_btn", use_container_width=True):
            if topic_status:
                st.session_state.study_progress[topic_status] = "Review"
                st.success(f"'{topic_status}' needs review")
    
    with col3:
        if st.button("✅ Mark as Mastered", key="mark_mastered_btn", use_container_width=True):
            if topic_status:
                st.session_state.study_progress[topic_status] = "Mastered"
                st.success(f"'{topic_status}' mastered!")
    
    if st.session_state.study_progress:
        st.markdown("### Your Progress")
        for topic, status in st.session_state.study_progress.items():
            emoji = "📖" if status == "Studying" else "🔄" if status == "Review" else "✅"
            st.write(f"{emoji} **{topic}**: {status}")

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: gray; padding: 20px;'>
    <p style='font-size: 16px;'>📚 <strong>AI Study Assistant</strong> - Your Personal Learning Companion</p>
    <p style='font-size: 14px;'>Made with ❤️ using Streamlit & OpenRouter AI</p>
</div>
""", unsafe_allow_html=True)