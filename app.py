from flask import Flask, render_template, request, redirect, url_for, session, flash
import joblib
import os
from pymongo import MongoClient

# Google OAuth
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = "THIS_IS_A_FIXED_SECRET_KEY_12345"

# ------------------ MONGODB CONNECTION ------------------
MONGO_URI = "mongodb+srv://gopi:12345@cluster-1.y6kcqaj.mongodb.net/?appName=Cluster-1"
client = MongoClient(MONGO_URI)
db = client["heart_app"]  # Database name
users_collection = db["users"]  # Collection name

# Create index for username (optional but recommended for performance)
users_collection.create_index("username", unique=True)

# Predictions collection for storing prediction history
predictions_collection = db["predictions"]

# ------------------ ML MODEL ------------------
model = joblib.load("heart_disease_model.pkl")

# ------------------ GOOGLE OAUTH CONFIG ------------------

from authlib.integrations.flask_client import OAuth

# ✅ create oauth object FIRST
oauth = OAuth(app)

# ✅ then register google
# ------------------ GOOGLE OAUTH CONFIG ------------------

oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id="57308368088-1gi7t1f869nds9crggpldeikihjctnbr.apps.googleusercontent.com",
    client_secret="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",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)




# ------------------ ROUTES ------------------

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/home")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", user=session["user"])


# ------------------ LOGIN ------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = users_collection.find_one({"username": username})
        if user and user["password"] == password:
            session["user"] = username
            return redirect(url_for("home"))
        else:
            flash("Invalid credentials", "danger")

    return render_template("login.html")


# ------------------ REGISTER ------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if users_collection.find_one({"username": username}):
            flash("User already exists!", "warning")
        else:
            users_collection.insert_one({"username": username, "password": password})
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


# ------------------ GOOGLE LOGIN ------------------
@app.route("/login/google")
def google_login():
    return google.authorize_redirect(
        "http://localhost:5000/login/google/callback"
    )

@app.route("/login/google/callback")
def google_callback():
    token = google.authorize_access_token()
    user_info = token["userinfo"]

    session["user"] = user_info["name"]
    session["email"] = user_info["email"]

    return redirect(url_for("home"))






# ------------------ LOGOUT ------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for("login"))


# ------------------ PREDICTION ------------------
@app.route("/predict", methods=["GET", "POST"])
def predict():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        field_names = [
            "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
            "thalach", "exang", "oldpeak", "slope", "ca", "thal"
        ]
        features = [float(request.form.get(field)) for field in field_names]

        prediction = model.predict([features])[0]
        
        # Save prediction to database
        from datetime import datetime
        prediction_data = {
            "username": session["user"],
            "timestamp": datetime.now(),
            "features": {
                "age": float(request.form.get("age")),
                "sex": float(request.form.get("sex")),
                "cp": float(request.form.get("cp")),
                "trestbps": float(request.form.get("trestbps")),
                "chol": float(request.form.get("chol")),
                "fbs": float(request.form.get("fbs")),
                "restecg": float(request.form.get("restecg")),
                "thalach": float(request.form.get("thalach")),
                "exang": float(request.form.get("exang")),
                "oldpeak": float(request.form.get("oldpeak")),
                "slope": float(request.form.get("slope")),
                "ca": float(request.form.get("ca")),
                "thal": float(request.form.get("thal"))
            },
            "prediction_result": int(prediction)
        }
        predictions_collection.insert_one(prediction_data)
        
        return render_template("result.html", prediction=prediction)

    return render_template("predict.html")


# ------------------ PREDICTION HISTORY ------------------
@app.route("/history")
def prediction_history():
    if "user" not in session:
        return redirect(url_for("login"))
    
    # Get all predictions for the logged-in user, sorted by most recent first
    predictions = list(predictions_collection.find(
        {"username": session["user"]}
    ).sort("timestamp", -1))
    
    return render_template("history.html", predictions=predictions)


# ------------------ RISK ANALYSIS ------------------
@app.route("/risk_analysis")
def risk_analysis():
    if "user" not in session:
        return redirect(url_for("login"))
    
    # Get all predictions for the logged-in user
    predictions = list(predictions_collection.find(
        {"username": session["user"]}
    ))
    
    # Calculate risk counts
    high_risk_count = sum(1 for p in predictions if p.get("prediction_result") == 1)
    low_risk_count = sum(1 for p in predictions if p.get("prediction_result") == 0)
    
    return render_template(
        "risk_analysis.html",
        user=session["user"],
        predictions=predictions,
        high_risk_count=high_risk_count,
        low_risk_count=low_risk_count
    )


# ------------------ MODEL PERFORMANCE ------------------
@app.route("/model_performance")
def model_performance():
    if "user" not in session:
        return redirect(url_for("login"))
    
    return render_template("model_performance.html", user=session["user"])


# ------------------ PROFILE ------------------
@app.route("/profile")
def profile():
    if "user" not in session:
        return redirect(url_for("login"))
    
    # Get all predictions for the logged-in user
    predictions = list(predictions_collection.find(
        {"username": session["user"]}
    ))
    
    # Calculate statistics
    total_predictions = len(predictions)
    high_risk_count = sum(1 for p in predictions if p.get("prediction_result") == 1)
    low_risk_count = sum(1 for p in predictions if p.get("prediction_result") == 0)
    
    return render_template(
        "profile.html",
        user=session["user"],
        total_predictions=total_predictions,
        high_risk_count=high_risk_count,
        low_risk_count=low_risk_count
    )


# ------------------ RUN ------------------
if __name__ == "__main__":
    app.run(debug=True)
