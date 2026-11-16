import importlib.util
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('read_export',Path(__file__).with_name('read-export.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class CopyExportTest(unittest.TestCase):
 def test_values_remain_exact(self):
  self.assertIsNone(module.decode_copy(r'\N'))
  self.assertEqual(module.decode_copy(r'\\N'),r'\N')
  self.assertEqual(module.decode_copy(r'a\tb\nc\\d'),'a\tb\nc\\d')
  self.assertEqual(module.decode_copy(r'\303\251'),'é')
  self.assertEqual(module.decode_copy('日本語'),'日本語')
  self.assertEqual(module.decode_copy('9007199254740993'),'9007199254740993')
 def test_empty_table_does_not_consume_following_rows(self):
  sql='COPY auth.users (id, email) FROM stdin;\n\\.\nCOPY public.records (id, title) FROM stdin;\na\tHello\\nworld\n\\.\n'
  self.assertEqual(module.copy_tables(sql),{'auth.users':[],'public.records':[{'id':'a','title':'Hello\nworld'}]})
 def test_incomplete_or_duplicate_sections_refused(self):
  with self.assertRaises(ValueError):module.copy_tables('COPY public.records (id, title) FROM stdin;\na\n\\.\n')
  with self.assertRaises(ValueError):module.copy_tables('COPY public.records (id) FROM stdin;\na\n')
  with self.assertRaises(ValueError):module.copy_tables('COPY public.records (id) FROM stdin;\n\\.\nCOPY public.records (id) FROM stdin;\n\\.\n')
 def test_stronger_identity_requirements_are_not_bypassed(self):
  tables={name:[] for name in ['auth.users','auth.identities','public.records','public.documents','public.report_jobs','storage.buckets','storage.objects','cron.job','drizzle.__drizzle_migrations']}
  tables['auth.mfa_factors']=[{'id':'factor'}]
  with self.assertRaisesRegex(ValueError,'MFA'):module.export_snapshot(tables)
  tables['auth.mfa_factors']=[];tables['auth.users']=[{'is_sso_user':'t'}]
  with self.assertRaisesRegex(ValueError,'SSO'):module.export_snapshot(tables)
if __name__=='__main__':unittest.main()
