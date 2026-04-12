# feel free to ignore this comment
     1|#!/usr/bin/env python3
     2|"""
     3|NexusOS MCP HTTP Server
     4|
     5|Provides web request capabilities to the agent.
     6|
     7|Features:
     8|- GET, POST, PUT, DELETE
     9|- Custom headers
    10|- JSON body
    11|- Timeout control
    12|"""
    13|
    14|import os
    15|import json
    16|import urllib.request
    17|import urllib.parse
    18|from http.server import HTTPServer, BaseHTTPRequestHandler
    19|import urllib.parse as urlp
    20|
    21|TIMEOUT = int(os.environ.get('TIMEOUT', 30))
    22|
    23|def make_request(method: str, url: str, headers: dict = None, data: dict = None) -> dict:
    24|    """Make an HTTP request"""
    25|    
    26|    try:
    27|        req = urllib.request.Request(url, method=method)
    28|        
    29|        # Add headers
    30|        default_headers = {
    31|            'User-Agent': 'NexusOS-MCP/1.0',
    32|            'Accept': 'application/json'
    33|        }
    34|        
    35|        for k, v in {**default_headers, **(headers or {})}.items():
    36|            req.add_header(k, v)
    37|        
    38|        # Add body for POST/PUT
    39|        if data and method in ['POST', 'PUT', 'PATCH']:
    40|            body = json.dumps(data).encode('utf-8')
    41|            req.add_header('Content-Type', 'application/json')
    42|            req.data = body
    43|        
    44|        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
    45|            body = resp.read().decode('utf-8')
    46|            
    47|            try:
    48|                json_body = json.loads(body)
    49|            except:
    50|                json_body = body
    51|            
    52|            return {
    53|                'success': True,
    54|                'method': method,
    55|                'url': url,
    56|                'status': resp.status,
    57|                'headers': dict(resp.headers),
    58|                'body': json_body
    59|            }
    60|    
    61|    except urllib.error.HTTPError as e:
    62|        return {
    63|            'success': False,
    64|            'error': f'HTTP {e.code}: {e.reason}',
    65|            'method': method,
    66|            'url': url,
    67|            'status': e.code
    68|        }
    69|    
    70|    except Exception as e:
    71|        return {
    72|            'success': False,
    73|            'error': str(e),
    74|            'method': method,
    75|            'url': url
    76|        }
    77|
    78|def get(url: str, headers: dict = None) -> dict:
    79|    return make_request('GET', url, headers)
    80|
    81|def post(url: str, data: dict = None, headers: dict = None) -> dict:
    82|    return make_request('POST', url, headers, data)
    83|
    84|def put(url: str, data: dict = None, headers: dict = None) -> dict:
    85|    return make_request('PUT', url, headers, data)
    86|
    87|def delete(url: str, headers: dict = None) -> dict:
    88|    return make_request('DELETE', url, headers)
    89|
    90|class MCPHandler(BaseHTTPRequestHandler):
    91|    def do_POST(self):
    92|        try:
    93|            content_length = int(self.headers['Content-Length'])
    94|            body = self.rfile.read(content_length)
    95|            request = json.loads(body.decode('utf-8'))
    96|            
    97|            method = request.get('method')
    98|            params = request.get('params', {})
    99|            
   100|            if method == 'get':
   101|                result = get(params.get('url'), params.get('headers'))
   102|            elif method == 'post':
   103|                result = post(params.get('url'), params.get('data'), params.get('headers'))
   104|            elif method == 'put':
   105|                result = put(params.get('url'), params.get('data'), params.get('headers'))
   106|            elif method == 'delete':
   107|                result = delete(params.get('url'), params.get('headers'))
   108|            else:
   109|                result = {'error': f'Unknown method: {method}'}
   110|            
   111|            response = json.dumps(result)
   112|            self.send_response(200)
   113|            self.send_header('Content-Type', 'application/json')
   114|            self.end_headers()
   115|            self.wfile.write(response.encode())
   116|            
   117|        except Exception as e:
   118|            error = json.dumps({'error': str(e)})
   119|            self.send_response(500)
   120|            self.end_headers()
   121|            self.wfile.write(error.encode())
   122|
   123|def main():
   124|    print(f'[MCP-HTTP] Starting HTTP Server on port 4896')
   125|    server = HTTPServer(('127.0.0.1', 4896), MCPHandler)
   126|    server.serve_forever()
   127|
   128|if __name__ == '__main__':
   129|    main()