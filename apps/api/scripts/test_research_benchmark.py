"""Meaningful offline regression checks; no service or app dependencies."""
import argparse
import json
from pathlib import Path
import tempfile
import unittest

import research_benchmark as rb


class BenchmarkTests(unittest.TestCase):
    def test_plan_reproducibility_and_family_isolation(self):
        a=rb.plan(); b=rb.plan()
        self.assertEqual(a,b)
        families,docs,assertions,qs=a
        self.assertEqual((len(families),len(docs),len(qs)),(24,96,120))
        self.assertEqual(sum(q['split']=='test' for q in qs),90)
        self.assertEqual(len({q['question'] for q in qs}),120)
        self.assertNotEqual(rb.plan(seed=7),a)
        for family in families:
            self.assertEqual({d['split'] for d in docs if d['family_id']==family['family_id']},{family['split']})

    def test_spans_hashes_and_hidden_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            args=argparse.Namespace(output=directory,seed=26014,families_per_category=4,limit_families=1,mode='template',model='unused')
            rb.generate(args)
            self.assertTrue(rb.validate(directory)['passed'])
            extra=Path(directory)/'raw'/'dev'/'answers.txt'
            extra.write_text('Should not enter retrieval',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'inventory'):
                rb.validate(directory)
            extra.unlink()
            path=next((Path(directory)/'raw'/'dev').glob('*.txt'))
            path.write_text(path.read_text()+' edited',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Hash mismatch'):
                rb.validate(directory)

    def test_disputed_requires_both_values_and_both_sources(self):
        _,_,assertions,questions=rb.plan()
        q=next(q for q in questions if q['expected_status']=='disputed')
        aids={a['assertion_id']:a for a in assertions}
        docs=[aids[aid]['doc_id'] for aid in q['evidence_assertions']]
        correct={'question_id':q['question_id'],'status':'disputed','values':q['required_values'],'citations':docs}
        summary,rows=rb.score_rows([q],assertions,[correct])
        self.assertEqual(summary['exact_value_status_accuracy_over_attempted'],1)
        self.assertEqual(rows[0]['evidence_group_citation_coverage'],1)
        correct['values']=q['required_values'][:1]
        self.assertEqual(rb.score_rows([q],assertions,[correct])[0]['exact_value_status_accuracy_over_attempted'],0)
        correct['citations']=docs[:1]
        self.assertEqual(rb.score_rows([q],assertions,[correct])[1][0]['evidence_group_citation_coverage'],0.5)

    def test_insufficient_and_errors_have_honest_denominators(self):
        _,_,assertions,questions=rb.plan()
        q=next(q for q in questions if q['expected_status']=='insufficient')
        result={'question_id':q['question_id'],'status':'insufficient','values':[],'citations':[]}
        summary,rows=rb.score_rows([q],assertions,[result])
        self.assertEqual(summary['exact_value_status_accuracy_over_attempted'],1)
        self.assertIsNone(summary['macro_document_citation_precision_proxy'])
        self.assertIsNone(rows[0]['evidence_group_citation_coverage'])
        summary,_=rb.score_rows([q],assertions,[{'question_id':q['question_id'],'error':'timeout'}])
        self.assertEqual(summary['run_errors'],1)
        self.assertEqual(summary['exact_value_status_accuracy_over_attempted'],0)
        self.assertFalse(summary['complete'])
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            rb.score_rows([q],assertions,[result,result])

    def test_retrieval_uses_only_source_text_and_handles_empty(self):
        docs=[('D2','harbor office'),('D1','retention aster 30 days')]
        self.assertEqual(rb.bm25('aster retention',docs,1)[0][0],'D1')
        self.assertEqual(rb.bm25('anything',[],3),[])

    def test_conflict_pairs_distinguish_scope_time_and_equivalent_units(self):
        _,_,assertions,_=rb.plan()
        pairs=rb.conflict_pairs(assertions)
        self.assertTrue(any(p['conflict'] for p in pairs))
        self.assertTrue(any(p['label']=='compatible_time' for p in pairs))
        self.assertTrue(any(p['label']=='compatible_scope' for p in pairs))
        unit_ids={a['assertion_id'] for a in assertions if a['truth_label']=='correct_equivalent_units'}
        same_scope_pairs=[p for p in pairs if ({p['assertion_a'],p['assertion_b']} & unit_ids) and p['label']!='compatible_scope']
        self.assertTrue(same_scope_pairs)
        self.assertTrue(all(p['label']=='compatible_same_value' for p in same_scope_pairs))

    def test_review_acceptance_survives_resume_but_not_changed_gold(self):
        import csv
        with tempfile.TemporaryDirectory() as directory:
            args=argparse.Namespace(output=directory,seed=26014,families_per_category=4,limit_families=1,mode='template',model='unused')
            rb.generate(args)
            root=Path(directory)
            review=root/'private'/'human_review.csv'
            with review.open('w',newline='',encoding='utf-8') as f:
                writer=csv.writer(f)
                writer.writerow(['family_id','reviewer','source_and_gold_checked','unexpected_prose_claims','decision','notes'])
                writer.writerow(['F001','Test reviewer','yes','no','accepted','fixture acceptance'])
            rb.write_json(root/'private'/'review_acceptance.json',{'dataset_content_digest':rb.dataset_content_digest(root)})
            self.assertEqual(rb.review_status(root),'first_pass_accepted')
            rb.generate(args)
            manifest=json.loads((root/'manifest.json').read_text())
            self.assertEqual(manifest['human_review_status'],'first_pass_accepted')
            qs=rb.read_jsonl(root/'private'/'questions.jsonl')
            qs[0]['required_values']=['Changed gold']
            rb.jsonl(root/'private'/'questions.jsonl',qs)
            self.assertEqual(rb.review_status(root),'stale_review')


if __name__=='__main__':
    unittest.main()
