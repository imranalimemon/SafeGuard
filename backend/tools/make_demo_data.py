"""Copy actual incident/evidence samples to a newly created TEMP demo database.
Refuses repository/backup sources. Never opens an API or alert transport.
"""
from contextlib import closing
import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile


def make_demo(source, evidence, limit=20):
    source=Path(source).resolve();evidence=Path(evidence).resolve()
    temp=Path(tempfile.gettempdir()).resolve()
    if temp not in source.parents or temp not in evidence.parents:
        raise ValueError('Use an existing disposable DB/evidence copy under the system temp folder; protected originals/backups are not accepted.')
    if not 1<=limit<=100:raise ValueError('Limit must be from 1 to 100')
    uri=source.as_uri()+'?mode=ro'
    with closing(sqlite3.connect(uri,uri=True)) as original:
        original.row_factory=sqlite3.Row
        schema=original.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='violations'").fetchone()[0]
        chosen=[]
        for row in original.execute('SELECT * FROM violations ORDER BY timestamp DESC,id DESC'):
            image=evidence/Path(row['screenshot_path'] or '').name
            if image.is_file() and image.resolve().parent==evidence:
                chosen.append((dict(row),image))
                if len(chosen)>=limit:break
    if not chosen:raise ValueError('No real incident records with existing evidence were found.')
    output=Path(tempfile.mkdtemp(prefix='safeguard-DEMO-'))
    screenshots=output/'screenshots';screenshots.mkdir()
    with closing(sqlite3.connect(output/'demo.db')) as db, db:
        db.execute(schema)
        for row,image in chosen:
            columns=list(row)
            db.execute('INSERT INTO violations ('+','.join('"'+key+'"' for key in columns)+') VALUES ('+','.join('?' for _ in columns)+')',[row[key] for key in columns])
            shutil.copy2(image,screenshots/image.name)
        db.execute('CREATE TABLE demo_metadata (label TEXT NOT NULL, source_copy TEXT NOT NULL)')
        db.execute('INSERT INTO demo_metadata VALUES (?,?)',('DEMO: COPIED REAL INCIDENT RECORDS AND EVIDENCE',str(source)))
        count=db.execute('SELECT count(*) FROM violations').fetchone()[0]
        integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
    result={'label':'DEMO: copied real records, not current monitoring','database':str(output/'demo.db'),'screenshots':str(screenshots),'records':count,'integrity':integrity,'source_copy':str(source)}
    (output/'DEMO.json').write_text(json.dumps(result,indent=2))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-copy',type=Path,required=True);parser.add_argument('--evidence-copy',type=Path,required=True);parser.add_argument('--limit',type=int,default=20);args=parser.parse_args()
    print(json.dumps(make_demo(args.source_copy,args.evidence_copy,args.limit),indent=2))
