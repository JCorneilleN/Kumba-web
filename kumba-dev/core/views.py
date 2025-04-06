from django.shortcuts import render, redirect
from django.http import JsonResponse
from .firebase import db
from django.http import HttpResponse
from django.contrib import messages
import os
import requests

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
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

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

        request.session["firebase_user"] = data["idToken"]
        return redirect("home")

    return render(request, "core/signup.html")

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

