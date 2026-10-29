"""Stateless MCP JSON-RPC endpoint for public-media inspection."""
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit
from reeldrop_media import extract_payload, MediaError, throttle, _slots

TOOLS=[
 {'name':'get_instagram_media','description':'Inspect accessible public Instagram photos, videos, Reels, carousels or Story URLs. Private accounts and login-only media are not supported.',
  'inputSchema':{'type':'object','properties':{'url':{'type':'string'},'mode':{'type':'string','enum':['all','video','photo','reels','story','igtv','carousel']}},'required':['url'],'additionalProperties':False},
  'annotations':{'readOnlyHint':True,'openWorldHint':True}},
 {'name':'get_instagram_profile','description':'Read a public profile when Instagram permits anonymous access. This does not expose private accounts or follower lists.',
  'inputSchema':{'type':'object','properties':{'username':{'type':'string'}},'required':['username'],'additionalProperties':False},
  'annotations':{'readOnlyHint':True,'openWorldHint':True}}
]

def dispatch(message):
    if not isinstance(message,dict) or message.get('jsonrpc')!='2.0':
        return {'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid JSON-RPC request'}}
    request_id=message.get('id');method=message.get('method');params=message.get('params') or {}
    if request_id is None and isinstance(method,str) and method.startswith('notifications/'):
        return None
    response={'jsonrpc':'2.0','id':request_id}
    if method=='initialize':
        version=params.get('protocolVersion','2025-06-18')
        response['result']={'protocolVersion':version if version in ('2026-07-28','2025-11-25','2025-06-18','2025-03-26') else '2025-06-18',
                            'capabilities':{'tools':{}},'serverInfo':{'name':'reeldrop','version':'0.2.0'}}
    elif method=='ping':response['result']={}
    elif method=='tools/list':response['result']={'tools':TOOLS}
    elif method=='tools/call':
        args=params.get('arguments') or {};name=params.get('name')
        if name not in ('get_instagram_media','get_instagram_profile'):
            response['error']={'code':-32602,'message':'Unknown tool'};return response
        acquired=_slots.acquire(blocking=False)
        try:
            if not acquired:raise MediaError('The service is busy. Retry shortly.','BUSY',429)
            payload=extract_payload(args.get('username') if name=='get_instagram_profile' else args.get('url'), 'viewer' if name=='get_instagram_profile' else args.get('mode','all'))
            response['result']={'content':[{'type':'text','text':json.dumps(payload)}],'structuredContent':payload,'isError':False}
        except MediaError as error:
            response['result']={'content':[{'type':'text','text':str(error)}],'isError':True}
        finally:
            if acquired:_slots.release()
    else:response['error']={'code':-32601,'message':'Method not found'}
    return response

class handler(BaseHTTPRequestHandler):
    def reply(self,status,data=None):
        self.send_response(status);self.send_header('Cache-Control','no-store')
        if data is not None:self.send_header('Content-Type','application/json')
        self.end_headers()
        if data is not None:self.wfile.write(json.dumps(data).encode())
    def do_GET(self):
        self.send_response(405);self.send_header('Allow','POST');self.end_headers()
    def do_POST(self):
        origin=self.headers.get('Origin')
        if origin and urlsplit(origin).netloc!=self.headers.get('Host'):
            return self.reply(403,{'error':'Origin not allowed'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=16384:raise ValueError()
            throttle(self.headers.get('x-forwarded-for','unknown').split(',')[0]+':mcp',12)
            message=json.loads(self.rfile.read(length));result=dispatch(message)
            return self.reply(202 if result is None else 200,result)
        except MediaError as error:return self.reply(error.status,{'error':str(error)})
        except (ValueError,TypeError,AttributeError):return self.reply(400,{'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Invalid JSON-RPC JSON'}})
        except Exception:return self.reply(502,{'jsonrpc':'2.0','id':None,'error':{'code':-32603,'message':'Public Instagram access is currently unavailable'}})
