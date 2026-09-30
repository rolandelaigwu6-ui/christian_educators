"""Exercise static layouts and mocked form flows in installed headless Chrome (no dependencies)."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {'admin-dashboard.html', 'member-dashboard.html'}
PAGES = ['index.html', '404.html'] + ['pages/' + p.name for p in sorted((ROOT / 'pages').glob('*.html')) if p.name not in EXCLUDE]
HARNESS = r'''<!doctype html><html><head><title>RUNNING</title></head><body><pre id="results">Running</pre><script>
(async function () {
 const results=[];
 function check(ok,label){results.push((ok?'PASS ':'FAIL ')+label);document.querySelector('pre').textContent=results.join('\n')}
 async function open(page,width){const f=document.createElement('iframe');f.style.cssText='border:0;width:'+width+'px;height:1000px';document.body.appendChild(f);await new Promise(resolve=>{f.onload=resolve;f.src=page});return f}
 for(const width of [320,768,1440]){
  for(const page of __PAGES__){
   const f=await open(page,width),w=f.contentWindow,d=w.document;
   check(d.documentElement.scrollWidth<=width,page+' fits '+width+'px');
   check(d.querySelectorAll('h1').length===1,page+' one heading at '+width+'px');
   check(d.querySelectorAll('.nav-logo').length===1,page+' branding at '+width+'px');
   const t=d.querySelector('.nav-toggle');
   if(width===320&&t){t.click();check(t.getAttribute('aria-expanded')==='true'&&w.getComputedStyle(d.querySelector('.nav-links')).display==='flex',page+' mobile menu');t.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));check(t.getAttribute('aria-expanded')==='false',page+' Escape closes menu')}
   check([...d.images].filter(i=>i.loading!=='lazy').every(i=>i.complete&&i.naturalWidth>0),page+' visible images loaded at '+width+'px');
   f.remove();
  }
 }
 const scenarios=[['pages/join.html?tier=gold','join'],['pages/get_help.html?topic=Teacher+salary+top-up','contact'],['pages/what_new.html','newsletter'],['pages/what_new.html','story'],['pages/state-coordinator.html','coordinator'],['pages/get-involved.html','volunteer'],['pages/get-involved.html','partner']];
 for(const [page,id] of scenarios){
  const f=await open(page,375),w=f.contentWindow,d=w.document,form=d.getElementById(id+'-form');
  if(id==='join')check(form.querySelector('[name=tier]').value==='gold','Membership link preselects Gold');
  if(id==='contact')check(form.querySelector('[name=topic]').value==='Teacher salary top-up','Support link preselects the enquiry');
  form.querySelectorAll('input,textarea').forEach(e=>{if(e.type==='checkbox'){e.checked=e.name!=='marketing_consent'}else if(e.type==='email'){e.value='frontend@example.com'}else if(e.type==='tel'){e.value='+2348030000000'}else if(e.tagName==='TEXTAREA'){e.value='This is a local browser test; no real submission is sent.'}else{e.value='Frontend check'}});
  form.querySelectorAll('select').forEach(e=>{if(!e.value)e.selectedIndex=1});
  for(const state of ['email-failed','success','api-error','offline']){
   form.hidden=false;d.getElementById(id+'-warning').hidden=true;d.getElementById(id+'-success').hidden=true;
   let calls=0,payload=null,settings=null;
   w.fetch=async(url,options)=>{calls++;settings=options;payload=JSON.parse(options.body);if(state==='offline')throw new Error('Offline');return {ok:state!=='api-error',json:async()=>state==='api-error'?{detail:[{loc:['body','email'],msg:'Invalid email'}]}:{email_sent:state==='success'}}};
   form.dispatchEvent(new w.Event('submit',{cancelable:true}));form.dispatchEvent(new w.Event('submit',{cancelable:true}));
   await new Promise(resolve=>setTimeout(resolve,20));
   check(calls===1,id+' '+state+' prevents duplicate sends');
   check(settings&&settings.credentials==='include',id+' '+state+' uses cookie credentials');
   const panel=state==='email-failed'?d.getElementById(id+'-warning'):state==='success'?d.getElementById(id+'-success'):form.querySelector('.form-error');
   check(!panel.hidden,id+' '+state+' displays correct feedback');
   check(!form.querySelector('button[type=submit]').disabled,id+' '+state+' restores button');
   if(state==='success'||state==='email-failed')check(d.activeElement===panel,id+' '+state+' focuses saved notice');
   if(state==='api-error')check(panel.textContent.includes('Invalid email')&&!panel.textContent.includes('[object Object]'),id+' shows readable validation error');
   if(id==='join'){check(payload&&payload.tier==='gold'&&payload.faith_agreement&&payload.terms_accepted&&payload.marketing_consent===false,'Membership preserves tier and separate consents');check(payload&&payload.location==='Frontend check'&&payload.church==='Frontend check','Membership includes profile details')}
   if(id==='coordinator')check(payload&&payload.topic==='State Coordinator application'&&payload.message.includes('State / country:')&&payload.message.includes('Current role:'),'Coordinator stores context in private inbox');
   if(id==='story')check(payload&&payload.topic==='Teacher story submission','Story goes to review inbox');
  }
  form.hidden=false;form.querySelector('[name=email]').value='invalid';let calls=0;w.fetch=()=>{calls++;return Promise.reject(new Error('Must not send'))};form.dispatchEvent(new w.Event('submit',{cancelable:true}));check(calls===0,id+' invalid email blocked before request');
  f.remove();
 }
 document.title=results.some(r=>r.startsWith('FAIL'))?'FAILED':'PASSED';
})().catch(error=>{document.title='FAILED';document.querySelector('pre').textContent+='\nERROR '+error.stack});
</script></body></html>'''.replace('__PAGES__', json.dumps(PAGES))


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/__cocegn_browser_checks__':
            content = HARNESS.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            super().do_GET()

    def log_message(self, *args):
        pass


def main():
    chrome = shutil.which('google-chrome') or shutil.which('chromium')
    if not chrome:
        raise SystemExit('Install/use a local Chrome or Chromium browser to run these checks.')
    with tempfile.TemporaryDirectory(prefix='cocegn-browser-') as temp:
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(ROOT)))
        Thread(target=server.serve_forever, daemon=True).start()
        try:
            result = subprocess.run([chrome, '--headless', '--no-sandbox', '--disable-gpu',
                '--disable-background-networking', '--user-data-dir=' + temp,
                '--dump-dom', '--virtual-time-budget=45000',
                f'http://127.0.0.1:{server.server_port}/__cocegn_browser_checks__'],
                capture_output=True, text=True, timeout=120)
        finally:
            server.shutdown()
            server.server_close()
        match = re.search(r'<pre id="results">(.*?)</pre>', result.stdout, re.S)
        if not match:
            raise SystemExit('Browser did not produce results: ' + result.stderr[-1000:])
        lines = match[1].splitlines()
        failures = [line for line in lines if not line.startswith('PASS ')]
        if failures or '<title>PASSED</title>' not in result.stdout:
            raise SystemExit('\n'.join(failures) or 'Browser checks did not finish.')
        print(f'PASS: {len(lines)} browser assertions across {len(PAGES)} pages at 320, 768 and 1440px; seven form flows tested with mocked API responses.')


if __name__ == '__main__':
    main()
