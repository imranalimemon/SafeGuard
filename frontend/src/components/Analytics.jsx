import React, { useEffect, useState } from 'react';
import client from '../api/client';

export default function Analytics() {
  const [data,setData]=useState(null),[error,setError]=useState(null);
  useEffect(()=>{const controller=new AbortController();
    const load=()=>client.get('/stats/analytics',{signal:controller.signal}).then(r=>{setData(r.data);setError(null);}).catch(()=>{if(!controller.signal.aborted)setError('Historical analytics unavailable.');});
    load();const timer=setInterval(load,10000);return()=>{controller.abort();clearInterval(timer);};
  },[]);
  if(error)return <p role="alert">{error}</p>;
  if(!data)return <p role="status">Loading historical analytics...</p>;
  const groups=[['Violations per day',data.violations_per_day.map(x=>[x.date,x.violations])],['Violations by source',data.violations_by_source.map(x=>[x.source,x.violations])],['Missing PPE',Object.entries(data.violations_by_type)],['Review status',Object.entries(data.review_status_counts)]];
  return <section className="analytics-panel p-4 border rounded" aria-label="Historical analytics">
    <h2 className="font-bold text-lg">Historical analytics</h2><p className="text-xs my-2">{data.note}</p>
    <div className="analytics-grid">{groups.map(([title,rows])=><section key={title}><h3 className="font-bold">{title}</h3>{!rows.length?<p>No records yet.</p>:<ul>{rows.map(([name,count])=><li key={name} className="flex justify-between gap-3 text-sm"><span className="break-words">{name}</span><strong>{count}</strong></li>)}</ul>}</section>)}</div>
    <h3 className="font-bold mt-4">Compliance trend — sampled observations</h3>
    {!data.compliance_trend.length?<p>No worker observations recorded yet. Analyze an upload or start a camera.</p>:<div className="overflow-auto"><table className="w-full text-sm"><thead><tr><th>Date UTC</th><th>Workers observed</th><th>Assessed</th><th>Unknown</th><th>Compliance</th></tr></thead><tbody>{data.compliance_trend.map(row=><tr key={row.date}><td>{row.date}</td><td>{row.worker_observations}</td><td>{row.assessed_denominator}</td><td>{row.unknown}</td><td>{row.compliance_rate==null?'Not available':`${row.compliance_rate}%`}</td></tr>)}</tbody></table></div>}
  </section>;
}
