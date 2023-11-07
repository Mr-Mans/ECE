import os
import nltk
import re
import string
import spacy
import secrets

nltk.download('punkt')
nltk.download('stopwords')


from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from flask_mail import Mail, Message

# Load the spaCy model
nlp = spacy.load("en_core_web_sm")



# Configure application
app = Flask(__name__)

app.run(debug=True)

# Configure session to use filesystem (instead of signed cookies)
# Make sessions permanent (session timeout will be applied)
app.config["SESSION_PERMANENT"] = True  
app.config["SESSION_TYPE"] = "filesystem"
# Set the session timeout to 2 hours
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=2)  
Session(app)


#Configure mail provider
app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'ess.comp.eva@gmail.com'
app.config['MAIL_PASSWORD'] = 'dhui dngq talv zqxu'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

#Create Flask-Mail instance
mail = Mail(app)


# Use SQLite database
db = SQL("sqlite:///ece.db")



@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response



def login_required(f):
   
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    if request.method == "POST":

        # Retrieve form data
        username = request.form.get("username")
        email = request.form.get("email").lower()
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        

        # Ensure passwords match
        if password != confirmation:
            return render_template("error.html", error_message="Confirmation password must match the password.", previous_page="/register")


        # Checking in the database if the username exists regardless of upper/lowercase - COLLATE NOCASE
        rows = db.execute("SELECT * FROM users WHERE username COLLATE NOCASE = ?", username)

        # Ensure username does not exist
        if len(rows) != 0:
            return render_template("error.html", error_message="This username already exists. <br> Kindly use a different name.", previous_page="/register")

        # Checking in the database if the email exists
        rows = db.execute("SELECT * FROM users WHERE email = ?", email)

        # Ensure email does not exist
        if len(rows) != 0:
            return render_template("error.html", error_message="This email is already associated with an account.<br> Please use a different email.", previous_page="/register")
            
        # Adding user to the database
        hash = generate_password_hash(password)
        result = db.execute("INSERT INTO users (username, email, password) VALUES(?, ?, ?)", username, email, hash)


        # Get the ID of the newly inserted user
        id = db.execute("SELECT last_insert_rowid()")
        user_id = id[0]['last_insert_rowid()']

        # Create a new session for the user to log them in
        session['user_id'] = user_id

        # After successful registration, you can redirect the user to the index page.
        flash("welcome!")
        return redirect("/")

    else:
        return render_template("register.html")



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached this page and wishes to post data to the server
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        
        # Query database for username regardless of upper/lowercase - COLLATE NOCASE
        rows = db.execute("SELECT * FROM users WHERE username COLLATE NOCASE = ?", username)

        # Ensure username exists and password is correct
        if len(rows) != 1:
            return render_template("error.html", error_message="Invalid name. <br> This account does not exist. <br> Kindly Register.", previous_page="/login")

        # Ensure password is correct
        if not check_password_hash(rows[0]["password"], password):
            return render_template("error.html", error_message="Invalid Password", previous_page="/login")


        # Remember which user has logged in
        session["user_id"] = rows[0]["userID"]

        # Redirect user to home page
        flash("welcome!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")



@app.route("/forgot_password", methods=['GET', 'POST'])
def forgot_password():

    if request.method == "POST":

        email = request.form.get("email").lower()

        # Check if the email exists in your database. This ensures tha the request is valid. 
        rows = db.execute("SELECT * FROM users WHERE email = ?", email)

        if len(rows) == 0:
            return render_template("error.html", error_message="This email does not exist. <br> Kindly use an existing email.", previous_page="/forgot_password")


        # Generate an 8-character reset code 
        reset_code = secrets.token_hex(4)

        # Set the expiration time to 2 hours from the current time
        expiration_time = datetime.now() + timedelta(hours=0.5)
  
        # sending the reset code to the user's email
        msg = Message(subject='Forgot Password Code', sender=('Thayu from ECE', 'ess.comp.eva@gmail.com'), recipients=[email])
        msg.html = f"Hello there,<br>Here is your Forgot Password Code: <br><strong>{reset_code}</strong> <br>This code shall expire after 30mins. <br><br> Regards,<br>~Essay complexity evaluator."
        mail.send(msg)


        # Store the reset code and its expiration time in the database
        # Check if the email exists in your table. If it does update the new reset_code and expiration _time. 
        reset = db.execute("SELECT * FROM reset_codes WHERE email = ?", email)
        if len(reset) == 0:
            db.execute("INSERT INTO reset_codes (email, code, expiration_time) VALUES (?, ?, ?)", email, reset_code, expiration_time)
        else:
            db.execute("UPDATE reset_codes SET code = ?, expiration_time = ? WHERE email = ?", reset_code, expiration_time, email)

        
        # Store the email in a session variable
        session["reset_email"] = email

        flash("A reset code has been sent to your email. Please check your email.")
        return render_template("reset_password.html")
        
    else:
        return render_template('forgot_password.html')     
    


@app.route("/reset_password", methods=['GET', 'POST'])
def reset_password():

    if request.method == "POST":

        # Retrieve the email from the session
        email = session["reset_email"]

        reset_code = request.form.get('reset_code')
        new_password = request.form.get('new_password')
        confirmation = request.form.get('confirmation')


        # Check if the reset code is valid and hasn't expired
        valid_reset = db.execute("SELECT * FROM reset_codes WHERE email = ? AND code = ?", email, reset_code)

        if not valid_reset:
            return render_template("error.html", error_message=f"Invalid reset code. Enter the correct code.", previous_page="/reset_password")

        # Convert the expiration time from a string to a datetime object
        expiration_time = datetime.strptime(valid_reset[0]["expiration_time"], "%Y-%m-%d %H:%M:%S")
        
        # Check if the reset code has expired
        if expiration_time < datetime.now():
            return render_template("error.html", error_message="This reset code has expired. Request for another code.", previous_page="/forgot_password")
       
        # Ensure passwords match
        if new_password != confirmation:
            return render_template("error.html", error_message="Confirmation password must match the new password.", previous_page="/reset_password")

        # Adding new password to the database
        hash = generate_password_hash(new_password)
        db.execute("UPDATE users SET password = ? WHERE email = ?", hash, email)

        flash("Password reset successful. You can now log in with your new password.")
        return  render_template("login.html") 

    else:
        return render_template("reset_password.html")      



@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Allow user to paste their essays"""

    if request.method == "POST":

        user_id = session["user_id"]

        text = request.form.get("essay")
        grade = request.form.get("grade")
        title = request.form.get("title")


        #Get number of words, letters, syllables and sentences
        #Number of words
        xwords = text.split()
        words = len(xwords)

        #number of sentences - Tokenize the text into sentences  
        xsentences = nltk.sent_tokenize(text)
        sentences = len(xsentences)

        # letters
        letters = 0
        for i in text:
            if i.isalpha():
                letters += 1

        # Syllables
        vowels = "aeiouyAEIOUY"
        syllables = 0
        prev_char = ' '

        for word in xwords:
            # Remove punctuation
            clean_word = word.strip(string.punctuation)
            # Check if the cleaned word ends with "e"
            if clean_word.endswith("e") and len(clean_word) > 3:
                syllables -= 1

            for char in word:
                if char in vowels and prev_char not in vowels:
                    syllables += 1
                prev_char = char
          


        # Getting the USER'S GRADE  
        # Coleman-Liau Index
        L = (100 * letters) / words
        S = (100 * sentences) / words
        coleman = round((0.0588 * L) - (0.296 * S) - 15.8)

        # Flesch-Kincaid Grade Level 
        flesch = round(0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59)

        # Average grade
        average = (coleman + flesch)/2
        
        if average < 1:
            grade_message = "Below Grade 1"
        elif average >= 16:
            grade_message = "Above Grade 16"
        else:
            grade_message = f"Grade {average}"



        # SENTENCE STRUCTURE ANALYSIS
        # Initialize counters for various sentence structures
        short_sentences = 0
        medium_sentences = 0
        long_sentences = 0

        # Analyze the sentence structure
        for sentence in xsentences:
            swords = sentence.split()
            if len(swords) <= 8:
                short_sentences += 1
            elif len(swords) > 8 and len(swords) <= 16:
                medium_sentences += 1
            else:
                long_sentences += 1



        # LEXICAL ANALYSIS
        # Calculate the WORD COUNT
        # words = len(xwords)

        # Calculate the AVERAGE WORD LENGTH
        average_word_length = round(letters / words)    
        

        # UNIQUE WORDS ANALYSIS
        unique_words = []
        for word in xwords:
            clean_word = word.strip(string.punctuation).lower()
            if clean_word not in unique_words:
                unique_words.append(clean_word)
            elif clean_word in unique_words:
                unique_words.remove(clean_word)

        unique_words_count = len(unique_words) 

        # Calculate vocabulary richness using Type-Token Ratio (TTR). TTR measures the diversity of words in a text by comparing the number of unique words to the total number of words (tokens).
        ttr = unique_words_count / words


        # VOCABULARY ANALYSIS        
        # Define a regular expression pattern to match common word patterns. Used to deal with hyphenated words, e.g. 1920-1931
        word_pattern = re.compile(r'^[a-zA-Z]+$')

        vocabulary = []
        for word in xwords:
            clean_word = word.strip(string.punctuation).lower()

            # Check if the word is a named entity (a person's name)
            is_person_name = False
            doc = nlp(clean_word)
            for ent in doc.ents:
                if ent.label_ == 'PERSON':
                    is_person_name = True
                    break

            # Remove: stopwords (common words like "is," "a," etc.), words with less than 5 letters, numeric values, hyphenated words, common names of people  and words ending with "ing" with a length (excluding "ing") less than 4
            if clean_word not in stopwords.words('english') and len(clean_word) > 4 and not clean_word.isnumeric() and word_pattern.match(clean_word) and not is_person_name and (not clean_word.endswith("ing") or len(clean_word) - 3 > 4):
                vocabulary.append(clean_word)

        filtered_vocabulary = set(vocabulary)

        vocab_size = len(filtered_vocabulary) 


        # Insert the essay into the database
        db.execute("INSERT INTO myessays (userID, title, studentgrade, essaygrade) VALUES (?, ?, ?, ?)", user_id, title, grade, average)

        # RESULTS PAGE
        # Render the results template and pass misspelled words to it
        return render_template("results.html", 
        grade=grade, grade_message=grade_message, coleman=coleman, flesch=flesch,
        words=words, average_word_length=average_word_length, unique_words_count=unique_words_count, vocab_size=vocab_size, ttr=ttr, 
        sentences=sentences, short_sentences=short_sentences, medium_sentences=medium_sentences, long_sentences=long_sentences,
        unique_words=unique_words, filtered_vocabulary=filtered_vocabulary,
        syllables=syllables)


    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("index.html")



@app.route("/myessays")
@login_required
def myessays():
    """Show essay history"""
    user_id = session["user_id"]

    # Query the database to retrieve the user's essays
    essays = db.execute("SELECT title, studentgrade, essaygrade FROM myessays WHERE userID = ?", user_id)

    return render_template("myessays.html", essays=essays)



@app.route("/view_essay/<string:essay_title>")
@login_required
def view_essay(essay_title):
    """View a particular essay"""
    user_id = session["user_id"]

    # Query the database to retrieve the user's essays
    essay = db.execute("SELECT studentgrade, essaygrade FROM myessays WHERE title = ?", essay_title)


    return render_template("view_essay.html", essay_title=essay_title, essay=essay)
    



@app.route("/change_password", methods=['GET', 'POST'])
@login_required
def change_password():
    """Allow user to change their passwords"""

    if request.method == "POST":

        user_id = session["user_id"] 

        # Retrieve form data
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirmation = request.form.get("confirmation")
        

        #Compare the old password with current password
        old_password = db.execute("SELECT password FROM users WHERE userID = ?", user_id)
        # Ensure passwords match
        if not check_password_hash(old_password[0]["password"], current_password):
            return render_template("error.html", error_message="This is not the current password.", previous_page="/change_password")

        # Ensure passwords match
        if new_password != confirmation:
            return render_template("error.html", error_message="Confirmation password must match the new password.", previous_page="/change_password")

        # Adding new password to the database
        hash = generate_password_hash(new_password)
        db.execute("UPDATE users SET PASSWORD = ? WHERE userID = ?", hash, user_id)

        # After successful password change, redirect user to home page.
        flash("Password change was successful.", "success")
        return redirect("/") 

    else:
        return render_template('change_password.html') 
    
    
@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/login")