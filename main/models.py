from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Conversation(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Conversation with {self.user.username} on {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

class Message(models.Model):
    id = models.AutoField(primary_key=True)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=10, choices=[('user', 'User'), ('ai', 'AI')])
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.upper()} at {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}: {self.content[:10]}"

class Person(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150)
    relation = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=150, blank=True)
    
    about = models.TextField(blank=True)
    image = models.ImageField(upload_to='person_images/', null=True, blank=True)
    
    date_created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class Location(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='location_images/', null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Emotion(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='emotion_images/', null=True, blank=True)

    def __str__(self):
        return self.name

class Event(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    people_present = models.ManyToManyField(Person, related_name='events', blank=True)
    emotions = models.ManyToManyField(Emotion, related_name='events', blank=True)
    image = models.ImageField(upload_to='event_images/', null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    color = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return self.title

class LifeStory(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='life_stories')
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_complete = models.BooleanField(default=False)
    people = models.ManyToManyField(Person, related_name='life_stories', blank=True)
    locations = models.ManyToManyField(Location, related_name='life_stories', blank=True)
    emotions = models.ManyToManyField(Emotion, related_name='life_stories', blank=True)
    events = models.ManyToManyField(Event, related_name='life_stories', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
        
    class Meta:
        verbose_name_plural = "Life Stories"