"""
Lipaira Client CLI
Connects to Lipaira Server API for LLM access
Usage: python client_cli.py --key *** --message "Hello"
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
        """Initialize the Lipaira client.

        Args:
            api_key: The API key for authentication with the Lipaira server.
            server_url: Optional base URL of the server. Defaults to localhost:8080.

        Returns:
            None. Initializes instance attributes: api_key, server_url, session.
        """
        self.api_key = api_key
        self.server_url = server_url or DEFAULT_SERVER
        self.session = requests.Session()
        self.session.headers.update({
            'X-Lipaira-Key': api_key,
            'Content-Type': 'application/json'
        })
    
    def chat(self, message: str, model: str = None, stream: bool = False):
        """Send a chat message to the LLM.

        Args:
            message: The user message to send.
            model: Optional model name to use (defaults to server config).
            stream: Whether to stream the response (default False).

        Returns:
            dict: A dictionary with keys:
                - success (bool): True if request succeeded, False otherwise.
                - content (str): The response content (on success).
                - model (str): The model used for the response.
                - provider (str): The provider that handled the request.
                - usage (dict): Token usage statistics.
                - error (str): Error message (on failure).
        """
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
        """Get the current LLM configuration.

        Args:
            None.

        Returns:
            dict: The server configuration including provider and model settings,
                  or {'error': 'message'} on failure.
        """
        response = self.session.get(f"{self.server_url}/api/config")
        return response.json() if response.status_code == 200 else {'error': response.text}
    
    def set_config(self, provider: str, model: str):
        """Update the LLM configuration.

        Args:
            provider: The provider name (e.g., 'openai', 'anthropic').
            model: The model name to use.

        Returns:
            dict: The updated configuration on success, or {'error': 'message'} on failure.
        """
        response = self.session.put(f"{self.server_url}/api/config", json={'provider': provider, 'model': model})
        return response.json() if response.status_code == 200 else {'error': response.text}
    
    def get_models(self):
        """Get available models from the server.

        Args:
            None.

        Returns:
            dict: A dictionary of available models by provider, or {'error': 'message'} on failure.
        """
        response = self.session.get(f"{self.server_url}/api/models")
        return response.json() if response.status_code == 200 else {'error': response.text}
    
    def get_credits(self):
        """Get the current credit balance.

        Args:
            None.

        Returns:
            dict: A dictionary containing 'credits' (float) on success, or {'error': 'message'} on failure.
        """
        response = self.session.get(f"{self.server_url}/api/credits")
        return response.json() if response.status_code == 200 else {'error': response.text}
    
    def login(self, email: str, password: str):
        """Login and retrieve an API key.

        Args:
            email: The user's email address.
            password: The user's password.

        Returns:
            dict: A dictionary containing 'api_key' on success, or {'error': 'message'} on failure.
        """
        response = self.session.post(f"{self.server_url}/api/auth/login", json={'email': email, 'password': password})
        return response.json() if response.status_code == 200 else {'error': response.text}
    
    def register(self, email: str, password: str, name: str = None):
        """Register a new account.

        Args:
            email: The user's email address.
            password: The desired password.
            name: Optional display name for the user.

        Returns:
            dict: A dictionary containing 'api_key' on success, or {'error': 'message'} on failure.
        """
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
        client = LipairaClient('dummy', args.server)
        result = client.register(args.register[0], args.register[1])
        if 'error' in result:
            print(f"Error: {result['error']}")
            sys.exit(1)
        print(f"Registered! API Key: {result.get('api_key')}")
        sys.exit(0)
    
    if args.login:
        client = LipairaClient('dummy', args.server)
        result = client.login(args.login[0], args.login[1])
        if 'error' in result:
            print(f"Error: {result['error']}")
            sys.exit(1)
        print(f"Logged in! API Key: {result.get('api_key')}")
        sys.exit(0)
    
    if not api_key:
        print("Error: API key required (--key or NEXUS_API_KEY)")
        sys.exit(1)
    
    client = LipairaClient(api_key, args.server)
    
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
