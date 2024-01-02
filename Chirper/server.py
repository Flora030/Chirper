import bcrypt
import secrets
from pymongo import MongoClient
from flask import Flask, render_template, request, redirect, url_for, make_response, escape, jsonify, abort, flash
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from werkzeug.utils import secure_filename
from PIL import Image
import os
import threading
from flask_socketio import SocketIO, send, emit
import json
from flask_mail import Mail, Message
import uuid
import time
from itsdangerous import SignatureExpired
from itsdangerous import URLSafeTimedSerializer
from config import setVar
from flask_limiter.util import get_remote_address

#1/1/2023

app = Flask(__name__)

socketio = SocketIO(app, cors_allowed_origins="*")

connections=[]

request_count = {}
limit = 50
time_window = 10
blocked_ips = {}

client = MongoClient("mongodb://mongo:27017/")

db = client["database"]  

#Stores emails and passwords {email, password', salt'} 
user_db = db["user_db"]  

#Stores authentication tokens {token, email}
auth_tokens = db["auth_tokens"]   

#Stores Post History {postID, email, title, description, question type, answer, image}
post_collection = db["post_collection"]

#Stores Grades {email, title, description, user_answer, expected_answer, score}
grade_collection = db["grade_collection"]

#Store all answers submitted for a question until timer for question is up. 
answerStorage = {}

#Websocket
connections=[]

app.secret_key = "secret_Key"
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

#Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
setVar()
app.config['MAIL_USERNAME'] = 'studentcse3122023@gmail.com'
app.config['MAIL_PASSWORD'] = 'kbfb xckc cbzy xujf'
#app.config['MAIL_EMAIL'] = os.environ.get('MAIL_EMAIL')
#app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
mail = Mail(app)  

@app.route('/') 
def welcomePage():
    return render_template('welcome.html')

@app.route('/homepage')
def homepage():
    token = request.cookies.get('auth_token')
    doc = None
    if token:
        for userInfo in auth_tokens.find({}):
            if bcrypt.checkpw(token.encode('utf-8'),userInfo['token']):
                doc = userInfo
                break
    if doc:
        return render_template('index.html')
    flash('Register or login first')
    return redirect("/")

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')

@app.route('/static/functions.js')
def functions():
    file = open("static/functions.js",encoding="utf-8")
    file = file.read()
    response = make_response(file)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.mimetype = "text/javascript"
    return response

@app.route('/static/style.css')
def style():
    file = open("static/style.css",encoding="utf-8")
    file = file.read()
    response = make_response(file)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.mimetype = "text/css"
    return response

@app.route('/get-email')
#Displays email
def get_email():
    token = request.cookies.get('auth_token')
    doc = None
    for userInfo in auth_tokens.find({}):
        if token:
            if bcrypt.checkpw(token.encode('utf-8'),userInfo['token']):
                doc = userInfo
        else:
            current_email = None
    if doc:
        current_email = doc['email']
        email = user_db.find_one({'email': current_email})
        verified = False
        if email['verified']:
            verified = True
        return jsonify({'email': doc['email'], 'verified': verified})
    return jsonify({'email': None})

@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        #HTML injection, escape all HTML characters in the email.
        email = escape(request.form['email']) #email
        password = request.form['password']
        #Check if email is already exists
        existing_email = user_db.find_one({'email': email})
        #Notify if the email is already taken
        if existing_email:
            flash("Email already used")
            response = make_response(render_template('register.html'))
            return response
        else:
            #Add email to database
            salt = bcrypt.gensalt()
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
            token = serializer.dumps(email, salt='email-confirm')
            user_db.insert_one({'email': email, 'password': hashed_password, 'verified': False})
            #Send verification email
            message = Message('Confirm Your Email', sender='studentcse3122023@gmail.com', recipients=[email])
            confirm_email_url = url_for('confirm_email', token=token, _external=True)
            message.body = 'Your link is {}'.format(confirm_email_url)
            mail.send(message)
            flash("Successfully register")
            return redirect("/")

def confirm_token(token):
    try:
        decrypt_email = serializer.loads(token, salt='email-confirm', max_age=3600)
        return decrypt_email
    except Exception:
        flash('The email comfirmation link is invalid or has expired')
        return redirect(url_for('resend_email'))
    
@app.route('/confirm-email/<token>')
def confirm_email(token):
    email = confirm_token(token)
    if email:
        document = user_db.find_one({'email': email})
        if document:
            verify = document.get("verified")
            if verify == False:
                user_db.update_one({'email': email}, { '$set': {'verified': True}})
                flash("Email successfully verified")
                return redirect("/")
            elif verify == True:
                flash("Email is already verified")
                return redirect("/")
        else:
            flash("Email not found")
            return redirect("/")
        
@app.route('/login', methods=['POST'])
def login():
    try:
        email = request.form['email']
        password = request.form['password']
        user_data = user_db.find_one({"email": email})
        if user_data:
            hashed_password = bcrypt.checkpw(password.encode('utf-8'), user_data['password'])
            if hashed_password:
                token = secrets.token_hex(32).encode('utf-8')
                hashed_token = bcrypt.hashpw(token, bcrypt.gensalt())
                if auth_tokens.find_one({'email' : email}) == None:
                    auth_tokens.insert_one({'token': hashed_token, 'email': email})
                else:
                    auth_tokens.update_one({'email' : email} , { "$set" : {'token' : hashed_token}})
                response = make_response(redirect(url_for('homepage')))
                response.set_cookie("auth_token", token, max_age=3600, httponly=True)
                return response
            else:
                flash("Wrong Credentials")
                response = make_response(render_template('login.html'))
                return response
        else:
            flash("Wrong Credentials")
            response = make_response(render_template('login.html'))
            return response
    except Exception:
        return response, 400

@app.route('/forgot-password', methods=['GET'])
def forgot_password():
    return render_template('forgotPassword.html')

@app.route('/send-reset-password-link', methods=['POST'])
def send_reset_password_link():
    email = request.form["email"]
    doc = user_db.find_one({"email":email})
    if doc:
        token = serializer.dumps(email, salt='reset-password')
        reset_url = url_for('reset_password', token=token, _external=True)
        message = Message('Confirm Your Email', sender='studentcse3122023@gmail.com', recipients=[email])
        message.body = 'Your link is {}'.format(reset_url)
        mail.send(message)
    flash('If an account with that email exists, a password reset link has been sent.')
    return redirect(url_for('login'))

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        decrypt_email = serializer.loads(token, salt='reset-password', max_age=3600)
    except:
        flash('The password reset link is invalid or has expired')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        #Set new password
        new_password = request.form['new_password']
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), salt)
        result = user_db.update_one({'email': decrypt_email}, {'$set': {'password': hashed_password}})
        if result.matched_count:
            flash('Your password has been updated')
            return redirect(url_for('login'))
        else:
            flash('Email not found')
            return redirect(url_for('forgot_password'))
    return render_template('resetPassword.html', token=token)
        
@app.route('/post-history')
def post_history():
    posts = list(post_collection.find({}))
    for post in posts:
        post['_id'] = str(post['_id'])
    return jsonify(posts)

class PostForm(FlaskForm):
    image = FileField('Image', validators=[FileRequired()])

def save_image(image, id):
    image_folder = os.path.join(app.root_path, 'static/images')
    file_extension = os.path.splitext(image.filename)[1]
    filename = secure_filename(id+file_extension)
    image_path = os.path.join(image_folder, filename)
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)
    try:
        img = Image.open(image.stream)
        img.save(image_path)
        img.close()
        return os.path.join('/static/images', filename)
    except Exception as e:
        print(f"Error occurred during saving image: {str(e)}")
        return None
    
@app.route('/save-image-websocket', methods=['POST'])
def save_image_websocket():
    id = secrets.token_hex(32)
    if 'image' in request.files:
        image = request.files['image']
        if image.filename != '':
            image_path = save_image(image, id)
            return jsonify({'image_path': image_path, 'postID':id})
    return jsonify({'image_path': "", 'postID': id})

@app.route('/my-scores')
def my_scores():
    token = request.cookies.get('auth_token')
    doc = None
    for userInfo in auth_tokens.find({}):
        if token:
            if bcrypt.checkpw(token.encode('utf-8'),userInfo['token']):
                doc = userInfo
        else:
            current_email = None
    if doc:
        current_email = doc['email']
    else: 
        current_email = None

    grades = list(grade_collection.find({"email":current_email}))
    attempts = len(grades)
    corrects = len([grade for grade in grades if grade['score'] == 1])
    return render_template('my_scores.html', grades_list = grades, attempts = attempts, corrects = corrects)

@app.route('/my-questions')
def my_questions():
    print("311 /my-questions")
    token = request.cookies.get('auth_token')
    doc = None
    for userInfo in auth_tokens.find({}):
        if token:
            if bcrypt.checkpw(token.encode('utf-8'),userInfo['token']):
                doc = userInfo
        else:
            current_email = None
    if doc:
        current_email = doc['email']
    else: 
        current_email = None
    print(f"324 current_email '{current_email}' (Type: {type(current_email)})")
    grades = list(grade_collection.find({"creater":current_email}))
    print("326 grades", grades)
    grades_by_ids = {}
    for g in grades:
        id = g["question_id"]
        if id not in grades_by_ids:
            grades_by_ids[id] = {'questions': [], 'correct_count': 0, 'attempted_count': 0}

        grades_by_ids[id]['questions'].append(g)
        grades_by_ids[id]['attempted_count'] += 1

        if g['score'] == 1:
            grades_by_ids[id]['correct_count'] += 1
        print("336 grades_by_ids", grades_by_ids)
    return render_template('/my_questions.html', grades_list = grades_by_ids)

@app.route('/check')
def check():
    token = request.cookies.get('auth_token')
    print("341 token", token)
    doc = None
    for userInfo in auth_tokens.find({}):
        if token:
            if bcrypt.checkpw(token.encode('utf-8'),userInfo['token']):
                doc = userInfo
        else:
            current_email = None
    if doc:
        current_email = doc['email']
    else: 
        current_email = None

    postID = request.args.get('postID')
    postInfo = post_collection.find_one({"_id":postID})

    TimeUp = False
    answered = False
    Owner = False
    QuestionType = False

    timeLeft = postInfo.get("timeLeft")
    if timeLeft is None:
        pass
    elif timeLeft == "0":
        TimeUp = True

    if current_email in postInfo["answered"]:
        answered = True
    else:
        post_collection.update_one({"_id":postID}, { "$push": { "answered": current_email } })

    stored_email = postInfo["email"]

    if stored_email == current_email:
        Owner = True
    
    question_type = postInfo.get("question_type")
    if question_type:
        QuestionType = question_type

    response_data = {
        "answered": answered,
        "owner": Owner,
        "timeUp": TimeUp,
        "question_type": QuestionType
    }
    return jsonify(response_data)

@app.route('/logout', methods=['POST'])
def logout():
    # Clear the token cookie
    response = make_response(redirect("/"))
    response.set_cookie('auth_token', '', expires=0)  # Replace 'auth_token' with your cookie name
    return response

@app.errorhandler(429)
def ratelimit_error(e):
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    block_ip(ip_address)
    return "Too Many Requests", 429

def block_ip(ip_address):
    blocked_ips[ip_address] = time.time() + 30

@app.before_request
def limit_requests():
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    current_time = time.time()

    request_count[ip_address] = request_count.get(ip_address, [])

    while request_count[ip_address] and request_count[ip_address][0] < current_time - time_window:
        request_count[ip_address].pop(0)

    if len(request_count[ip_address]) >= limit:
        abort(429) 
    
    if ip_address in blocked_ips and blocked_ips[ip_address] > time.time():
        return "Too Many Requests", 429

    request_count[ip_address].append(current_time)

#-----------------------------------------------------WEBSOCKETS--------------------------------------------------------------
@socketio.on("connected")
def sendConnectedMessage():
    print("User has connected!")

#Send time updates to the clients
def timer(postID):
    duration = 20
    while duration:
        timeLeft = '{:02d} second'.format(duration)
        output = json.dumps({'postID':postID, 'timeLeft': timeLeft})
        socketio.emit('timeUpdateForClient', output)
        socketio.sleep(1)
        duration = duration -1
    post_collection.update_one({'_id' : postID}, { "$set": { "timeLeft": "0" } })
    socketio.emit('timeIsUp', {'message': 'Time is up!','postID': postID})

@socketio.on("questionSubmission")
def handleQuestion(question_JSON):
    #Do Question Parsing
    dict = json.loads(question_JSON) #Dictionary of all Post Form Values
    print("442 questionSubmission dict", dict)
    post_collection.insert_one(dict)
    output = json.dumps(dict)
    emit("questionSubmission",output,broadcast=True)
    id = dict.get("_id")
    socketio.start_background_task(timer, id)

answerStorage_lock = threading.Lock()
@socketio.on("submitAnswer")
def storeAnswer(postIDAndAnswer):
    dict = json.loads(postIDAndAnswer)
    email = dict['email']
    print("453 user who submit answer is ", email)
    postID = dict['postID']
    answer = dict['user_answer']
    newDictionary={'email' : email,'postID' : postID, 'user_answer' : answer}
    postInfo = post_collection.find_one({'_id' : postID})
    #Check if the user submitting the answer is the same as the creator of the question
    if email == postInfo.get('email'):
        return
    with answerStorage_lock:
        if postID in answerStorage:
            answerStorage[postID].append(newDictionary)
        else:
            answerStorage[postID] = [newDictionary]

@socketio.on("gradeQuestion")
def gradeQuestion(postID):
    with answerStorage_lock:
        if postID not in answerStorage:
            return
        answer_data = answerStorage.pop(postID, [])

    postInfo = post_collection.find_one({'_id' : postID})
    title = postInfo['title']
    description = postInfo['description']
    questionType = postInfo['question_type']
    expectedAnswer = postInfo['answer']
    creater = postInfo['email']
    question_id = postInfo['_id']

    for answer in answer_data:
        user_answer = answer['user_answer']
        score = 0

        print("490 user_answer and expectedAnswer", user_answer, expectedAnswer)
        if questionType == "Open Ended":
            try:
                if str(user_answer).isnumeric() and str(expectedAnswer).isnumeric():
                    score = 1 if int(user_answer) == int(expectedAnswer) else 0
                else:
                    score = 1 if user_answer.strip().lower() == expectedAnswer.strip().lower() else 0
            except ValueError:
                score = 0
        elif questionType == "Multiple Choice":
            try:
                score = 1 if user_answer == expectedAnswer else 0
            except ValueError:
                score = 0

        out = {
            'creater': creater,
            'email': answer['email'], 
            'title': title, 
            'description': description,
            'user_answer': user_answer, 
            'expected_answer': expectedAnswer, 
            'score': score,
            'question_id': question_id
        }
        grade_collection.insert_one(out)


if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=8080)
