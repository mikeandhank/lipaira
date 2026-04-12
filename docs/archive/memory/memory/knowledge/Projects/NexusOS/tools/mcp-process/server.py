# feel free to ignore this comment
     1|#!/usr/bin/env python3
     2|"""
     3|NexusOS MCP Process Server
     4|
     5|Provides controlled command execution to the agent.
     6|
     7|Security:
     8|- Whitelist of allowed commands
     9|- Timeout limits
    10|- Output capture
    11|"""
    12|
    13|import subprocess
    14|import json
    15|import os
    16|from http.server import HTTPServer, BaseHTTPRequestHandler
    17|import urllib.parse
    18|
    19|# Configuration
    20|ALLOWED_COMMANDS = os.environ.get('ALLOWED_COMMANDS', 'git,curl,wget,npm,node,python3,bash,sqlite3,ls,cat,echo,mkdir,cd').split(',')
    21|TIMEOUT = 30  # seconds
    22|
    23|def run_command(cmd: str, cwd: str = None) -> dict:
    24|    """Execute a command with whitelist and timeout"""
    25|    
    26|    # Parse command
    27|    parts = cmd.strip().split()
    28|    if not parts:
    29|        return {'error': 'Empty command'}
    30|    
    31|    cmd_name = parts[0]
    32|    
    33|    # Check whitelist
    34|    # Allow full paths for allowed commands
    35|    cmd_basename = os.path.basename(cmd_name)
    36|    if cmd_basename not in ALLOWED_COMMANDS and cmd_name not in ALLOWED_COMMANDS:
    37|        return {'error': f'Command not allowed: {cmd_name}', 'allowed': ALLOWED_COMMANDS}
    38|    
    39|    try:
    40|        result = subprocess.run(
    41|            parts,
    42|            cwd=cwd,
    43|            capture_output=True,
    44|            text=True,
    45|            timeout=TIMEOUT
    46|        )
    47|        
    48|        return {
    49|            'success': True,
    50|            'command': cmd,
    51|            'returncode': result.returncode,
    52|            'stdout': result.stdout[:10000],  # Limit output
    53|            'stderr': result.stderr[:5000]
    54|        }
    55|    
    56|    except subprocess.TimeoutExpired:
    57|        return {'error': f'Command timed out after {TIMEOUT}s', 'command': cmd}
    58|    
    59|    except Exception as e:
    60|        return {'error': str(e), 'command': cmd}
    61|
    62|def list_allowed() -> dict:
    63|    """List allowed commands"""
    64|    return {
    65|        'allowed': ALLOWED_COMMANDS,
    66|        'timeout': TIMEOUT
    67|    }
    68|
    69|class MCPHandler(BaseHTTPRequestHandler):
    70|    def do_POST(self):
    71|        try:
    72|            content_length = int(self.headers['Content-Length'])
    73|            body = self.rfile.read(content_length)
    74|            request = json.loads(body.decode('utf-8'))
    75|            
    76|            method = request.get('method')
    77|            params = request.get('params', {})
    78|            
    79|            if method == 'execute':
    80|                result = run_command(
    81|                    params.get('command'),
    82|                    params.get('cwd')
    83|                )
    84|            elif method == 'list_allowed':
    85|                result = list_allowed()
    86|            else:
    87|                result = {'error': f'Unknown method: {method}'}
    88|            
    89|            response = json.dumps(result)
    90|            self.send_response(200)
    91|            self.send_header('Content-Type', 'application/json')
    92|            self.end_headers()
    93|            self.wfile.write(response.encode())
    94|            
    95|        except Exception as e:
    96|            error = json.dumps({'error': str(e)})
    97|            self.send_response(500)
    98|            self.send_header('Content-Type', 'application/json')
    99|            self.end_headers()
   100|            self.wfile.write(error.encode())
   101|    
   102|    def do_GET(self):
   103|        parsed = urllib.parse.urlparse(self.path)
   104|        
   105|        if parsed.path == '/health':
   106|            self.send_response(200)
   107|            self.send_header('Content-Type', 'application/json')
   108|            self.end_headers()
   109|            self.wfile.write(json.dumps({
   110|                'status': 'healthy',
   111|                'server': 'mcp-process',
   112|                'allowed': ALLOWED_COMMANDS
   113|            }).encode())
   114|        else:
   115|            self.send_response(404)
   116|            self.end_headers()
   117|
   118|def main():
   119|    print(f'[MCP-Process] Allowed commands: {ALLOWED_COMMANDS}')
   120|    print('[MCP-Process] Starting Process Server on port 4895')
   121|    
   122|    server = HTTPServer(('127.0.0.1', 4895), MCPHandler)
   123|    server.serve_forever()
   124|
   125|if __name__ == '__main__':
   126|    main()