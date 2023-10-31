import os
import nltk
import string
nltk.download('punkt')
nltk.download('stopwords')


from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from datetime import timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords




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
            
        # Adding user to the database
        hash = generate_password_hash(password)
        result = db.execute("INSERT INTO users (username, password) VALUES(?, ?)", username, hash)


        # Get the ID of the newly inserted user
        user_id = db.execute("SELECT last_insert_rowid()")

        # Create a new session for the user to log them in
        session['user_id'] = user_id

        # After successful registration, you can redirect the user to the index page.
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
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")



@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Allow user to paste their essays"""

    if request.method == "POST":

        text = request.form.get("essay")
        grade = request.form.get("grade")


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

        #Syllables
        vowels = "aeiouyAEIOUY"
        syllables = 0
        prev_char = ' '

        for word in text.split():
            # Remove punctuation
            clean_word = word.strip(string.punctuation)
            # Check if the cleaned word ends with "e"
            if clean_word.endswith("e"):
                syllables -= 1

            for char in word:
                if char in vowels and prev_char not in vowels:
                    syllables += 1
                prev_char = char

            


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



        # Sentence Structure analysis
        # Initialize counters for various sentence structures
        short_sentences = 0
        medium_sentences = 0
        long_sentences = 0

        # Analyze the sentence structure
        for sentence in xsentences:
            swords = sentence.split()
            if len(swords) <= 10:
                short_sentences += 1
            elif len(swords) > 10 and len(swords) <= 20:
                medium_sentences += 1
            else:
                medium_sentences += 1



        # Lexical Analysis
        # Calculate the word count
        #...........words = words

        # Calculate the average word length
        average_word_length = round(letters / words)

        # Calculate vocabulary richness using Type-Token Ratio (TTR). TTR measures the diversity of words in a text by comparing the number of unique words to the total number of words (tokens).
        unique_words = set(word.strip(string.punctuation) for word in xwords)
        unique_words_count = len(unique_words) 

        # Calculate Type-Token Ratio (TTR) for unique words richness
        ttr = len(unique_words) / words



        #Vocabulary Analysis
        
        # Remove stopwords (common words like "is," "a," etc.)
        filtered_words = [word.strip(string.punctuation) for word in xwords if word.lower() not in stopwords.words('english')]

        vocabulary = set(filtered_words)
        vocab_size = len(vocabulary) 


        # Render the results template and pass misspelled words to it
        return render_template("results.html", grade=grade, sentences=sentences, words=words, coleman=coleman, flesch=flesch, grade_message=grade_message, syllables=syllables, short_sentences=short_sentences, medium_sentences=medium_sentences, long_sentences=long_sentences, average_word_length=average_word_length, unique_words_count=unique_words_count,ttr=ttr, unique_words=unique_words, vocabulary=vocabulary)


    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("index.html")



@app.route("/myessays")
@login_required
def myessays():
    """Show history of transactions"""
    user_id = session["user_id"]

    # Query the database to retrieve the user's transactions
    essays = db.execute(
        "SELECT title, readability score, lexical analysis FROM essays WHERE user_id = ?", user_id)

    return render_template("myessays.html", essays=essays)



@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/login")