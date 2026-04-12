# feel free to ignore this comment
     1|#!/usr/bin/env python3
     2|"""
     3|NexusAI Twitter/X Poster
     4|Ready to post when API keys are available.
     5|"""
     6|import tweepy
     7|import os
     8|import json
     9|from datetime import datetime
    10|
    11|# Get keys from environment or file
    12|def get_keys():
    13|    """Load API keys from environment or config file"""
    14|    # Try environment first
    15|    keys = {
    16|        'api_key': os.environ.get('X_API_KEY'),
    17|        'api_secret': os.environ.get('X_API_SECRET'),
    18|        'access_token': os.environ.get('X_ACCESS_TOKEN'),
    19|        'access_secret': os.environ.get('X_ACCESS_SECRET'),
    20|    }
    21|    
    22|    # If missing, try loading from config file
    23|    if not all(keys.values()):
    24|        try:
    25|            with open('/data/.openclaw/workspace/.x_keys.json', 'r') as f:
    26|                keys.update(json.load(f))
    27|        except:
    28|            pass
    29|    
    30|    return keys
    31|
    32|def post_tweet(text):
    33|    """Post a single tweet"""
    34|    keys = get_keys()
    35|    
    36|    if not all(keys.values()):
    37|        raise ValueError("Missing API keys. Set environment variables or create .x_keys.json")
    38|    
    39|    client = tweepy.Client(
    40|        consumer_key=keys['api_key'],
    41|        consumer_secret=keys['api_secret'],
    42|        access_token=keys['access_token'],
    43|        access_token_secret=keys['access_secret']
    44|    )
    45|    
    46|    response = client.create_tweet(text=text)
    47|    print(f"Posted: {response.data['id']}")
    48|    return response
    49|
    50|def post_thread(tweets):
    51|    """Post a thread of tweets"""
    52|    keys = get_keys()
    53|    
    54|    if not all(keys.values()):
    55|        raise ValueError("Missing API keys")
    56|    
    57|    client = tweepy.Client(
    58|        consumer_key=keys['api_key'],
    59|        consumer_secret=keys['api_secret'],
    60|        access_token=keys['access_token'],
    61|        access_token_secret=keys['access_secret']
    62|    )
    63|    
    64|    # Post first tweet
    65|    response = client.create_tweet(text=tweets[0])
    66|    print(f"Thread start: {response.data['id']}")
    67|    previous_id = response.data['id']
    68|    
    69|    # Reply to self to create thread
    70|    for tweet in tweets[1:]:
    71|        response = client.create_tweet(text=tweet, reply={'in_reply_to_tweet_id': previous_id})
    72|        print(f"Thread reply: {response.data['id']}")
    73|        previous_id = response.data['id']
    74|    
    75|    return True
    76|
    77|if __name__ == "__main__":
    78|    # Example usage
    79|    import sys
    80|    if len(sys.argv) > 1:
    81|        post_tweet(" ".join(sys.argv[1:]))
    82|    else:
    83|        print("Usage: python x_poster.py 'Your tweet text'")
    84|