"""Read-only fact extraction; never imports or executes training scripts."""
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'docs/evidence/phase5';out.mkdir(parents=True,exist_ok=True)
artifacts=ROOT/'training_artifacts'
training=[]
for args in artifacts.rglob('args.yaml'):
    record={'args_file':str(args.relative_to(ROOT)),'args_sha256':hashlib.sha256(args.read_bytes()).hexdigest(),'args_text':args.read_text(encoding='utf-8')}
    results=args.parent/'results.csv'
    if results.exists():
        with results.open(encoding='utf-8') as file:
            rows=[{k.strip():v.strip() for k,v in row.items()} for row in csv.DictReader(file)]
        record.update(results_file=str(results.relative_to(ROOT)),results_sha256=hashlib.sha256(results.read_bytes()).hexdigest(),epochs_logged=len(rows),last_row=rows[-1] if rows else None)
        key='metrics/mAP50-95(B)'
        if rows and key in rows[0]:record['best_map50_95_row']=max(rows,key=lambda row:float(row[key]))
    training.append(record)
splits={}
for name in ('train','valid','test'):
    root=Path('I:/AntiGRavity/My_FYP_Dataset')/name
    images=[p for p in (root/'images').iterdir() if p.suffix.lower() in ('.jpg','.jpeg','.png','.webp')]
    counts=[0]*4
    for path in (root/'labels').glob('*.txt'):
        for line in path.read_text().splitlines():
            if line.strip():counts[int(line.split()[0])]+=1
    splits[name]={'images':len(images),'labels':len(list((root/'labels').glob('*.txt'))),'class_box_counts':dict(zip(['Face Mask','Helmet','Person','Safety Vest'],counts))}
augmentation=artifacts/'dataset_scripts/augment_dataset.py'
lines=augmentation.read_text(encoding='utf-8').splitlines()
result={'command':'python -B tools/project_facts.py','dataset_root':'I:/AntiGRavity/My_FYP_Dataset','dataset_splits':splits,'training_runs':training,
'augmentation_script_sha256':hashlib.sha256(augmentation.read_bytes()).hexdigest(),'pooling_evidence':[{'line':i,'text':line} for i,line in enumerate(lines,1) if any(word in line for word in ['train', 'valid', 'test', 'all_images', 'shuffle', 'split'])],
'augmented_report':(artifacts/'dataset_scripts/augmented_report.txt').read_text(encoding='utf-8'),'model_training_link':'ONNX hash is known; exact export-to-training-run provenance has not been independently established.'}
(out/'project-facts.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'dataset':splits,'training_runs':len(training),'runs':[{'args':r['args_file'],'epochs':r.get('epochs_logged'),'last':r.get('last_row'),'best':r.get('best_map50_95_row')} for r in training]},indent=2))
