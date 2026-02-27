from fastapi import FastAPI,Request,Response
import httpx
import redis
import json
from .headers import RequestHeadersManager,ResponseHeadersManager
import time
import datetime as dt

app = FastAPI()
r=redis.Redis(decode_responses=False)
client=httpx.AsyncClient(follow_redirects=True)
@app.on_event("shutdown")
async def shutdown_event():
    await client.aclose()

@app.api_route('/{path:path}',methods=['GET','POST','PUT','DELETE'])

async def proxy(path,request:Request):
    
        origin=request.app.state.origin
        clean_path = path if path.startswith('/') else f'/{path}'
        url=f"{origin}{clean_path}"
        headers_obj=RequestHeadersManager(request)
        modified_request_headers=headers_obj.modify_headers()
        host=modified_request_headers['host']
        BASE_CACHE_KEY=f"{request.url}{host}"
        FINAL_CACHE_KEY=BASE_CACHE_KEY
        try:
            meta=r.get(f"{BASE_CACHE_KEY}:meta")
            if meta is not None:     #check if this request is vary sensitive
                vary_meta=json.loads(meta.decode('utf-8'))
                
                request_vary_values=[
                f"{field}:{modified_request_headers.get(field,'')}" for field in vary_meta
                    ]
                request_vary_values.sort()
                #update cache key based on request headers values refered in response vary field
                FINAL_CACHE_KEY=f"{BASE_CACHE_KEY}:{'|'.join(request_vary_values)}"
            cached_response=r.get(FINAL_CACHE_KEY)
            if request.method=="GET" and cached_response is not None:
                cached_headers=r.get(f"{FINAL_CACHE_KEY}:header")
                res_headers=json.loads(cached_headers.decode('utf-8'))
                res_headers['content-length']=str(len(cached_response))
                res_headers['X-CACHE']='HIT'
                now=int(time.time())
                stored_at=int(r.get(f"{FINAL_CACHE_KEY}:stored_at")or now)
                origin_age=int(r.get(f"{FINAL_CACHE_KEY}:origin_age")or 0)
                current_age=origin_age+(now-stored_at)
                res_headers['Age']=str(current_age)
                print('X-CACHE : HIT')
                TTL=r.ttl(FINAL_CACHE_KEY)
                print(f'TTL:{TTL}')
                return Response(content=cached_response,headers=res_headers)
            else:
                pass
        except Exception as e:
            print(e)
        
        body=await request.body()
        #forward the request to origin server
        response =await client.request(
            method=request.method,
            url=url,
            headers=modified_request_headers,
            params=dict(request.query_params),
            content=body,
            timeout=None
        )

        res_headers_manager=ResponseHeadersManager(response,headers_obj)
        response_time=dt.datetime.now(dt.timezone.utc)
        freshness=res_headers_manager.calculate_freshness(response_time)
        origin_age=int(response.headers.get('age',0))
        
        remaining=freshness-origin_age
    

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

        
        modified_response_headers=res_headers_manager.modify_headers()
        cachable=res_headers_manager.is_cachable()
        
        vary_fields=res_headers_manager.check_vary()
        if vary_fields is not None:
            r.set(f"{BASE_CACHE_KEY}:meta",json.dumps(vary_fields),ex=300)
            if '*' in vary_fields:
                cachable=False
            else:
                request_vary_values=[
                    f"{field}:{modified_request_headers.get(field,'')}" for field in vary_fields
                ]

                request_vary_values.sort()
                FINAL_CACHE_KEY=f"{BASE_CACHE_KEY}:{'|'.join(request_vary_values)}"

                
            

        modified_response_headers["X-CACHE"]="MISS"
        modified_response_headers["content-length"]=str(len(final_content))
        json_headers=json.dumps(modified_response_headers)
        origin_content_length=response.headers.get('content-length')
        if origin_content_length is not None and int(origin_content_length)!=len(final_content):
            cachable=False
        if response.status_code==200 and cachable and remaining>0:
            expire_time=int(remaining)
    
            r.set(FINAL_CACHE_KEY,final_content,ex=expire_time)    #cache key will remain for 5 mins.
            r.set(f"{FINAL_CACHE_KEY}:header",json_headers,ex=expire_time)
            r.set(f"{FINAL_CACHE_KEY}:stored_at",int(time.time()),ex=expire_time)
            origin_age=response.headers.get('age',0)
            r.set(f"{FINAL_CACHE_KEY}:origin_age",origin_age,ex=expire_time)
        print(f"X-CACHE:{modified_response_headers['X-CACHE']}")

        return Response(
            content=final_content,
            headers=modified_response_headers,
            status_code=response.status_code,
            )