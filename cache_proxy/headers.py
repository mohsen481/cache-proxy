from urllib.parse import urlparse


hop_by_hop_headers=[ #headers that should not be forwarded by proxie.

    'connection',
    'keep-alive',
    'proxy-authenticate',
    'proxy-authorization',
    'te',
    'trailers',
    'transfer-encoding',
    'upgrade',
]
class RequestHeadersManager:
    def __init__(self,request):
        self.request=request
        self.headers=dict(self.request.headers)
        self.origin=self.request.app.state.origin
    def modify_headers(self):
        self.req_headers={
            k:v for k,v in self.headers.items() if k.lower() not in hop_by_hop_headers
            and k.lower()!='accept-encoding'
            }
        self.req_headers['host']=urlparse(self.origin).netloc
        return self.req_headers

    def is_cachable(self):
        directives=self.headers.get('cache-control','').lower()
        return ("private" not in directives and "no-store" not in directives)
    

class ResponseHeadersManager:
    def __init__(self,response):
        self.response=response
        self.headers=dict(self.response.headers)
        
    def modify_headers(self):
        self.res_headers={
            k:v for k,v in self.headers.items() if k.lower() not in hop_by_hop_headers
            and k.lower() not in ['content-encoding','content-length']
            }
        return self.res_headers
        
    def is_cachable(self):
            directives=self.headers.get('cache-control','').lower()
            return ("private" not in directives and "no-store" not in directives)