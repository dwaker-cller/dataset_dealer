import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verification import may_fill
class GateTest(unittest.TestCase):
 def test_only_approved_candidates_fill(self):
  for status in ['待核验','来源冲突']:
   self.assertFalse(may_fill({'status':status}))
  self.assertTrue(may_fill({'status':'已核验'}))
  self.assertFalse(may_fill(None))
if __name__=='__main__':unittest.main()
