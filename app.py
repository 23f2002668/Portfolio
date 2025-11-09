from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
from passlib.hash import sha256_crypt
from flask_mail import Mail, Message
from flask_pymongo import PyMongo
from flask_cors import CORS
from urllib.parse import quote_plus
import os, certifi, sqlite3, threading
from dotenv import load_dotenv
from datetime import datetime
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64, os, json

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
CORS(app)

# MongoDB Atlas URI
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

encoded_password = quote_plus(password)

app.config["MONGO_URI"] = f"mongodb+srv://{username}:{encoded_password}@portfolio.rl5on7r.mongodb.net/Portfolio"
mongo = PyMongo(app, tlsCAFile=certifi.where())

# Access the 'contacts' collection
contacts_collection = mongo.db.Contacts     # mongo.db.Contacts --> Here Contacts is the name filled in 'Contacts' field in Create Database


# Gmail API global OAuth credentials
CREDENTIALS = {
    "installed": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "auth_uri": os.getenv("GOOGLE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
        "token_uri": os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uris": ["http://localhost"]
    }
}

SCOPES = ['https://www.googleapis.com/auth/gmail.send']


# Email Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Mail Provider
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")  # Gmail App Password
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER")
mail = Mail(app)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/submit_contact', methods=['GET', 'POST'])
def submit_contact():
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        subject = data.get('subject')
        message = data.get('message')

        print(name, email, subject, message)

        if not all([name, email, subject, message]):
            return jsonify({
                'message': 'All fields are required.'
            }), 400

        # Insert Data Into DataBase
        db_thread = threading.Thread(target=InsertIntoDataBase, args=(name, email, subject, message))
        db_thread.start()

        send_email(email, subject, message)

        # Send Email To User
        user_thread = threading.Thread(target=SendEmailToUser, args=(name, email, subject, message))
        user_thread.start()

        # Send Email To Me
        my_thread = threading.Thread(target=SendEmailToMe, args=(name, email, subject, message))
        my_thread.start()

        # Join threads to ensure they finish before app shutdown
        db_thread.join()
        user_thread.join()
        my_thread.join()

        return jsonify({
            'message': 'Thank you for your message! Your response has been recorded successfully. I will get back to you soon.'
        })

    except Exception as e:
        print(f"Error processing contact form: {str(e)}")
        return jsonify({
            'message': 'Sorry, there was an error sending your message. Please try again later.'
        }), 500


def InsertIntoDataBase(name, email, subject, message):
    contacts_collection.insert_one({
        "name": name,
        "email": email,
        "subject": subject,
        "message": message
    })

def SendEmailToUser(name, email, subject, message):
    msg = Message("Confirmation of Message Received",
                  sender=os.getenv("MAIL_DEFAULT_SENDER"),
                  recipients=[email])
    msg.body = f"""Hello {name},
        Myself Shahzada Moon and I hope this message finds you in good health and high spirits. 

        Thank you for reaching out to me via my portfolio. This email is to confirm that I have successfully received your message with the following details:
        
        Subject: {subject}\n
        Message: {message}
        
        I will review your query carefully and you can expect a personalized response from me as soon as possible. Your interest and time are highly appreciated.
        
        In the meantime, I wish you the very best for your health and your ongoing work.
        
        Warm regards,
        Shahzada Moon
        Data Scienctist, Web Developer & System Administrator
        """

    mail.send(msg)
    print("Mail sent successfully !")
    return "Mail Sent Successfully !"


def SendEmailToMe(user_name, user_email, subject, message):
    msg = Message('Regarding viewer query',
                  sender=os.getenv("MAIL_DEFAULT_SENDER"),
                  recipients=os.getenv("MAIL_DEFAULT_SENDER"))
    msg.body = f"""Hey Shahzada Moon! A new viewer has left a message for you. Please take a look on the message.
    \nName : {user_name} 
    \nEmail : {user_email} 
    \nSubject : {subject} 
    \nMessage : {message}"""

    mail.send(msg)
    print("Mail sent successfully !")
    return "Mail Sent Successfully !"


def send_email(to_email, subject, message):
    try:
        flow = Flow.from_client_config(CREDENTIALS, SCOPES)
        creds = flow.run_local_server(port=0)  # Authorize once locally
        service = build('gmail', 'v1', credentials=creds)

        message = MIMEText(message_text)
        message['to'] = to_email
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        sent = service.users().messages().send(
            userId="me",
            body={'raw': raw}
        ).execute()

        print(f"Email sent successfully! Message ID: {sent['id']}")
        return True
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return False



if __name__ == '__main__':
    app.debug = True
    port = int(os.environ.get("PORT", 5000))  # 5000 for local development
    app.run(host="0.0.0.0", port=port)
