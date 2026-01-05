from fastapi import FastAPI,Request,Response
import httpx
import redis
from urllib.parse import urlparse
import json

app = FastAPI()

r=redis.Redis(decode_responses=False)

hop_by_hop_headers=[ #headers that should not be forwarded by proxie.

    'Connection',
    'Keep-Alive',
    'Proxy-Authenticate',
    'Proxy-Authorization',
    'TE',
    'Trailers',
    'Transfer-Encoding',
    'Upgrade',
]

hop_by_hop_headers=[i.lower() for i in hop_by_hop_headers]


@app.api_route('/{path:path}',methods=['GET','POST','PUT','DELETE'])

async def proxy(path,request:Request):
    
        origin=request.app.state.origin
        clean_path = path if path.startswith('/') else f'/{path}'
        url=f"{origin}{clean_path}"
        request_headers=dict(request.headers)
        #remove hop-by-hop headers in request before forwarding to origin server
        modified_request_headers={
            k:v for k,v in request_headers.items() if k.lower() not in hop_by_hop_headers
            and k.lower()!='accept-encoding'
            }
        modified_request_headers['host']=urlparse(origin).netloc
        host=modified_request_headers['host']
        CACHE_KEY=f"{request.url}{host}"
        HEADER_KEY=f"{CACHE_KEY}:header"
        try:
            cached_response=r.get(CACHE_KEY)
            if request.method=="GET" and cached_response is not None:
                cached_headers=r.get(HEADER_KEY)
                res_headers=json.loads(cached_headers.decode('utf-8'))
                res_headers['content-length']=str(len(cached_response))
                res_headers['X-CACHE']='HIT'
                print('X-CACHE : HIT')
                TTL=r.ttl(CACHE_KEY)
                print(f'TTL:{TTL}')
                return Response(content=cached_response,headers=res_headers)
            else:
                pass
        except Exception as e:
            print(e)
        
        body=await request.body()
        #forward the request to origin server
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response =await client.request(
                method=request.method,
                url=url,
                headers=modified_request_headers,
                params=dict(request.query_params),
                content=body,
                timeout=None
            )
        def replace_url():
            """
             Replace origin URL with proxy URL in text-based responses
             to ensure links work through the proxy.
            """
            try:
                content_=response.content
                content_type=response.headers['content-type']
                if 'text'in content_type or 'javascript' in content_type:
                    text_content=content_.decode('utf8')
                    port=request.app.state.port
                    proxy_url=f"http://127.0.0.1:{port}"
                    text_content=text_content.replace(origin,proxy_url)
                    content_=text_content.encode('utf8')
                    return content_
            except:
                return response.content
            
        final_content=replace_url()
        if final_content is None:
            final_content=response.content

        response_headers=dict(response.headers)
        #remove hop-by-hop headers in response before forwarding to client
        End_to_end_headers={
            k:v for k,v in response_headers.items() if k.lower() not in hop_by_hop_headers
            and k.lower() not in ['content-encoding','content-length']
            }

        End_to_end_headers["X-CACHE"]="MISS"
        End_to_end_headers["content-length"]=str(len(final_content))
        json_headers=json.dumps(End_to_end_headers)
        if response.status_code==200:
            r.set(CACHE_KEY,final_content,ex=300)    #cache key will remain for 5 mins.
            r.set(HEADER_KEY,json_headers,ex=300)
        print(f"X-CACHE:{End_to_end_headers['X-CACHE']}")

        return Response(
            content=final_content,
            headers=End_to_end_headers,
            status_code=response.status_code,
            )