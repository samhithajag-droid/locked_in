from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import bcrypt
from datetime import datetime
import random

app = Flask(__name__)
app.secret_key = "locked_in_secret" 

# MySQL connection
import os
import mysql.connector

db = mysql.connector.connect(
    host="shinkansen.proxy.rlwy.net",
    user="root",
    password="YOUR_RAILWAY_PASSWORD",  # copy from Railway (click "show")
    database="railway",
    port=48492
)


    
cursor = db.cursor(dictionary=True)

# HOME / DASHBOARD
@app.route('/')
def home():
    if "user_id" in session:
        return render_template("index.html", username=session["username"])
    return redirect(url_for("login"))

# SIGNUP
@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"].encode('utf-8')
        hashed = bcrypt.hashpw(password, bcrypt.gensalt())

        cursor.execute("INSERT INTO user (username, password) VALUES (%s, %s)", (username, hashed))
        db.commit()
        flash("Signup successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

# LOGIN
@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"].encode('utf-8')

        cursor.execute("SELECT * FROM user WHERE username=%s", (username,))
        account = cursor.fetchone()

        if account and bcrypt.checkpw(password, account["password"].encode('utf-8')):
            session["user_id"] = account["id"]
            session["username"] = account["username"]
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html")

# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))

# MOOD TRACKER PAGE
@app.route('/mood', methods=["GET", "POST"])
def mood_tracker():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        mood = request.form["mood"]
        cursor.execute(
            "INSERT INTO moods (user_id, mood, date) VALUES (%s, %s, %s)",
            (session["user_id"], mood, datetime.now())
        )
        db.commit()
        flash("Mood saved successfully!", "success")
        return redirect(url_for("mood_tracker"))

    # Fetch mood history
    cursor.execute(
        "SELECT mood, date FROM moods WHERE user_id=%s ORDER BY date DESC",
        (session["user_id"],)
    )
    moods = cursor.fetchall()

    return render_template("mood.html", username=session["username"], moods=moods)

# --- EXPENSE TRACKER ---
@app.route("/expenses", methods=["GET", "POST"])
def expense_tracker():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        category = request.form["category"]
        amount = request.form["amount"]
        note = request.form["note"]

        cursor.execute(
            "INSERT INTO expenses (category, amount, note, date, user_id) VALUES (%s, %s, %s, NOW(), %s)",
            (category, amount, note, session["user_id"])
        )
        db.commit()
        return redirect(url_for("expense_tracker"))

    # Fetch expenses for logged-in user
    cursor.execute("SELECT * FROM expenses WHERE user_id=%s", (session["user_id"],))
    expenses = cursor.fetchall()

    # Fetch category totals
    cursor.execute("""
        SELECT category, SUM(amount) AS total
        FROM expenses
        WHERE user_id=%s
        GROUP BY category
    """, (session["user_id"],))
    rows = cursor.fetchall()

    # Convert MySQL rows -> dictionary
    category_totals = {row["category"]: float(row["total"]) for row in rows}

    return render_template(
        "expenses.html",
        username=session["username"],
        expenses=expenses,
        labels=list(category_totals.keys()),
        data=list(category_totals.values())

    )

# FITNESS TRACKER
@app.route('/fitness', methods=["GET", "POST"])
def fitness_tracker():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        activity = request.form["activity"]
        duration = int(request.form["duration"])
        category = request.form["category"]  # new field
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        cursor.execute(
            "INSERT INTO fitness (user_id, activity, duration, category, date) VALUES (%s, %s, %s, %s, %s)",
            (session["user_id"], activity, duration, category, date)
        )
        db.commit()
        flash("Workout logged!", "success")
        return redirect(url_for("fitness_tracker"))

    # Fetch workout history
    cursor.execute(
        "SELECT activity, duration, category, date FROM fitness WHERE user_id=%s ORDER BY date DESC",
        (session["user_id"],)
    )
    workouts = cursor.fetchall()

    # Fetch category totals
    cursor.execute("""
        SELECT category, SUM(duration) AS total_duration
        FROM fitness
        WHERE user_id=%s
        GROUP BY category
    """, (session["user_id"],))
    rows = cursor.fetchall()

    # Convert rows -> dict
    category_totals = {row["category"]: int(row["total_duration"]) for row in rows}

    # ✅ THIS RETURN is inside the function now
    return render_template(
        "fitness.html",
        username=session["username"],
        workouts=workouts,
        labels=list(category_totals.keys()),
        data=list(category_totals.values())
    )
# STUDY TRACKER
@app.route('/study', methods=['GET', 'POST'])
def study_tracker():
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        duration = request.form.get('duration', '').strip()
        goal_minutes = request.form.get('goal', '').strip()
        goal_sessions = request.form.get('goal_sessions', '').strip()
        use_pomo = request.form.get('use_pomodoro')
        pomo_len = request.form.get('pomodoro_length', '').strip()
        pomo_count = request.form.get('pomodoro_count', '').strip()

        # Compute duration if Pomodoro is used
        computed = 0
        if use_pomo:
            try:
                length = int(pomo_len) if pomo_len else 25
                count = int(pomo_count) if pomo_count else 1
                computed = length * count
            except ValueError:
                computed = 0

        # Determine final duration
        final_duration = None
        if duration:
            try:
                final_duration = int(duration)
            except ValueError:
                final_duration = None

        if computed > 0:
            final_duration = computed

        # Normalize nullable ints
        gm = int(goal_minutes) if goal_minutes.strip().isdigit() else None
        gs = int(goal_sessions) if goal_sessions.strip().isdigit() else None

        # Insert into DB if valid
        if subject and final_duration is not None and final_duration >= 0:
            cursor.execute(
                "INSERT INTO study_sessions (subject, duration_minutes, goal_minutes, goal_sessions) VALUES (%s,%s,%s,%s)",
                (subject, final_duration, gm, gs)
            )
            db.commit()

        return redirect('/study')

    # Fetch past sessions
    cursor.execute("SELECT * FROM study_sessions ORDER BY date DESC LIMIT 200")
    sessions = cursor.fetchall()

    # Aggregate: minutes per subject
    cursor.execute("""
        SELECT subject, SUM(duration_minutes) AS total_minutes
        FROM study_sessions
        GROUP BY subject
        ORDER BY total_minutes DESC
    """)
    by_subject = cursor.fetchall()
    subj_labels = [row['subject'] for row in by_subject]
    subj_totals_min = [int(row['total_minutes'] or 0) for row in by_subject]

    # Aggregate: weekly totals (last 8 weeks)
    cursor.execute("""
        SELECT YEARWEEK(date, 1) AS yw,
               DATE_FORMAT(date - INTERVAL WEEKDAY(date) DAY, '%Y-%m-%d') AS week_start,
               SUM(duration_minutes) AS total_minutes
        FROM study_sessions
        WHERE date >= DATE_SUB(CURDATE(), INTERVAL 8 WEEK)
        GROUP BY YEARWEEK(date, 1), week_start
        ORDER BY YEARWEEK(date, 1)
    """)
    by_week = cursor.fetchall()
    week_labels = [row['week_start'] for row in by_week]
    week_totals_min = [int(row['total_minutes'] or 0) for row in by_week]

    return render_template(
        'study.html',
        sessions=sessions,
        subj_labels=subj_labels,
        subj_totals_min=subj_totals_min,
        week_labels=week_labels,
        week_totals_min=week_totals_min
    )


# --- MEAL TRACKER ---
@app.route('/meals', methods=["GET", "POST"])
def meal_tracker():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        meal_type = request.form["meal_type"]
        food = request.form["food"]
        calories = request.form["calories"]

        cursor.execute(
            "INSERT INTO meals (user_id, meal_type, food, calories, date) VALUES (%s, %s, %s, %s, NOW())",
            (session["user_id"], meal_type, food, calories)
        )
        db.commit()
        flash("Meal logged successfully!", "success")
        return redirect(url_for("meal_tracker"))

    # Fetch meal history
    cursor.execute(
        "SELECT meal_type, food, calories, date FROM meals WHERE user_id=%s ORDER BY date DESC",
        (session["user_id"],)
    )
    meals = cursor.fetchall()

    # Fetch calories per category for chart
    cursor.execute("""
        SELECT meal_type, SUM(calories) AS total
        FROM meals
        WHERE user_id=%s
        GROUP BY meal_type
    """, (session["user_id"],))
    rows = cursor.fetchall()
    chart_labels = [row["meal_type"] for row in rows]
    chart_data = [int(row["total"]) for row in rows]

    return render_template(
        "meals.html",
        username=session["username"],
        meals=meals,
        labels=chart_labels,
        data=chart_data
    )


if __name__ == "__main__":
    app.run(debug=True)