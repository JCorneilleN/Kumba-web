from django.shortcuts import render, redirect
from django.http import JsonResponse
from .firebase import db
from django.http import HttpResponse
from django.contrib import messages
import os
import requests
from datetime import datetime, date

import csv
from django.conf import settings

def load_colleges():
    csv_path = os.path.join(settings.BASE_DIR, 'core/static/core/colleges.csv')
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        print("HEADERS:", reader.fieldnames)  # optional: to verify
        return sorted(set(row["LocationName"] for row in reader if row.get("LocationName")))





def test_firestore(request):
    users_ref = db.collection('users')
    docs = users_ref.stream()
    user_list = [doc.to_dict() for doc in docs]
    return JsonResponse(user_list, safe=False)

def home(request):
    if not request.session.get("firebase_user"):
        return redirect("login")
    rides = db.collection("rides").stream()
    ride_list = [r.to_dict() for r in rides]
    return render(request, 'core/home.html', {"rides": ride_list})


FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")

def signup(request):
    colleges = load_colleges()

    if request.method == "POST":
        # Form fields
        email = request.POST.get("email")
        password = request.POST.get("password")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        gender = request.POST.get("gender")
        school = request.POST.get("school")
        dob = request.POST.get("dob")

        # Email must end with .edu
        if not email.endswith(".edu"):
            messages.error(request, "Only .edu email addresses are allowed.")
            return redirect("signup")

        # Must be at least 18 years old
        try:
            dob_obj = datetime.strptime(dob, "%Y-%m-%d").date()
            today = date.today()
            age = today.year - dob_obj.year - ((today.month, today.day) < (dob_obj.month, dob_obj.day))
            if age < 18:
                messages.error(request, "You must be at least 18 years old to sign up.")
                return redirect("signup")
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect("signup")

        # Create Firebase Auth user
        signup_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }

        res = requests.post(signup_url, json=payload)
        data = res.json()

        if "error" in data:
            messages.error(request, data["error"]["message"])
            return redirect("signup")

        user_id = data.get("localId")
        id_token = data.get("idToken")

        # Save profile in Firestore
        db.collection("users").document(user_id).set({
            "first_name": first_name,
            "last_name": last_name,
            "gender": gender,
            "school": school,
            "dob": dob,
            "email": email,
            "user_id": user_id,
        })

        # Send email verification
        verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}"
        requests.post(verify_url, json={
            "requestType": "VERIFY_EMAIL",
            "idToken": id_token
        })

        messages.success(request, "Account created! Check your .edu email to verify your account.")
        return redirect("login")
    
    print("COLLEGES:", colleges[:5])  # Print first 5 colleges to confirm it's loading


    return render(request, "core/signup.html", {"colleges": colleges})


def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        login_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }

        res = requests.post(login_url, json=payload)
        data = res.json()

        if "error" in data:
            messages.error(request, data["error"]["message"])
            return redirect("login")

        request.session["firebase_user"] = data["idToken"]
        return redirect("home")

    return render(request, "core/login.html")

def post_ride(request):
    if not request.session.get("firebase_user"):
        return redirect("login")

    if request.method == "POST":
        data = {
            "from": request.POST.get("from"),
            "to": request.POST.get("to"),
            "date": request.POST.get("date"),
            "time": request.POST.get("time"),
            "social": request.POST.get("social"),
            "notes": request.POST.get("notes"),
            "is_driver": bool(request.POST.get("is_driver")),
            "user_id": "firebase_user",  # replace later with actual UID
        }
        db.collection("rides").add(data)
        messages.success(request, "Ride posted!")
        return redirect("home")

    return render(request, "core/post_ride.html")

def logout_view(request):
    request.session.flush()
    messages.success(request, "You have been logged out.")
    return redirect("home")

