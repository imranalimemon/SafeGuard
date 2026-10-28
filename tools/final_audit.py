"""Collect final observed QA outputs and verify protected-file hashes read-only."""
import argparse
from collections import Counter
from contextlib import closing
import hashlib,json,sqlite3,subprocess
from pathlib import Path

parser=argparse.ArgumentParser();parser.add_argument('--trial',type=Path,required=True);args=parser.parse_args()
root=Path.cwd();trial=args.trial.resolve();output=root/'docs/evidence/phase5';output.mkdir(parents=True,exist_ok=True)
results=[];telemetry=[]
for name,command in [('phase-a-results.json','tools/qa_final_live.cjs'),('phase-b2-results.json','tools/qa_final_cameras.cjs'),('phase-d-results.json','tools/qa_final_uploads.cjs'),('phase-e2-results.json','tools/qa_final_errors.cjs')]:
 data=json.loads((trial/name).read_text(encoding='utf-8-sig'))
 data['command']='node '+command+' <Playwright-directory> <temporary-auth.json>'
 (output/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
 results.extend(data['results']);telemetry.extend(data.get('telemetry',[]))
manifest=json.loads((trial/'manifest.json').read_text(encoding='utf-8'))
protected=[{'path':path,'unchanged':hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,'bytes':Path(path).stat().st_size} for path,digest in manifest['protected'].items()]
with closing(sqlite3.connect((trial/'trial.db').as_uri()+'?mode=ro',uri=True)) as db,closing(sqlite3.connect(Path(manifest['source_copy']).as_uri()+'?mode=ro',uri=True)) as original:
 original_ids={row[0] for row in original.execute('SELECT id FROM violations')};actual_ids={row[0] for row in db.execute('SELECT id FROM violations')}
 baseline_max=max(original_ids)
 original_alert_max=original.execute('SELECT coalesce(max(id),0) FROM alert_logs').fetchone()[0]
 audit={'original_copy_rows':len(original_ids),'current_copy_rows':len(actual_ids),'original_ids_preserved':original_ids<=actual_ids,'integrity':db.execute('PRAGMA integrity_check').fetchone()[0],
 'new_incidents_email_success_flags':db.execute('SELECT count(*) FROM violations WHERE id>? AND alert_sent=1',(baseline_max,)).fetchone()[0],
 'new_alert_status_counts':[list(row) for row in db.execute('SELECT status,transport,count(*) FROM alert_logs WHERE id>? GROUP BY status,transport',(original_alert_max,))],
 'historical_alert_log_note':'Legacy success/failed rows are inherited from the original disposable source; only rows above its maximum alert-log ID belong to this master task.',
 'alert_status_counts':[list(row) for row in db.execute('SELECT status,transport,count(*) FROM alert_logs GROUP BY status,transport')],
 'saved_settings':dict(zip([d[0] for d in db.execute('SELECT * FROM alert_settings LIMIT 1').description],db.execute('SELECT * FROM alert_settings LIMIT 1').fetchone()))}
page_errors=[event for event in telemetry if event['type']=='pageerror']
known_areas={'59-camera-delete-error-visible','60-camera-validation-does-not-crash','39-no-violation-deletion','54-renamed-text'}
unexpected=[]
for event in telemetry:
 if event['type']=='pageerror':unexpected.append(event)
 elif event.get('area') in known_areas:continue
 elif event['type']=='network' and ('ERR_ABORTED' in event.get('error','') or 'whatsapp.com' in event.get('url','')):continue
 elif event['type']=='http' and event.get('status') in (401,405,415,422):continue
 elif event['type']=='console' and ('Failed to load resource' in event.get('message','') or 'WebSocket connection' in event.get('message','')):continue
 else:unexpected.append(event)
summary={'command':'python -B tools/final_audit.py --trial <temporary-trial-directory>','cases':len(results),'pass':sum(r['result']=='PASS' for r in results),'fail':[r for r in results if r['result']!='PASS'],'page_errors':page_errors,'telemetry_counts':dict(Counter(e['type'] for e in telemetry)),
 'unexpected_telemetry':unexpected,'telemetry_note':'Raw telemetry is retained. Intentional synthetic 500/422 validation, blocked deletion, invalid renamed image and cancelled navigation/session requests are identified separately; no claim that every network request succeeded.',
 'protected_files':protected,'temporary_database':audit,'branch':subprocess.check_output(['git','branch','--show-current'],text=True).strip()}
(output/'final-audit.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({k:summary[k] for k in ['cases','pass','fail','telemetry_counts','unexpected_telemetry','protected_files','temporary_database']},indent=2))
assert not summary['fail'] and not page_errors
assert all(item['unchanged'] for item in protected)
assert audit['original_ids_preserved'] and audit['integrity']=='ok' and audit['new_incidents_email_success_flags']==0

assert all(row[0]=='preview' and row[1]=='preview' for row in audit['new_alert_status_counts'])
