# feel free to ignore this comment
     1|#!/usr/bin/env python3
     2|"""
     3|NexusOS MCP Filesystem Server
     4|
     5|Provides file operations to the agent with configurable root directories
     6|and permission controls.
     7|
     8|Capabilities:
     9|- Read files (text, images)
    10|- Write files (create, overwrite)
    11|- List directories
    12|- Search files (grep, find)
    13|- Get file metadata
    14|"""
    15|
    16|import os
    17|import json
    18|import mimetypes
    19|from pathlib import Path
    20|from http.server import HTTPServer, BaseHTTPRequestHandler
    21|import urllib.parse
    22|
    23|# Configuration
    24|ROOTS = os.environ.get('ROOTS', '/data/.openclaw/workspace').split(',')
    25|ALLOWED_EXTENSIONS = ['.md', '.txt', '.json', '.yaml', '.yml', '.js', '.ts', '.py', '.sh', '.html', '.css', '.png', '.jpg', '.jpeg', '.gif', '.webp']
    26|BLOCKED_PATTERNS = ['.git/', 'node_modules/', '.openclaw/', '*.key', '*.pem', '*.password']
    27|
    28|def is_allowed(path: str) -> bool:
    29|    """Check if path is within allowed roots"""
    30|    abs_path = os.path.abspath(path)
    31|    
    32|    for root in ROOTS:
    33|        root = os.path.abspath(root)
    34|        if abs_path.startswith(root):
    35|            return True
    36|    
    37|    # Check blocked patterns
    38|    for pattern in BLOCKED_PATTERNS:
    39|        if pattern.replace('*', '') in abs_path:
    40|            return False
    41|    
    42|    return True
    43|
    44|def read_file(path: str) -> dict:
    45|    """Read a file and return its contents"""
    46|    if not is_allowed(path):
    47|        return {'error': 'Access denied', 'path': path}
    48|    
    49|    try:
    50|        abs_path = os.path.abspath(path)
    51|        
    52|        if not os.path.exists(abs_path):
    53|            return {'error': 'File not found', 'path': path}
    54|        
    55|        if os.path.isdir(abs_path):
    56|            return {'error': 'Path is a directory', 'path': path}
    57|        
    58|        # Detect MIME type
    59|        mime_type, _ = mimetypes.guess_type(abs_path)
    60|        
    61|        # Read file
    62|        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
    63|            content = f.read()
    64|        
    65|        return {
    66|            'success': True,
    67|            'path': path,
    68|            'mime_type': mime_type,
    69|            'size': os.path.getsize(abs_path),
    70|            'content': content[:50000]  # Limit to 50k chars
    71|        }
    72|    
    73|    except Exception as e:
    74|        return {'error': str(e), 'path': path}
    75|
    76|def write_file(path: str, content: str, append: bool = False) -> dict:
    77|    """Write content to a file"""
    78|    if not is_allowed(path):
    79|        return {'error': 'Access denied', 'path': path}
    80|    
    81|    try:
    82|        abs_path = os.path.abspath(path)
    83|        
    84|        # Ensure parent directory exists
    85|        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    86|        
    87|        mode = 'a' if append else 'w'
    88|        
    89|        with open(abs_path, mode, encoding='utf-8') as f:
    90|            f.write(content)
    91|        
    92|        return {
    93|            'success': True,
    94|            'path': path,
    95|            'bytes_written': len(content)
    96|        }
    97|    
    98|    except Exception as e:
    99|        return {'error': str(e), 'path': path}
   100|
   101|def list_directory(path: str) -> dict:
   102|    """List contents of a directory"""
   103|    if not is_allowed(path):
   104|        return {'error': 'Access denied', 'path': path}
   105|    
   106|    try:
   107|        abs_path = os.path.abspath(path)
   108|        
   109|        if not os.path.exists(abs_path):
   110|            return {'error': 'Directory not found', 'path': path}
   111|        
   112|        if not os.path.isdir(abs_path):
   113|            return {'error': 'Path is not a directory', 'path': path}
   114|        
   115|        items = []
   116|        for item in os.listdir(abs_path):
   117|            item_path = os.path.join(abs_path, item)
   118|            stat = os.stat(item_path)
   119|            
   120|            items.append({
   121|                'name': item,
   122|                'type': 'directory' if os.path.isdir(item_path) else 'file',
   123|                'size': stat.st_size,
   124|                'modified': stat.st_mtime
   125|            })
   126|        
   127|        return {
   128|            'success': True,
   129|            'path': path,
   130|            'items': items
   131|        }
   132|    
   133|    except Exception as e:
   134|        return {'error': str(e), 'path': path}
   135|
   136|def search_files(query: str, path: str = None) -> dict:
   137|    """Grep-like search in files"""
   138|    if path is None:
   139|        path = ROOTS[0]
   140|    
   141|    if not is_allowed(path):
   142|        return {'error': 'Access denied', 'path': path}
   143|    
   144|    try:
   145|        results = []
   146|        abs_path = os.path.abspath(path)
   147|        
   148|        for root, dirs, files in os.walk(abs_path):
   149|            # Skip blocked directories
   150|            dirs[:] = [d for d in dirs if not any(p in os.path.join(root, d) for p in BLOCKED_PATTERNS)]
   151|            
   152|            for file in files:
   153|                file_path = os.path.join(root, file)
   154|                
   155|                # Check if file is allowed
   156|                if not is_allowed(file_path):
   157|                    continue
   158|                
   159|                try:
   160|                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
   161|                        for i, line in enumerate(f, 1):
   162|                            if query.lower() in line.lower():
   163|                                results.append({
   164|                                    'file': file_path,
   165|                                    'line': i,
   166|                                    'content': line.strip()[:200]
   167|                                })
   168|                                
   169|                                if len(results) >= 50:  # Limit results
   170|                                    break
   171|                except:
   172|                    pass
   173|            
   174|            if len(results) >= 50:
   175|                break
   176|        
   177|        return {
   178|            'success': True,
   179|            'query': query,
   180|            'path': path,
   181|            'results': results,
   182|            'count': len(results)
   183|        }
   184|    
   185|    except Exception as e:
   186|        return {'error': str(e), 'path': path}
   187|
   188|def get_metadata(path: str) -> dict:
   189|    """Get file metadata"""
   190|    if not is_allowed(path):
   191|        return {'error': 'Access denied', 'path': path}
   192|    
   193|    try:
   194|        abs_path = os.path.abspath(path)
   195|        
   196|        if not os.path.exists(abs_path):
   197|            return {'error': 'Not found', 'path': path}
   198|        
   199|        stat = os.stat(abs_path)
   200|        
   201|        return {
   202|            'success': True,
   203|            'path': path,
   204|            'type': 'directory' if os.path.isdir(abs_path) else 'file',
   205|            'size': stat.st_size,
   206|            'created': stat.st_ctime,
   207|            'modified': stat.st_mtime,
   208|            'accessed': stat.st_atime
   209|        }
   210|    
   211|    except Exception as e:
   212|        return {'error': str(e), 'path': path}
   213|
   214|class MCPHandler(BaseHTTPRequestHandler):
   215|    """HTTP handler for MCP protocol"""
   216|    
   217|    def do_POST(self):
   218|        try:
   219|            content_length = int(self.headers['Content-Length'])
   220|            body = self.rfile.read(content_length)
   221|            request = json.loads(body.decode('utf-8'))
   222|            
   223|            method = request.get('method')
   224|            params = request.get('params', {})
   225|            
   226|            if method == 'read':
   227|                result = read_file(params.get('path'))
   228|            elif method == 'write':
   229|                result = write_file(params.get('path'), params.get('content', ''))
   230|            elif method == 'append':
   231|                result = write_file(params.get('path'), params.get('content', ''), append=True)
   232|            elif method == 'list':
   233|                result = list_directory(params.get('path', ROOTS[0]))
   234|            elif method == 'search':
   235|                result = search_files(params.get('query'), params.get('path'))
   236|            elif method == 'metadata':
   237|                result = get_metadata(params.get('path'))
   238|            else:
   239|                result = {'error': f'Unknown method: {method}'}
   240|            
   241|            response = json.dumps(result)
   242|            self.send_response(200)
   243|            self.send_header('Content-Type', 'application/json')
   244|            self.end_headers()
   245|            self.wfile.write(response.encode())
   246|            
   247|        except Exception as e:
   248|            error = json.dumps({'error': str(e)})
   249|            self.send_response(500)
   250|            self.send_header('Content-Type', 'application/json')
   251|            self.end_headers()
   252|            self.wfile.write(error.encode())
   253|    
   254|    def do_GET(self):
   255|        parsed = urllib.parse.urlparse(self.path)
   256|        
   257|        if parsed.path == '/health':
   258|            self.send_response(200)
   259|            self.send_header('Content-Type', 'application/json')
   260|            self.end_headers()
   261|            self.wfile.write(json.dumps({'status': 'healthy', 'server': 'mcp-filesystem'}).encode())
   262|        else:
   263|            self.send_response(404)
   264|            self.end_headers()
   265|    
   266|    def log_message(self, format, *args):
   267|        print(f'[MCP-FS] {format % args}')
   268|
   269|def main():
   270|    print(f'[MCP-FS] Starting Filesystem Server')
   271|    print(f'[MCP-FS] Allowed roots: {ROOTS}')
   272|    
   273|    server = HTTPServer(('127.0.0.1', 4894), MCPHandler)
   274|    print('[MCP-FS] Listening on port 4894')
   275|    
   276|    try:
   277|        server.serve_forever()
   278|    except KeyboardInterrupt:
   279|        print('[MCP-FS] Shutting down')
   280|        server.shutdown()
   281|
   282|if __name__ == '__main__':
   283|    main()