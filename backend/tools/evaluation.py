"""Pure YOLO-format evaluation math; no model, API, database or alerts."""
from pathlib import Path
import numpy as np

CLASSES = {0:'Face Mask',1:'Helmet',2:'Person',3:'Safety Vest'}
LEAKAGE_WARNING = 'LEAKAGE WARNING: test/valid images were pooled into the augmentation workflow. Scores are likely optimistic and are not leakage-free generalization evidence; a clean retrain/evaluation is pending.'


def iou(a,b):
    x1,y1=max(a[0],b[0]),max(a[1],b[1])
    x2,y2=min(a[2],b[2]),min(a[3],b[3])
    intersection=max(0,x2-x1)*max(0,y2-y1)
    union=max(0,a[2]-a[0])*max(0,a[3]-a[1])+max(0,b[2]-b[0])*max(0,b[3]-b[1])-intersection
    return intersection/union if union else 0.0


def read_labels(path, width, height):
    if not Path(path).is_file(): raise ValueError(f'Missing annotation: {path}')
    labels=[]
    for line_number,line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(),1):
        if not line.strip(): continue
        values=line.split()
        if len(values)!=5: raise ValueError(f'{path}:{line_number}: expected class cx cy width height')
        cls,cx,cy,w,h=map(float,values)
        if not np.isfinite([cls,cx,cy,w,h]).all() or cls!=int(cls) or int(cls) not in CLASSES or not all(0<=v<=1 for v in (cx,cy,w,h)) or w<=0 or h<=0:
            raise ValueError(f'{path}:{line_number}: invalid YOLO box/class')
        labels.append({'class_id':int(cls),'class_name':CLASSES[int(cls)],'bbox':[max(0,(cx-w/2)*width),max(0,(cy-h/2)*height),min(width,(cx+w/2)*width),min(height,(cy+h/2)*height)]})
    return labels


def ranked_matches(records, class_id, threshold):
    gt={r['filename']:[g for g in r['labels'] if g['class_id']==class_id] for r in records}
    detections=sorted([(r['filename'],p) for r in records for p in r['predictions'] if p['class_id']==class_id],key=lambda item:item[1]['confidence'],reverse=True)
    used={name:set() for name in gt}
    flags=[]
    for name,pred in detections:
        options=[(iou(pred['bbox'],g['bbox']),i) for i,g in enumerate(gt[name]) if i not in used[name]]
        score,index=max(options,default=(0,-1))
        hit=score>=threshold
        if hit: used[name].add(index)
        flags.append(hit)
    return np.asarray(flags,dtype=float),sum(map(len,gt.values())),[p['confidence'] for _,p in detections]


def curve(flags, count):
    if not len(flags): return np.asarray([]),np.asarray([])
    return np.cumsum(flags)/max(1,count), np.cumsum(flags)/np.arange(1,len(flags)+1)


def average_precision(recall,precision,count):
    if not count:return None
    if not len(recall):return 0.0
    # 101 recall samples, monotonic precision envelope; unreachable recall has zero precision.
    return float(np.mean([max(precision[recall>=r],default=0.0) for r in np.linspace(0,1,101)]))


def evaluate(records):
    per_class={}
    for cls,name in CLASSES.items():
        values=[]
        for threshold in np.linspace(.5,.95,10):
            flags,count,scores=ranked_matches(records,cls,float(threshold))
            recall,precision=curve(flags,count)
            values.append(average_precision(recall,precision,count))
            if threshold==.5:
                true=int(flags.sum()); fp=len(flags)-true
                base={'ground_truth':count,'predictions':len(flags),'tp':true,'fp':fp,'fn':count-true,
                      'precision':true/len(flags) if len(flags) else None,'recall':true/count if count else None,
                      'pr_curve':{'recall':recall.tolist(),'precision':precision.tolist(),'confidence':scores}}
        per_class[name]={**base,'ap50':values[0],'ap50_95':float(np.mean(values)) if count else None,'ap_by_iou':values}
    matrix=np.zeros((5,5),dtype=int)
    for record in records:
        used=set()
        for pred in sorted(record['predictions'],key=lambda p:p['confidence'],reverse=True):
            options=[(iou(pred['bbox'],g['bbox']),i) for i,g in enumerate(record['labels']) if i not in used]
            score,index=max(options,default=(0,-1))
            if score>=.5:
                used.add(index); matrix[record['labels'][index]['class_id'],pred['class_id']]+=1
            else: matrix[4,pred['class_id']]+=1
        for index,gt in enumerate(record['labels']):
            if index not in used: matrix[gt['class_id'],4]+=1
    return {'per_class':per_class,'map50':float(np.mean([v['ap50'] for v in per_class.values() if v['ap50'] is not None])) if any(v['ap50'] is not None for v in per_class.values()) else None,
            'map50_95':float(np.mean([v['ap50_95'] for v in per_class.values() if v['ap50_95'] is not None])) if any(v['ap50_95'] is not None for v in per_class.values()) else None,
            'confusion_matrix':matrix.tolist(),'confusion_axes':'rows=ground truth, columns=prediction; final row/column=background'}
