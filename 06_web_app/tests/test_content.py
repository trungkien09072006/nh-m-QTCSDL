import unittest
from unittest.mock import patch, MagicMock
import app
from content import parse_values,save

class ContentTests(unittest.TestCase):
 def setUp(self):
  app.app.config.update(TESTING=True,SECRET_KEY='test')
  self.c=app.app.test_client()
 def teacher(self,role='Teacher'):
  with self.c.session_transaction() as s:
   s.update(user_id=2,role=role,fullname='Giáo viên',_csrf_token='token')
 def test_login_required(self):
  self.assertIn('/login',self.c.get('/teacher/').location)
 def test_student_denied(self):
  self.teacher('Student')
  self.assertEqual(self.c.get('/teacher/').status_code,403)
 def test_csrf(self):
  self.teacher()
  self.assertEqual(self.c.post('/teacher/subjects/new',data={'SubjectName':'Toán'}).status_code,400)
 def test_invalid_kind(self):
  self.teacher();self.assertEqual(self.c.get('/teacher/injected').status_code,404)
 def test_validation(self):
  for kind,data in [
   ('subjects',{'SubjectName':''}),
   ('questions',{'CompetencyID':'1','Content':'A','Difficulty':'6'}),
   ('resources',{'CompetencyID':'1','Title':'x','ResourceType':'VIDEO','EstimatedMin':'0'}),
   ('resources',{'CompetencyID':'1','Title':'x','ResourceType':'VIDEO','EstimatedMin':'10','Url':'javascript:alert(1)'}),
   ('exams',{'Title':'a','ExamType':'BAD','DurationMin':'10'})]:
   with self.subTest(kind=kind,data=data),self.assertRaises(ValueError):parse_values(kind,data)
 def test_valid_resource(self):
  vals=parse_values('resources',{'CompetencyID':'1','Title':'Video','ResourceType':'VIDEO','EstimatedMin':'10','Url':'https://example.org'})
  self.assertEqual(vals['EstimatedMin'],10)
 @patch('content.pyodbc.connect')
 @patch('content._fetch_all',return_value=[])
 def test_all_lists_render(self,fetch,connect):
  self.teacher()
  for kind in ('subjects','competencies','resources','questions','exams'):
   response=self.c.get('/teacher/'+kind,follow_redirects=True)
   self.assertEqual(response.status_code,200)
 @patch('content.pyodbc.connect')
 @patch('content._fetch_all',return_value=[])
 def test_all_forms_render(self,fetch,connect):
  self.teacher()
  for kind in ('subjects','competencies','resources','questions','exams'):
   self.assertEqual(self.c.get('/teacher/'+kind+'/new').status_code,200)
 def test_unapproved_question_rejected(self):
  from werkzeug.datastructures import MultiDict
  cur=MagicMock();cur.fetchone.side_effect=[(5,),(0,)]
  with app.app.test_request_context('/teacher/exams/new'):
   from flask import session
   session['user_id']=2
   with self.assertRaisesRegex(ValueError,'đã duyệt'):
    save(cur,'exams',None,MultiDict([('Title','Đề A'),('ExamType','QUIZ'),('DurationMin','10'),('question_ids','7')]))
 def test_question_requires_four_options(self):
  cur=MagicMock();cur.fetchone.return_value=(9,)
  with app.app.test_request_context('/'):
   from flask import session
   session['user_id']=2
   with self.assertRaisesRegex(ValueError,'4 đáp án'):
    save(cur,'questions',None,{'CompetencyID':'1','Content':'a','Difficulty':'1','correct':'A'})
 @patch('content.pyodbc.connect')
 def test_self_approval_denied(self,connect):
  self.teacher();connect.return_value.cursor.return_value.fetchone.return_value=(2,)
  r=self.c.post('/teacher/questions/9/approve',data={'csrf_token':'token'})
  self.assertEqual(r.status_code,302)
  connect.return_value.commit.assert_not_called()
 @patch('content.pyodbc.connect')
 def test_approval_requires_one_correct(self,connect):
  self.teacher();connect.return_value.cursor.return_value.fetchone.side_effect=[(3,),(4,0)]
  self.c.post('/teacher/questions/9/approve',data={'csrf_token':'token'})
  connect.return_value.commit.assert_not_called()
 @patch('content.pyodbc.connect')
 def test_admin_approval(self,connect):
  self.teacher('Admin');connect.return_value.cursor.return_value.fetchone.side_effect=[(2,),(4,1)]
  self.c.post('/teacher/questions/9/approve',data={'csrf_token':'token'})
  connect.return_value.commit.assert_called_once()
 @patch('content.pyodbc.connect')
 def test_other_teacher_cannot_edit(self,connect):
  self.teacher();cur=connect.return_value.cursor.return_value
  cur.description=[('CreatedBy',)];cur.fetchone.return_value=(3,)
  self.assertEqual(self.c.get('/teacher/questions/8/edit').status_code,403)

if __name__=='__main__':unittest.main()
