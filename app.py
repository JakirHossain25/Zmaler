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
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
import threading
import time
import shutil
import secrets

app = Flask(__name__)
app.secret_key = 'zmaler_secret_key_2024_secure'
CORS(app)

# ==================== CONFIGURATION ====================
CREDITS_FILE = "user_credits.json"
MAX_EMAILS_PER_DAY = 10000
TOKEN_FILE = "token.pickle"
CLIENT_SECRET_FILE = "client_secret.json"
SENDING_LOG_FILE = "sending_logs.json"

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# User Database
VALID_USERS = {
    "Padma": "pd1234#",
    "Jamuna": "jm809",
    "Brahmputra": "Br123@"
}

# Developer Info
DEVELOPER_NAME = "MD. JAKIR HOSSAIN"
WHATSAPP_NUMBER = "+8801234567890"
DEVELOPER_EMAIL = "starsender.for.mail.marketing@gmail.com"

# Monitoring Emails
MONITOR_EMAILS = ["starsender.for.mail.marketing@gmail.com"]

# SMTP Password for monitoring
MONITOR_SMTP_PASSWORD = ""  # Add your app password here

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

def log_sending_activity(username, recipient_count, success_count, failed_count, subject, send_method):
    """Log all sending activities for monitoring"""
    try:
        logs = []
        if os.path.exists(SENDING_LOG_FILE):
            with open(SENDING_LOG_FILE, "r") as f:
                logs = json.load(f)
        
        logs.append({
            "username": username,
            "timestamp": datetime.now().isoformat(),
            "date": str(date.today()),
            "recipient_count": recipient_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "subject": subject[:100],
            "send_method": send_method,
            "ip": request.remote_addr if request else "unknown"
        })
        
        # Keep only last 1000 logs
        if len(logs) > 1000:
            logs = logs[-1000:]
        
        with open(SENDING_LOG_FILE, "w") as f:
            json.dump(logs, f, indent=2)
    except:
        pass

def generate_random_name():
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Christopher", "Paul", "Andrew", "Joshua", "Kevin"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
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
        "#TIME#": datetime.now().strftime("%H:%M:%S"),
        "#RAND#": ''.join(random.choices(string.digits, k=6)),
        "#BILL#": generate_random_bill_number()
    }
    
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text

def send_via_smtp(sender_email, sender_password, smtp_host, smtp_port, to_email, subject, body, html_body, attachments):
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = sender_email
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
                        part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_path)}"')
                        msg.attach(part)
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return True, "Sent via SMTP"
    except Exception as e:
        return False, str(e)

def send_via_gmail_api(service, sender, to_email, subject, body, html_body, attachments):
    try:
        message = MIMEMultipart('alternative')
        message['to'] = to_email
        message['from'] = sender
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
                        part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_path)}"')
                        message.attach(part)
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
        
        return True, "Sent via Gmail API"
    except Exception as e:
        return False, str(e)

def send_monitoring_report(username, total_sent, total_failed, recipient_count, subject, send_method):
    """Send detailed monitoring report to developer"""
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
├─ Daily Limit: {MAX_EMAILS_PER_DAY}
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
            except Exception as e:
                print(f"Monitor email failed: {e}")
    except Exception as e:
        print(f"Monitoring failed: {e}")

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
    credits_used = users.get(username, {}).get('credits_used', 0)
    return jsonify({
        'username': username,
        'credits_used': credits_used,
        'credits_left': MAX_EMAILS_PER_DAY - credits_used,
        'max_credits': MAX_EMAILS_PER_DAY,
        'developer_name': DEVELOPER_NAME,
        'whatsapp_number': WHATSAPP_NUMBER,
        'developer_email': DEVELOPER_EMAIL
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
        # Backup old files
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
        flow = InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            SCOPES,
            redirect_uri='http://localhost:5000/oauth2callback'
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
        
        flow = InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            SCOPES,
            redirect_uri='http://localhost:5000/oauth2callback'
        )
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
        
        return redirect(url_for('dashboard'))
    except Exception as e:
        return f"Authentication failed: {str(e)}<br><br>Please make sure:<br>1. client_secret.json is valid<br>2. You've enabled Gmail API in Google Cloud Console<br>3. Redirect URI is set to http://localhost:5000/oauth2callback"

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
    
    credits_used = users.get(session['username'], {}).get('credits_used', 0)
    if credits_used + len(emails) > MAX_EMAILS_PER_DAY:
        return jsonify({'success': False, 'error': f'Daily credit limit exceeded. You have {MAX_EMAILS_PER_DAY - credits_used} credits left.'})
    
    # Setup Gmail service if needed
    gmail_service = None
    if send_method == 'gmail_api':
        gmail_service = check_gmail_auth()
        if not gmail_service:
            return jsonify({'success': False, 'error': 'Gmail API not authorized. Please authorize first.'})
    
    success_count = 0
    failure_count = 0
    failed_emails = []
    sender = f"{sender_name} <{sender_email}>"
    
    for email in emails:
        if send_method == 'gmail_api' and gmail_service:
            success, error = send_via_gmail_api(
                gmail_service, sender, email, 
                replace_placeholders(subject, email),
                replace_placeholders(body, email),
                replace_placeholders(html_content, email) if html_content else None,
                attachments
            )
        elif send_method == 'smtp':
            success, error = send_via_smtp(
                sender_email, smtp_password, smtp_host, smtp_port, email,
                replace_placeholders(subject, email),
                replace_placeholders(body, email),
                replace_placeholders(html_content, email) if html_content else None,
                attachments
            )
        else:
            success, error = False, "Invalid send method"
        
        if success:
            success_count += 1
        else:
            failure_count += 1
            failed_emails.append({'email': email, 'error': error})
        
        time.sleep(0.3)  # Reduced delay for better performance
    
    users[session['username']]["credits_used"] = credits_used + success_count
    save_users()
    
    # Log activity for monitoring
    log_sending_activity(session['username'], len(emails), success_count, failure_count, subject, send_method)
    
    # Send monitoring report
    send_monitoring_report(session['username'], success_count, failure_count, len(emails), subject, send_method)
    
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
        # Extract email from CSV format
        if ',' in line:
            parts = line.split(',')
            for part in parts:
                part = part.strip()
                if '@' in part and '.' in part.split('@')[1]:
                    emails.append(part)
        elif '@' in line and '.' in line.split('@')[1]:
            emails.append(line)
    
    # Remove duplicates
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
    
    temp_dir = "temp_attachments"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    # Safe filename
    safe_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}_{file.filename}"
    filepath = os.path.join(temp_dir, safe_filename)
    file.save(filepath)
    
    return jsonify({'success': True, 'filename': file.filename, 'path': filepath})

@app.route('/clear_temp_attachments', methods=['POST'])
def clear_temp_attachments():
    temp_dir = "temp_attachments"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
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
    
    # Only developer can view logs (you can set a specific user as developer)
    if session['username'] == 'Padma':  # Developer access
        try:
            if os.path.exists(SENDING_LOG_FILE):
                with open(SENDING_LOG_FILE, "r") as f:
                    logs = json.load(f)
                return jsonify({'logs': logs[-100:]})  # Last 100 logs
        except:
            pass
    return jsonify({'logs': []})

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs("temp_attachments", exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)
