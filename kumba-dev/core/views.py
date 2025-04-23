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
from firebase_admin import auth as firebase_auth  # if needed
from .firebase import db

FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")


def load_colleges():
    csv_path = os.path.join(settings.BASE_DIR, 'static/core/colleges.csv')
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return sorted({row["LocationName"] for row in reader if row.get("LocationName")})


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

        # Validate .edu email
        if not email.lower().endswith('.edu'):
            messages.error(request, "Only .edu email addresses are allowed.")
            return render(request, "core/signup.html", {"colleges": colleges})
        # Validate age >=18
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

        # Send verification code
        code = generate_verification_code()
        send_verification_email(email, code)

        # Store pending user in session
        request.session['pending_user'] = {
            'first_name': first_name,
            'last_name': last_name,
            'gender': gender,
            'school': school,
            'dob': dob,
            'email': email,
            'password': password,
            'code': code
        }
        return redirect('verify_code')
    return render(request, "core/signup.html", {"colleges": colleges})


def verify_code(request):
    pending = request.session.get('pending_user')
    if not pending:
        messages.error(request, "Session expired. Please sign up again.")
        return redirect('signup')
    if request.method == 'POST':
        input_code = request.POST.get('code')
        if input_code != pending.get('code'):
            messages.error(request, "Incorrect verification code.")
            return redirect('verify_code')
        # Create Firebase Auth user
        signup_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
        payload = {
            'email': pending['email'],
            'password': pending['password'],
            'returnSecureToken': True
        }
        res = requests.post(signup_url, json=payload)
        data = res.json()
        if 'error' in data:
            messages.error(request, data['error']['message'])
            return redirect('signup')
        user_id = data.get('localId')
        # Save profile to Firestore
        db.collection('users').document(user_id).set({
            'first_name': pending['first_name'],
            'last_name': pending['last_name'],
            'gender': pending['gender'],
            'school': pending['school'],
            'dob': pending['dob'],
            'email': pending['email'],
            'user_id': user_id
        })
        # Store in session
        request.session['firebase_user'] = data.get('idToken')
        request.session['user_id'] = user_id  # <-- store user_id here
        request.session['user_name'] = f"{pending['first_name']} {pending['last_name']}"
        request.session['dob'] = pending['dob']
        request.session['email'] = pending['email']
        del request.session['pending_user']
        return redirect('home')
    return render(request, "core/verify.html")


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        login_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
        payload = {'email': email, 'password': password, 'returnSecureToken': True}
        res = requests.post(login_url, json=payload)
        data = res.json()
        if 'error' in data:
            messages.error(request, "Invalid credentials. Please try again.")
            return render(request, 'core/login.html')
        user_id = data.get('localId')
        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            messages.error(request, "User record not found.")
            return render(request, 'core/login.html')
        user_data = user_doc.to_dict()
        request.session['firebase_user'] = data.get('idToken')
        request.session['user_id'] = user_id  # <-- store on login as well
        request.session['user_name'] = f"{user_data['first_name']} {user_data['last_name']}"
        request.session['dob'] = user_data['dob']
        request.session['email'] = user_data['email']
        return redirect('home')
    return render(request, "core/login.html")


def home(request):
    if not request.session.get('firebase_user'):
        return redirect('login')
    context = {
        'name': request.session.get('user_name'),
        'dob': request.session.get('dob'),
        'email': request.session.get('email')
    }
    return render(request, 'core/home.html', context)


def logout_view(request):
    request.session.flush()
    return redirect('login')


def reset_password(request):
    if request.method == 'POST':
        email = request.session.get('email')
        if not email:
            messages.error(request, "Session expired. Please log in again.")
            return redirect('login')
        payload = {'requestType': 'PASSWORD_RESET', 'email': email}
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}"
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            messages.success(request, "Password reset email sent.")
        else:
            messages.error(request, "Failed to send reset email.")
        return redirect('home')


def post_ride(request):
    if not request.session.get('firebase_user'):
        return redirect('login')
    if request.method == 'POST':
        origin = request.POST.get('origin')
        destination = request.POST.get('destination')
        date = request.POST.get('date')
        time = request.POST.get('time')
        seats = int(request.POST.get('seats'))
        notes = request.POST.get('notes', '')
        user_id = request.session.get('user_id')  # <-- retrieved from session
        ride_data = {
            'origin': origin,
            'destination': destination,
            'date': date,
            'time': time,
            'seats': seats,
            'notes': notes,
            'driver_id': user_id,
            'created_at': datetime.utcnow().isoformat()
        }
        db.collection('rides').add(ride_data)
        messages.success(request, "Ride posted successfully!")
        return redirect('home')
    return render(request, 'core/post_ride.html')



