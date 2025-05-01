from django.shortcuts import render, redirect, get_object_or_404
from .models import *
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
import re

# Create your views here.

@login_required
def home(request):
    return render(request, "front/home.html")


@login_required
def about(request):
    return render(request, "front/about.html")

@login_required
def my_stories(request):
    """View all life stories for the logged-in user"""
    stories = LifeStory.objects.filter(user=request.user).order_by('-created_at')
    return render(request, "front/my_stories.html", {'stories': stories})

@login_required
def view_story(request, story_id):
    """View a single life story in detail"""
    story = get_object_or_404(LifeStory, id=story_id, user=request.user)
    return render(request, "front/view_story.html", {'story': story})

# Auth views (login, signup)
