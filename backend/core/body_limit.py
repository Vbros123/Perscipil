"""Bound JSON request bodies before validation allocates the full payload."""
from starlette.responses import JSONResponse

class BodyLimitMiddleware:
    def __init__(self, app, max_bytes=1048576):
        self.app,self.max_bytes=app,max_bytes
    async def __call__(self, scope, receive, send):
        if scope['type']!='http' or scope['method'] in {'GET','HEAD','OPTIONS'}:
            return await self.app(scope,receive,send)
        chunks=[];size=0
        while True:
            message=await receive()
            if message['type']=='http.disconnect':return
            size+=len(message.get('body',b''))
            if size>self.max_bytes:
                return await JSONResponse({'detail':'Request body too large'},status_code=413)(scope,receive,send)
            chunks.append(message)
            if not message.get('more_body'):break
        async def bounded_receive():
            if chunks:return chunks.pop(0)
            return await receive()
        return await self.app(scope,bounded_receive,send)
