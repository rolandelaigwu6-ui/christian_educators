"""Check readable motion fallbacks in local Chrome; no external packages or mail."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''<!doctype html><html><head><title>RUNNING</title></head><body><pre id="results">Running</pre><script>
(async function(){
 const results=[];
 function check(ok,label){results.push((ok?'PASS ':'FAIL ')+label);document.querySelector('pre').textContent=results.join('\n')}
 const mode=new URLSearchParams(location.search).get('mode');
 const html=await(await fetch('/index.html')).text();
 const frame=document.createElement('iframe');frame.style.cssText='width:375px;height:900px;border:0';
 const setup='<base href="'+location.origin+'/"><script>'+(mode==='fallback'?'window.IntersectionObserver=undefined;':'')+'window.fetch=async()=>({ok:false,status:401,json:async()=>({})});<\/script>';
 await new Promise(resolve=>{frame.onload=resolve;frame.srcdoc=html.replace('<head>','<head>'+setup);document.body.appendChild(frame)});
 const w=frame.contentWindow,d=w.document;
 await new Promise(resolve=>setTimeout(resolve,2100));
 const hero=d.querySelector('.mission-hero'),image=d.querySelector('.hero-background img'),heading=d.querySelector('h1');
 const style=element=>w.getComputedStyle(element);
 // Finish finite entrances explicitly: compositor time can lag virtual timers.
 const entrances=hero.getAnimations({subtree:true});
 check(entrances.every(a=>a.effect.getTiming().iterations!==Infinity&&Number(a.effect.getTiming().duration)<=2000),'Hero entrances are finite and brief');
 entrances.forEach(a=>a.finish());
 check(d.documentElement.scrollWidth<=375,'Phone layout has no horizontal overflow');
 check(image.complete&&image.naturalWidth>0,'Local background image loaded');
 check(style(d.querySelector('.hero-background')).position==='absolute','Image sits behind the hero copy');
 check(style(heading).opacity==='1'&&heading.getBoundingClientRect().width>0,'Hero copy remains readable after entrance');
 check(d.querySelector('.hero-background figcaption').textContent.includes('AI-generated'),'Illustration remains labelled');
 check(style(d.documentElement).getPropertyValue('--navy').trim()==='#1b3a6b','Original blue palette retained');
 check(!!d.querySelector('#our-calling')&&!!hero.querySelector('a[href="#our-calling"]'),'Explore link has an existing destination');
 if(mode==='reduced'){
  check(w.matchMedia('(prefers-reduced-motion: reduce)').matches,'Browser requests reduced motion');
  check(style(heading).animationName==='none'&&style(image).animationName==='none','Hero entrance stops for reduced motion');
  check([...d.querySelectorAll('.mission-card,.facts-strip > div')].every(e=>style(e).opacity==='1'),'Content is visible without reveal animations');
 }else if(mode==='fallback'){
  check(!w.IntersectionObserver,'Observer fallback is exercised');
  check([...d.querySelectorAll('.mission-card,.facts-strip > div')].every(e=>style(e).opacity==='1'),'Content stays visible without observer support');
 }else{
  const card=d.querySelector('.mission-card');card.querySelector('a').focus();
  check(card.classList.contains('is-visible'),'Keyboard focus reveals its content immediately');
  card.scrollIntoView({block:'center'});
  await new Promise(resolve=>setTimeout(resolve,1100));
  card.getAnimations().forEach(a=>a.finish());
  check(style(card).opacity==='1','Focused card finishes its reveal');
 }
 document.title=results.some(r=>r.startsWith('FAIL'))?'FAILED':'PASSED';
})().catch(error=>{document.title='FAILED';document.querySelector('pre').textContent+='\nERROR '+error.stack});
</script></body></html>'''


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/__motion_checks__'):
            body = HARNESS.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def log_message(self, *args):
        pass


def main():
    chrome = shutil.which('google-chrome') or shutil.which('chromium')
    if not chrome:
        raise SystemExit('Chrome or Chromium is required.')
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    assertions = 0
    try:
        for mode in ('normal', 'reduced', 'fallback'):
            with tempfile.TemporaryDirectory(prefix='cocegn-motion-') as profile:
                args = [chrome, '--headless', '--no-sandbox', '--disable-gpu',
                        '--disable-background-networking', '--user-data-dir=' + profile,
                        '--dump-dom', '--virtual-time-budget=15000']
                if mode == 'reduced':
                    args.append('--force-prefers-reduced-motion=reduce')
                args.append(f'http://127.0.0.1:{server.server_port}/__motion_checks__?mode={mode}')
                result = subprocess.run(args, capture_output=True, text=True, timeout=45)
                match = re.search(r'<pre id="results">(.*?)</pre>', result.stdout, re.S)
                if not match:
                    raise SystemExit(f'{mode}: no browser result: {result.stderr[-500:]}')
                lines = match[1].splitlines()
                failures = [line for line in lines if not line.startswith('PASS ')]
                if failures or '<title>PASSED</title>' not in result.stdout:
                    raise SystemExit(mode + ':\n' + ('\n'.join(failures) or 'Checks did not finish.'))
                assertions += len(lines)
                print(f'PASS: {mode}: {len(lines)} motion/accessibility checks.')
    finally:
        server.shutdown()
        server.server_close()
    print(f'PASS: {assertions} checks across normal motion, reduced motion and observer fallback.')


if __name__ == '__main__':
    main()
