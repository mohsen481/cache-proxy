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

def parse_cache_control(cc_val :str) -> dict:
    directives={}
    items=[val.strip().lower() for val in cc_val.split(',')]
    for i in items:
        if '=' in i:
            key,value=i.split('=',1)
            key=key.strip()
            value=value.strip().strip('"')
            if value.isdigit():
                directives[key]=int(value)
            else:
                directives[key]=value
        else:
            directives[i]=True
    return directives

class RequestHeadersManager:
    def __init__(self,request):
        self.request=request
        self.headers=dict(self.request.headers)
        self.origin=self.request.app.state.origin
        req_cc=self.headers.get('cache-control','')
        if req_cc:
            self.directives=parse_cache_control(req_cc)
        else:
            self.directives=None

    def modify_headers(self):
        self.req_headers={k.lower():v for k,v in self.headers.items() if k not in hop_by_hop_headers}
            
        self.req_headers['host']=urlparse(self.origin).netloc
        return self.req_headers

    def hardstop(self):
        if self.directives is None:
            return True
       
        return all(
            (
                'no-store' not in self.directives,
                'private' not in self.directives,
                self.directives.get('max-age',1)>0,
                self.directives.get('expires',1)>0,

            )
                    )
    
    def is_cachable(self):

        rules=[
            self.hardstop,
        ]

        return all([rule() for rule in rules])

        
            
class ResponseHeadersManager:
    def __init__(self,response,r:RequestHeadersManager):
        self.response=response
        self.headers=dict(self.response.headers)
        self.r=r
    def modify_headers(self):
        self.res_headers={
            k:v for k,v in self.headers.items() if k.lower() not in hop_by_hop_headers
            and k.lower() not in ['content-length']
            }
        return self.res_headers

    def check_vary(self):
        vary_header=self.headers.get('vary','')
        if not vary_header:
            return None
        elif vary_header.strip()=='*':
            return '*'
        else:
            vary_fields=[h.strip().lower() for h in vary_header.split(',')]
            return vary_fields
    

    def is_cachable(self):
        res_cc=self.headers.get('cache-control','')
        if res_cc:
            directives=parse_cache_control(res_cc)
            if ("private" in directives or "no-store" in directives):
                return False

            req_headers=self.r.modify_headers()
            if "authorization" in req_headers:
                return ('public' in directives or 's-maxage' in directives)

        return True
                    
                

