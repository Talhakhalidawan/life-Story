from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import json
import openai
from main.models import Conversation, Message, Person, Location, Emotion, Event, LifeStory
from django.utils import timezone

# Set OpenAI API key
openai.api_key = settings.OPENAI_API_KEY

@login_required
def chat(request):
    # Get conversation or create a new one
    conversation, created = Conversation.objects.get_or_create(
        user=request.user,
    )
    
    # Get all messages for this conversation
    messages = Message.objects.filter(conversation=conversation)
    
    return render(request, "front/chat.html", {
        'conversation': conversation,
        'messages': messages,
    })

@login_required
@csrf_exempt
def send_message(request):
    if request.method == 'POST':
        try:
            print(f"[{timezone.now()}] Processing new message request")
            data = json.loads(request.body)
            message_content = data.get('message', '')
            mode = data.get('mode', 'free')  # 'interview' or 'free'
            print(f"[{timezone.now()}] Message received: {message_content[:30]}... (Mode: {mode})")
            
            # Get conversation or create new one
            conversation, created = Conversation.objects.get_or_create(
                user=request.user,
            )
            print(f"[{timezone.now()}] {'Created new' if created else 'Retrieved existing'} conversation (ID: {conversation.id})")
            
            # Save user message
            user_message = Message.objects.create(
                conversation=conversation,
                sender='user',
                content=message_content
            )
            print(f"[{timezone.now()}] User message saved (ID: {user_message.id})")
            
            # Prepare conversation history for OpenAI - ONLY LAST 4 USER MESSAGES
            user_messages = Message.objects.filter(
                conversation=conversation, 
                sender='user'
            ).order_by('-created_at')[:4]  # Get last 4 user messages
            
            # Reverse to get chronological order
            user_messages = list(reversed(user_messages))
            
            print(f"[{timezone.now()}] Retrieved {len(user_messages)} user messages for context")
            chat_history = []
            
            # Get existing entities to provide to the AI (limited to 6 chars for names)
            existing_people = Person.objects.all()[:15]  # Limit to 15 people
            existing_locations = Location.objects.all()[:10]  # Limit to 10 locations
            existing_emotions = Emotion.objects.all()[:10]  # Limit to 10 emotions
            existing_events = Event.objects.all()[:10]  # Limit to 10 events
            
            # Format existing entities with trimmed names
            existing_entities = {
                "people": [f"{p.name[:6]},{p.id}" for p in existing_people],
                "locations": [f"{l.name[:6]},{l.id}" for l in existing_locations],
                "emotions": [f"{e.name[:6]},{e.id}" for e in existing_emotions],
                "events": [f"{e.title[:6]},{e.id}" for e in existing_events]
            }
            
            # Convert to JSON
            existing_entities_json = json.dumps(existing_entities)
            
            # Add system message based on mode
            if mode == 'interview':
                system_prompt = get_interview_system_prompt(existing_entities_json)
                print(f"[{timezone.now()}] Using INTERVIEW system prompt with {len(existing_entities['people'])} existing people")
            else:  # free mode
                system_prompt = get_free_mode_system_prompt(existing_entities_json)
                print(f"[{timezone.now()}] Using FREE MODE system prompt with {len(existing_entities['people'])} existing people")
                
            chat_history.append({"role": "system", "content": system_prompt})
            
            # Add user message history (only the most recent 4, trimmed to 200 chars)
            MAX_CHARS = 200
            for msg in user_messages:
                chat_history.append({"role": "user", "content": msg.content[:MAX_CHARS]})
            
            # Send to OpenAI
            print(f"[{timezone.now()}] Sending request to OpenAI API (total messages: {len(chat_history)})")
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=chat_history,
                temperature=0.7,
                max_tokens=1500,
            )
            
            ai_message_content = response.choices[0].message['content']
            print(f"[{timezone.now()}] Received response from OpenAI API: {ai_message_content[:50]}...")
            
            # Process AI response for saving to database
            try:
                # Try to parse the content as valid JSON
                ai_data = None
                user_display_message = ai_message_content
                
                # Check if the message is pure JSON
                if ai_message_content.strip().startswith('{') and ai_message_content.strip().endswith('}'):
                    try:
                        print(f"[{timezone.now()}] Attempting to parse response as JSON")
                        ai_data = json.loads(ai_message_content)
                        if ai_data and 'response' in ai_data:
                            user_display_message = ai_data['response']
                            print(f"[{timezone.now()}] Successfully parsed JSON, extracted user display message")
                    except json.JSONDecodeError as json_err:
                        print(f"[{timezone.now()}] Failed to parse AI response as JSON: {str(json_err)}")
                        
                # Save the raw AI message to the database
                ai_message = Message.objects.create(
                    conversation=conversation,
                    sender='ai',
                    content=ai_message_content
                )
                print(f"[{timezone.now()}] Saved raw AI message to database (ID: {ai_message.id})")
                
                # Process the structured data if available and valid
                if ai_data and isinstance(ai_data, dict):
                    print(f"[{timezone.now()}] Processing extracted structured data")
                    # Process the extracted data
                    process_ai_response(ai_data, request.user)
                    
                    # Check if story_mode or story_complete is true, which means we need to generate a complete story
                    story_mode = ai_data.get('story_mode', False)
                    story_complete = ai_data.get('story_complete', False)
                    print(f"[{timezone.now()}] story_mode: {story_mode}, story_complete: {story_complete}")
                    
                    if story_mode or story_complete:
                        print(f"[{timezone.now()}] Story mode activated, generating life story")
                        # Generate the story automatically without requiring user action
                        story = generate_life_story(request.user)
                        if story:
                            print(f"[{timezone.now()}] Story generated successfully: '{story.title}' (ID: {story.id})")
                            # Inform the user that a story has been generated
                            user_display_message += f"\n\nI've created a comprehensive narrative of your life story titled '{story.title}'."
                        else:
                            print(f"[{timezone.now()}] Failed to generate story")
                    
                    # Return just the response part to the user
                    print(f"[{timezone.now()}] Returning structured response to user")
                    return JsonResponse({
                        'message': user_display_message,
                        'timestamp': ai_message.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    })
                
                # If we couldn't extract structured data, return the original message
                print(f"[{timezone.now()}] No structured data found, returning raw message")
                return JsonResponse({
                    'message': user_display_message,
                    'timestamp': ai_message.created_at.strftime('%Y-%m-%d %H:%M:%S')
                })
                
            except Exception as process_err:
                print(f"[{timezone.now()}] Error processing AI response: {str(process_err)}")
                # Save the raw message in case of processing error
                ai_message = Message.objects.create(
                    conversation=conversation,
                    sender='ai',
                    content=ai_message_content
                )
                return JsonResponse({
                    'message': ai_message_content,
                    'timestamp': ai_message.created_at.strftime('%Y-%m-%d %H:%M:%S')
                })
                
        except Exception as main_err:
            print(f"[{timezone.now()}] Error in send_message: {str(main_err)}")
            return JsonResponse({'error': str(main_err)}, status=500)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

def generate_life_story(user):
    """Generate a complete life story based on collected data for a user"""
    try:
        print(f"[{timezone.now()}] Starting life story generation for user {user.username}")
        
        # Get recent user messages for context (last 4)
        user_messages = Message.objects.filter(
            conversation__user=user, 
            sender='user'
        ).order_by('-created_at')[:4]
        
        # Reverse to get chronological order
        user_messages = list(reversed(user_messages))
        
        # Get all entities for this user
        life_stories = LifeStory.objects.filter(user=user)

        # Get all entities associated with the user
        people = Person.objects.all()[:20]
        locations = Location.objects.all()[:15]
        emotions = Emotion.objects.all()[:15]
        events = Event.objects.all()[:20]
        
        print(f"[{timezone.now()}] Entity counts - People: {people.count()}, Locations: {locations.count()}, Emotions: {emotions.count()}, Events: {events.count()}")
        
        # Check if we have enough data to generate a story
        if not (people.exists() and events.exists()):
            print(f"[{timezone.now()}] Not enough data to generate a story")
            return None
            
        # Format people data with IDs
        print(f"[{timezone.now()}] Formatting people data")
        people_data = []
        for person in people:
            people_data.append({
                "id": person.id,
                "name": person.name,
                "relation": person.relation[:50] if person.relation else "",
                "about": person.about[:100] if person.about else ""
            })
        
        # Format locations data with IDs
        print(f"[{timezone.now()}] Formatting locations data")
        locations_data = []
        for location in locations:
            locations_data.append({
                "id": location.id,
                "name": location.name,
                "description": location.description[:100] if location.description else ""
            })
        
        # Format emotions data with IDs
        print(f"[{timezone.now()}] Formatting emotions data")
        emotions_data = []
        for emotion in emotions:
            emotions_data.append({
                "id": emotion.id,
                "name": emotion.name,
                "description": emotion.description[:100] if emotion.description else ""
            })
        
        # Format events data with IDs
        print(f"[{timezone.now()}] Formatting events data")
        events_data = []
        processed_event_titles = set()  # To keep track of processed events
        
        for event in events:
            # Skip duplicate event titles
            if event.title in processed_event_titles:
                print(f"[{timezone.now()}] Skipping duplicate event: {event.title}")
                continue
                
            processed_event_titles.add(event.title)
            
            event_data = {
                "id": event.id,
                "title": event.title,
                "description": event.description[:150] if event.description else "",
            }
            
            if event.location:
                event_data["location_id"] = event.location.id
            
            # Add people present IDs
            people_present_ids = []
            for person in event.people_present.all():
                people_present_ids.append(person.id)
            event_data["people_ids"] = people_present_ids
            
            # Add emotion IDs
            emotion_ids = []
            for emotion in event.emotions.all():
                emotion_ids.append(emotion.id)
            event_data["emotion_ids"] = emotion_ids
            
            events_data.append(event_data)
        
        print(f"[{timezone.now()}] Processed {len(events_data)} unique events")
        
        # Format recent user messages
        user_messages_data = []
        MAX_CHARS = 200
        for msg in user_messages:
            user_messages_data.append(msg.content[:MAX_CHARS])
        
        # Create the complete data structure
        data = {
            "people": people_data,
            "locations": locations_data,
            "emotions": emotions_data,
            "events": events_data,
            "recent_messages": user_messages_data
        }
        
        # Create the system prompt
        print(f"[{timezone.now()}] Creating system prompt for story generation")
        system_prompt = """You are an AI specializing in crafting comprehensive life narratives. 
Your task is to use the information provided to create a cohesive life story.

I'll provide:
1. Recent messages from the user's conversation
2. People mentioned (with IDs)
3. Locations mentioned (with IDs)
4. Emotions mentioned (with IDs)
5. Events mentioned (with IDs)

Please analyze all the information and provide a JSON response with:
1. A list of entity IDs that should be associated with this story
2. A complete narrative that tells the user's life story

Your response must be in this JSON format:
{
    "title": "A meaningful title for the life story",
    "narrative": "The complete life narrative (detailed, well-structured)",
    "people_ids": [1, 2, 3],  // IDs of people to include in the story
    "location_ids": [1, 2, 3],  // IDs of locations to include
    "emotion_ids": [1, 2, 3],  // IDs of emotions to include
    "event_ids": [1, 2, 3]  // IDs of events to include
}

The narrative should be comprehensive but focus on the most important elements from the data."""

        # Serialize the data to JSON
        data_json = json.dumps(data, indent=2)
        
        # Create the messages array
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is the information to create the life story:\n{data_json}"}
        ]
        
        # Send to OpenAI for story generation
        print(f"[{timezone.now()}] Sending request to OpenAI for story generation")
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=3000,
        )
        
        story_content = response.choices[0].message['content']
        print(f"[{timezone.now()}] Received story content from OpenAI: {len(story_content)} characters")
        
        # Try to parse the response as JSON
        try:
            print(f"[{timezone.now()}] Attempting to parse story content as JSON")
            story_data = json.loads(story_content)
            
            # Get the narrative and title
            narrative = story_data.get('narrative', '')
            title = story_data.get('title', "My Life Story")
            print(f"[{timezone.now()}] Successfully parsed JSON response. Title: {title}")
            
            # Get the associated entity IDs
            people_ids = story_data.get('people_ids', [])
            location_ids = story_data.get('location_ids', [])
            emotion_ids = story_data.get('emotion_ids', [])
            event_ids = story_data.get('event_ids', [])
            
            # Create a new LifeStory object with just the narrative
            print(f"[{timezone.now()}] Creating new LifeStory object")
            life_story = LifeStory.objects.create(
                user=user,
                title=title,
                content=narrative,  # Just the narrative, not the full JSON
                is_complete=True
            )
            
            # Add related entities by ID
            print(f"[{timezone.now()}] Adding related entities to story by ID")
            
            # Add people
            if people_ids:
                people_to_add = Person.objects.filter(id__in=people_ids)
                life_story.people.set(people_to_add)
                print(f"[{timezone.now()}] Added {people_to_add.count()} people to story")
            
            # Add locations
            if location_ids:
                locations_to_add = Location.objects.filter(id__in=location_ids)
                life_story.locations.set(locations_to_add)
                print(f"[{timezone.now()}] Added {locations_to_add.count()} locations to story")
            
            # Add emotions
            if emotion_ids:
                emotions_to_add = Emotion.objects.filter(id__in=emotion_ids)
                life_story.emotions.set(emotions_to_add)
                print(f"[{timezone.now()}] Added {emotions_to_add.count()} emotions to story")
            
            # Add events
            if event_ids:
                events_to_add = Event.objects.filter(id__in=event_ids)
                life_story.events.set(events_to_add)
                print(f"[{timezone.now()}] Added {events_to_add.count()} events to story")
            
            print(f"[{timezone.now()}] Life story created successfully (ID: {life_story.id})")
            return life_story
            
        except json.JSONDecodeError:
            print(f"[{timezone.now()}] Failed to parse as JSON, using raw text")
            # If it's not valid JSON, use the raw text
            life_story = LifeStory.objects.create(
                user=user,
                title="My Life Story",
                content=story_content,
                is_complete=True
            )
            
            # Add all entities as we couldn't determine specific ones
            life_story.people.set(people)
            life_story.locations.set(locations)
            life_story.emotions.set(emotions)
            life_story.events.set(events)
            
            print(f"[{timezone.now()}] Life story created successfully (ID: {life_story.id})")
            return life_story
            
    except Exception as e:
        print(f"[{timezone.now()}] Error generating life story: {str(e)}")
        return None

def process_ai_response(ai_data, user):
    """Process the AI response to extract and save entities"""
    print(f"[{timezone.now()}] Starting to process AI response for user {user.username}")
    
    try:
        # Extract people if available
        if 'people' in ai_data and ai_data['people']:
            people_count = len(ai_data['people']) if isinstance(ai_data['people'], list) else 0
            print(f"[{timezone.now()}] Processing {people_count} people from AI response")
            
            for person_data in ai_data['people']:
                if not isinstance(person_data, dict) or 'name' not in person_data:
                    print(f"[{timezone.now()}] Skipping invalid person data: {person_data}")
                    continue
                    
                try:
                    person, created = Person.objects.get_or_create(
                        name=person_data.get('name', ''),
                        defaults={
                            'relation': person_data.get('relation', ''),
                            'location': person_data.get('location', ''),
                            'about': person_data.get('about', '')
                        }
                    )
                    if created:
                        print(f"[{timezone.now()}] Created new person: {person.name}")
                    else:
                        # Update existing person if new info is available
                        updated = False
                        if 'relation' in person_data and person_data['relation'] and not person.relation:
                            person.relation = person_data['relation']
                            updated = True
                        if 'location' in person_data and person_data['location'] and not person.location:
                            person.location = person_data['location']
                            updated = True
                        if 'about' in person_data and person_data['about'] and not person.about:
                            person.about = person_data['about']
                            updated = True
                        
                        if updated:
                            person.save()
                            print(f"[{timezone.now()}] Updated existing person: {person.name}")
                        else:
                            print(f"[{timezone.now()}] Found existing person, no updates needed: {person.name}")
                except Exception as e:
                    print(f"[{timezone.now()}] Error processing person {person_data.get('name', '')}: {str(e)}")
        
        # Extract locations if available
        if 'locations' in ai_data and ai_data['locations']:
            locations_count = len(ai_data['locations']) if isinstance(ai_data['locations'], list) else 0
            print(f"[{timezone.now()}] Processing {locations_count} locations from AI response")
            
            for location_data in ai_data['locations']:
                if not isinstance(location_data, dict) or 'name' not in location_data:
                    print(f"[{timezone.now()}] Skipping invalid location data: {location_data}")
                    continue
                    
                try:
                    location, created = Location.objects.get_or_create(
                        name=location_data.get('name', ''),
                        defaults={
                            'description': location_data.get('description', '')
                        }
                    )
                    if created:
                        print(f"[{timezone.now()}] Created new location: {location.name}")
                    elif 'description' in location_data and location_data['description'] and not location.description:
                        location.description = location_data['description']
                        location.save()
                        print(f"[{timezone.now()}] Updated existing location: {location.name}")
                    else:
                        print(f"[{timezone.now()}] Found existing location, no updates needed: {location.name}")
                except Exception as e:
                    print(f"[{timezone.now()}] Error processing location {location_data.get('name', '')}: {str(e)}")
        
        # Extract emotions if available
        if 'emotions' in ai_data and ai_data['emotions']:
            emotions_count = len(ai_data['emotions']) if isinstance(ai_data['emotions'], list) else 0
            print(f"[{timezone.now()}] Processing {emotions_count} emotions from AI response")
            
            for emotion_data in ai_data['emotions']:
                if not isinstance(emotion_data, dict) or 'name' not in emotion_data:
                    print(f"[{timezone.now()}] Skipping invalid emotion data: {emotion_data}")
                    continue
                    
                try:
                    emotion, created = Emotion.objects.get_or_create(
                        name=emotion_data.get('name', ''),
                        defaults={
                            'description': emotion_data.get('description', '')
                        }
                    )
                    if created:
                        print(f"[{timezone.now()}] Created new emotion: {emotion.name}")
                    elif 'description' in emotion_data and emotion_data['description'] and not emotion.description:
                        emotion.description = emotion_data['description']
                        emotion.save()
                        print(f"[{timezone.now()}] Updated existing emotion: {emotion.name}")
                    else:
                        print(f"[{timezone.now()}] Found existing emotion, no updates needed: {emotion.name}")
                except Exception as e:
                    print(f"[{timezone.now()}] Error processing emotion {emotion_data.get('name', '')}: {str(e)}")
        
        # Extract events if available
        if 'events' in ai_data and ai_data['events']:
            events_count = len(ai_data['events']) if isinstance(ai_data['events'], list) else 0
            print(f"[{timezone.now()}] Processing {events_count} events from AI response")
            
            for event_data in ai_data['events']:
                if not isinstance(event_data, dict) or 'title' not in event_data:
                    print(f"[{timezone.now()}] Skipping invalid event data: {event_data}")
                    continue
                    
                try:
                    # Create or get location if specified
                    location = None
                    if 'location' in event_data and event_data['location']:
                        loc_data = event_data['location']
                        if isinstance(loc_data, dict) and 'name' in loc_data:
                            location, location_created = Location.objects.get_or_create(
                                name=loc_data.get('name', ''),
                                defaults={'description': loc_data.get('description', '')}
                            )
                            print(f"[{timezone.now()}] {'Created' if location_created else 'Found'} location for event: {location.name}")
                        elif isinstance(loc_data, str):
                            location, location_created = Location.objects.get_or_create(name=loc_data)
                            print(f"[{timezone.now()}] {'Created' if location_created else 'Found'} location for event: {location.name}")
                    
                    # Check if event with the same title already exists
                    print(f"[{timezone.now()}] Looking for existing event: {event_data.get('title', '')}")
                    try:
                        event = Event.objects.get(title=event_data.get('title', ''))
                        created = False
                        print(f"[{timezone.now()}] Found existing event: {event.title}")
                    except Event.DoesNotExist:
                        event = Event.objects.create(
                            title=event_data.get('title', ''),
                            description=event_data.get('description', ''),
                            location=location,
                            color=event_data.get('color', '')
                        )
                        created = True
                        print(f"[{timezone.now()}] Created new event: {event.title}")
                    except Event.MultipleObjectsReturned:
                        # If multiple events with the same title exist, use the first one
                        event = Event.objects.filter(title=event_data.get('title', '')).first()
                        created = False
                        print(f"[{timezone.now()}] Found multiple events with title '{event.title}', using first one (ID: {event.id})")
                    
                    if not created:
                        # Update existing event if needed
                        updated = False
                        if event_data.get('description') and not event.description:
                            event.description = event_data.get('description')
                            updated = True
                        if location and not event.location:
                            event.location = location
                            updated = True
                        if event_data.get('color') and not event.color:
                            event.color = event_data.get('color')
                            updated = True
                        
                        if updated:
                            event.save()
                            print(f"[{timezone.now()}] Updated existing event: {event.title}")
                    
                    # Add people to event if available
                    if 'people_present' in event_data and event_data['people_present']:
                        people_present_count = len(event_data['people_present']) if isinstance(event_data['people_present'], list) else 0
                        print(f"[{timezone.now()}] Adding {people_present_count} people to event: {event.title}")
                        
                        for person_name in event_data['people_present']:
                            try:
                                if isinstance(person_name, str):
                                    person, person_created = Person.objects.get_or_create(name=person_name)
                                    event.people_present.add(person)
                                    print(f"[{timezone.now()}] Added person to event: {person.name}")
                                elif isinstance(person_name, dict) and 'name' in person_name:
                                    person, person_created = Person.objects.get_or_create(name=person_name['name'])
                                    event.people_present.add(person)
                                    print(f"[{timezone.now()}] Added person to event: {person.name}")
                            except Exception as e:
                                print(f"[{timezone.now()}] Error adding person {person_name} to event: {str(e)}")
                    
                    # Add emotions to event if available
                    if 'emotions' in event_data and event_data['emotions']:
                        emotions_count = len(event_data['emotions']) if isinstance(event_data['emotions'], list) else 0
                        print(f"[{timezone.now()}] Adding {emotions_count} emotions to event: {event.title}")
                        
                        for emotion_name in event_data['emotions']:
                            try:
                                if isinstance(emotion_name, str):
                                    emotion, emotion_created = Emotion.objects.get_or_create(name=emotion_name)
                                    event.emotions.add(emotion)
                                    print(f"[{timezone.now()}] Added emotion to event: {emotion.name}")
                                elif isinstance(emotion_name, dict) and 'name' in emotion_name:
                                    emotion, emotion_created = Emotion.objects.get_or_create(name=emotion_name['name'])
                                    event.emotions.add(emotion)
                                    print(f"[{timezone.now()}] Added emotion to event: {emotion.name}")
                            except Exception as e:
                                print(f"[{timezone.now()}] Error adding emotion {emotion_name} to event: {str(e)}")

                except Exception as e:
                    print(f"[{timezone.now()}] Error processing event {event_data.get('title', '')}: {str(e)}")
    
    except Exception as e:
        print(f"[{timezone.now()}] Error in process_ai_response: {str(e)}")
    
    print(f"[{timezone.now()}] Completed processing AI response")

def get_interview_system_prompt(existing_entities_json=None):
    base_prompt = """You are an AI interviewer conducting an in-depth interview about someone's life story. 
BE DIRECT AND CONVERSATIONAL. DO NOT INTRODUCE YOURSELF OR ASK HOW YOU CAN HELP.

Your interview approach:
1. Ask specific, thoughtful questions about key life experiences, relationships, and feelings
2. Follow up on interesting details the person shares
3. Guide the conversation to uncover meaningful life events and emotions
4. Maintain a warm, empathetic tone throughout

IMPORTANT: NEVER say things like "How can I assist you?" or "What can I help you with?"
Just start the interview with direct questions about their life.

Your responses must be in valid JSON format:
{
"response": "Your actual interview question or follow-up (be conversational and natural)",
"people": [
{
"name": "Name",
"relation": "Relation to user",
"location": "Where they're from",
"about": "Brief description"
}
],
"locations": [
{
"name": "Place name",
"description": "Description of place"
}
],
"emotions": [
{
"name": "Emotion name",
"description": "Context for emotion"
}
],
"events": [
{
"title": "Event title",
"description": "What happened",
"location": {"name": "Where it happened"},
"people_present": ["Person1", "Person2"],
"emotions": ["Emotion1", "Emotion2"],
"color": "#HEX"
}
],
"story_mode": false
}
you have to ask users according to the last conversation
Why user share a story or in last messages user has shared a complete story which is't in saved, set "story_mode": true"""

    # Add existing entities if provided
    if existing_entities_json:
        try:
            existing_entities = json.loads(existing_entities_json)
            addition = "\n\nExisting entities (If already some data exists don't send it in json) (format: name,id):\n"
            
            if existing_entities.get('people'):
                addition += "\nPeople:\n" + "\n".join(existing_entities['people'])
            
            if existing_entities.get('locations'):
                addition += "\nLocations:\n" + "\n".join(existing_entities['locations'])
            
            if existing_entities.get('emotions'):
                addition += "\nEmotions:\n" + "\n".join(existing_entities['emotions'])
            
            if existing_entities.get('events'):
                addition += "\nEvents:\n" + "\n".join(existing_entities['events'])
            
            print("\n\n", base_prompt + addition, "\n\n")
            return base_prompt + addition
        except:
            pass
    
    return base_prompt

def get_free_mode_system_prompt(existing_entities_json=None):
    base_prompt = """You are an AI chatbot having an engaging conversation about someone's life experiences and memories.
BE DIRECT AND CONVERSATIONAL. DO NOT INTRODUCE YOURSELF OR ASK HOW YOU CAN HELP.

Your conversation approach:
1. Ask interesting questions about the person's life, experiences, and feelings
2. Respond naturally to what they share, showing genuine interest
3. Extract meaningful events, people, and emotions from their responses
4. Build a natural connection through the conversation

IMPORTANT: NEVER say things like "How can I assist you?" or "What can I help you with?"
Just start the conversation with direct questions about their life.

Your responses must be in valid JSON format:
{
"response": "Your actual conversational response to the user (be natural and engaging)",
"people": [
{
"name": "Name",
"relation": "Relation to user",
"location": "Where they're from",
"about": "Brief description"
}
],
"locations": [
{
"name": "Place name",
"description": "Description of place"
}
],
"emotions": [
{
"name": "Emotion name",
"description": "Context for emotion"
}
],
"events": [
{
"title": "Event title",
"description": "What happened",
"location": {"name": "Where it happened"},
"people_present": ["Person1", "Person2"],
"emotions": ["Emotion1", "Emotion2"],
"color": "#HEX"
}
]
},
"story_mode": false
}
you have to ask users according to the last conversation
Why user share a story or in last messages user has shared a complete story which is't in saved, set "story_mode": true"""

    # Add existing entities if provided
    if existing_entities_json:
        try:
            existing_entities = json.loads(existing_entities_json)
            addition = "\n\nExisting entities (If already some data exists don't send it in json) (format: name,id):\n"
            
            if existing_entities.get('people'):
                addition += "\nPeople:\n" + "\n".join(existing_entities['people'])
            
            if existing_entities.get('locations'):
                addition += "\nLocations:\n" + "\n".join(existing_entities['locations'])
            
            if existing_entities.get('emotions'):
                addition += "\nEmotions:\n" + "\n".join(existing_entities['emotions'])
            
            if existing_entities.get('events'):
                addition += "\nEvents:\n" + "\n".join(existing_entities['events'])
            
            print("\n\n", base_prompt + addition, "\n\n")
            return base_prompt + addition
        except:
            pass
    
    return base_prompt