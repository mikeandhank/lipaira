#!/usr/bin/env python3
"""
NexusOS MCP HTTP Server

Provides web request capabilities to the agent.

Features:
- GET, POST, PUT, DELETE
- Custom headers
- JSON body
- Timeout control
"""

import os
import json
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse as urlp

TIMEOUT = int(os.environ.get('TIMEOUT', 30))

def make_request(method: str, url: str, headers: dict = None, data: dict = None) -> dict:
    """Make an HTTP request"""
    
    try:
        req = urllib.request.Request(url, method=method)
        
        # Add headers
        default_headers = {
            'User-Agent': 'NexusOS-MCP/1.0',
            'Accept': 'application/json'
        }
        
        for k, v in {**default_headers, **(headers or {})}.items():
            req.add_header(k, v)
        
        # Add body for POST/PUT
        if data and method in ['POST', 'PUT', 'PATCH']:
            body = json.dumps(data).encode('utf-8')
            req.add_header('Content-Type', 'application/json')
            req.data = body
        
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode('utf-8')
            
            try:
                json_body = json.loads(body)
            except:
                json_body = body
            
            return {
                'success': True,
                'method': method,
                'url': url,
                'status': resp.status,
                'headers': dict(resp.headers),
                'body': json_body
            }
    
    except urllib.error.HTTPError as e:
        return {
            'success': False,
            'error': f'HTTP {e.code}: {e.reason}',
            'method': method,
            'url': url,
            'status': e.code
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'method': method,
            'url': url
        }

def get(url: str, headers: dict = None) -> dict:
    return make_request('GET', url, headers)

def post(url: str, data: dict = None, headers: dict = None) -> dict:
    return make_request('POST', url, headers, data)

def put(url: str, data: dict = None, headers: dict = None) -> dict:
    return make_request('PUT', url, headers, data)

def delete(url: str, headers: dict = None) -> dict:
    return make_request('DELETE', url, headers)

class MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            request = json.loads(body.decode('utf-8'))
            
            method = request.get('method')
            params = request.get('params', {})
            
            if method == 'get':
                result = get(params.get('url'), params.get('headers'))
            elif method == 'post':
                result = post(params.get('url'), params.get('data'), params.get('headers'))
            elif method == 'put':
                result = put(params.get('url'), params.get('data'), params.get('headers'))
            elif method == 'delete':
                result = delete(params.get('url'), params.get('headers'))
            else:
                result = {'error': f'Unknown method: {method}'}
            
            response = json.dumps(result)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(response.encode())
            
        except Exception as e:
            error = json.dumps({'error': str(e)})
            self.send_response(500)
            self.end_headers()
            self.wfile.write(error.encode())

def main():
    print(f'[MCP-HTTP] Starting HTTP Server on port 4896')
    server = HTTPServer(('127.0.0.1', 4896), MCPHandler)
    server.serve_forever()

if __name__ == '__main__':
    main()