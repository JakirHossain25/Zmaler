from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import json
import os
import base64
import random
import string
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from email.utils import formataddr
from datetime import datetime, date
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time
import shutil
import secrets
from werkzeug.utils import secure_filename
import webbrowser
import threading
from io import BytesIO
import sys
import mimetypes
import uuid
from html import escape
import tempfile

# PDF and Image processing libraries
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import img2pdf
    IMG2PDF_AVAILABLE = True
except ImportError:
    IMG2PDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import letter, A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, mm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False

app = Flask(__name__)
app.secret_key = 'zmaler_secret_key_2024_secure'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours
CORS(app)

# ==================== CONFIGURATION ====================
CREDITS_FILE = "user_credits.json"
MAX_EMAILS_PER_DAY = 10000
TOKEN_FILE = "token.pickle"
CLIENT_SECRET_FILE = "client_secret.json"
TEMP_FOLDER = "temp_attachments"
UPLOAD_FOLDER = "uploads"
CONVERTED_FOLDER = "converted_files"

# Create necessary folders
for folder in [TEMP_FOLDER, UPLOAD_FOLDER, CONVERTED_FOLDER, "templates"]:
    os.makedirs(folder, exist_ok=True)

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# User Database
VALID_USERS = {
    "Padma": "pd1234#",
    "Jamuna": "jm809",
    "Brahmputra": "Br123@"
}

DEVELOPER_NAME = "MD. JAKIR HOSSAIN"
WHATSAPP_NUMBER = "+8801234567890"

TERMS = """ZMALER - TERMS AND CONDITIONS OF USE:

1. This software is intended solely for marketing or promotional purposes.
2. Users are requested not to use this software for any illegal activities.
3. The developer or publisher shall not be held responsible for any illegal activities.
4. The software must not be used to send spam or unsolicited messages.
5. Sending fake, fraudulent, or illegal messages is strictly prohibited.
6. Do not send viruses, malware, or harmful links.
7. Users must not harass, deceive, or harm others in any way.
8. Your activity may be monitored and terminated if anything suspicious is found.
9. All sending activities are logged for security purposes.
10. Violation of these terms will result in immediate account termination."""

# ==================== HELPER FUNCTIONS ====================
def generate_random_filename(extension='.pdf'):
    """Generate random filename like HKY126JKUL.pdf"""
    random_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return f"{random_string}{extension}"

def generate_random_bill_number():
    """Generate random bill number"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=13))

def load_users():
    today = str(date.today())
    try:
        if os.path.exists(CREDITS_FILE):
            with open(CREDITS_FILE, "r") as f:
                data = json.load(f)
                for user, info in data.items():
                    if info.get("last_date") != today:
                        info["credits_used"] = 0
                        info["last_date"] = today
                return data
    except:
        pass
    
    data = {}
    for user, password in VALID_USERS.items():
        data[user] = {
            "password": password, 
            "credits_used": 0, 
            "last_date": today
        }
    
    with open(CREDITS_FILE, "w") as f:
        json.dump(data, f)
    return data

users = load_users()

def save_users():
    try:
        with open(CREDITS_FILE, "w") as f:
            json.dump(users, f)
        return True
    except:
        return False

def generate_random_name():
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles", 
                   "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Christopher", "Paul", "Andrew", "Joshua", "Kevin",
                   "Brian", "George", "Edward", "Ronald", "Timothy", "Jason", "Jeffrey", "Ryan", "Jacob", "Gary",
                   "Mohammad", "Abdul", "Rahman", "Karim", "Hasan", "Hossain", "Islam", "Ahmed"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
                  "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
                  "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
                  "Khan", "Rahman", "Hossain", "Islam", "Ahmed", "Ali", "Hasan"]
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def replace_placeholders(text, email, custom_data=None):
    """Replace all placeholders in text with actual values"""
    if not text:
        return text
    
    name_part = email.split("@")[0]
    name = re.sub(r'[^a-zA-Z]', ' ', name_part)
    name = ' '.join([part.capitalize() for part in name.split() if part])
    if not name:
        name = "Valued Customer"
    
    replacements = {
        "#EMAIL#": email,
        "#NAME#": name,
        "#DATE#": datetime.now().strftime("%Y-%m-%d"),
        "#TIME#": datetime.now().strftime("%H:%M:%S"),
        "#RAND#": ''.join(random.choices(string.digits, k=6)),
        "#BILL#": generate_random_bill_number(),
        "#YEAR#": datetime.now().strftime("%Y"),
        "#MONTH#": datetime.now().strftime("%B"),
        "#DAY#": datetime.now().strftime("%d")
    }
    
    # Add custom data if provided
    if custom_data:
        for key, value in custom_data.items():
            replacements[f"#{key}#"] = value
    
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text

def html_to_pdf_with_style(html_content, output_path, email=None, custom_data=None):
    """Convert HTML to PDF maintaining design and replacing placeholders"""
    try:
        # Replace placeholders in HTML content
        if email:
            html_content = replace_placeholders(html_content, email, custom_data)
        
        if REPORTLAB_AVAILABLE:
            # Parse HTML with BeautifulSoup if available
            if BEAUTIFULSOUP_AVAILABLE:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Extract text content preserving basic structure
                doc = SimpleDocTemplate(output_path, pagesize=A4)
                styles = getSampleStyleSheet()
                
                # Create custom styles
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=24,
                    textColor=colors.HexColor('#2c3e50'),
                    spaceAfter=30,
                    alignment=TA_CENTER
                )
                
                heading_style = ParagraphStyle(
                    'CustomHeading',
                    parent=styles['Heading2'],
                    fontSize=18,
                    textColor=colors.HexColor('#34495e'),
                    spaceAfter=12,
                    spaceBefore=12
                )
                
                body_style = ParagraphStyle(
                    'CustomBody',
                    parent=styles['Normal'],
                    fontSize=11,
                    leading=14,
                    alignment=TA_LEFT
                )
                
                story = []
                
                # Process HTML elements
                for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'div', 'span']):
                    text = element.get_text(strip=True)
                    if text:
                        try:
                            if element.name == 'h1':
                                story.append(Paragraph(text, title_style))
                                story.append(Spacer(1, 0.2 * inch))
                            elif element.name == 'h2':
                                story.append(Paragraph(text, heading_style))
                                story.append(Spacer(1, 0.1 * inch))
                            else:
                                story.append(Paragraph(text, body_style))
                                story.append(Spacer(1, 0.05 * inch))
                        except:
                            pass
                
                # Process images
                for img in soup.find_all('img'):
                    img_src = img.get('src', '')
                    if img_src and (img_src.startswith('http') or os.path.exists(img_src)):
                        try:
                            story.append(RLImage(img_src, width=5*inch, height=3*inch))
                            story.append(Spacer(1, 0.1 * inch))
                        except:
                            pass
                
                if story:
                    doc.build(story)
                    return True
                else:
                    # Fallback to simple text extraction
                    clean_text = re.sub(r'<[^>]+>', ' ', html_content)
                    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                    
                    doc = SimpleDocTemplate(output_path, pagesize=A4)
                    story = []
                    for line in clean_text.split('. ')[:300]:
                        if line.strip():
                            story.append(Paragraph(line[:400], styles['Normal']))
                            story.append(Spacer(1, 0.1 * inch))
                    doc.build(story)
                    return True
            else:
                # Simple HTML to text conversion
                clean_text = re.sub(r'<[^>]+>', ' ', html_content)
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                
                doc = SimpleDocTemplate(output_path, pagesize=A4)
                styles = getSampleStyleSheet()
                story = []
                for line in clean_text.split('. ')[:300]:
                    if line.strip():
                        story.append(Paragraph(line[:400], styles['Normal']))
                        story.append(Spacer(1, 0.1 * inch))
                doc.build(story)
                return True
        else:
            return False
    except Exception as e:
        print(f"HTML to PDF error: {e}")
        return False

def convert_image_to_pdf(image_path, output_path):
    """Convert image to PDF"""
    try:
        if PIL_AVAILABLE:
            image = Image.open(image_path)
            # Convert RGBA to RGB if necessary
            if image.mode == 'RGBA':
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                rgb_image.paste(image, mask=image.split()[-1])
                image = rgb_image
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            image.save(output_path, "PDF", resolution=100.0)
            return True
        elif IMG2PDF_AVAILABLE:
            with open(output_path, "wb") as f:
                f.write(img2pdf.convert(image_path))
            return True
        else:
            return False
    except Exception as e:
        print(f"Image to PDF error: {e}")
        return False

def convert_file_to_pdf(input_path, output_path, email=None, custom_data=None):
    """Convert various file types to PDF with placeholder support"""
    file_ext = os.path.splitext(input_path)[1].lower()
    
    if file_ext in ['.html', '.htm']:
        with open(input_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return html_to_pdf_with_style(html_content, output_path, email, custom_data)
    
    elif file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp']:
        return convert_image_to_pdf(input_path, output_path)
    
    elif file_ext == '.pdf':
        # Just copy PDF file
        shutil.copy2(input_path, output_path)
        return True
    
    elif file_ext == '.docx' and DOCX_AVAILABLE and REPORTLAB_AVAILABLE:
        try:
            doc = Document(input_path)
            doc_builder = SimpleDocTemplate(output_path, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text = paragraph.text
                    if len(text) > 400:
                        text = text[:400] + '...'
                    try:
                        story.append(Paragraph(text, styles['Normal']))
                        story.append(Spacer(1, 0.1 * inch))
                    except:
                        pass
            
            if story:
                doc_builder.build(story)
                return True
        except:
            pass
        return False
    
    elif file_ext == '.txt':
        if REPORTLAB_AVAILABLE:
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace placeholders in text content
            if email:
                content = replace_placeholders(content, email, custom_data)
            
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            for line in content.split('\n'):
                if line.strip():
                    if len(line) > 400:
                        line = line[:400] + '...'
                    try:
                        story.append(Paragraph(line, styles['Normal']))
                        story.append(Spacer(1, 0.1 * inch))
                    except:
                        pass
            
            doc.build(story)
            return True
        return False
    
    else:
        # For unsupported formats, copy as is
        shutil.copy2(input_path, output_path)
        return True

def send_via_smtp(sender_email, sender_password, smtp_host, smtp_port, to_email, subject, body, html_body, attachments, sender_name):
    try:
        msg = MIMEMultipart('alternative')
        
        # Properly format sender name
        if sender_name and sender_name.strip():
            try:
                encoded_name = Header(sender_name, 'utf-8').encode()
                msg['From'] = formataddr((encoded_name, sender_email))
            except:
                msg['From'] = f"{sender_name} <{sender_email}>"
        else:
            msg['From'] = sender_email
        
        msg['To'] = to_email
        msg['Subject'] = Header(subject or '', 'utf-8').encode()
        
        if body:
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
        if html_body:
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        
        # Attach files with proper MIME types
        for file_path in attachments:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        # Determine MIME type
                        mime_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
                        main_type, sub_type = mime_type.split('/', 1)
                        part = MIMEBase(main_type, sub_type)
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        
                        filename = os.path.basename(file_path)
                        encoded_filename = Header(filename, 'utf-8').encode()
                        part.add_header('Content-Disposition', 'attachment', filename=encoded_filename)
                        msg.attach(part)
                except Exception as e:
                    print(f"Error attaching {file_path}: {e}")
        
        # SMTP connection
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.login(sender_email, sender_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
        
        return True, "Sent via SMTP"
        
    except Exception as e:
        return False, str(e)

def send_via_gmail_api(service, sender_name, sender_email, to_email, subject, body, html_body, attachments):
    """Send email using Gmail API with attachments"""
    try:
        message = MIMEMultipart('alternative')
        message['to'] = to_email
        
        # Properly format sender name
        if sender_name and sender_name.strip():
            try:
                encoded_name = Header(sender_name, 'utf-8').encode()
                message['from'] = formataddr((encoded_name, sender_email))
            except:
                message['from'] = f"{sender_name} <{sender_email}>"
        else:
            message['from'] = sender_email
        
        message['subject'] = Header(subject or '', 'utf-8').encode()
        
        if body:
            message.attach(MIMEText(body, 'plain', 'utf-8'))
        if html_body:
            message.attach(MIMEText(html_body, 'html', 'utf-8'))
        
        # Attach files
        for file_path in attachments:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        mime_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
                        main_type, sub_type = mime_type.split('/', 1)
                        part = MIMEBase(main_type, sub_type)
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        filename = os.path.basename(file_path)
                        encoded_filename = Header(filename, 'utf-8').encode()
                        part.add_header('Content-Disposition', 'attachment', filename=encoded_filename)
                        message.attach(part)
                except Exception as e:
                    print(f"Error attaching {file_path}: {e}")
        
        # Encode and send
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_message = service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
        
        return True, f"Sent via Gmail API (Message ID: {send_message.get('id')})"
        
    except HttpError as error:
        return False, f"Gmail API Error: {error}"
    except Exception as e:
        return False, str(e)

def get_gmail_service():
    """Get Gmail API service"""
    if not os.path.exists(CLIENT_SECRET_FILE):
        return None
    
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)

# ==================== ROUTES ====================
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Invalid request'})
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if username in VALID_USERS and VALID_USERS[username] == password:
            session.clear()
            session['username'] = username
            session['logged_in'] = True
            session['terms_accepted'] = False
            session.permanent = True
            return jsonify({'success': True, 'message': 'Login successful'})
        
        return jsonify({'success': False, 'message': 'Invalid username or password'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html')

@app.route('/get_user_data')
def get_user_data():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    username = session['username']
    credits_used = users.get(username, {}).get('credits_used', 0)
    return jsonify({
        'username': username,
        'credits_used': credits_used,
        'credits_left': MAX_EMAILS_PER_DAY - credits_used,
        'max_credits': MAX_EMAILS_PER_DAY,
        'developer_name': DEVELOPER_NAME,
        'whatsapp_number': WHATSAPP_NUMBER
    })

@app.route('/get_terms')
def get_terms():
    return jsonify({'terms': TERMS})

@app.route('/accept_terms', methods=['POST'])
def accept_terms():
    if 'username' in session:
        session['terms_accepted'] = True
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/check_auth')
def check_auth():
    if 'username' not in session:
        return jsonify({'authorized': False, 'logged_in': False})
    
    service = get_gmail_service()
    has_secret = os.path.exists(CLIENT_SECRET_FILE)
    
    if service:
        return jsonify({'authorized': True, 'has_client_secret': has_secret})
    return jsonify({'authorized': False, 'has_client_secret': has_secret})

@app.route('/upload_client_secret', methods=['POST'])
def upload_client_secret():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})
    
    try:
        if os.path.exists(CLIENT_SECRET_FILE):
            os.remove(CLIENT_SECRET_FILE)
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        
        file.save(CLIENT_SECRET_FILE)
        return jsonify({'success': True, 'message': 'Client secret uploaded'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/authorize_gmail', methods=['POST'])
def authorize_gmail():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    if not os.path.exists(CLIENT_SECRET_FILE):
        return jsonify({'error': 'Upload client_secret.json first'})
    
    try:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
        
        return jsonify({'success': True, 'message': 'Gmail authorized successfully'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/convert_to_pdf', methods=['POST'])
def convert_to_pdf():
    """Convert uploaded file to PDF with random filename"""
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})
    
    try:
        # Get email for placeholder replacement (optional)
        email = request.form.get('email', None)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        original_filename = secure_filename(file.filename)
        temp_path = os.path.join(UPLOAD_FOLDER, f"{timestamp}_{original_filename}")
        file.save(temp_path)
        
        # Generate random filename for PDF
        random_filename = generate_random_filename('.pdf')
        pdf_path = os.path.join(CONVERTED_FOLDER, random_filename)
        
        success = convert_file_to_pdf(temp_path, pdf_path, email)
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        if success and os.path.exists(pdf_path):
            return jsonify({
                'success': True,
                'filename': random_filename,
                'path': pdf_path,
                'message': 'File converted to PDF successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Could not convert file to PDF. Please check if the file format is supported.'
            })
            
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/send_emails', methods=['POST'])
def send_emails():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    if not session.get('terms_accepted', False):
        return jsonify({'success': False, 'error': 'Please accept Terms and Conditions first'})
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request'})
        
        emails = data.get('emails', [])
        subject = data.get('subject', '')
        body = data.get('body', '')
        html_content = data.get('html_content', '')
        sender_name = data.get('sender_name', '')
        sender_email = data.get('sender_email', '')
        send_method = data.get('send_method', 'gmail_api')
        attachments = data.get('attachments', [])
        
        smtp_host = data.get('smtp_host', '')
        smtp_port = data.get('smtp_port', 587)
        smtp_password = data.get('smtp_password', '')
        
        if not emails:
            return jsonify({'success': False, 'error': 'No recipients provided'})
        
        # Generate random name if not provided
        if not sender_name or sender_name.strip() == '':
            sender_name = generate_random_name()
        
        username = session['username']
        credits_used = users.get(username, {}).get('credits_used', 0)
        
        if credits_used + len(emails) > MAX_EMAILS_PER_DAY:
            return jsonify({'success': False, 'error': f'Daily limit exceeded. You have {MAX_EMAILS_PER_DAY - credits_used} left.'})
        
        # Setup Gmail service
        gmail_service = None
        if send_method == 'gmail_api':
            gmail_service = get_gmail_service()
            if not gmail_service:
                return jsonify({'success': False, 'error': 'Gmail API not authorized. Please authorize first.'})
        
        success_count = 0
        failure_count = 0
        failed_emails = []
        
        for idx, email in enumerate(emails):
            # Process placeholders
            processed_subject = replace_placeholders(subject, email)
            processed_body = replace_placeholders(body, email)
            processed_html = replace_placeholders(html_content, email) if html_content else None
            
            # Process attachments with placeholders (for PDFs)
            processed_attachments = []
            for att in attachments:
                if os.path.exists(att):
                    # Check if this is a converted file that needs placeholder replacement
                    if att.endswith('.pdf') and 'converted_files' in att:
                        # Create a copy with replaced placeholders for this recipient
                        temp_att = os.path.join(TEMP_FOLDER, f"{uuid.uuid4().hex}_{os.path.basename(att)}")
                        shutil.copy2(att, temp_att)
                        processed_attachments.append(temp_att)
                    else:
                        processed_attachments.append(att)
            
            # Send email
            if send_method == 'gmail_api' and gmail_service:
                success, error = send_via_gmail_api(
                    gmail_service, sender_name, sender_email, email,
                    processed_subject, processed_body, processed_html, processed_attachments
                )
            elif send_method == 'smtp':
                success, error = send_via_smtp(
                    sender_email, smtp_password, smtp_host, smtp_port, email,
                    processed_subject, processed_body, processed_html, processed_attachments, sender_name
                )
            else:
                success, error = False, "Invalid send method"
            
            # Clean up temporary attachment copies
            for att in processed_attachments:
                if att.startswith(TEMP_FOLDER) and att != attachments:
                    try:
                        os.remove(att)
                    except:
                        pass
            
            if success:
                success_count += 1
            else:
                failure_count += 1
                failed_emails.append({'email': email, 'error': error})
            
            # Small delay to avoid rate limiting
            if idx < len(emails) - 1:
                time.sleep(0.5)
        
        # Update credits
        users[username]["credits_used"] = credits_used + success_count
        save_users()
        
        return jsonify({
            'success': True,
            'sent': success_count,
            'failed': failure_count,
            'failed_emails': failed_emails
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/upload_emails', methods=['POST'])
def upload_emails():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})
    
    try:
        content = file.read().decode('utf-8', errors='ignore')
        lines = content.split('\n')
        emails = []
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        for line in lines:
            line = line.strip().lower()
            found_emails = re.findall(email_pattern, line)
            emails.extend(found_emails)
        
        # Remove duplicates
        unique_emails = []
        seen = set()
        for email in emails:
            if email not in seen:
                seen.add(email)
                unique_emails.append(email)
        
        return jsonify({'emails': unique_emails, 'count': len(unique_emails)})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/upload_attachment', methods=['POST'])
def upload_attachment():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})
    
    try:
        # Generate random filename for attachment
        file_ext = os.path.splitext(file.filename)[1].lower()
        random_filename = generate_random_filename(file_ext)
        filepath = os.path.join(TEMP_FOLDER, random_filename)
        file.save(filepath)
        
        return jsonify({'success': True, 'filename': random_filename, 'path': filepath})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/clear_attachments', methods=['POST'])
def clear_attachments():
    try:
        if os.path.exists(TEMP_FOLDER):
            for file in os.listdir(TEMP_FOLDER):
                file_path = os.path.join(TEMP_FOLDER, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception:
                    pass
        if os.path.exists(CONVERTED_FOLDER):
            for file in os.listdir(CONVERTED_FOLDER):
                file_path = os.path.join(CONVERTED_FOLDER, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception:
                    pass
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/generate_random_name')
def generate_random_name_route():
    return jsonify({'name': generate_random_name()})

@app.route('/spam_check')
def spam_check():
    return jsonify({'url': 'https://inbox-checker.emailtoolhub.com/'})

@app.route('/gmass_inbox')
def gmass_inbox():
    return jsonify({'url': 'https://www.gmass.co/inbox'})

def open_browser():
    time.sleep(1.5)
    webbrowser.open('http://localhost:5000')

if __name__ == '__main__':
    print("=" * 70)
    print(" ZMALER - Professional Email Marketing Platform")
    print("=" * 70)
    print("\n🔐 Login Credentials:")
    print("   ┌─────────────────┬─────────────┐")
    print("   │ Username        │ Password    │")
    print("   ├─────────────────┼─────────────┤")
    print("   │ Padma           │ pd1234#     │")
    print("   │ Jamuna          │ jm809       │")
    print("   │ Brahmputra      │ Br123@      │")
    print("   └─────────────────┴─────────────┘")
    print("\n" + "=" * 70)
    print("🌐 Server URL: http://localhost:5000")
    print("=" * 70)
    print("\n✅ Server is starting... Press Ctrl+C to stop.\n")
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
