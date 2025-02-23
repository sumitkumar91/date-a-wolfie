import os
import eventlet
eventlet.monkey_patch()

import logging
logging.basicConfig(level=logging.DEBUG)

from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
from flask_mysqldb import MySQL
from MySQLdb.cursors import DictCursor
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "sbu_dating_secret_key"
socketio = SocketIO(app)

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'pass'
app.config['MYSQL_DB'] = 'date-a-wolfie'
mysql = MySQL(app)

# Configure upload folder and allowed extensions for profile pictures
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Routes

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('matches'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        logging.debug("Login attempt for email: %s", email)
        
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("SELECT * FROM Users WHERE email = %s AND password = %s", (email, password))
        user = cur.fetchone()
        cur.close()
        
        if user:
            session['user_id'] = user['id']
            logging.debug("User logged in: %s", user['id'])
            return redirect(url_for('matches'))
        else:
            logging.error("Invalid login attempt for email: %s", email)
            return "Invalid email or password"
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        gender = request.form['gender']
        major = request.form['major']
        clubs = request.form['clubs']
        bio = request.form['bio']
        looking_for = request.form['looking_for']
        sexual_orientation = request.form['sexual_orientation']
        interests = request.form['interests']

        # Verify SBU email
        if not email.endswith('@stonybrook.edu'):
            logging.error("Signup error: Non-SBU email used: %s", email)
            return "Please use an SBU email address."

        # Handle profile picture upload
        file = request.files.get('profile_picture')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)
            logging.debug("Profile picture saved to: %s", save_path)
        else:
            filename = 'default.png'
        
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("SELECT * FROM Users WHERE email = %s", (email,))
        existing_user = cur.fetchone()
        if existing_user:
            cur.close()
            logging.error("Signup error: Email already exists: %s", email)
            return "Email already exists."

        # Insert new user into Users table (without profile picture column)
        cur.execute(
            "INSERT INTO Users (name, email, password, gender, major, clubs, bio, looking_for, sexual_orientation, interests) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (name, email, password, gender, major, clubs, bio, looking_for, sexual_orientation, interests)
        )
        mysql.connection.commit()
        new_id = cur.lastrowid
        cur.close()
        
        # Insert profile picture info into Profile_Pictures table
        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO Profile_Pictures (user_id, filename, uploaded_at) VALUES (%s, %s, %s)",
            (new_id, filename, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        mysql.connection.commit()
        cur.close()

        session['user_id'] = new_id
        logging.debug("New user created with id: %s", new_id)
        return redirect(url_for('matches'))
    return render_template('signup.html')

@app.route('/matches')
def matches():
    if 'user_id' not in session:
        logging.error("Access to matches without valid session")
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor(DictCursor)
    cur.execute("SELECT * FROM Users WHERE id = %s", (session['user_id'],))
    current_user = cur.fetchone()
    if not current_user:
        cur.close()
        logging.error("Current user not found for session id: %s", session['user_id'])
        return redirect(url_for('login'))
    
    cur.execute("SELECT * FROM Users WHERE id != %s", (session['user_id'],))
    all_users = cur.fetchall()
    cur.close()

    matches = []
    current_user_interests = [i.strip() for i in current_user['interests'].split(',')]
    current_user_gender = current_user['gender']
    current_user_sexual_orientation = current_user['sexual_orientation']

    for user in all_users:
        user_interests = [i.strip() for i in user['interests'].split(',')]
        common_interests = set(current_user_interests) & set(user_interests)
        # Adjust condition as needed (currently always true)
        if len(common_interests) >= 0:
            if current_user_sexual_orientation == 'Straight':
                if user['gender'] != current_user_gender and user['sexual_orientation'] == 'Straight':
                    matches.append(user)
            elif current_user_sexual_orientation in ['Gay', 'Lesbian']:
                if user['gender'] == current_user_gender and user['sexual_orientation'] in ['Gay', 'Lesbian']:
                    matches.append(user)
            elif current_user_sexual_orientation == 'Bisexual':
                if user['sexual_orientation'] in ['Straight', 'Gay', 'Lesbian', 'Bisexual']:
                    matches.append(user)

    # For each match, retrieve the profile picture from Profile_Pictures table
    for user in matches:
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("SELECT filename FROM Profile_Pictures WHERE user_id = %s", (user['id'],))
        picture = cur.fetchone()
        cur.close()
        if picture:
            user['profile_picture'] = picture['filename']
        else:
            user['profile_picture'] = 'default.png'
    logging.debug("Matches found: %s", matches)
    return render_template('matches.html', matches=matches)

@app.route('/send_interested_request/<int:match_id>', methods=['POST'])
def send_interested_request(match_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not logged in"})

    sender_id = session['user_id']
    receiver_id = match_id

    cur = mysql.connection.cursor(DictCursor)
    cur.execute("SELECT * FROM Interested_Requests WHERE sender_id = %s AND receiver_id = %s", (sender_id, receiver_id))
    exists = cur.fetchone()
    if exists:
        cur.close()
        logging.error("Interested request already sent from %s to %s", sender_id, receiver_id)
        return jsonify({"success": False, "error": "Request already sent"})

    cur.execute(
        "INSERT INTO Interested_Requests (sender_id, receiver_id, timestamp) VALUES (%s, %s, %s)",
        (sender_id, receiver_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    mysql.connection.commit()
    cur.close()

    logging.debug("Interested request sent from %s to %s", sender_id, receiver_id)
    socketio.emit('interested_request', {
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }, room=str(receiver_id))
    return jsonify({"success": True})

@app.route('/chat/<int:receiver_id>')
def chat(receiver_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cur = mysql.connection.cursor(DictCursor)
    cur.execute("SELECT * FROM Users WHERE id = %s", (receiver_id,))
    receiver = cur.fetchone()
    cur.close()
    if not receiver:
        logging.error("Chat receiver not found: %s", receiver_id)
        return redirect(url_for('matches'))
    return render_template('chat.html', receiver=receiver)

@app.route('/get_messages/<int:receiver_id>')
def get_messages(receiver_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    sender_id = session['user_id']
    cur = mysql.connection.cursor(DictCursor)
    cur.execute(
        "SELECT * FROM Messages WHERE (sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s) ORDER BY timestamp ASC",
        (sender_id, receiver_id, receiver_id, sender_id)
    )
    messages = cur.fetchall()
    cur.close()
    
    formatted_messages = []
    for msg in messages:
        formatted_messages.append({
            'sender': msg['sender_id'],
            'receiver': msg['receiver_id'],
            'message': msg['message'],
            'timestamp': msg['timestamp'].strftime("%Y-%m-%d %H:%M:%S") if isinstance(msg['timestamp'], datetime) else msg['timestamp']
        })
    logging.debug("Retrieved messages between %s and %s: %s", sender_id, receiver_id, formatted_messages)
    return jsonify({'messages': formatted_messages})

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# Socket.IO Event Handlers

@socketio.on('join')
def handle_join(data):
    user_id = data.get('user_id')
    room = str(user_id)
    join_room(room)
    app.logger.debug("User %s joined room %s", user_id, room)

@socketio.on('message')
def handle_message(data):
    app.logger.debug("Received data from client: %s", data)
    with app.app_context():
        try:
            sender_id = data['sender']
            receiver_id = data['receiver']
            message = data['message']
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            app.logger.debug("Inserting message: sender=%s, receiver=%s, message=%s, timestamp=%s",
                             sender_id, receiver_id, message, timestamp)
            
            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO Messages (sender_id, receiver_id, message, timestamp) VALUES (%s, %s, %s, %s)",
                (sender_id, receiver_id, message, timestamp)
            )
            mysql.connection.commit()
            app.logger.debug("Message inserted into DB successfully.")
        except Exception as e:
            app.logger.error("Error inserting message into DB: %s", e)
        finally:
            try:
                cur.close()
            except Exception as e:
                app.logger.error("Error closing cursor: %s", e)
    
    app.logger.debug("Emitting message to rooms %s and %s", str(sender_id), str(receiver_id))
    emit('message', {'sender': sender_id, 'message': message, 'timestamp': timestamp}, room=str(sender_id))
    emit('message', {'sender': sender_id, 'message': message, 'timestamp': timestamp}, room=str(receiver_id))

if __name__ == '__main__':
    socketio.run(app, debug=True)
