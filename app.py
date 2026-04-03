from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import json
import os
import base64
import random
import string
import re
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import threading
import time

app = Flask(__name__)
app.secret_key = 'star_sender_secret_key_2024'
CORS(app)

# Configuration
CREDITS_FILE = "user_credits.json"
MAX_EMAILS_PER_DAY = 10000
EXPIRATION_DATE = datetime(2026, 4, 5, 14, 59, 59)
TOKEN_FILE = "token.pickle"
CLIENT_SECRET_FILE = "client_secret.json"

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]

VALID_USERS = {
    "Padma": "pd1234#",
    "Jamuna": "jm809",
    "Brahmputra": "Br123@"
}

MONITOR_EMAILS = ["starsender.for.mail.marketing@gmail.com"]

TERMS = """TERMS AND CONDITIONS OF USE:

1. This software is intended solely for marketing or promotional purposes.
2. Users are requested not to use this software for any illegal activities.
3. The developer or publisher shall not be held responsible for any illegal activities.
4. The software must not be used to send spam or unsolicited messages.
5. Sending fake, fraudulent, or illegal messages is strictly prohibited.
6. Do not send viruses, malware, or harmful links.
7. Users must not harass, deceive, or harm others in any way.
8. Your user may be monitored and terminated if anything suspicious is found."""

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
    
    data = {user: {"password": password, "credits_used": 0, "last_date": today} 
            for user, password in VALID_USERS.items()}
    
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
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def generate_random_bill_number():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(13))

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
        "#RAND#": ''.join(random.choices(string.digits, k=6)),
        "#BILL#": generate_random_bill_number()
    }
    
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text

def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            return None
    
    return build('gmail', 'v1', credentials=creds)

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
        return jsonify({'success': True, 'message': 'Login successful'})
    return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/logout')
def logout():
    session.pop('username', None)
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
    credits_used = users.get(username, {}).get('credits_used', 0)
    return jsonify({
        'username': username,
        'credits_used': credits_used,
        'credits_left': MAX_EMAILS_PER_DAY - credits_used,
        'max_credits': MAX_EMAILS_PER_DAY
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
    if service:
        return jsonify({'authorized': True, 'logged_in': True})
    return jsonify({'authorized': False, 'logged_in': True})

@app.route('/get_auth_url')
def get_auth_url():
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri='http://localhost:5000/oauth2callback'
        )
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        session['state'] = state
        return jsonify({'auth_url': auth_url})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/oauth2callback')
def oauth2callback():
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri='http://localhost:5000/oauth2callback'
        )
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
        
        return redirect(url_for('dashboard'))
    except Exception as e:
        return f"Authentication failed: {str(e)}"

@app.route('/send_emails', methods=['POST'])
def send_emails():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    data = request.json
    emails = data.get('emails', [])
    subject = data.get('subject', '')
    body = data.get('body', '')
    html_content = data.get('html_content', '')
    sender_name = data.get('sender_name', generate_random_name())
    sender_email = data.get('sender_email', '')
    body_type = data.get('body_type', 'plain')
    
    if not emails:
        return jsonify({'success': False, 'error': 'No recipients provided'})
    
    credits_used = users.get(session['username'], {}).get('credits_used', 0)
    if credits_used + len(emails) > MAX_EMAILS_PER_DAY:
        return jsonify({'success': False, 'error': 'Daily credit limit exceeded'})
    
    service = get_gmail_service()
    if not service:
        return jsonify({'success': False, 'error': 'Gmail API not authorized'})
    
    success_count = 0
    failure_count = 0
    failed_emails = []
    
    for email in emails:
        try:
            message_text = replace_placeholders(body, email)
            current_subject = replace_placeholders(subject, email)
            sender = f"{sender_name} <{sender_email}>"
            
            message = MIMEMultipart()
            message['to'] = email
            message['from'] = sender
            message['subject'] = current_subject
            
            if body_type == 'html' and html_content:
                filled_html = replace_placeholders(html_content, email)
                msg = MIMEText(filled_html, 'html')
            else:
                msg = MIMEText(message_text, 'plain')
            message.attach(msg)
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
            
            success_count += 1
            users[session['username']]["credits_used"] = credits_used + success_count
            save_users()
            
        except Exception as e:
            failure_count += 1
            failed_emails.append({'email': email, 'error': str(e)})
        
        time.sleep(0.5)  # Rate limiting
    
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
    
    content = file.read().decode('utf-8')
    lines = content.split('\n')
    emails = [line.strip() for line in lines if line.strip() and '@' in line]
    
    return jsonify({'emails': emails, 'count': len(emails)})

@app.route('/generate_random_name')
def generate_random_name_route():
    return jsonify({'name': generate_random_name()})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)