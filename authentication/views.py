from django.shortcuts import render, redirect
from .models import *
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
import re

# Create your views here.

@login_required
def logoutUser(request):
    logout(request)
    return redirect("login")




def loginUser(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            
            try:
                # Try to authenticate the user
                user = authenticate(request, username=username, password=password)
                
                if user is not None:
                    login(request, user)
                    return JsonResponse({'status': 'success', 'message': 'Login successful'})
                else:
                    return JsonResponse({'status': 'error', 'message': 'Invalid username or password'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})
                
    return render(request, "auth/login.html")




def signupUser(request):
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            data = json.loads(request.body)
            username = data.get('username')
            first_name = data.get('first_name')
            last_name = data.get('last_name')
            password = data.get('password')
            
            try:
                # Create new user
                user = User.objects.create_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    password=password
                )
                
                # Login the new user
                login(request, user)
                return JsonResponse({'status': 'success', 'message': 'Account created successfully'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})
    
    return render(request, "auth/signup.html")





# API endpoints for form validation
def check_username(request):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        data = json.loads(request.body)
        username = data.get('username')
        
        if not username:
            return JsonResponse({'valid': False, 'message': 'Username is required'})
        
        # Check if username exists
        if User.objects.filter(username=username).exists():
            return JsonResponse({'valid': False, 'message': 'Username already exists'})
        
        return JsonResponse({'valid': True, 'message': 'Username is available'})
        
    return JsonResponse({'valid': False, 'message': 'Invalid request'})





def validate_password(request):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        data = json.loads(request.body)
        password = data.get('password')
        
        if not password:
            return JsonResponse({'valid': False, 'message': 'Password is required'})
            
        # Check password strength
        if len(password) < 8:
            return JsonResponse({'valid': False, 'message': 'Password must be at least 8 characters'})
            
        if not re.search(r'[A-Z]', password):
            return JsonResponse({'valid': False, 'message': 'Password must contain at least one uppercase letter'})
            
        if not re.search(r'[a-z]', password):
            return JsonResponse({'valid': False, 'message': 'Password must contain at least one lowercase letter'})
            
        if not re.search(r'[0-9]', password):
            return JsonResponse({'valid': False, 'message': 'Password must contain at least one number'})
            
        return JsonResponse({'valid': True, 'message': 'Password is strong'})
        
    return JsonResponse({'valid': False, 'message': 'Invalid request'})



def check_login(request):
    if request.method == 'GET' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        if request.user.is_authenticated:
            return JsonResponse({'is_authenticated': True})
        return JsonResponse({'is_authenticated': False})
