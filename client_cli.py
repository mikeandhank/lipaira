# feel free to ignore this comment
     1|"""
     2|Lipaira Client CLI
     3|Connects to Lipaira Server API for LLM access
     4|Usage: python client_cli.py --key *** --message "Hello"
     5|"""
     6|
     7|import os
     8|import sys
     9|import json
    10|import argparse
    11|import requests
    12|from datetime import datetime
    13|
    14|DEFAULT_SERVER = "http://localhost:8080"
    15|# trigger QA pipeline
    16|
    17|
    18|class LipairaClient:
    19|    """Client for Lipaira Server API."""
    20|    
    21|    def __init__(self, api_key: str, server_url: str = None):
    22|        self.api_key = api_key
    23|        self.server_url = server_url or DEFAULT_SERVER
    24|        self.session = requests.Session()
    25|        self.session.headers.update({
    26|            'X-Lipaira-Key': api_key,
    27|            'Content-Type': 'application/json'
    28|        })
    29|    
    30|    def chat(self, message: str, model: str = None, stream: bool = False):
    31|        """Send a chat message."""
    32|        data = {'message': message}
    33|        if model:
    34|            data['model'] = model
    35|        if stream:
    36|            data['stream'] = True
    37|        
    38|        response = self.session.post(f"{self.server_url}/api/chat", json=data)
    39|        
    40|        if response.status_code != 200:
    41|            return {
    42|                'success': False,
    43|                'error': response.text
    44|            }
    45|        
    46|        result = response.json()
    47|        
    48|        return {
    49|            'success': True,
    50|            'content': result.get('content', ''),
    51|            'model': result.get('model'),
    52|            'provider': result.get('provider'),
    53|            'usage': result.get('usage', {})
    54|        }
    55|    
    56|    def get_config(self):
    57|        """Get LLM configuration."""
    58|        response = self.session.get(f"{self.server_url}/api/config")
    59|        return response.json() if response.status_code == 200 else {'error': response.text}
    60|    
    61|    def set_config(self, provider: str, model: str):
    62|        """Update LLM configuration."""
    63|        response = self.session.put(f"{self.server_url}/api/config", json={'provider': provider, 'model': model})
    64|        return response.json() if response.status_code == 200 else {'error': response.text}
    65|    
    66|    def get_models(self):
    67|        """Get available models."""
    68|        response = self.session.get(f"{self.server_url}/api/models")
    69|        return response.json() if response.status_code == 200 else {'error': response.text}
    70|    
    71|    def get_credits(self):
    72|        """Get credit balance."""
    73|        response = self.session.get(f"{self.server_url}/api/credits")
    74|        return response.json() if response.status_code == 200 else {'error': response.text}
    75|    
    76|    def login(self, email: str, password: str):
    77|        """Login and get API key."""
    78|        response = self.session.post(f"{self.server_url}/api/auth/login", json={'email': email, 'password': password})
    79|        return response.json() if response.status_code == 200 else {'error': response.text}
    80|    
    81|    def register(self, email: str, password: str, name: str = None):
    82|        """Register new account."""
    83|        data = {'email': email, 'password': password}
    84|        if name:
    85|            data['name'] = name
    86|        response = self.session.post(f"{self.server_url}/api/auth/register", json=data)
    87|        return response.json() if response.status_code in [200, 201] else {'error': response.text}
    88|
    89|
    90|def main():
    91|    parser = argparse.ArgumentParser(description='Lipaira Client')
    92|    parser.add_argument('--key', '-k', help='Lipaira API Key (or set LIPAIRA_API_KEY)')
    93|    parser.add_argument('--server', '-s', default=DEFAULT_SERVER, help='Server URL')
    94|    parser.add_argument('--message', '-m', help='Message to send')
    95|    parser.add_argument('--model', help='Model to use')
    96|    parser.add_argument('--config', action='store_true', help='Show config')
    97|    parser.add_argument('--credits', action='store_true', help='Show credits')
    98|    parser.add_argument('--models', action='store_true', help='List models')
    99|    parser.add_argument('--register', nargs=2, help='Register: email password')
   100|    parser.add_argument('--login', nargs=2, help='Login: email password')
   101|    
   102|    args = parser.parse_args()
   103|    
   104|    api_key = args.key or os.environ.get('LIPAIRA_API_KEY')
   105|    
   106|    if args.register:
   107|        client = LipairaClient('dummy', args.server)
   108|        result = client.register(args.register[0], args.register[1])
   109|        if 'error' in result:
   110|            print(f"Error: {result['error']}")
   111|            sys.exit(1)
   112|        print(f"Registered! API Key: {result.get('api_key')}")
   113|        sys.exit(0)
   114|    
   115|    if args.login:
   116|        client = LipairaClient('dummy', args.server)
   117|        result = client.login(args.login[0], args.login[1])
   118|        if 'error' in result:
   119|            print(f"Error: {result['error']}")
   120|            sys.exit(1)
   121|        print(f"Logged in! API Key: {result.get('api_key')}")
   122|        sys.exit(0)
   123|    
   124|    if not api_key:
   125|        print("Error: API key required (--key or LIPAIRA_API_KEY)")
   126|        sys.exit(1)
   127|    
   128|    client = LipairaClient(api_key, args.server)
   129|    
   130|    if args.config:
   131|        print(json.dumps(client.get_config(), indent=2))
   132|    elif args.credits:
   133|        print(f"Credits: {client.get_credits().get('credits', 0)}")
   134|    elif args.models:
   135|        print(json.dumps(client.get_models(), indent=2))
   136|    elif args.message:
   137|        result = client.chat(args.message, args.model)
   138|        if result.get('success'):
   139|            print(f"\n{result.get('content')}")
   140|        else:
   141|            print(f"Error: {result.get('error')}")
   142|    else:
   143|        print("Lipaira Client - Type message:")
   144|        while True:
   145|            try:
   146|                msg = input("\n> ")
   147|                if msg.strip():
   148|                    result = client.chat(msg)
   149|                    print(f"\n{result.get('content', result.get('error'))}")
   150|            except KeyboardInterrupt:
   151|                break
   152|
   153|
   154|if __name__ == '__main__':
   155|    main()
   156|