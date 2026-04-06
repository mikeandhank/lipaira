#!/usr/bin/env python3
"""
NexusOS MCP Filesystem Server

Provides file operations to the agent with configurable root directories
and permission controls.

Capabilities:
- Read files (text, images)
- Write files (create, overwrite)
- List directories
- Search files (grep, find)
- Get file metadata
"""

import os
import json
import mimetypes
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# Configuration
ROOTS = os.environ.get('ROOTS', '/data/.openclaw/workspace').split(',')
ALLOWED_EXTENSIONS = ['.md', '.txt', '.json', '.yaml', '.yml', '.js', '.ts', '.py', '.sh', '.html', '.css', '.png', '.jpg', '.jpeg', '.gif', '.webp']
BLOCKED_PATTERNS = ['.git/', 'node_modules/', '.openclaw/', '*.key', '*.pem', '*.password']

def is_allowed(path: str) -> bool:
    """Check if path is within allowed roots"""
    abs_path = os.path.abspath(path)
    
    for root in ROOTS:
        root = os.path.abspath(root)
        if abs_path.startswith(root):
            return True
    
    # Check blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if pattern.replace('*', '') in abs_path:
            return False
    
    return True

def read_file(path: str) -> dict:
    """Read a file and return its contents"""
    if not is_allowed(path):
        return {'error': 'Access denied', 'path': path}
    
    try:
        abs_path = os.path.abspath(path)
        
        if not os.path.exists(abs_path):
            return {'error': 'File not found', 'path': path}
        
        if os.path.isdir(abs_path):
            return {'error': 'Path is a directory', 'path': path}
        
        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(abs_path)
        
        # Read file
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return {
            'success': True,
            'path': path,
            'mime_type': mime_type,
            'size': os.path.getsize(abs_path),
            'content': content[:50000]  # Limit to 50k chars
        }
    
    except Exception as e:
        return {'error': str(e), 'path': path}

def write_file(path: str, content: str, append: bool = False) -> dict:
    """Write content to a file"""
    if not is_allowed(path):
        return {'error': 'Access denied', 'path': path}
    
    try:
        abs_path = os.path.abspath(path)
        
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
        mode = 'a' if append else 'w'
        
        with open(abs_path, mode, encoding='utf-8') as f:
            f.write(content)
        
        return {
            'success': True,
            'path': path,
            'bytes_written': len(content)
        }
    
    except Exception as e:
        return {'error': str(e), 'path': path}

def list_directory(path: str) -> dict:
    """List contents of a directory"""
    if not is_allowed(path):
        return {'error': 'Access denied', 'path': path}
    
    try:
        abs_path = os.path.abspath(path)
        
        if not os.path.exists(abs_path):
            return {'error': 'Directory not found', 'path': path}
        
        if not os.path.isdir(abs_path):
            return {'error': 'Path is not a directory', 'path': path}
        
        items = []
        for item in os.listdir(abs_path):
            item_path = os.path.join(abs_path, item)
            stat = os.stat(item_path)
            
            items.append({
                'name': item,
                'type': 'directory' if os.path.isdir(item_path) else 'file',
                'size': stat.st_size,
                'modified': stat.st_mtime
            })
        
        return {
            'success': True,
            'path': path,
            'items': items
        }
    
    except Exception as e:
        return {'error': str(e), 'path': path}

def search_files(query: str, path: str = None) -> dict:
    """Grep-like search in files"""
    if path is None:
        path = ROOTS[0]
    
    if not is_allowed(path):
        return {'error': 'Access denied', 'path': path}
    
    try:
        results = []
        abs_path = os.path.abspath(path)
        
        for root, dirs, files in os.walk(abs_path):
            # Skip blocked directories
            dirs[:] = [d for d in dirs if not any(p in os.path.join(root, d) for p in BLOCKED_PATTERNS)]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # Check if file is allowed
                if not is_allowed(file_path):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f, 1):
                            if query.lower() in line.lower():
                                results.append({
                                    'file': file_path,
                                    'line': i,
                                    'content': line.strip()[:200]
                                })
                                
                                if len(results) >= 50:  # Limit results
                                    break
                except:
                    pass
            
            if len(results) >= 50:
                break
        
        return {
            'success': True,
            'query': query,
            'path': path,
            'results': results,
            'count': len(results)
        }
    
    except Exception as e:
        return {'error': str(e), 'path': path}

def get_metadata(path: str) -> dict:
    """Get file metadata"""
    if not is_allowed(path):
        return {'error': 'Access denied', 'path': path}
    
    try:
        abs_path = os.path.abspath(path)
        
        if not os.path.exists(abs_path):
            return {'error': 'Not found', 'path': path}
        
        stat = os.stat(abs_path)
        
        return {
            'success': True,
            'path': path,
            'type': 'directory' if os.path.isdir(abs_path) else 'file',
            'size': stat.st_size,
            'created': stat.st_ctime,
            'modified': stat.st_mtime,
            'accessed': stat.st_atime
        }
    
    except Exception as e:
        return {'error': str(e), 'path': path}

class MCPHandler(BaseHTTPRequestHandler):
    """HTTP handler for MCP protocol"""
    
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            request = json.loads(body.decode('utf-8'))
            
            method = request.get('method')
            params = request.get('params', {})
            
            if method == 'read':
                result = read_file(params.get('path'))
            elif method == 'write':
                result = write_file(params.get('path'), params.get('content', ''))
            elif method == 'append':
                result = write_file(params.get('path'), params.get('content', ''), append=True)
            elif method == 'list':
                result = list_directory(params.get('path', ROOTS[0]))
            elif method == 'search':
                result = search_files(params.get('query'), params.get('path'))
            elif method == 'metadata':
                result = get_metadata(params.get('path'))
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
            self.wfile.write(json.dumps({'status': 'healthy', 'server': 'mcp-filesystem'}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f'[MCP-FS] {format % args}')

def main():
    print(f'[MCP-FS] Starting Filesystem Server')
    print(f'[MCP-FS] Allowed roots: {ROOTS}')
    
    server = HTTPServer(('127.0.0.1', 4894), MCPHandler)
    print('[MCP-FS] Listening on port 4894')
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('[MCP-FS] Shutting down')
        server.shutdown()

if __name__ == '__main__':
    main()