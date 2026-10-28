"""Tiny synthetic evaluation dataset; no network, database or real model."""
import tempfile
import unittest
from pathlib import Path
from backend.tools.evaluation import evaluate, read_labels, average_precision, iou
from backend import test_detection_model as detector_tests
import numpy as np


class EvaluationTests(unittest.TestCase):
    def test_perfect_predictions_yolo_labels_and_production_postprocess(self):
        with tempfile.TemporaryDirectory() as temp:
            label=Path(temp)/'tiny.txt'; label.write_text('1 0.5 0.5 0.5 0.5\n')
            ground=read_labels(label,640,640)
            detector=detector_tests.PPEDetector.__new__(detector_tests.PPEDetector);detector.input_width=detector.input_height=640
            predictions=detector.postprocess(detector_tests.DetectorProcessingTests.outputs(([160,160,480,480],1,.99)),(640,640))
            result=evaluate([{'filename':'tiny.png','labels':ground,'predictions':predictions}])
            self.assertEqual(result['per_class']['Helmet']['ap50_95'],1)
            self.assertEqual(result['confusion_matrix'][1][1],1)
            self.assertIsNone(result['per_class']['Face Mask']['ap50'])

    def test_duplicate_and_high_scoring_false_positive_reduce_precision_and_ap(self):
        gt={'class_id':1,'bbox':[0,0,10,10]}
        wrong={'class_id':1,'bbox':[30,30,40,40],'confidence':.99}
        hit={**gt,'confidence':.9};duplicate={**hit,'confidence':.8}
        result=evaluate([{'filename':'a','labels':[gt],'predictions':[wrong,hit,duplicate]}])['per_class']['Helmet']
        self.assertEqual(result['tp'],1);self.assertEqual(result['fp'],2)
        self.assertAlmostEqual(result['ap50'],.5)
        self.assertAlmostEqual(result['precision'],1/3)

    def test_class_confusion_and_missed_ground_truth(self):
        gt={'class_id':1,'bbox':[0,0,10,10]}
        result=evaluate([{'filename':'a','labels':[gt],'predictions':[{**gt,'class_id':0,'confidence':.9}]}])
        self.assertEqual(result['confusion_matrix'][1][0],1)
        self.assertEqual(result['per_class']['Helmet']['recall'],0)
        self.assertEqual(result['per_class']['Helmet']['ap50'],0)

    def test_iou_thresholds_and_unreachable_recall(self):
        self.assertEqual(iou([0,0,10,10],[0,0,10,10]),1)
        self.assertEqual(iou([0,0,0,0],[0,0,0,0]),0)
        self.assertAlmostEqual(average_precision(np.array([.5]),np.array([1.0]),2),51/101)

    def test_invalid_or_missing_labels_fail_loudly(self):
        with tempfile.TemporaryDirectory() as temp:
            label=Path(temp)/'bad.txt'
            for text in ['4 .5 .5 .1 .1','0 nan .5 .1 .1','0 .5 .5 -1 .1']:
                label.write_text(text)
                with self.assertRaises(ValueError):read_labels(label,640,480)
            with self.assertRaises(ValueError):read_labels(Path(temp)/'missing.txt',640,480)

if __name__=='__main__':unittest.main()

class ValidationAndWorkerTests(unittest.TestCase):
    def test_model_contract_class_metadata_and_shape(self):
        from backend.tools.validate_model import check_contract
        from types import SimpleNamespace
        session=SimpleNamespace(get_inputs=lambda:[SimpleNamespace(shape=[1,3,640,640])],get_outputs=lambda:[SimpleNamespace(shape=[1,8,8400])],get_modelmeta=lambda:SimpleNamespace(custom_metadata_map={'names':"{0:'Face Mask',1:'Helmet',2:'Person',3:'Safety Vest'}"}))
        self.assertEqual(check_contract(session)['input_shape'],[1,3,640,640])
        session.get_modelmeta=lambda:SimpleNamespace(custom_metadata_map={'names':"{0:'Helmet',1:'Face Mask',2:'Person',3:'Safety Vest'}"})
        with self.assertRaises(ValueError):check_contract(session)
        session.get_modelmeta=lambda:SimpleNamespace(custom_metadata_map={})
        with self.assertRaises(ValueError):check_contract(session)
        session.get_outputs=lambda:[SimpleNamespace(shape=[1,300,6])]
        with self.assertRaises(ValueError):check_contract(session)

    def test_worker_truth_mask_absence_unknown_without_independent_visibility(self):
        from backend.tools.violation_eval import ground_workers
        labels=[{'class_id':2,'bbox':[0,0,100,200]}, {'class_id':1,'bbox':[30,5,70,35]}, {'class_id':3,'bbox':[20,40,80,120]}]
        truth,_=ground_workers(labels)
        self.assertEqual(truth[0]['status'],'UNKNOWN')
        self.assertIn('Face Mask',truth[0]['unknown_ppe'])
        visible,_=ground_workers(labels,{'0':True})
        self.assertEqual(visible[0]['missing_ppe'],['Face Mask'])
        self.assertEqual(visible[0]['status'],'VIOLATION')
        labels.append({'class_id':0,'bbox':[35,35,65,55]})
        masked,_=ground_workers(labels)
        self.assertEqual(masked[0]['status'],'COMPLIANT')

    def test_worker_assignment_ambiguity_is_excluded_and_orphan_not_worker(self):
        from backend.tools.violation_eval import ground_workers
        people=[{'class_id':2,'bbox':[0,0,100,200]},{'class_id':2,'bbox':[0,0,100,200]}]
        people.append({'class_id':1,'bbox':[30,5,70,35]})
        truth,counts=ground_workers(people)
        self.assertEqual(counts['ambiguous_ppe_annotations'],1)
        self.assertTrue(all('Helmet' in w['unknown_ppe'] for w in truth))
        truth,_=ground_workers([{'class_id':1,'bbox':[0,0,10,10]}])
        self.assertEqual(truth,[])

    def test_worker_false_positives_misses_and_abstention(self):
        from backend.tools.violation_eval import worker_counts,metrics
        gt={'person_bbox':[0,0,100,200],'has_ppe':[],'unknown_ppe':[],'status':'VIOLATION'}
        predicted={**gt,'status':'COMPLIANT','confidence':.9}
        counts=worker_counts([gt],[predicted])
        self.assertEqual(counts['missed_violation'],1)
        self.assertEqual(metrics(counts)['violation']['recall'],0)
        self.assertEqual(worker_counts([gt],[])['missed_worker'],1)
        self.assertEqual(worker_counts([],[predicted])['COMPLIANT_fp'],1)
