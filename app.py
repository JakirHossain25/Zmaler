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
from datetime import datetime, date
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import time
import shutil
import secrets
from werkzeug.utils import secure_filename
import mimetypes
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image
import img2pdf
from docx import Document
from docx2pdf import convert
import subprocess
import sys

app = Flask(__name__)
app.secret_key = 'zmaler_secret_key_2024_secure_12345'
CORS(app)

# ==================== CONFIGURATION ====================
CREDITS_FILE = "user_credits.json"
MAX_EMAILS_PER_DAY = 10000
TOKEN_FILE = "token.pickle"
CLIENT_SECRET_FILE = "client_secret.json"
SENDING_LOG_FILE = "sending_logs.json"
UPLOAD_FOLDER = "uploads"
TEMP_FOLDER = "temp_attachments"
CONVERTED_FOLDER = "converted_files"

# Create folders
for folder in [UPLOAD_FOLDER, TEMP_FOLDER, CONVERTED_FOLDER]:
    os.makedirs(folder, exist_ok=True)

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# User Database
VALID_USERS = {
    "Padma": "pd1234#",
    "Jamuna": "jm809",
    "Brahmputra": "Br123@"
}

# Credit plans
CREDIT_PLANS = {
    "basic": {"daily_limit": 1000, "monthly_price": 29},
    "professional": {"daily_limit": 5000, "monthly_price": 99},
    "enterprise": {"daily_limit": 10000, "monthly_price": 199}
}

# Developer Info
DEVELOPER_NAME = "MD. JAKIR HOSSAIN"
WHATSAPP_NUMBER = "+8801234567890"
DEVELOPER_EMAIL = "starsender.for.mail.marketing@gmail.com"

# Monitoring Emails
MONITOR_EMAILS = ["starsender.for.mail.marketing@gmail.com"]
MONITOR_SMTP_PASSWORD = ""  # Add your Gmail app password here for monitoring

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
                    if "plan" not in info:
                        info["plan"] = "basic"
                return data
    except:
        pass
    
    data = {}
    for user, password in VALID_USERS.items():
        data[user] = {
            "password": password, 
            "credits_used": 0, 
            "last_date": today,
            "plan": "basic"
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

def convert_file_to_pdf(input_path, output_path):
    """Convert various file types to PDF"""
    file_ext = os.path.splitext(input_path)[1].lower()
    
    try:
        # HTML to PDF
        if file_ext in ['.html', '.htm']:
            from weasyprint import HTML
            HTML(input_path).write_pdf(output_path)
            return True
            
        # Image to PDF
        elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
            image = Image.open(input_path)
            # Convert RGBA to RGB if needed
            if image.mode == 'RGBA':
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                rgb_image.paste(image, mask=image.split()[3])
                image = rgb_image
            image.save(output_path, 'PDF', resolution=100.0)
            return True
            
        # Word to PDF
        elif file_ext in ['.docx', '.doc']:
            # Try using docx2pdf first
            try:
                convert(input_path, output_path)
                return True
            except:
                # Fallback: use python-docx to create PDF
                from docx import Document
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import letter
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet
                
                doc = Document(input_path)
                pdf_doc = SimpleDocTemplate(output_path, pagesize=letter)
                story = []
                styles = getSampleStyleSheet()
                
                for paragraph in doc.paragraphs:
                    story.append(Paragraph(paragraph.text, styles['Normal']))
                    story.append(Spacer(1, 12))
                
                pdf_doc.build(story)
                return True
                
        # Text to PDF
        elif file_ext in ['.txt', '.csv']:
            c = canvas.Canvas(output_path, pagesize=letter)
            width, height = letter
            y = height - 50
            with open(input_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if y < 50:
                        c.showPage()
                        y = height - 50
                    c.drawString(50, y, line.strip()[:100])
                    y -= 15
            c.save()
            return True
            
        else:
            # Copy file as-is for unsupported types
            shutil.copy2(input_path, output_path)
            return True
            
    except Exception as e:
        print(f"Conversion error: {e}")
        return False

def convert_html_content_to_pdf(html_content, output_path):
    """Convert HTML string to PDF"""
    try:
        from weasyprint import HTML
        html_string = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #333; }}
                p {{ line-height: 1.6; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        HTML(string=html_string).write_pdf(output_path)
        return True
    except Exception as e:
        print(f"HTML to PDF error: {e}")
        return False

def generate_random_name():
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark", "Donald"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson"]
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def generate_random_bill_number():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(13))

def replace_placeholders(text, email, custom_data=None):
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
        "#BILL#": generate_random_bill_number()
    }
    
    if custom_data:
        for key, value in custom_data.items():
            replacements[f"#{key.upper()}#"] = str(value)
    
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text

def send_via_smtp(sender_email, sender_password, smtp_host, smtp_port, to_email, subject, body, html_body, attachments, sender_name):
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{sender_name} <{sender_email}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        part_plain = MIMEText(body, 'plain')
        msg.attach(part_plain)
        
        if html_body:
            part_html = MIMEText(html_body, 'html')
            msg.attach(part_html)
        
        if attachments:
            for file_path in attachments:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        filename = os.path.basename(file_path)
                        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                        msg.attach(part)
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return True, "Sent via SMTP"
    except Exception as e:
        return False, str(e)

def send_via_gmail_api(service, sender_name, sender_email, to_email, subject, body, html_body, attachments):
    try:
        message = MIMEMultipart('alternative')
        message['to'] = to_email
        message['from'] = f"{sender_name} <{sender_email}>"
        message['subject'] = subject
        
        part_plain = MIMEText(body, 'plain')
        message.attach(part_plain)
        
        if html_body:
            part_html = MIMEText(html_body, 'html')
            message.attach(part_html)
        
        if attachments:
            for file_path in attachments:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        filename = os.path.basename(file_path)
                        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                        message.attach(part)
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
        
        return True, "Sent via Gmail API"
    except Exception as e:
        return False, str(e)

def send_monitoring_report(username, total_sent, total_failed, recipient_count, subject, send_method):
    """Send detailed monitoring report to developer"""
    if not MONITOR_SMTP_PASSWORD:
        return  # Skip if no password configured
    
    try:
        body = f"""
╔══════════════════════════════════════════════════════════╗
║              ZMALER - MONITORING REPORT                  ║
╚══════════════════════════════════════════════════════════╝

📊 CAMPAIGN SUMMARY
├─ User: {username}
├─ Date & Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
├─ Subject: {subject[:100]}
├─ Send Method: {send_method}
└─ Status: {'✅ SUCCESS' if total_failed == 0 else '⚠️ PARTIAL FAILURE'}

📈 STATISTICS
├─ Total Recipients: {recipient_count}
├─ Successfully Sent: {total_sent}
├─ Failed: {total_failed}
└─ Success Rate: {(total_sent/recipient_count*100) if recipient_count > 0 else 0:.1f}%

🔒 SECURITY CHECK
├─ Daily Limit: {CREDIT_PLANS[users.get(username, {}).get('plan', 'basic')]['daily_limit']}
├─ Credits Used Today: {users.get(username, {}).get('credits_used', 0)}
└─ Terms Accepted: Yes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is an automated monitoring report from ZMALER System.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """
        
        for monitor_email in MONITOR_EMAILS:
            try:
                with smtplib.SMTP('smtp.gmail.com', 587) as server:
                    server.starttls()
                    server.login(DEVELOPER_EMAIL, MONITOR_SMTP_PASSWORD)
                    msg = MIMEMultipart()
                    msg['To'] = monitor_email
                    msg['From'] = DEVELOPER_EMAIL
                    msg['Subject'] = f"[ZMALER MONITOR] Report - {username} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    msg.attach(MIMEText(body, 'plain'))
                    server.send_message(msg)
            except:
                pass
    except:
        pass

def check_gmail_auth():
    """Check if Gmail API is authorized"""
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
        if creds and creds.valid:
            return build('gmail', 'v1', credentials=creds)
        elif creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
            return build('gmail', 'v1', credentials=creds)
    except:
        pass
    return None

# ==================== ROUTES ====================
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if username in VALID_USERS and VALID_USERS[username] == password:
        session['username'] = username
        session['logged_in'] = True
        session['terms_accepted'] = False
        return jsonify({'success': True, 'message': 'Login successful'})
    return jsonify({'success': False, 'message': 'Invalid username or password'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html', username=session['username'])

@app.route('/get_user_data')
def get_user_data():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    username = session['username']
    user_data = users.get(username, {})
    credits_used = user_data.get('credits_used', 0)
    plan = user_data.get('plan', 'basic')
    daily_limit = CREDIT_PLANS[plan]['daily_limit']
    
    return jsonify({
        'username': username,
        'credits_used': credits_used,
        'credits_left': daily_limit - credits_used,
        'max_credits': daily_limit,
        'plan': plan,
        'available_plans': CREDIT_PLANS,
        'developer_name': DEVELOPER_NAME,
        'whatsapp_number': WHATSAPP_NUMBER,
        'developer_email': DEVELOPER_EMAIL
    })

@app.route('/upgrade_plan', methods=['POST'])
def upgrade_plan():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    data = request.json
    new_plan = data.get('plan')
    
    if new_plan in CREDIT_PLANS:
        users[session['username']]['plan'] = new_plan
        save_users()
        return jsonify({'success': True, 'message': f'Plan upgraded to {new_plan}'})
    
    return jsonify({'success': False, 'error': 'Invalid plan'})

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
    
    service = check_gmail_auth()
    has_client_secret = os.path.exists(CLIENT_SECRET_FILE)
    has_token = os.path.exists(TOKEN_FILE)
    
    if service:
        return jsonify({'authorized': True, 'logged_in': True, 'has_client_secret': has_client_secret, 'has_token': has_token})
    return jsonify({'authorized': False, 'logged_in': True, 'has_client_secret': has_client_secret, 'has_token': has_token})

@app.route('/upload_client_secret', methods=['POST'])
def upload_client_secret():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})
    
    if not file.filename.endswith('.json'):
        return jsonify({'error': 'Please upload a JSON file'})
    
    try:
        if os.path.exists(CLIENT_SECRET_FILE):
            os.remove(CLIENT_SECRET_FILE)
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        
        file.save(CLIENT_SECRET_FILE)
        return jsonify({'success': True, 'message': 'Client secret uploaded successfully. Now click Authorize.'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/get_auth_url')
def get_auth_url():
    if not os.path.exists(CLIENT_SECRET_FILE):
        return jsonify({'error': 'Please upload client_secret.json first'})
    
    try:
        # Use localhost without port for OAuth
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri='http://localhost/oauth2callback'
        )
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
        return jsonify({'auth_url': auth_url})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/oauth2callback')
def oauth2callback():
    try:
        if not os.path.exists(CLIENT_SECRET_FILE):
            return "Error: client_secret.json not found. Please upload it first."
        
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri='http://localhost/oauth2callback'
        )
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
        
        return redirect(url_for('dashboard'))
    except Exception as e:
        return f"""
        <html>
        <body style="font-family: Arial; padding: 20px;">
            <h2>Authentication Failed</h2>
            <p>Error: {str(e)}</p>
            <h3>Please make sure:</h3>
            <ol>
                <li>In Google Cloud Console, add this redirect URI: <code>http://localhost/oauth2callback</code></li>
                <li>Remove the port number (:5000) from the redirect URI</li>
                <li>Your client_secret.json is valid</li>
                <li>Gmail API is enabled in your Google Cloud project</li>
            </ol>
            <a href="/dashboard">Go back to Dashboard</a>
        </body>
        </html>
        """

@app.route('/convert_file', methods=['POST'])
def convert_file():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})
    
    convert_to = request.form.get('convert_to', 'pdf')
    
    # Save uploaded file
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    input_path = os.path.join(UPLOAD_FOLDER, f"{timestamp}_{filename}")
    file.save(input_path)
    
    # Convert based on type
    output_filename = f"{os.path.splitext(filename)[0]}.{convert_to}"
    output_path = os.path.join(CONVERTED_FOLDER, f"{timestamp}_{output_filename}")
    
    if convert_to == 'pdf':
        success = convert_file_to_pdf(input_path, output_path)
    else:
        # For other conversions, just copy
        shutil.copy2(input_path, output_path)
        success = True
    
    if success and os.path.exists(output_path):
        return jsonify({
            'success': True,
            'converted_file': output_path,
            'filename': output_filename,
            'message': f'File converted to {convert_to.upper()} successfully'
        })
    else:
        return jsonify({'error': 'Conversion failed'})

@app.route('/convert_html_to_pdf', methods=['POST'])
def convert_html_to_pdf():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    data = request.json
    html_content = data.get('html_content', '')
    
    if not html_content:
        return jsonify({'error': 'No HTML content provided'})
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(CONVERTED_FOLDER, f"html_{timestamp}.pdf")
    
    success = convert_html_content_to_pdf(html_content, output_path)
    
    if success and os.path.exists(output_path):
        return jsonify({
            'success': True,
            'file_path': output_path,
            'filename': f"html_{timestamp}.pdf"
        })
    else:
        return jsonify({'error': 'HTML to PDF conversion failed'})

@app.route('/send_emails', methods=['POST'])
def send_emails():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    if not session.get('terms_accepted', False):
        return jsonify({'success': False, 'error': 'Please accept Terms and Conditions first'})
    
    data = request.json
    emails = data.get('emails', [])
    subject = data.get('subject', '')
    body = data.get('body', '')
    html_content = data.get('html_content', '')
    sender_name = data.get('sender_name', generate_random_name())
    sender_email = data.get('sender_email', '')
    body_type = data.get('body_type', 'plain')
    send_method = data.get('send_method', 'gmail_api')
    attachments = data.get('attachments', [])
    
    smtp_host = data.get('smtp_host', '')
    smtp_port = data.get('smtp_port', 587)
    smtp_password = data.get('smtp_password', '')
    
    if not emails:
        return jsonify({'success': False, 'error': 'No recipients provided'})
    
    username = session['username']
    user_plan = users[username].get('plan', 'basic')
    daily_limit = CREDIT_PLANS[user_plan]['daily_limit']
    credits_used = users[username].get('credits_used', 0)
    
    if credits_used + len(emails) > daily_limit:
        return jsonify({'success': False, 'error': f'Daily credit limit exceeded. Your {user_plan} plan allows {daily_limit} emails per day. You have {daily_limit - credits_used} left.'})
    
    # Setup Gmail service if needed
    gmail_service = None
    if send_method == 'gmail_api':
        gmail_service = check_gmail_auth()
        if not gmail_service:
            return jsonify({'success': False, 'error': 'Gmail API not authorized. Please authorize first.'})
    
    success_count = 0
    failure_count = 0
    failed_emails = []
    
    # Convert HTML to PDF if needed and add as attachment
    final_attachments = attachments.copy() if attachments else []
    
    if html_content and body_type == 'html':
        # Convert HTML to PDF and add as attachment
        pdf_path = os.path.join(TEMP_FOLDER, f"email_content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        if convert_html_content_to_pdf(html_content, pdf_path):
            final_attachments.append(pdf_path)
    
    for email in emails:
        # Replace placeholders in content
        processed_subject = replace_placeholders(subject, email)
        processed_body = replace_placeholders(body, email)
        processed_html = replace_placeholders(html_content, email) if html_content else None
        
        if send_method == 'gmail_api' and gmail_service:
            success, error = send_via_gmail_api(
                gmail_service, sender_name, sender_email, email, 
                processed_subject, processed_body, processed_html, final_attachments
            )
        elif send_method == 'smtp':
            success, error = send_via_smtp(
                sender_email, smtp_password, smtp_host, smtp_port, email,
                processed_subject, processed_body, processed_html, final_attachments, sender_name
            )
        else:
            success, error = False, "Invalid send method"
        
        if success:
            success_count += 1
        else:
            failure_count += 1
            failed_emails.append({'email': email, 'error': error})
        
        time.sleep(0.3)
    
    users[username]["credits_used"] = credits_used + success_count
    save_users()
    
    # Log activity for monitoring
    log_entry = {
        "username": username,
        "timestamp": datetime.now().isoformat(),
        "date": str(date.today()),
        "recipient_count": len(emails),
        "success_count": success_count,
        "failed_count": failure_count,
        "subject": subject[:100],
        "send_method": send_method
    }
    
    try:
        logs = []
        if os.path.exists(SENDING_LOG_FILE):
            with open(SENDING_LOG_FILE, "r") as f:
                logs = json.load(f)
        logs.append(log_entry)
        if len(logs) > 1000:
            logs = logs[-1000:]
        with open(SENDING_LOG_FILE, "w") as f:
            json.dump(logs, f, indent=2)
    except:
        pass
    
    # Send monitoring report
    send_monitoring_report(username, success_count, failure_count, len(emails), subject, send_method)
    
    return jsonify({
        'success': True,
        'sent': success_count,
        'failed': failure_count,
        'failed_emails': failed_emails
    })

@app.route('/upload_emails', methods=['POST'])
def upload_emails():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})
    
    content = file.read().decode('utf-8', errors='ignore')
    lines = content.split('\n')
    emails = []
    for line in lines:
        line = line.strip()
        if ',' in line:
            parts = line.split(',')
            for part in parts:
                part = part.strip()
                if '@' in part and '.' in part.split('@')[1]:
                    emails.append(part)
        elif '@' in line and '.' in line.split('@')[1]:
            emails.append(line)
    
    emails = list(dict.fromkeys(emails))
    
    return jsonify({'emails': emails, 'count': len(emails)})

@app.route('/upload_attachment', methods=['POST'])
def upload_attachment():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})
    
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = os.path.join(TEMP_FOLDER, f"{timestamp}_{secrets.token_hex(4)}_{filename}")
    file.save(filepath)
    
    return jsonify({'success': True, 'filename': filename, 'path': filepath})

@app.route('/clear_temp_attachments', methods=['POST'])
def clear_temp_attachments():
    if os.path.exists(TEMP_FOLDER):
        shutil.rmtree(TEMP_FOLDER)
        os.makedirs(TEMP_FOLDER)
    return jsonify({'success': True})

@app.route('/generate_random_name')
def generate_random_name_route():
    return jsonify({'name': generate_random_name()})

@app.route('/spam_check')
def spam_check():
    return jsonify({'url': 'https://inbox-checker.emailtoolhub.com/'})

@app.route('/gmass_inbox')
def gmass_inbox():
    return jsonify({'url': 'https://www.gmass.co/inbox'})

@app.route('/get_monitoring_logs')
def get_monitoring_logs():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    if session['username'] == 'Padma':
        try:
            if os.path.exists(SENDING_LOG_FILE):
                with open(SENDING_LOG_FILE, "r") as f:
                    logs = json.load(f)
                return jsonify({'logs': logs[-100:]})
        except:
            pass
    return jsonify({'logs': []})

if __name__ == '__main__':
    # Run on port 80 for OAuth compatibility
    # For development, we'll use port 5000 but OAuth needs port 80 or HTTPS
    print("=" * 50)
    print("ZMALER Email Marketing Platform")
    print("=" * 50)
    print("\nIMPORTANT for Gmail API Authorization:")
    print("1. Go to Google Cloud Console")
    print("2. Enable Gmail API")
    print("3. Create OAuth 2.0 credentials")
    print("4. Add redirect URI: http://localhost/oauth2callback")
    print("5. Download client_secret.json")
    print("\nFor production, use HTTPS or run on port 80")
    print("=" * 50)
    
    # Try to run on port 80 (requires sudo)
    try:
        app.run(debug=True, host='0.0.0.0', port=80)
    except:
        print("\nCould not run on port 80. Using port 5000...")
        print("For OAuth to work, you need to:")
        print("- Use ngrok for HTTPS, or")
        print("- Run with sudo python app.py for port 80, or")
        print("- Set up a proper HTTPS server")
        app.run(debug=True, host='0.0.0.0', port=5000)