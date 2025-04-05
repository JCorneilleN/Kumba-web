from django.shortcuts import render
from django.http import JsonResponse
from .firebase import db
from django.http import HttpResponse

def test_firestore(request):
    users_ref = db.collection('users')
    docs = users_ref.stream()
    user_list = [doc.to_dict() for doc in docs]
    return JsonResponse(user_list, safe=False)

def home(request):
    return HttpResponse("Welcome to Kumba Web App!")

