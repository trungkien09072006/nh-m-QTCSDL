"""Phần 2: nội dung học tập. SQL luôn dùng tham số cho dữ liệu người dùng."""
from contextlib import closing
from urllib.parse import urlsplit
import pyodbc
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from database import _connection_string, _fetch_all

bp = Blueprint('content', __name__, url_prefix='/teacher')
# Tên bảng/cột chỉ lấy từ cấu hình cố định này.
KINDS = {
 'subjects': ('Môn học', 'Subjects', 'SubjectID', [('SubjectName','Tên môn','text',100),('Description','Mô tả','textarea',500)]),
 'competencies': ('Năng lực', 'Competencies', 'CompetencyID', [('SubjectID','Môn học','subjects',0),('CompetencyName','Tên năng lực','text',150),('ParentCompID','Năng lực cha (có thể bỏ trống)','parent',0)]),
 'resources': ('Tài liệu', 'LearningResources', 'ResourceID', [('CompetencyID','Năng lực','competencies',0),('Title','Tiêu đề','text',200),('ResourceType','Loại tài liệu','resource_type',0),('Url','Liên kết tài liệu','url',500),('EstimatedMin','Thời lượng (phút)','number',0)]),
 'questions': ('Câu hỏi', 'Questions', 'QuestionID', [('CompetencyID','Năng lực','competencies',0),('Content','Nội dung câu hỏi','textarea',10000),('Difficulty','Độ khó (1–5)','number',0),('Explanation','Giải thích đáp án','textarea',10000)]),
 'exams': ('Đề thi', 'Exams', 'ExamID', [('Title','Tên đề','text',200),('ExamType','Loại đề','exam_type',0),('DurationMin','Thời gian (phút)','number',0)])
}

@bp.before_request
def authorize():
 if 'user_id' not in session: return redirect(url_for('login'))
 if session.get('role') not in ('Teacher','Admin'): abort(403)

def positive(value):
 try: n=int(value)
 except (ValueError,TypeError): raise ValueError('Vui lòng nhập số nguyên hợp lệ.')
 if n<=0: raise ValueError('Giá trị phải lớn hơn 0.')
 return n

def parse_values(kind, form):
 values={}
 for name,label,typ,limit in KINDS[kind][3]:
  v=form.get(name,'').strip()
  if name=='ParentCompID': v=positive(v) if v else None
  elif typ in ('number','subjects','competencies'): v=positive(v)
  elif not v and name not in ('Description','Explanation','Url'): raise ValueError(f'Chưa nhập {label}.')
  if limit and len(v)>limit: raise ValueError(f'{label} tối đa {limit} ký tự.')
  values[name]=v
 if kind=='resources':
  if values['ResourceType'] not in ('VIDEO','ARTICLE','SLIDE','EXERCISE'): raise ValueError('Loại tài liệu không hợp lệ.')
  u=values['Url']
  if u and (urlsplit(u).scheme not in ('http','https') or not urlsplit(u).netloc): raise ValueError('Liên kết phải là URL http/https hợp lệ.')
 if kind=='questions' and not 1<=values['Difficulty']<=5: raise ValueError('Độ khó phải từ 1 đến 5.')
 if kind=='exams' and values['ExamType'] not in ('DIAGNOSTIC','MOCK','QUIZ'): raise ValueError('Loại đề không hợp lệ.')
 return values

def owned(cursor,kind,item_id):
 _,table,pk,_=KINDS[kind]
 cursor.execute(f'SELECT * FROM {table} WITH (UPDLOCK,HOLDLOCK) WHERE {pk}=?',(item_id,))
 row=cursor.fetchone()
 if row is None: abort(404)
 data=dict(zip([c[0] for c in cursor.description],row))
 if 'CreatedBy' in data and data['CreatedBy']!=session['user_id'] and session['role']!='Admin': abort(403)
 return data

def locked_question(cursor,item_id):
 cursor.execute('SELECT 1 FROM ExamQuestions WHERE QuestionID=?',(item_id,))
 if cursor.fetchone(): raise ValueError('Câu hỏi đã nằm trong đề. Hãy tạo câu hỏi mới để bảo toàn đề và lịch sử thi.')

def save(cursor,kind,item_id,form):
 vals=parse_values(kind,form)
 if item_id:
  owned(cursor,kind,item_id)
  if kind=='questions': locked_question(cursor,item_id)
  if kind=='exams':
   cursor.execute('SELECT 1 FROM ExamAttempts WHERE ExamID=?',(item_id,))
   if cursor.fetchone(): raise ValueError('Đề đã có lượt làm, không thể chỉnh sửa.')
 if kind=='competencies' and vals['ParentCompID']:
  parent=vals['ParentCompID'];seen={item_id} if item_id else set()
  while parent:
   if parent in seen: raise ValueError('Năng lực cha tạo thành vòng lặp.')
   seen.add(parent)
   cursor.execute('SELECT SubjectID,ParentCompID FROM Competencies WITH (UPDLOCK,HOLDLOCK) WHERE CompetencyID=?',(parent,))
   r=cursor.fetchone()
   if not r or r[0]!=vals['SubjectID']: raise ValueError('Năng lực cha phải thuộc cùng môn học.')
   parent=r[1]
  # Không cho đổi môn của nút đang có con sang môn khác.
 if kind=='competencies' and item_id:
  cursor.execute('SELECT 1 FROM Competencies WHERE ParentCompID=? AND SubjectID<>?',(item_id,vals['SubjectID']))
  if cursor.fetchone(): raise ValueError('Cần chuyển năng lực con trước khi đổi môn.')
 if kind=='questions': vals['IsApproved']=0
 if kind in ('resources','questions','exams') and not item_id: vals['CreatedBy']=session['user_id']
 _,table,pk,_=KINDS[kind]
 if item_id:
  cursor.execute(f"UPDATE {table} SET {','.join(n+'=?' for n in vals)} WHERE {pk}=?",(*vals.values(),item_id))
 else:
  cursor.execute(f"INSERT INTO {table} ({','.join(vals)}) OUTPUT INSERTED.{pk} VALUES ({','.join('?' for _ in vals)})",tuple(vals.values()))
  item_id=cursor.fetchone()[0]
 if kind=='questions':
  options=[form.get('option_'+x,'').strip() for x in 'ABCD']
  correct=form.get('correct','')
  if any(not x or len(x)>1000 for x in options) or correct not in 'ABCD' or len(correct)!=1: raise ValueError('Cần đủ 4 đáp án A–D (tối đa 1000 ký tự), chọn đúng một đáp án đúng.')
  cursor.execute('DELETE FROM QuestionOptions WHERE QuestionID=?',(item_id,))
  for label,txt in zip('ABCD',options): cursor.execute('INSERT INTO QuestionOptions(QuestionID,OptionLabel,OptionText,IsCorrect) VALUES (?,?,?,?)',(item_id,label,txt,int(label==correct)))
 if kind=='exams':
  ids=[positive(x) for x in form.getlist('question_ids')]
  if not ids or len(ids)!=len(set(ids)): raise ValueError('Chọn ít nhất một câu hỏi, không trùng lặp.')
  cursor.execute('DELETE FROM ExamQuestions WHERE ExamID=?',(item_id,))
  for order,qid in enumerate(ids,1):
   cursor.execute('SELECT IsApproved FROM Questions WITH (UPDLOCK,HOLDLOCK) WHERE QuestionID=?',(qid,))
   q=cursor.fetchone()
   if not q or not q[0]: raise ValueError('Chỉ được đưa câu hỏi đã duyệt vào đề.')
   cursor.execute('INSERT INTO ExamQuestions VALUES (?,?,?)',(item_id,qid,order))
 return item_id

@bp.route('/',defaults={'kind':'questions'})
@bp.route('/<kind>')
def listing(kind):
 if kind not in KINDS: abort(404)
 with closing(pyodbc.connect(_connection_string(),timeout=5)) as conn:
  cur=conn.cursor();_,table,pk,_=KINDS[kind]
  rows=_fetch_all(cur,f'SELECT * FROM {table} ORDER BY {pk} DESC')
 q=request.args.get('q','').strip().casefold()
 if q: rows=[r for r in rows if q in ' '.join(str(v) for v in r.values()).casefold()]
 return render_template('content_list.html',kind=kind,kinds=KINDS,rows=rows,q=request.args.get('q',''))

@bp.route('/<kind>/new',methods=['GET','POST'],defaults={'item_id':None})
@bp.route('/<kind>/<int:item_id>/edit',methods=['GET','POST'])
def edit(kind,item_id):
 if kind not in KINDS: abort(404)
 with closing(pyodbc.connect(_connection_string(),timeout=5)) as conn:
  cur=conn.cursor();data={};options={};selected=[]
  if item_id: data=owned(cur,kind,item_id)
  if request.method=='POST':
   try:
    save(cur,kind,item_id,request.form);conn.commit();flash('Đã lưu nội dung. Câu hỏi cần được duyệt trước khi thêm vào đề.','success')
    return redirect(url_for('content.listing',kind=kind))
   except ValueError as e: conn.rollback();flash(str(e),'error')
   except pyodbc.IntegrityError: conn.rollback();flash('Dữ liệu trùng hoặc vi phạm ràng buộc liên kết. Vui lòng kiểm tra lại.','error')
   data=request.form.to_dict()
  choices={
   'subjects':_fetch_all(cur,'SELECT SubjectID AS id,SubjectName AS label FROM Subjects'),
   'competencies':_fetch_all(cur,"SELECT c.CompetencyID AS id,CONCAT(s.SubjectName,N' / ',c.CompetencyName) AS label FROM Competencies c JOIN Subjects s ON s.SubjectID=c.SubjectID"),
   'resource_type':[{'id':x,'label':x} for x in ('VIDEO','ARTICLE','SLIDE','EXERCISE')],
   'exam_type':[{'id':x,'label':x} for x in ('DIAGNOSTIC','MOCK','QUIZ')]}
  choices['parent']=choices['competencies']
  if kind=='questions':
   if item_id: options={r['OptionLabel']:r for r in _fetch_all(cur,'SELECT * FROM QuestionOptions WHERE QuestionID=?',(item_id,))}
   if request.method=='POST': options={x:{'OptionText':request.form.get('option_'+x,''),'IsCorrect':request.form.get('correct')==x} for x in 'ABCD'}
  questions=_fetch_all(cur,'SELECT QuestionID,Content FROM Questions WHERE IsApproved=1 ORDER BY QuestionID') if kind=='exams' else []
  if kind=='exams' and item_id: selected=[r['QuestionID'] for r in _fetch_all(cur,'SELECT QuestionID FROM ExamQuestions WHERE ExamID=? ORDER BY OrderNo',(item_id,))]
  if request.method=='POST': selected=[int(x) for x in request.form.getlist('question_ids') if x.isdigit()]
  conn.rollback()
 return render_template('content_form.html',kind=kind,kinds=KINDS,data=data,choices=choices,options=options,questions=questions,selected=selected)

@bp.post('/questions/<int:item_id>/approve')
def approve(item_id):
 # Giáo viên duyệt ngân hàng chung; không tự duyệt câu do mình soạn, Admin có thể duyệt.
 with closing(pyodbc.connect(_connection_string(),timeout=5)) as conn:
  cur=conn.cursor()
  cur.execute('SELECT CreatedBy FROM Questions WITH (UPDLOCK,HOLDLOCK) WHERE QuestionID=?',(item_id,));r=cur.fetchone()
  if not r: abort(404)
  if r[0]==session['user_id'] and session['role']!='Admin':
   flash('Cần giáo viên khác hoặc quản trị viên duyệt câu hỏi của bạn.','error')
  else:
   cur.execute('SELECT COUNT(*),SUM(CAST(IsCorrect AS INT)) FROM QuestionOptions WHERE QuestionID=?',(item_id,));n,c=cur.fetchone()
   if n<2 or c!=1: flash('Câu hỏi phải có ít nhất 2 lựa chọn và đúng một đáp án đúng.','error')
   else:
    cur.execute('UPDATE Questions SET IsApproved=1 WHERE QuestionID=?',(item_id,));conn.commit();flash('Đã duyệt câu hỏi.','success')
 return redirect(url_for('content.listing',kind='questions'))

@bp.post('/<kind>/<int:item_id>/delete')
def delete(kind,item_id):
 if kind not in KINDS: abort(404)
 with closing(pyodbc.connect(_connection_string(),timeout=5)) as conn:
  cur=conn.cursor();owned(cur,kind,item_id)
  try:
   if kind=='questions': locked_question(cur,item_id)
   _,table,pk,_=KINDS[kind];cur.execute(f'DELETE FROM {table} WHERE {pk}=?',(item_id,));conn.commit();flash('Đã xóa.','success')
  except ValueError as e: conn.rollback();flash(str(e),'error')
  except pyodbc.IntegrityError: conn.rollback();flash('Không thể xóa nội dung đang được tham chiếu.','error')
 return redirect(url_for('content.listing',kind=kind))

@bp.errorhandler(pyodbc.Error)
def database_error(error):
 from flask import current_app
 current_app.logger.exception('Lỗi SQL Server trong phân hệ nội dung')
 return render_template('content_error.html'),503

@bp.get('/<kind>/<int:item_id>')
def detail(kind,item_id):
 if kind not in ('questions','exams'): abort(404)
 with closing(pyodbc.connect(_connection_string(),timeout=5)) as conn:
  cur=conn.cursor();_,table,pk,_=KINDS[kind]
  rows=_fetch_all(cur,f'SELECT * FROM {table} WHERE {pk}=?',(item_id,))
  if not rows: abort(404)
  if kind=='questions': questions=rows
  else: questions=_fetch_all(cur,'SELECT q.*,eq.OrderNo FROM ExamQuestions eq JOIN Questions q ON q.QuestionID=eq.QuestionID WHERE eq.ExamID=? ORDER BY eq.OrderNo',(item_id,))
  for q in questions: q['options']=_fetch_all(cur,'SELECT * FROM QuestionOptions WHERE QuestionID=? ORDER BY OptionLabel',(q['QuestionID'],))
 return render_template('content_detail.html',kind=kind,kinds=KINDS,item=rows[0],questions=questions)
