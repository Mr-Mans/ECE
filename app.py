import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from datetime import timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps


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


        sentences = 0
        words = 1
        letters = 0

        for i in text:
            # Sentences
            if i == "." or i == "?" or i == "!":
                sentences += 1

            # words
            elif i == " " or i == "\0":
                words += 1

            # letters
            elif i.isalpha():
                letters += 1

        # Coleman-Liau Index
        L = (100 * letters) / words
        S = (100 * sentences) / words
        coleman = round(((0.0588 * L) - (0.296 * S) - 15.8))

        if coleman < 1:
            return render_template("results.html", grade_message="Below Grade 1")
        elif coleman >= 16:
            return render_template("results.html", grade_message="Above Grade 16")
        else:
            return render_template("results.html", grade_message=f"Grade {coleman}")


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
    return redirect("/")