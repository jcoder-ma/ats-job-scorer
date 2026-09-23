"""Regression coverage for the deterministic scoring and document-parsing rules.

Fictional fixtures exercise evidence credit, category weights, eligibility,
manual review, and input boundaries without a browser or external services.
These tests validate the rubric's behavior, not real-world hiring accuracy.
"""
import sys
import unittest
import base64
import io
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'web'))
from engine import score, extract_requirements, extract_document, concepts, api
RESUME='Built Python APIs for enterprise software applications and mentored engineers across two teams.\nSkills: React, Kubernetes.'
JOB='Required qualifications\nBuild Python APIs and React applications.\nLead mentoring and roadmap planning.\nPreferred qualifications\nExperience with Kubernetes and FastAPI.'

class EngineTests(unittest.TestCase):
 def test_weights_total_100(self):
  r=score(JOB,RESUME);self.assertEqual(sum(c['weight'] for c in r['categories']),100)
 def test_category_sum(self):
  r=score(JOB,RESUME);self.assertAlmostEqual(sum(c['earned'] for c in r['categories']),r['score'])
 def test_preferred_cap(self):
  r=score(JOB,RESUME);self.assertEqual(next(c['weight'] for c in r['categories'] if c['category']=='Preferred qualifications'),15)
 def test_keyword_only(self):
  r=score(JOB,RESUME);self.assertEqual(next(x['level'] for x in r['requirements'] if x['concept']=='React'),.25)
 def test_action_evidence_capped(self):
  r=score(JOB,RESUME);self.assertEqual(next(x['level'] for x in r['requirements'] if x['concept']=='Python'),.75)
 def test_repetition_does_not_inflate(self):
  self.assertEqual(score(JOB,RESUME)['score'],score(JOB,RESUME+'\n'+RESUME)['score'])
 def test_duplicate_requirements(self):
  rows=extract_requirements('Build Python applications.\nBuild Python applications.');self.assertEqual(len(rows),1)
 def test_no_go_false_positive(self):self.assertNotIn('Go',concepts('Help customers go faster and improve delivery.'))
 def test_language_go(self):self.assertIn('Go',concepts('Programming languages: Go, Python'))
 def test_java_not_javascript(self):self.assertNotIn('Java',concepts('JavaScript and React'))
 def test_deployment_not_database_migration(self):
  rows=extract_requirements('Required qualifications\nExperience with zero-downtime database migrations and schema decoupling.')
  r=score('Experience with zero-downtime database migrations.', 'Introduced zero-downtime deployments using Kubernetes and distributed caching for applications.',requirements=rows)
  self.assertTrue(all(x['level']==0 for x in r['requirements']))
 def test_unknown_gate_not_deducted(self):
  a=score(JOB,RESUME);b=score(JOB+'\nMust be authorized to work without sponsorship.',RESUME)
  self.assertEqual(a['score'],b['score']);self.assertEqual(b['unknown_gates'],1)
 def test_unmet_gate_overrides(self):
  rows=extract_requirements(JOB+'\nMust be authorized to work without sponsorship.')
  for x in rows:
   if x['importance']=='eligibility':x['gate_status']='unmet'
  self.assertEqual(score(JOB,RESUME,requirements=rows)['recommendation'],'Do not apply under the stated conditions')
 def test_review_requires_reason(self):
  rows=extract_requirements(JOB);rows[0].update(reviewed=True,level=1)
  with self.assertRaises(ValueError):score(JOB,RESUME,requirements=rows)
 def test_manual_review(self):
  rows=extract_requirements(JOB);rows[0].update(reviewed=True,level=1,reason='Verified production project with exact scope.')
  self.assertEqual(score(JOB,RESUME,requirements=rows)['reviewed_count'],1)
 def test_negative_evidence(self):
  r=score(JOB,'No experience with Python.\nBuilt React applications for an internal customer service portal.')
  self.assertEqual(next(x['level'] for x in r['requirements'] if x['concept']=='Python'),0)
 def test_conflict(self):
  r=score(JOB,RESUME,'No experience with Python.')
  self.assertEqual(next(x['status'] for x in r['requirements'] if x['concept']=='Python'),'Conflicting')
 def test_extra_experience_separate(self):
  a=score(JOB,RESUME);b=score(JOB,RESUME,'Built FastAPI applications with production monitoring and tests for internal users.')
  self.assertGreater(b['score'],a['score'])
 def test_unsupported_kept(self):self.assertEqual(extract_requirements('Must know the obscure WonderWidget system.')[0]['concept'],'')
 def test_empty_inputs(self):
  with self.assertRaises(ValueError):score('',RESUME)
 def test_empty_requirements(self):
  with self.assertRaises(ValueError):score(JOB,RESUME,requirements=[])
 def test_invalid_score(self):
  rows=extract_requirements(JOB);rows[0].update(reviewed=True,level=5,reason='invalid')
  with self.assertRaises(ValueError):score(JOB,RESUME,requirements=rows)
 def test_docx_extract(self):
  buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'+RESUME+'</w:t></w:r></w:p></w:body></w:document>')
  self.assertIn('Python',extract_document('sample.docx',base64.b64encode(buf.getvalue()).decode()))
 def test_blank_scan(self):
  with self.assertRaises(ValueError):extract_document('sample.txt',base64.b64encode(b' ').decode())
 def test_unsupported_upload(self):
  with self.assertRaises(ValueError):extract_document('sample.exe',base64.b64encode(b'test').decode())
 def test_source_excerpts_exact(self):
  r=score(JOB,RESUME)
  for row in r['requirements']:
   for e in row['evidence']:self.assertIn(e['text'],RESUME)
 def test_preferred_only_cannot_score(self):
  with self.assertRaises(ValueError):score('Preferred qualifications\nExperience with Python and React.',RESUME)
 def test_oversized_text(self):
  with self.assertRaises(ValueError):score('x'*150001,RESUME)
 def test_payload_never_executed(self):
  import json
  r=json.loads(api(json.dumps({'job':JOB,'resume':RESUME+"\n__import__('os').system('false')"})))
  self.assertIn('score',r)

if __name__=='__main__':unittest.main()
