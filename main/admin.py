from django.contrib import admin
from .models import Conversation, Message, Person, Location, Emotion, Event, LifeStory

# Register your models here.
admin.site.register(Conversation)
admin.site.register(Message)
admin.site.register(Person)
admin.site.register(Location)
admin.site.register(Emotion)
admin.site.register(Event)
admin.site.register(LifeStory)
