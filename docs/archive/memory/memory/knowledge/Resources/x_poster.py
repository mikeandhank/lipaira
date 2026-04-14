#!/usr/bin/env python3
"""
NexusAI Twitter/X Poster
Ready to post when API keys are available.
"""
import tweepy
import os
import json
from datetime import datetime

# Get keys from environment or file
def get_keys():
    """Load API keys from environment or config file"""
    # Try environment first
    keys = {
        'api_key': os.environ.get('X_API_KEY'),
        'api_secret': os.environ.get('X_API_SECRET'),
        'access_token': os.environ.get('X_ACCESS_TOKEN'),
        'access_secret': os.environ.get('X_ACCESS_SECRET'),
    }
    
    # If missing, try loading from config file
    if not all(keys.values()):
        try:
            with open('/data/.openclaw/workspace/.x_keys.json', 'r') as f:
                keys.update(json.load(f))
        except:
            pass
    
    return keys

def post_tweet(text):
    """Post a single tweet"""
    keys = get_keys()
    
    if not all(keys.values()):
        raise ValueError("Missing API keys. Set environment variables or create .x_keys.json")
    
    client = tweepy.Client(
        consumer_key=keys['api_key'],
        consumer_secret=keys['api_secret'],
        access_token=keys['access_token'],
        access_token_secret=keys['access_secret']
    )
    
    response = client.create_tweet(text=text)
    print(f"Posted: {response.data['id']}")
    return response

def post_thread(tweets):
    """Post a thread of tweets"""
    keys = get_keys()
    
    if not all(keys.values()):
        raise ValueError("Missing API keys")
    
    client = tweepy.Client(
        consumer_key=keys['api_key'],
        consumer_secret=keys['api_secret'],
        access_token=keys['access_token'],
        access_token_secret=keys['access_secret']
    )
    
    # Post first tweet
    response = client.create_tweet(text=tweets[0])
    print(f"Thread start: {response.data['id']}")
    previous_id = response.data['id']
    
    # Reply to self to create thread
    for tweet in tweets[1:]:
        response = client.create_tweet(text=tweet, reply={'in_reply_to_tweet_id': previous_id})
        print(f"Thread reply: {response.data['id']}")
        previous_id = response.data['id']
    
    return True

if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) > 1:
        post_tweet(" ".join(sys.argv[1:]))
    else:
        print("Usage: python x_poster.py 'Your tweet text'")
