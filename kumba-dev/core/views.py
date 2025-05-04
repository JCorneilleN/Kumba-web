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
from firebase_admin import auth as firebase_auth, storage as firebase_storage
from firebase_admin import firestore
from .firebase import db, bucket

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

        if not email.lower().endswith('.edu'):
            messages.error(request, "Only .edu email addresses are allowed.")
            return render(request, "core/signup.html", {"colleges": colleges})
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

        code = generate_verification_code()
        send_verification_email(email, code)

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
        signup_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
        payload = {'email': pending['email'], 'password': pending['password'], 'returnSecureToken': True}
        res = requests.post(signup_url, json=payload)
        data = res.json()
        if 'error' in data:
            messages.error(request, data['error']['message'])
            return redirect('signup')
        user_id = data.get('localId')
        db.collection('users').document(user_id).set({
            'first_name': pending['first_name'],
            'last_name': pending['last_name'],
            'gender': pending['gender'],
            'school': pending['school'],
            'dob': pending['dob'],
            'email': pending['email'],
            'user_id': user_id,
            'profile_picture': ''
        })
        request.session['firebase_user'] = data.get('idToken')
        request.session['user_id'] = user_id
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
        request.session['user_id'] = user_id
        request.session['user_name'] = f"{user_data['first_name']} {user_data['last_name']}"
        request.session['dob'] = user_data['dob']
        request.session['email'] = user_data['email']
        return redirect('home')
    return render(request, "core/login.html")


def home(request):
    if not request.session.get('firebase_user'):
        return redirect('login')
    # Handle profile picture upload
    if request.method == 'POST' and request.FILES.get('profile_picture'):
        file = request.FILES['profile_picture']
        user_id = request.session.get('user_id')
        ext = file.name.split('.')[-1]
        blob = bucket.blob(f'profile_pictures/{user_id}.{ext}')
        blob.upload_from_file(file, content_type=file.content_type)
        blob.make_public()
        url = blob.public_url
        db.collection('users').document(user_id).update({'profile_picture': url})
        messages.success(request, 'Profile picture updated.')
        return redirect('home')
    # Fetch current profile picture
    user_ref = db.collection('users').document(request.session.get('user_id'))
    user_doc = user_ref.get()
    user_data = user_doc.to_dict() if user_doc.exists else {}
    context = {
        'name': request.session.get('user_name'),
        'dob': request.session.get('dob'),
        'email': request.session.get('email'),
        'profile_picture': user_data.get('profile_picture', '')
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
        date_str = request.POST.get('date')
        time_str = request.POST.get('time')
        seats = int(request.POST.get('seats'))
        price = float(request.POST.get('price', 0))
        notes = request.POST.get('notes', '')
        car_type = request.POST.get('car_type', '')
        car_year = request.POST.get('car_year', '')
        car_color = request.POST.get('car_color', '')
        user_id = request.session.get('user_id')
        ride_data = {
            'origin': origin,
            'destination': destination,
            'date': date_str,
            'time': time_str,
            'seats': seats,
            'notes': notes,
            'car_type': car_type,
            'car_year': car_year,
            'car_color': car_color,
            'price_per_person': price,
            'driver_id': user_id,
            'created_at': datetime.utcnow().isoformat()
        }
        # Create ride document
        ride_ref = db.collection('rides').add(ride_data)[1]
        messages.success(request, "Ride posted successfully!")
        return redirect('list_rides')
    return render(request, 'core/post_ride.html')


def _parse_date_string(s: str):
    """
    Try multiple common date formats, return a date or None.
    """
    for fmt in ("%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None

def list_rides(request):
    # 1) Require login
    if not request.session.get("firebase_user"):
        return redirect("login")

    today = date.today()
    user_id = request.session.get("user_id")

    upcoming = []
    rides_ref = db.collection("rides")

    for doc in rides_ref.stream():
        r = doc.to_dict()

        # parse ride date
        ride_date = _parse_date_string(r.get("date", ""))
        if not ride_date:
            continue

        # delete past rides
        if ride_date < today:
            doc.reference.delete()
            continue

        # fetch driver
        driver = db.collection("users").document(r.get("driver_id")).get().to_dict() or {}
        dob_d = _parse_date_string(driver.get("dob", ""))
        age = None
        if dob_d:
            age = today.year - dob_d.year - ((today.month, today.day) < (dob_d.month, dob_d.day))

        upcoming.append({
            "id":                   doc.id,
            "driver_id":            r.get("driver_id"),
            "driver_first_name":    driver.get("first_name", ""),
            "driver_age":           age,
            "driver_gender":        driver.get("gender", ""),
            "driver_school":        driver.get("school", ""),
            "driver_picture":       driver.get("profile_picture", ""),
            "origin":               r.get("origin", ""),
            "destination":          r.get("destination", ""),
            "date":                 r.get("date", ""),
            "time":                 r.get("time", ""),
            "seats":                r.get("seats", 0),
            'car_type':             r.get("car_type",""),
            'car_year':             r.get("car_year",""),
            'car_color':            r.get("car_color",""),
            'notes':                r.get("notes",""),
            "price_per_person":     r.get("price_per_person", 0),
        })

    return render(request, "core/rides.html", {
        "rides": upcoming,
        "current_user_id": user_id,
    })

def delete_ride(request, ride_id):
    if not request.session.get("firebase_user"):
        return redirect("login")

    ride_ref = db.collection("rides").document(ride_id)
    ride = ride_ref.get().to_dict() or {}

    # only the poster can delete
    if ride.get("driver_id") != request.session.get("user_id"):
        messages.error(request, "You can only delete your own rides.")
    else:
        ride_ref.delete()
        messages.success(request, "Ride deleted.")

    return redirect("list_rides")


def join_ride(request, ride_id):
    if not request.session.get('firebase_user'):
        return redirect('login')

    user_id = request.session['user_id']
    ride_ref = db.collection('rides').document(ride_id)
    ride = ride_ref.get().to_dict()

    # Make sure seats remain
    if ride.get('seats', 0) < 1:
        messages.error(request, "Sorry, this ride is full.")
        return redirect('list_rides')

    # Add this rider to a subcollection (or array) of participants
    ride_ref.collection('participants').document(user_id).set({
        'joined_at': datetime.utcnow().isoformat(),
        'user_id': user_id
    })

    # Decrement available seats
    ride_ref.update({
        'seats': firestore.Increment(-1)
    })

    messages.success(request, "You’ve joined the ride!")
    return redirect('list_rides')

def request_join(request, ride_id):
    if not request.session.get('firebase_user'):
        return redirect('login')
    user_id = request.session['user_id']
    ride_ref = db.collection('rides').document(ride_id)
    # Add to requests subcollection
    ride_ref.collection('requests').document(user_id).set({
        'user_id': user_id,
        'status': 'pending',
        'requested_at': datetime.utcnow().isoformat()
    })
    messages.success(request, "Join request sent to driver.")
    return redirect('list_rides')

# DRIVER VIEW: see incoming requests

def ride_requests(request, ride_id):
    if not request.session.get('firebase_user'):
        return redirect('login')
    ride = db.collection('rides').document(ride_id).get().to_dict()
    if ride.get('driver_id') != request.session['user_id']:
        return redirect('list_rides')
    reqs = db.collection('rides').document(ride_id).collection('requests').stream()
    requests_list = []
    for doc in reqs:
        r = doc.to_dict()
        # fetch user profile
        user_doc = db.collection('users').document(r['user_id']).get()
        user = user_doc.to_dict() if user_doc.exists else {}
        r.update({'name': user.get('first_name'), 'profile': user.get('profile_picture')})
        requests_list.append(r)
    return render(request, 'core/ride_requests.html', {'requests': requests_list, 'ride_id': ride_id})

# ACCEPT or REJECT join

def handle_request(request, ride_id, user_id, action):
    if not request.session.get('firebase_user'):
        return redirect('login')
    ride_ref = db.collection('rides').document(ride_id)
    req_ref = ride_ref.collection('requests').document(user_id)
    if action == 'accept':
        # move to participants and decrement seats
        ride_ref.collection('participants').document(user_id).set({'joined_at': datetime.utcnow().isoformat()})
        ride_ref.update({'seats': firestore.Increment(-1)})
        req_ref.update({'status': 'accepted'})
        messages.success(request, "Join request accepted.")
    else:
        req_ref.update({'status': 'rejected'})
        messages.error(request, "Join request rejected.")
    return redirect('ride_requests', ride_id=ride_id)




def edit_profile(request):
    if not request.session.get('firebase_user'):
        return redirect('login')
    user_id = request.session.get('user_id')
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    if request.method == 'POST':
        file = request.FILES.get('profile_picture')
        if file:
            ext = file.name.split('.')[-1]
            blob = bucket.blob(f'profile_pictures/{user_id}.{ext}')
            blob.upload_from_file(file, content_type=file.content_type)
            blob.make_public()
            url = blob.public_url
            user_ref.update({'profile_picture': url})
            messages.success(request, 'Profile picture updated.')
        return redirect('home')
    user = user_doc.to_dict() if user_doc.exists else {}
    return render(request, 'core/profile.html', {'user': user, 'today': date.today()})




