"""Validate a candidate model without replacing the deployed file or opening a DB."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from tools.evaluation import CLASSES


def check_contract(session, supplied_classes=None):
    inputs=session.get_inputs();outputs=session.get_outputs()
    if len(inputs)!=1 or list(inputs[0].shape)!=[1,3,640,640]:
        raise ValueError('Expected exactly one 1x3x640x640 input.')
    if len(outputs)!=1 or list(outputs[0].shape)!=[1,8,8400]:
        raise ValueError('Expected exactly one 1x8x8400 output without embedded NMS.')
    raw=session.get_modelmeta().custom_metadata_map.get('names')
    if raw:
        mapping=ast.literal_eval(raw)
        if isinstance(mapping,list):mapping=dict(enumerate(mapping))
        mapping={int(k):v for k,v in mapping.items()}
        provenance='ONNX names metadata (declared class order; learned semantics still require visual inspection)'
    elif supplied_classes is not None:
        mapping={int(k):v for k,v in supplied_classes.items()}
        provenance='Operator-supplied class mapping; model has no class-name metadata. Learned order is NOT independently verified.'
    else:raise ValueError('Model lacks names metadata. Supply --class-map JSON and visually verify class semantics.')
    if mapping!=CLASSES:raise ValueError('Class order must be Face Mask, Helmet, Person, Safety Vest.')
    return {'input_shape':list(inputs[0].shape),'output_shape':list(outputs[0].shape),'class_mapping':mapping,'class_order_evidence':provenance}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,default=ROOT/'backend/best.onnx')
    parser.add_argument('--images-dir',type=Path,required=True)
    parser.add_argument('--class-map',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    images=sorted(p for p in args.images_dir.iterdir() if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'})[:5]
    if len(images)!=5:parser.error('At least five images are required.')
    with tempfile.TemporaryDirectory(prefix='safeguard-validate-') as temp,patch.dict(os.environ,{'SCREENSHOT_DIR':temp,'ALERT_DELIVERY_MODE':'preview'}),patch('dotenv.load_dotenv'):
        import cv2
        from detection.model import PPEDetector
        detector=PPEDetector(str(args.model.resolve()))
        supplied=json.loads(args.class_map.read_text()) if args.class_map else None
        result=check_contract(detector.session,supplied)
        result.update({'model':str(args.model.resolve()),'model_sha256':hashlib.sha256(args.model.read_bytes()).hexdigest(),'providers':detector.session.get_providers(),'images':[], 'command':' '.join([sys.executable,'-B',*sys.argv])})
        for path in images:
            frame=cv2.imread(str(path))
            if frame is None:raise ValueError(f'Cannot decode {path.name}')
            tensor,shape=detector.preprocess(frame)
            output=detector.session.run(None,{detector.input_name:tensor})
            if list(output[0].shape)!=[1,8,8400]:raise ValueError('Runtime output shape does not match contract.')
            import numpy as np
            if not np.isfinite(output[0]).all():raise ValueError('Model output contains nonfinite values.')
            detections=detector.postprocess(output,shape)
            result['images'].append({'filename':path.name,'image_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'detections_per_class':{name:sum(d['class_id']==cls for d in detections) for cls,name in CLASSES.items()}})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
