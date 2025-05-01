from django.urls import path
from .views import *

urlpatterns = [
    path("", home, name="home"),
    path("about/", about, name="about"),
    
    # Redirect to auth login page
    path("login/", lambda request: redirect('login'), name="main_login"),
    path("signup/", lambda request: redirect('signup'), name="main_signup"),
    path("logout/", lambda request: redirect('logout'), name="main_logout"),
    path("chat/", lambda request: redirect('chat'), name="main_chat"),
    path("my-stories/", my_stories, name="my_stories"),
    path("story/<int:story_id>/", view_story, name="view_story"),
]