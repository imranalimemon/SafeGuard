import React,{useEffect,useState} from 'react';
import client from '../api/client';
export default function DeliveryControl(){
 const [data,setData]=useState(null),[error,setError]=useState(null),[confirmation,setConfirmation]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{const controller=new AbortController();client.get('/settings/alerts/delivery',{signal:controller.signal}).then(r=>setData(r.data)).catch(()=>{if(!controller.signal.aborted)setError('Delivery mode unavailable.');});return()=>controller.abort();},[]);
 const change=async mode=>{setBusy(true);setError(null);try{setData((await client.post('/settings/alerts/delivery',{mode,confirmation})).data);setConfirmation('');}catch(e){setError(e.response?.data?.detail||'Could not change delivery mode.');}finally{setBusy(false);}};
 return <section className="border rounded p-4 mb-4" aria-label="Alert delivery mode"><h2 className="font-bold">Alert delivery: {data?.effective_mode||'Checking...'}</h2>{error&&<p role="alert">{error}</p>}
 {data&&<><p className="text-sm">{data.explanation}</p>{!data.can_go_live&&<p>Preview restriction is active. Real email and WhatsApp are blocked.</p>}
 {data.effective_mode==='live'?<button disabled={busy} onClick={()=>change('preview')}>Return to preview</button>:<><label className="block" htmlFor="live-confirm">Type ENABLE LIVE ALERTS to confirm real messages to saved recipients</label><input id="live-confirm" disabled={!data.can_go_live||busy} value={confirmation} onChange={e=>setConfirmation(e.target.value)} className="border rounded p-2"/><button className="border rounded p-2 ml-2" disabled={!data.can_go_live||confirmation!=='ENABLE LIVE ALERTS'||busy} onClick={()=>change('live')}>Enable live delivery</button></>}</>}
 </section>;
}
