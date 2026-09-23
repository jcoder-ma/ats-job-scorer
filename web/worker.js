/* All candidate text remains in the browser's worker memory. */
import { loadPyodide } from './vendor/pyodide.mjs';
let runtime, pdfReady;
const ready=(async()=>{
 runtime=await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/'});
 const response=await fetch('engine.py');
 if(!response.ok)throw new Error('Could not load the scoring engine.');
 runtime.runPython(await response.text());
 postMessage({type:'ready'});
})();
ready.catch(error=>postMessage({type:'fatal',error:String(error)}));
self.onmessage=async event=>{
 const {id,payload}=event.data;
 try{
  await ready;
  if(payload.action==='extract'&&payload.name.toLowerCase().endsWith('.pdf')) {
   pdfReady ||= (async()=>{const response=await fetch('vendor/pypdf-6.9.1-py3-none-any.whl');if(!response.ok)throw new Error('Could not load PDF support.');runtime.unpackArchive(new Uint8Array(await response.arrayBuffer()),'zip',{extractDir:'/home/pyodide'});})();
   await pdfReady;
  }
  runtime.globals.set('_request_json',JSON.stringify(payload));
  const result=runtime.runPython('api(_request_json)');
  runtime.globals.delete('_request_json');
  postMessage({id,result:JSON.parse(result)});
 }catch(error){postMessage({id,error:String(error.message||error)});}
};



