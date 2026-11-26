import sys, unittest, copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verification import classify
from unittest.mock import patch
from verification import verification

class VerificationTest(unittest.TestCase):
    def test_verified(self):
        self.assertEqual(classify(True,True,False),'已核验')
    def test_conflict_priority(self):
        self.assertEqual(classify(True,True,True),'来源冲突')
    def test_changed_source_invalidates(self):
        self.assertEqual(classify(False,True,True),'待核验')
    def test_incomplete_checks(self):
        self.assertEqual(classify(True,False,False),'待核验')
    def test_live_source_invalidation(self):
        with patch('verification.digest',return_value='changed'):
            data=verification()
        self.assertEqual({p['id'] for p in data['projects']},{'chuanshan','maoshan','xiuqing','peixian','puti'})
        for p in data['projects']:
            self.assertEqual(p['counts']['待核验'],len(p['items']))
            self.assertTrue(all('失效' in i['reason'] for i in p['items']))
    def test_real_records(self):
        for p in verification()['projects']:
            self.assertEqual(p['counts']['已核验'],{'maoshan':37,'chuanshan':38,'xiuqing':30,'peixian':33,'puti':20}[p['id']])
            self.assertTrue(all(i['evidence']['unit']=='万元' for i in p['items']))
if __name__=='__main__':unittest.main()
