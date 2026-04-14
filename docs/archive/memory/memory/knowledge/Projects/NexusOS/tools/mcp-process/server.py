#!/usr/bin/env python3
"""
NexusOS MCP Process Server

Provides controlled command execution to the agent.

Security:
- Whitelist of allowed commands
- Timeout limits
- Output capture
"""

import subprocess
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# Configuration
ALLOWED_COMMANDS = os.environ.get('ALLOWED_COMMANDS', 'git,curl,wget,npm,node,python3,bash,sqlite3,ls,cat,echo,mkdir,cd').split(',')
TIMEOUT = 30  # seconds

def run_command(cmd: str, cwd: str = None) -> dict:
    """Execute a command with whitelist and timeout"""
    
    # Parse command
    parts = cmd.strip().split()
    if not parts:
        return {'error': 'Empty command'}
    
    cmd_name = parts[0]
    
    # Check whitelist
    # Allow full paths for allowed commands
    cmd_basename = os.path.basename(cmd_name)
    if cmd_basename not in ALLOWED_COMMANDS and cmd_name not in ALLOWED_COMMANDS:
        return {'error': f'Command not allowed: {cmd_name}', 'allowed': ALLOWED_COMMANDS}
    
    try:
        result = subprocess.run(
            parts,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT
        )
        
        return {
            'success': True,
            'command': cmd,
            'returncode': result.returncode,
            'stdout': result.stdout[:10000],  # Limit output
            'stderr': result.stderr[:5000]
        }
    
    except subprocess.TimeoutExpired:
        return {'error': f'Command timed out after {TIMEOUT}s', 'command': cmd}
    
    except Exception as e:
        return {'error': str(e), 'command': cmd}

def list_allowed() -> dict:
    """List allowed commands"""
    return {
        'allowed': ALLOWED_COMMANDS,
        'timeout': TIMEOUT
    }

class MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            request = json.loads(body.decode('utf-8'))
            
            method = request.get('method')
            params = request.get('params', {})
            
            if method == 'execute':
                result = run_command(
                    params.get('command'),
                    params.get('cwd')
                )
            elif method == 'list_allowed':
                result = list_allowed()
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
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(error.encode())
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'status': 'healthy',
                'server': 'mcp-process',
                'allowed': ALLOWED_COMMANDS
            }).encode())
        else:
            self.send_response(404)
            self.end_headers()

def main():
    print(f'[MCP-Process] Allowed commands: {ALLOWED_COMMANDS}')
    print('[MCP-Process] Starting Process Server on port 4895')
    
    server = HTTPServer(('127.0.0.1', 4895), MCPHandler)
    server.serve_forever()

if __name__ == '__main__':
    main()