"""Development-only HTTP adapter for the same Python handlers deployed on Vercel."""
import os
from http.server import ThreadingHTTPServer
from api import direct, save, mcp

class Router(save.handler,direct.handler,mcp.handler):
    def do_GET(self):
        path=self.path.split('?',1)[0]
        if path=='/api/save':return save.handler.do_GET(self)
        if path=='/api/mcp':return mcp.handler.do_GET(self)
        return direct.handler.do_GET(self)
    def do_POST(self):
        path=self.path.split('?',1)[0]
        if path=='/api/save':return save.handler.do_POST(self)
        if path=='/api/mcp':return mcp.handler.do_POST(self)
        if path in ('/api/direct','/api/download'):return direct.handler.do_POST(self)
        return self.send_json(404,{'error':'Not found'})
    def log_message(self,*_args):pass

if __name__=='__main__':
    port=int(os.environ.get('REELDROP_API_PORT','3001'))
    ThreadingHTTPServer(('127.0.0.1',port),Router).serve_forever()
