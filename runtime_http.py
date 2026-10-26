"""Run RetryModel through actual SDK HTTP calls to a synthetic loopback peer."""
import argparse, asyncio, hashlib, importlib.metadata, json, socket, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

args=argparse.ArgumentParser();args.add_argument('--source');args.add_argument('--expect',choices=['baseline','fixed'],required=True);args.add_argument('--output',required=True);opts=args.parse_args()
if opts.source:sys.path.insert(0,opts.source)
import mirascope
from mirascope import llm
import httpx,openai

class Peer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self, scenario):
        super().__init__(('127.0.0.1',0), Handler);self.scenario=scenario;self.requests=[]

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append({'path':self.path,'model':request['model'],'stream':request.get('stream')})
        first=len(self.server.requests)==1
        scenario=self.server.scenario
        if first and scenario=='disconnect':
            self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
        if first and scenario=='timeout':time.sleep(.3)
        status=429 if scenario=='exhaust' or (first and scenario=='429') else 401 if scenario=='401' else 200
        if status!=200:
            body=json.dumps({'error':{'message':'synthetic peer failure','type':'rate_limit_exceeded' if status==429 else 'invalid_api_key','code':'rate_limit_exceeded' if status==429 else 'invalid_api_key'}}).encode();content_type='application/json'
        else:
            events=[{'type':'response.output_text.delta','delta':'ok','item_id':'msg_test','output_index':0,'content_index':0,'sequence_number':0},{'type':'response.output_text.done','text':'ok','item_id':'msg_test','output_index':0,'content_index':0,'sequence_number':1}]
            body=(''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events)+'data: [DONE]\n\n').encode();content_type='text/event-stream'
        try:
            self.send_response(status);self.send_header('content-type',content_type);self.send_header('content-length',str(len(body)));self.end_headers();self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass

async def case(mode,scenario):
    peer=Peer(scenario);thread=threading.Thread(target=peer.serve_forever,daemon=True);thread.start();llm.reset_provider_registry()
    provider=llm.register_provider('openai:responses',api_key='synthetic-not-a-secret',base_url=f'http://127.0.0.1:{peer.server_port}/v1')
    provider.client.close();await provider.async_client.close()
    provider.client=openai.OpenAI(api_key='synthetic-not-a-secret',base_url=f'http://127.0.0.1:{peer.server_port}/v1',max_retries=0,timeout=.1,http_client=httpx.Client(trust_env=False))
    provider.async_client=openai.AsyncOpenAI(api_key='synthetic-not-a-secret',base_url=f'http://127.0.0.1:{peer.server_port}/v1',max_retries=0,timeout=.1,http_client=httpx.AsyncClient(trust_env=False))
    model=llm.retry_model('openai/test-model',max_retries=2,initial_delay=0,max_delay=0,jitter=0)
    result={'mode':mode,'scenario':scenario,'sdk_max_retries':provider.client.max_retries}
    try:
        response=model.stream('Hello') if mode=='sync' else await model.stream_async('Hello')
        text=''.join(response.text_stream()) if mode=='sync' else ''.join([s async for s in response.text_stream()])
        result.update(text=text,failures=[type(f.exception).__name__ for f in response.retry_failures],error=None)
    except Exception as error:
        result.update(error=type(error).__name__,failures=[type(f.exception).__name__ for f in getattr(error,'failures',[])])
    finally:
        provider.client.close();await provider.async_client.close();peer.shutdown();peer.server_close();thread.join(timeout=2);llm.reset_provider_registry()
    result['requests']=peer.requests
    if scenario=='success':valid=result.get('text')=='ok\n' and len(peer.requests)==1
    elif scenario=='401':valid=result['error']=='AuthenticationError' and len(peer.requests)==1
    elif opts.expect=='baseline':valid=len(peer.requests)==1 and result['error'] in ['RateLimitError','ConnectionError','TimeoutError']
    elif scenario=='exhaust':valid=result['error']=='RetriesExhausted' and len(peer.requests)==3 and len(result['failures'])==3
    else:valid=result.get('text')=='ok\n' and len(peer.requests)==2 and len(result['failures'])==1
    result['expected_behavior_verified']=valid
    print(json.dumps(result),flush=True);return result

async def main():
    results=[]
    for mode in ['sync','async']:
        for scenario in ['success','429','disconnect','timeout','exhaust','401']:results.append(await case(mode,scenario))
    package=Path(mirascope.__file__).parent
    record={'expect':opts.expect,'package':str(package),'versions':{p:importlib.metadata.version(p) for p in ['mirascope','openai','httpx','pydantic']},'python':sys.version,'source_sha256':{str(p.relative_to(package)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [package/'llm/retries/retry_models.py',package/'llm/retries/retry_stream_responses.py',package/'llm/retries/utils.py']},'results':results,'all_expected':all(r['expected_behavior_verified'] for r in results),'boundary':'Real public RetryModel + real SDK + actual loopback HTTP/SSE; peer responses synthetic, no external service or inference'}
    Path(opts.output).write_text(json.dumps(record,indent=2),encoding='utf8')
    assert record['all_expected'],record

asyncio.run(main())
