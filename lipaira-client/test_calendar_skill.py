#!/usr/bin/env python3
"""
Test harness for calendar skill with real Google OAuth.
Verifies CalendarReadSkill and CalendarWriteSkill end-to-end with
live credentials obtained through the OAuth flow.
"""
import os
import sys

# Set up environment
os.environ['GATEWAY_URL'] = 'http://lipaira-api:8080'
os.environ['USER_ID'] = '1'  # Michael's user ID

# Add skills to path
sys.path.insert(0, os.path.dirname(__file__))

from skills.calendar_skill import CalendarReadSkill, CalendarWriteSkill

# Test 1: Read calendar
print("=" * 50)
print("TEST 1: Reading calendar...")
print("=" * 50)

read_skill = CalendarReadSkill()
result = read_skill.execute({'days_ahead': 7, 'max_events': 5})

if result.success:
    print(f"✅ Success! Found {result.output.get('count', 0)} events:")
    for e in result.output.get('events', [])[:3]:
        print(f"  - {e['title']} at {e['start']}")
else:
    print(f"❌ Failed: {result.error}")

# Test 2: Create event
print("\n" + "=" * 50)
print("TEST 2: Creating test event...")
print("=" * 50)

from datetime import datetime
today = datetime.now().strftime('%Y-%m-%d')

write_skill = CalendarWriteSkill()
result = write_skill.execute({
    'title': 'Lipaira Test Event',
    'date': today,
    'time': '14:00',  # 2 PM
    'duration_minutes': 30,
    'description': 'Testing Lipaira calendar skill via Google OAuth'
})

if result.success:
    print(f"✅ Event created!")
    print(f"   ID: {result.output.get('event_id')}")
    print(f"   Link: {result.output.get('link')}")
else:
    print(f"❌ Failed: {result.error}")