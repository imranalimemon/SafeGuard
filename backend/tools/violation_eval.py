"""Worker-level evaluation from saved real detector outputs and YOLO annotations.
Ground truth is a geometric proxy, not human-verified worker/PPE relations.
Mask absence is unknown unless an independent visibility file marks the face visible.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from tools.evaluation import CLASSES,LEAKAGE_WARNING,iou


def ground_workers(labels, visibility=None):
    persons=[p for p in labels if p['class_id']==2]
    workers=[{'person_bbox':p['bbox'],'has_ppe':set(),'unknown_ppe':set()} for p in persons]
    orphan=ambiguous=0
    for item in labels:
        cls=item['class_id']
        if cls==2:continue
        box=item['bbox'];cx=(box[0]+box[2])/2;cy=(box[1]+box[3])/2
        candidates=[]
        for index,person in enumerate(persons):
            x1,y1,x2,y2=person['bbox'];w=max(1,x2-x1);h=max(1,y2-y1)
            # Broad annotation proxy, intentionally independent of production scoring.
            lo,hi=(-.2,.4) if cls==1 else (.05,.8) if cls==3 else (-.05,.55)
            if x1-.1*w<=cx<=x2+.1*w and y1+lo*h<=cy<=y1+hi*h:
                target=.15 if cls==1 else .45 if cls==3 else .25
                distance=((cx-(x1+x2)/2)/w)**2+((cy-(y1+target*h))/h)**2
                candidates.append((distance,index))
        candidates.sort()
        if not candidates:orphan+=1;continue
        if len(candidates)>1 and candidates[0][0]>=.6*candidates[1][0]:
            ambiguous+=1
            for _,index in candidates:workers[index]['unknown_ppe'].add(CLASSES[cls])
            continue
        workers[candidates[0][1]]['has_ppe'].add(CLASSES[cls])
    for index,worker in enumerate(workers):
        visible=(visibility or {}).get(str(index))
        if 'Face Mask' not in worker['has_ppe'] and visible is not True:worker['unknown_ppe'].add('Face Mask')
        missing=set(CLASSES.values())-{'Person'}-worker['has_ppe']-worker['unknown_ppe']
        worker['missing_ppe']=sorted(missing)
        worker['status']='VIOLATION' if missing else 'UNKNOWN' if worker['unknown_ppe'] else 'COMPLIANT'
        worker['has_ppe']=sorted(worker['has_ppe']);worker['unknown_ppe']=sorted(worker['unknown_ppe'])
    return workers,{'orphan_ppe_annotations':orphan,'ambiguous_ppe_annotations':ambiguous}


def worker_counts(truth,predicted):
    counts=Counter();used=set()
    for pred in sorted(predicted,key=lambda p:p.get('confidence',0),reverse=True):
        options=[(iou(pred['person_bbox'],gt['person_bbox']),index) for index,gt in enumerate(truth) if index not in used]
        score,index=max(options,default=(0,-1))
        if score<.5:
            counts['spurious_worker']+=1
            if pred['status'] in ('COMPLIANT','VIOLATION'):counts[pred['status']+'_fp']+=1
            continue
        used.add(index);counts['matched_workers']+=1;gt=truth[index]
        if gt['status']=='UNKNOWN':counts['unknown_ground_truth_excluded']+=1;continue
        for status in ('COMPLIANT','VIOLATION'):
            actual=gt['status']==status;positive=pred['status']==status
            if actual and positive:counts[status+'_tp']+=1
            elif actual:counts[status+'_fn']+=1
            elif positive:counts[status+'_fp']+=1
        if pred['status']=='VIOLATION' and gt['status']=='COMPLIANT':counts['false_violation']+=1
        if pred['status']!='VIOLATION' and gt['status']=='VIOLATION':counts['missed_violation']+=1
        for ppe in ('Helmet','Safety Vest','Face Mask'):
            if ppe not in gt['unknown_ppe'] and ((ppe in gt['has_ppe'])!=(ppe in pred.get('has_ppe',[]))):counts['wrong_ppe:'+ppe]+=1
        if pred['status']=='NOT_ASSESSABLE':counts['prediction_abstained_on_known_worker']+=1
    for index,gt in enumerate(truth):
        if index not in used:
            counts['missed_worker']+=1
            if gt['status']!='UNKNOWN':counts[gt['status']+'_fn']+=1
            else:counts['unknown_ground_truth_excluded']+=1
    return counts


def metrics(counts):
    result={}
    for status in ('COMPLIANT','VIOLATION'):
        tp,fp,fn=(counts[status+'_'+key] for key in ('tp','fp','fn'))
        result[status.lower()]={'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions',type=Path,required=True,help='evaluate_onnx.py predictions.json; hashes checked before reuse')
    parser.add_argument('--model',type=Path,default=ROOT/'backend/best.onnx')
    parser.add_argument('--visibility',type=Path,help='Independent JSON: {filename: {zero-based-person-label-index: true/false}}')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    cache=json.loads(args.predictions.read_text(encoding='utf-8'));metadata=cache['metadata'];split=Path(metadata['split'])
    if hashlib.sha256(args.model.read_bytes()).hexdigest()!=metadata['model_sha256']:raise ValueError('Model hash does not match cached predictions')
    visibility=json.loads(args.visibility.read_text()) if args.visibility else {}
    for name,entries in visibility.items():
        if not isinstance(entries,dict) or any(type(v) is not bool for v in entries.values()):raise ValueError('Visibility values must be independent booleans keyed by person index.')
    output=args.output.resolve()
    if output==split or split in output.parents:parser.error('Output must be outside the dataset split')
    output.mkdir(parents=True,exist_ok=True)
    counts=Counter();annotation_counts=Counter();examples=[];details=[]
    with tempfile.TemporaryDirectory(prefix='safeguard-worker-eval-') as temp,patch.dict(os.environ,{'SCREENSHOT_DIR':temp,'ALERT_DELIVERY_MODE':'preview'}),patch('dotenv.load_dotenv'):
        import cv2
        from detection.violation_logic import compute_violations
        from detection.annotator import annotate_frame
        from config import settings
        if metadata['nms_iou']!=settings.IOU_THRESHOLD or metadata['confidence_threshold']!=settings.CONFIDENCE_THRESHOLD or metadata['class_mapping']!={str(k):v for k,v in CLASSES.items()}:raise ValueError('Cached production threshold/class mapping mismatch')
        for record in cache['records']:
            path=split/'images'/record['filename'];label=split/'labels'/f'{path.stem}.txt'
            if hashlib.sha256(path.read_bytes()).hexdigest()!=record['image_sha256'] or hashlib.sha256(label.read_bytes()).hexdigest()!=record['label_sha256']:raise ValueError(f'Input changed: {path.name}')
            frame=cv2.imread(str(path))
            if frame is None:raise ValueError(f'Cannot decode {path.name}')
            truth,annotations=ground_workers(record['labels'],visibility.get(path.name))
            predicted=compute_violations(record['predictions'],required_ppe=['Helmet','Safety Vest','Face Mask'],frame=frame)
            local=worker_counts(truth,predicted);counts.update(local);annotation_counts.update(annotations)
            for worker in truth:
                annotation_counts['ground_truth_workers']+=1
                annotation_counts['ground_truth_'+worker['status'].lower()]+=1
                annotation_counts['mask_ground_truth_unknown']+=int('Face Mask' in worker['unknown_ppe'])
            if len(examples)<8 and any(local[key] for key in ('missed_worker','spurious_worker','false_violation','missed_violation')):
                image=annotate_frame(frame.copy(),record['predictions'],predicted)
                name=f'error-{len(examples)+1:02d}-{path.stem}.jpg'
                cv2.imwrite(str(output/name),image);examples.append({'filename':path.name,'image':name,'errors':dict(local)})
            details.append({'filename':path.name,'ground_truth_proxy':truth,'predicted_workers':predicted,'counts':dict(local)})
    result={'warning':LEAKAGE_WARNING,'ground_truth_warning':'Worker/PPE relations are geometric annotation proxies. Absence assumes exhaustive PPE labels. Ambiguous associations are unknown. Mask absence is assessable ONLY with independent human face-visibility labels; model visibility predictions are never used as truth. These are exploratory proxy scores, not validated compliance accuracy.',
            'mask_visibility_file':str(args.visibility) if args.visibility else None,'model_sha256':metadata['model_sha256'],'images':len(details),'metrics':metrics(counts),
            'counts':dict(counts),'annotation_counts':dict(annotation_counts),'frequent_errors':[(k,v) for k,v in counts.most_common() if k in ('missed_worker','spurious_worker','false_violation','missed_violation') or k.startswith('wrong_ppe:')],
            'examples':examples,'cache_source':str(args.predictions),'command':' '.join([sys.executable,'-B',*sys.argv])}
    (output/'worker-metrics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (output/'worker-details.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
    (output/'report.md').write_text('# Worker-level exploratory evaluation\n\n'+result['warning']+'\n\n'+result['ground_truth_warning']+'\n\n```json\n'+json.dumps(result['metrics'],indent=2)+'\n```\n\nCommand: `'+result['command']+'`\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
