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
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import time
import shutil
import secrets
from werkzeug.utils import secure_filename
import sys
import webbrowser
import threading

app = Flask(__name__)
app.secret_key = 'zmaler_secret_key_2024_secure'
CORS(app)

# ==================== CONFIGURATION ====================
CREDITS_FILE = "user_credits.json"
MAX_EMAILS_PER_DAY = 10000
TOKEN_FILE = "token.pickle"
CLIENT_SECRET_FILE = "client_secret.json"
TEMP_FOLDER = "temp_attachments"

# Create necessary folders
os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs("templates", exist_ok=True)

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
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Christopher", "Paul", "Andrew", "Joshua", "Kevin"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def generate_random_bill_number():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=13))

def replace_placeholders(text, email):
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
    
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text

def send_via_smtp(sender_email, sender_password, smtp_host, smtp_port, to_email, subject, body, html_body, attachments, sender_name):
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{sender_name} <{sender_email}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        if html_body:
            msg.attach(MIMEText(html_body, 'html'))
        
        if attachments:
            for file_path in attachments:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_path)}"')
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
        
        message.attach(MIMEText(body, 'plain'))
        if html_body:
            message.attach(MIMEText(html_body, 'html'))
        
        if attachments:
            for file_path in attachments:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_path)}"')
                        message.attach(part)
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
        
        return True, "Sent via Gmail API"
    except Exception as e:
        return False, str(e)

def get_gmail_service():
    """Desktop App flow - no HTTPS required"""
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
        sender_name = data.get('sender_name', generate_random_name())
        sender_email = data.get('sender_email', '')
        send_method = data.get('send_method', 'gmail_api')
        attachments = data.get('attachments', [])
        
        smtp_host = data.get('smtp_host', '')
        smtp_port = data.get('smtp_port', 587)
        smtp_password = data.get('smtp_password', '')
        
        if not emails:
            return jsonify({'success': False, 'error': 'No recipients provided'})
        
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
        
        for email in emails:
            processed_subject = replace_placeholders(subject, email)
            processed_body = replace_placeholders(body, email)
            processed_html = replace_placeholders(html_content, email) if html_content else None
            
            if send_method == 'gmail_api' and gmail_service:
                success, error = send_via_gmail_api(
                    gmail_service, sender_name, sender_email, email,
                    processed_subject, processed_body, processed_html, attachments
                )
            elif send_method == 'smtp':
                success, error = send_via_smtp(
                    sender_email, smtp_password, smtp_host, smtp_port, email,
                    processed_subject, processed_body, processed_html, attachments, sender_name
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
        
        for line in lines:
            line = line.strip()
            if ',' in line:
                for part in line.split(','):
                    part = part.strip()
                    if '@' in part and '.' in part.split('@')[1]:
                        emails.append(part.lower())
            elif '@' in line and '.' in line.split('@')[1]:
                emails.append(line.lower())
        
        emails = list(dict.fromkeys(emails))
        return jsonify({'emails': emails, 'count': len(emails)})
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
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = secure_filename(file.filename)
        filepath = os.path.join(TEMP_FOLDER, f"{timestamp}_{secrets.token_hex(4)}_{filename}")
        file.save(filepath)
        
        return jsonify({'success': True, 'filename': filename, 'path': filepath})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/clear_attachments', methods=['POST'])
def clear_attachments():
    try:
        if os.path.exists(TEMP_FOLDER):
            shutil.rmtree(TEMP_FOLDER)
            os.makedirs(TEMP_FOLDER)
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
    """Open browser after server starts"""
    time.sleep(1.5)
    webbrowser.open('http://localhost:5000')

if __name__ == '__main__':
    print("=" * 60)
    print("ZMALER - Email Marketing Platform")
    print("=" * 60)
    print("\n🔐 Login Credentials:")
    print("   ┌─────────────────┬─────────────┐")
    print("   │ Username        │ Password    │")
    print("   ├─────────────────┼─────────────┤")
    print("   │ Padma           │ pd1234#     │")
    print("   │ Jamuna          │ jm809       │")
    print("   │ Brahmputra      │ Br123@      │")
    print("   └─────────────────┴─────────────┘")
    print("\n" + "=" * 60)
    print("🌐 Server starting at: http://localhost:5000")
    print("📁 Make sure 'templates' folder has login.html and dashboard.html")
    print("=" * 60)
    print("\n✅ Server is running! Press Ctrl+C to stop.\n")
    
    # Open browser automatically
    threading.Thread(target=open_browser, daemon=True).start()
    
    app.run(debug=True, host='0.0.0.0', port=5000)