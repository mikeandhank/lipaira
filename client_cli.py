"""
Lipaira Client CLI
Connects to Lipaira Server API for LLM access
Usage: python client_cli.py --key sk-lipaira-xxx --message "Hello"
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime

DEFAULT_SERVER = "http://localhost:8080"


class LipairaClient:
    """Client for Lipaira Server API."""
    
    def __init__(self, api_key: str, server_url: str = None):
        self.api_key = api_key
        self.server_url = server_url or DEFAULT_SERVER
        self.session = requests.Session()
        self.session.headers.update({
            'X-Lipaira-Key': api_key,
            'Content-Type': 'application/json'
        })
    
    def chat(self, message: str, model: str = None, stream: bool = False):
        """Send a chat message."""
        data = {'message': message}
        if model:
            data['model'] = model
        if stream:
            data['stream'] = True
        
        response = self.session.post(f"{self.server_url}/api/chat", json=data)
        
        if response.status_code != 200:
            return {
                'success': False,
                'error': response.text
            }
        
        result = response.json()
        
        return {
            'success': True,
            'content': result.get('content', ''),
            'model': result.get('model'),
            'provider': result.get('provider'),
            'usage': result.get('usage', {})
        }
    
    def get_config(self):
        """Get LLM configuration."""
        response = self.session.get(f"{self.server_url}/api/config")
        return response.json() if response.status_code == 200 else {'error': response.text}
    
    def set_config(self, provider: str, model: str):
        """Update LLM configuration."""
        response = self.session.put(f"{self.server_url}/api/config", json={'provider': provider, 'model': model})
        return response.json() if response.status_code == 200 else {'error': response.text}
    
    def get_models(self):
        """Get available models."""
        response = self.session.get(f"{self.server_url}/api/models")
        return response.json() if response.status_code == 200 else {'error': response.text}
    
    def get_credits(self):
        """Get credit balance."""
        response = self.session.get(f"{self.server_url}/api/credits")
        return response.json() if response.status_code == 200 else {'error': response.text}
    
    def login(self, email: str, password: str):
        """Login and get API key."""
        response = self.session.post(f"{self.server_url}/api/auth/login", json={'email': email, 'password': password})
        return response.json() if response.status_code == 200 else {'error': response.text}
    
    def register(self, email: str, password: str, name: str = None):
        """Register new account."""
        data = {'email': email, 'password': password}
        if name:
            data['name'] = name
        response = self.session.post(f"{self.server_url}/api/auth/register", json=data)
        return response.json() if response.status_code in [200, 201] else {'error': response.text}


def main():
    parser = argparse.ArgumentParser(description='Lipaira Client')
    parser.add_argument('--key', '-k', help='Nexus API Key (or set NEXUS_API_KEY)')
    parser.add_argument('--server', '-s', default=DEFAULT_SERVER, help='Server URL')
    parser.add_argument('--message', '-m', help='Message to send')
    parser.add_argument('--model', help='Model to use')
    parser.add_argument('--config', action='store_true', help='Show config')
    parser.add_argument('--credits', action='store_true', help='Show credits')
    parser.add_argument('--models', action='store_true', help='List models')
    parser.add_argument('--register', nargs=2, help='Register: email password')
    parser.add_argument('--login', nargs=2, help='Login: email password')
    
    args = parser.parse_args()
    
    api_key = args.key or os.environ.get('NEXUS_API_KEY')
    
    if args.register:
        client = NexusClient('dummy', args.server)
        result = client.register(args.register[0], args.register[1])
        if 'error' in result:
            print(f"Error: {result['error']}")
            sys.exit(1)
        print(f"Registered! API Key: {result.get('api_key')}")
        sys.exit(0)
    
    if args.login:
        client = NexusClient('dummy', args.server)
        result = client.login(args.login[0], args.login[1])
        if 'error' in result:
            print(f"Error: {result['error']}")
            sys.exit(1)
        print(f"Logged in! API Key: {result.get('api_key')}")
        sys.exit(0)
    
    if not api_key:
        print("Error: API key required (--key or NEXUS_API_KEY)")
        sys.exit(1)
    
    client = NexusClient(api_key, args.server)
    
    if args.config:
        print(json.dumps(client.get_config(), indent=2))
    elif args.credits:
        print(f"Credits: {client.get_credits().get('credits', 0)}")
    elif args.models:
        print(json.dumps(client.get_models(), indent=2))
    elif args.message:
        result = client.chat(args.message, args.model)
        if result.get('success'):
            print(f"\n{result.get('content')}")
        else:
            print(f"Error: {result.get('error')}")
    else:
        print("Lipaira Client - Type message:")
        while True:
            try:
                msg = input("\n> ")
                if msg.strip():
                    result = client.chat(msg)
                    print(f"\n{result.get('content', result.get('error'))}")
            except KeyboardInterrupt:
                break


if __name__ == '__main__':
    main()
