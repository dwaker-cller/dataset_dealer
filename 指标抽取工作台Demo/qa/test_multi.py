import sys, unittest, copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from projects import project_list, apply_snapshot, combine
from server import inspect_inputs, ROOT

class MultiProjectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results=[]
        for p in project_list():
            info=inspect_inputs(dict(folder=p['folder'],template=str(ROOT/'2025主网项目指标参考(1).xlsx'),owl=str(ROOT/'Algorithm/grid_tech_economic_framework_v3(1).owl')))
            cls.results.append(apply_snapshot(info))

    def test_five_real_projects(self):
        self.assertEqual(len(self.results),5)
        for r in self.results:
            self.assertGreaterEqual(r['extraction']['filled'],10)
            self.assertEqual(len(r['sheets'][0]['rows']),1)
            self.assertTrue(all(Path(f['evidence']['file']).is_file() for f in r['sheets'][0]['fields'] if f.get('evidence')))

    def test_accumulate_and_replace(self):
        out=combine(self.results+[self.results[0]])
        s=out['sheets'][0]
        self.assertEqual(len(s['rows']),5)
        self.assertEqual(len(s['rowFields']),5)
        for n,fields in enumerate(s['rowFields'],6):
            for f in fields:
                if f.get('evidence'): self.assertEqual(f['evidence']['templateCell'],f['column']+str(n))
        self.assertEqual(len({r[8] for r in s['rows']}),5)

    def test_reject_mixed_contract(self):
        changed=copy.deepcopy(self.results[0]);changed['contractKey']='changed'
        with self.assertRaises(ValueError):combine([self.results[1],changed])

    def test_source_values(self):
        expected={'maoshan':972.2553,'peixian':853.0682,'chuanshan':2615.8375}
        for r in self.results:
            f={f['column']:f for f in r['sheets'][0]['fields']}
            if r['projectId'] in expected:self.assertEqual(f['DB']['evidence']['value'],expected[r['projectId']])
            if r['projectId']=='puti':self.assertEqual(f['ES']['evidence']['value'],763)
            if r['projectId']=='xiuqing':
                self.assertEqual(r['extraction']['filled'],53)
                self.assertFalse(f['DT'].get('evidence'))
                self.assertEqual(f['DT']['missingStatus'],'来源冲突')
                self.assertFalse(f['DV'].get('evidence'))
                self.assertEqual(f['DV']['missingStatus'],'来源冲突')
                self.assertEqual(f['CI']['evidence']['value'],6.9473)
                self.assertEqual(f['CL']['evidence']['value'],224.7000)
                self.assertFalse(f['EN'].get('evidence'))
            if r['projectId']=='peixian':
                self.assertEqual(f['EN']['evidence']['value'],6471)
                self.assertEqual(f['EP']['evidence']['value'],6568)
                self.assertEqual(f['DU']['evidence']['value'],0)
                self.assertEqual(f['DO']['evidence']['value'],19.5198)
            if r['projectId'] in ['xiuqing','peixian']:
                for col in ['DL','DM']:
                    self.assertFalse(f[col].get('evidence'))
                    self.assertEqual(f[col]['missingStatus'],'待核验')

if __name__=='__main__':unittest.main()
