import os
import csv
import random
import requests
from datetime import datetime, date
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from .firebase import db

FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")


def load_colleges():
    csv_path = os.path.join(settings.BASE_DIR, 'core/static/core/colleges.csv')
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return sorted(set(row["LocationName"] for row in reader if row.get("LocationName")))


def generate_verification_code():
    return str(random.randint(100000, 999999))


def send_verification_email(email, code):
    try:
        message = Mail(
            from_email='no-reply@kumbaapp.com',
            to_emails=email,
            subject='Verify your Kumba account',
            plain_text_content=f'Your verification code is: {code}'
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
    except Exception as e:
        print("SendGrid error:", e)


def signup(request):
    colleges = load_colleges()

    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        gender = request.POST.get("gender")
        school = request.POST.get("school")
        dob = request.POST.get("dob")
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Email validation
        if not email.lower().endswith('.edu'):
            messages.error(request, "Only .edu email addresses are allowed.")
            return render(request, "core/signup.html", {"colleges": colleges})

        # Age validation
        try:
            dob_obj = datetime.strptime(dob, "%Y-%m-%d").date()
            today = date.today()
            age = today.year - dob_obj.year - ((today.month, today.day) < (dob_obj.month, dob_obj.day))
            if age < 18:
                messages.error(request, "You must be at least 18 years old to register.")
                return render(request, "core/signup.html", {"colleges": colleges})
        except ValueError:
            messages.error(request, "Invalid date format.")
            return render(request, "core/signup.html", {"colleges": colleges})

        # Generate and send verification code
        code = generate_verification_code()
        send_verification_email(email, code)

        # Store temporarily
        request.session["pending_user"] = {
            "first_name": first_name,
            "last_name": last_name,
            "gender": gender,
            "school": school,
            "dob": dob,
            "email": email,
            "password": password,
            "code": code
        }

        return redirect("verify_code")

    return render(request, "core/signup.html", {"colleges": colleges})
