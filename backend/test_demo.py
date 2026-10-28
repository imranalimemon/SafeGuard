"""Demo-data creation is restricted to temporary source copies."""
from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from backend.tools.make_demo_data import make_demo

class DemoDataTests(unittest.TestCase):
 def test_copies_real_source_values_evidence_and_labels_demo(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);images=root/'images';images.mkdir();(images/'actual.jpg').write_bytes(b'evidence-fixture')
   source=root/'source.db'
   with closing(sqlite3.connect(source)) as db, db:
    db.execute('CREATE TABLE violations (id INTEGER PRIMARY KEY,timestamp TEXT,screenshot_path TEXT,details TEXT)')
    db.execute('INSERT INTO violations VALUES (?,?,?,?)',(7,'2026-10-01','/screenshots/actual.jpg','real-source-values'))
   result=make_demo(source,images,1)
   def cleanup_demo():
    target=Path(result['database']).resolve().parent
    self.assertEqual(target.parent,Path(tempfile.gettempdir()).resolve())
    self.assertTrue(target.name.startswith('safeguard-DEMO-'))
    __import__('shutil').rmtree(target)
   self.addCleanup(cleanup_demo)
   with closing(sqlite3.connect(result['database'])) as copied:
    self.assertEqual(copied.execute('SELECT * FROM violations').fetchone(),(7,'2026-10-01','/screenshots/actual.jpg','real-source-values'))
    self.assertIn('DEMO',copied.execute('SELECT label FROM demo_metadata').fetchone()[0])
   self.assertEqual((Path(result['screenshots'])/'actual.jpg').read_bytes(),b'evidence-fixture')
   with closing(sqlite3.connect(source)) as original:self.assertEqual(original.execute('SELECT count(*) FROM violations').fetchone()[0],1)
   self.assertEqual(result['integrity'],'ok')

 def test_refuses_non_temporary_sources(self):
  with self.assertRaises(ValueError):make_demo(Path(__file__).parent/'safeguard.db',Path(__file__).parent/'screenshots')

if __name__=='__main__':unittest.main()
