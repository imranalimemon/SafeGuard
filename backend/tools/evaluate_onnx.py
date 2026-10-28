"""Evaluate ONNX with the production letterbox/per-class NMS; read-only dataset.
The deployed confidence threshold stays unchanged. AP/PR are explicitly truncated
at that threshold, rather than claiming full-score COCO/Ultralytics equivalence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from tools.evaluation import CLASSES,LEAKAGE_WARNING,read_labels,evaluate


def plots(result,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names=list(CLASSES.values())+['Background']
    fig,ax=plt.subplots(figsize=(8,7))
    matrix=result['confusion_matrix']; view=ax.imshow(matrix,cmap='Blues')
    ax.set_xticks(range(5),names,rotation=30,ha='right');ax.set_yticks(range(5),names)
    ax.set_xlabel('Prediction');ax.set_ylabel('Ground truth');ax.set_title('Confusion matrix — leaked split, thresholded detections')
    for i,row in enumerate(matrix):
        for j,value in enumerate(row):ax.text(j,i,str(value),ha='center',va='center')
    fig.colorbar(view,ax=ax);fig.tight_layout();fig.savefig(output/'confusion-matrix.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,5))
    for name,item in result['per_class'].items():
        ax.plot(item['pr_curve']['recall'],item['pr_curve']['precision'],label=name)
    ax.set(xlim=(0,1),ylim=(0,1),xlabel='Recall',ylabel='Precision',title='PR curves — retained detections only; leaked split')
    ax.legend();fig.tight_layout();fig.savefig(output/'pr-curves.png',dpi=150);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,default=ROOT/'backend/best.onnx')
    parser.add_argument('--split',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    split=args.split.resolve();output=args.output.resolve()
    if output==split or split in output.parents:parser.error('Output must be outside the read-only split.')
    images=sorted(p for p in (split/'images').iterdir() if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'})
    if not images:parser.error('No images found')
    output.mkdir(parents=True,exist_ok=True)
    records=[]; started=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='safeguard-evaluation-') as temp,patch.dict(os.environ,{'SCREENSHOT_DIR':temp,'ALERT_DELIVERY_MODE':'preview'}),patch('dotenv.load_dotenv'):
        import cv2
        from config import settings
        from detection.model import PPEDetector
        detector=PPEDetector(str(args.model.resolve()))
        for index,path in enumerate(images,1):
            frame=cv2.imread(str(path))
            if frame is None:raise ValueError(f'Cannot decode {path.name}; refusing to silently skip it')
            label=split/'labels'/f'{path.stem}.txt'
            labels=read_labels(label,frame.shape[1],frame.shape[0])
            t=time.perf_counter();predictions=detector.detect(frame);ms=(time.perf_counter()-t)*1000
            records.append({'filename':path.name,'image_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'label_sha256':hashlib.sha256(label.read_bytes()).hexdigest(),'labels':labels,'predictions':predictions,'detector_ms':ms})
            if index%100==0: print(f'{split.name}: {index}/{len(images)}',flush=True)
        result=evaluate(records)
        result.update({'warning':LEAKAGE_WARNING,'class_mapping':CLASSES,'images':len(records),'split':str(split),
            'model_sha256':hashlib.sha256(args.model.read_bytes()).hexdigest(),'providers':detector.session.get_providers(),
            'confidence_threshold':settings.CONFIDENCE_THRESHOLD,'nms_iou':settings.IOU_THRESHOLD,
            'ap_definition':'101-point interpolated AP at IoU .50:.05:.95. Production confidence cutoff unchanged; PR/AP are truncated at this cutoff and are NOT full-score Ultralytics/COCO metrics.',
            'elapsed_seconds':time.perf_counter()-started,'command':' '.join([sys.executable,'-B',*sys.argv])})
    (output/'predictions.json').write_text(json.dumps({'metadata':{k:v for k,v in result.items() if k not in ('per_class','confusion_matrix')},'records':records},indent=2),encoding='utf-8')
    (output/'metrics.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    plots(result,output)
    table='| Class | Precision | Recall | AP50 (thresholded) | AP50-95 (thresholded) |\n|---|---:|---:|---:|---:|\n'
    for name,item in result['per_class'].items():
        cells=['N/A' if item[k] is None else f'{item[k]:.4f}' for k in ('precision','recall','ap50','ap50_95')]
        table+='| '+name+' | '+' | '.join(cells)+' |\n'
    (output/'report.md').write_text('# ONNX evaluation\n\n'+LEAKAGE_WARNING+'\n\n'+result['ap_definition']+'\n\n'+table+'\nCommand: `'+result['command']+'`\n',encoding='utf-8')
    print(table)

if __name__=='__main__':main()
