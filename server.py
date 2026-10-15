#!/usr/bin/env python3
"""Samadhan Sathi local full-stack server (Python standard library + SQLite)."""
import hashlib, hmac, json, math, os, re, secrets, sqlite3, sys, time, uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / 'public'
DB_PATH = Path(os.environ.get('SAMADHAN_DB', ROOT / 'samadhan_sathi.sqlite3'))
HOST = os.environ.get('HOST', '127.0.0.1')
PORT = int(os.environ.get('PORT', '3000'))
CATEGORIES = ['Roads & Potholes','Garbage & Sanitation','Water Supply','Drainage','Streetlights','Public Infrastructure','Traffic & Public Spaces','Other']
STATUSES = ['Submitted','Under Review','Assigned','In Progress','Resolved','Reopened']

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def connect():
    db=sqlite3.connect(DB_PATH, timeout=10); db.row_factory=sqlite3.Row; db.execute('PRAGMA foreign_keys=ON'); return db

def init_db():
    with connect() as d:
        d.executescript('''
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('citizen','admin')), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id TEXT, csrf TEXT NOT NULL, expires REAL NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS complaints(id TEXT PRIMARY KEY, reference_id TEXT UNIQUE NOT NULL, user_id TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL, category TEXT NOT NULL, locality TEXT NOT NULL, landmark TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Submitted', department TEXT NOT NULL DEFAULT 'Not confirmed', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, latitude REAL, longitude REAL, FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT, complaint_id TEXT NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL, actor_id TEXT, actor_role TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(complaint_id) REFERENCES complaints(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT, actor_role TEXT NOT NULL, complaint_id TEXT, action TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', metadata TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, complaint_id TEXT, title TEXT NOT NULL, message TEXT NOT NULL, read_at TEXT, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        CREATE INDEX IF NOT EXISTS complaints_user_idx ON complaints(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS complaints_status_idx ON complaints(status);
        CREATE INDEX IF NOT EXISTS history_complaint_idx ON history(complaint_id, created_at DESC);
        ''')
        # Upgrade an existing local SQLite database without deleting saved complaints.
        complaint_columns = {row['name'] for row in d.execute('PRAGMA table_info(complaints)').fetchall()}
        if 'latitude' not in complaint_columns:
            d.execute('ALTER TABLE complaints ADD COLUMN latitude REAL')
        if 'longitude' not in complaint_columns:
            d.execute('ALTER TABLE complaints ADD COLUMN longitude REAL')
        d.execute('CREATE INDEX IF NOT EXISTS complaints_location_idx ON complaints(latitude, longitude)')

def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 310000)
    return 'pbkdf2_sha256$310000$%s$%s' % (salt.hex(), digest.hex())
def verify_password(password, encoded):
    try:
        _, rounds, salt, digest=encoded.split('$'); check=hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(rounds)).hex(); return hmac.compare_digest(check,digest)
    except Exception: return False

def public_user(row): return {'id':row['id'],'name':row['name'],'email':row['email'],'role':row['role']}
def public_complaint(row): return {'id':row['id'],'referenceId':row['reference_id'],'title':row['title'],'description':row['description'],'category':row['category'],'locality':row['locality'],'landmark':row['landmark'],'status':row['status'],'department':row['department'],'createdAt':row['created_at'],'updatedAt':row['updated_at'],'latitude':row['latitude'] if 'latitude' in row.keys() else None,'longitude':row['longitude'] if 'longitude' in row.keys() else None,'ownerName':row['owner_name'] if 'owner_name' in row.keys() else None}
def fallback_suggestion(title, desc, language='en'):
    low=(title+' '+desc).lower(); cat='Other'
    for words, category in [(['pothole','road','street','asphalt'],'Roads & Potholes'),(['garbage','waste','trash','sanitation'],'Garbage & Sanitation'),(['water','tap','supply'],'Water Supply'),(['drain','sewer','overflow','flood'],'Drainage'),(['light','lamp','streetlight'],'Streetlights'),(['traffic','footpath','park'],'Traffic & Public Spaces'),(['building','bench','infrastructure'],'Public Infrastructure')]:
        if any(w in low for w in words): cat=category; break
    cleaned=re.sub(r'\s+',' ',desc.strip()); cleaned=cleaned[:1].upper()+cleaned[1:] if cleaned else cleaned
    if cleaned and cleaned[-1] not in '.!?': cleaned+='.'
    return {'category':cat,'improvedText':cleaned,'summary':desc[:240],'language':language,'source':'rule-based-fallback','notice':'Review this suggestion. It may miss context and is not an official decision.'}

class Handler(BaseHTTPRequestHandler):
    server_version='SamadhanSathi/1.0'
    def log_message(self, fmt, *args): print('%s - %s' % (self.address_string(), fmt%args))
    def send_json(self, status, obj=None):
        data=b'' if obj is None else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','same-origin'); self.send_header('Content-Length',str(len(data)))
        if getattr(self,'set_cookie',None): self.send_header('Set-Cookie',self.set_cookie)
        self.end_headers()
        if data: self.wfile.write(data)
    def body(self):
        try: length=int(self.headers.get('Content-Length','0'))
        except ValueError: length=0
        if length>65536: raise ValueError('Request body is too large.')
        raw=self.rfile.read(length) if length else b'{}'
        try: value=json.loads(raw.decode('utf-8'))
        except Exception: raise ValueError('Invalid JSON request.')
        if not isinstance(value,dict): raise ValueError('JSON body must be an object.')
        return value
    def cookie_token(self):
        for part in self.headers.get('Cookie','').split(';'):
            if part.strip().startswith('samadhan.sid='): return part.strip().split('=',1)[1]
        return None
    def session(self, create=False):
        token=self.cookie_token(); d=connect(); row=None
        if token: row=d.execute('SELECT s.*,u.name,u.email,u.role FROM sessions s LEFT JOIN users u ON u.id=s.user_id WHERE token=? AND expires>?',(token,time.time())).fetchone()
        if row:
            self.session_token=token; self.session_csrf=row['csrf']; user={'id':row['user_id'],'name':row['name'],'email':row['email'],'role':row['role']} if row['user_id'] else None; d.close(); return user
        if create:
            token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32); d.execute('INSERT INTO sessions(token,user_id,csrf,expires) VALUES(?,?,?,?)',(token,None,csrf,time.time()+28800)); d.commit(); self.session_token=token; self.session_csrf=csrf; self.set_cookie=f'samadhan.sid={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'; d.close(); return None
        d.close(); self.session_token=None; self.session_csrf=None; return None
    def ensure_session(self):
        user=self.session(create=False)
        if not getattr(self,'session_token',None):
            self.session(create=True)
        return user
    def csrf_ok(self):
        token=self.cookie_token(); header=self.headers.get('X-CSRF-Token','')
        if not token or not header: return False
        with connect() as d: row=d.execute('SELECT csrf,expires FROM sessions WHERE token=?',(token,)).fetchone()
        return bool(row and row['expires']>time.time() and hmac.compare_digest(row['csrf'],header))
    def require_auth(self, admin=False):
        user=self.ensure_session()
        if not user: self.send_json(401,{'error':'Sign in to continue.'}); return None
        if admin and user['role']!='admin': self.send_json(403,{'error':'Administrator access required.'}); return None
        return user
    def do_GET(self):
        parsed=urlparse(self.path); path=parsed.path; q={k:v[-1] for k,v in parse_qs(parsed.query).items()}
        if path.startswith('/api/'): return self.api_get(path,q)
        if path=='/' or path=='/index.html': return self.static('index.html')
        if path in ['/styles.css','/app.js']: return self.static(path[1:])
        return self.static(path.lstrip('/'))
    def static(self,name):
        p=(PUBLIC/name).resolve()
        if PUBLIC.resolve() not in p.parents and p!=PUBLIC.resolve(): return self.send_json(404,{'error':'Not found'})
        if not p.is_file(): return self.send_json(404,{'error':'File not found'})
        data=p.read_bytes(); typ='text/html; charset=utf-8' if p.suffix=='.html' else 'text/css; charset=utf-8' if p.suffix=='.css' else 'text/javascript; charset=utf-8' if p.suffix=='.js' else 'application/octet-stream'
        self.send_response(200); self.send_header('Content-Type',typ); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def api_get(self,path,q):
        if path=='/api/health':
            try:
                with connect() as d: d.execute('SELECT 1')
                return self.send_json(200,{'ok':True,'database':'connected','engine':'SQLite'})
            except Exception: return self.send_json(503,{'ok':False,'database':'unavailable'})
        if path in ['/api/auth/me','/api/auth/csrf']:
            user=self.ensure_session(); csrf=getattr(self,'session_csrf',None)
            if not csrf:
                self.session(create=True); csrf=self.session_csrf
            return self.send_json(200,{'user':user,'csrfToken':csrf})
        if path=='/api/complaints':
            user=self.require_auth()
            if not user:return
            sql='SELECT c.*,u.name AS owner_name FROM complaints c JOIN users u ON u.id=c.user_id'; where=[]; args=[]
            if user['role']!='admin': where.append('c.user_id=?'); args.append(user['id'])
            if q.get('status') in STATUSES: where.append('c.status=?'); args.append(q['status'])
            if q.get('category') in CATEGORIES: where.append('c.category=?'); args.append(q['category'])
            if q.get('q'): where.append('(c.reference_id LIKE ? OR c.title LIKE ? OR c.locality LIKE ?)'); term='%'+q['q'][:100]+'%'; args.extend([term,term,term])
            sql+=(' WHERE '+' AND '.join(where)) if where else ''; sql+=' ORDER BY c.updated_at DESC LIMIT 100'
            with connect() as d: rows=d.execute(sql,args).fetchall()
            return self.send_json(200,{'complaints':[public_complaint(r) for r in rows]})
        if path.startswith('/api/complaints/'):
            user=self.require_auth()
            if not user:return
            ident=unquote(path[len('/api/complaints/'):]); parts=ident.split('/')
            with connect() as d:
                row=d.execute('SELECT c.*,u.name AS owner_name FROM complaints c JOIN users u ON u.id=c.user_id WHERE c.reference_id=? OR c.id=?',(parts[0],parts[0])).fetchone()
                if not row or (user['role']!='admin' and row['user_id']!=user['id']): return self.send_json(404,{'error':'Complaint not found.'})
                if len(parts)>1 and parts[1]=='reopen': return self.send_json(405,{'error':'Use POST to request reopening.'})
                history=d.execute('SELECT status,note,actor_role,created_at FROM history WHERE complaint_id=? ORDER BY id DESC',(row['id'],)).fetchall()
            return self.send_json(200,{'complaint':public_complaint(row),'history':[dict(x) for x in history]})
        if path=='/api/admin/stats':
            if not self.require_auth(admin=True): return
            with connect() as d:
                row=d.execute("SELECT count(*) total, sum(status IN ('Submitted','Under Review')) awaiting_review, sum(status IN ('Assigned','In Progress')) active, sum(status='Resolved') resolved, sum(status='Reopened') reopened FROM complaints").fetchone()
                cats=d.execute('SELECT category,count(*) count FROM complaints GROUP BY category ORDER BY count DESC, category').fetchall()
                status_rows=d.execute('SELECT status,count(*) count FROM complaints GROUP BY status ORDER BY count DESC, status').fetchall()
                localities=d.execute('SELECT locality,count(*) count FROM complaints GROUP BY locality ORDER BY count DESC, locality LIMIT 8').fetchall()
                monthly=d.execute("SELECT substr(created_at,1,7) month,count(*) count FROM complaints GROUP BY substr(created_at,1,7) ORDER BY month DESC LIMIT 6").fetchall()
            return self.send_json(200,{'stats':{k:(row[k] or 0) for k in row.keys()},'categories':[dict(x) for x in cats],'statuses':[dict(x) for x in status_rows],'localities':[dict(x) for x in localities],'monthly':list(reversed([dict(x) for x in monthly]))})
        if path=='/api/admin/map-data':
            if not self.require_auth(admin=True): return
            with connect() as d:
                rows=d.execute("SELECT reference_id,title,category,locality,status,department,latitude,longitude,created_at,updated_at FROM complaints WHERE latitude IS NOT NULL AND longitude IS NOT NULL ORDER BY updated_at DESC LIMIT 500").fetchall()
                total=d.execute('SELECT count(*) FROM complaints').fetchone()[0]
                located=d.execute('SELECT count(*) FROM complaints WHERE latitude IS NOT NULL AND longitude IS NOT NULL').fetchone()[0]
            return self.send_json(200,{'complaints':[dict(x) for x in rows],'total':total,'locatedCount':located,'withoutLocation':max(0,total-located)})
        if path=='/api/admin/audit':
            if not self.require_auth(admin=True):return
            with connect() as d: rows=d.execute('SELECT a.*,u.name AS actor,c.reference_id FROM audit a LEFT JOIN users u ON u.id=a.actor_id LEFT JOIN complaints c ON c.id=a.complaint_id ORDER BY a.id DESC LIMIT 200').fetchall()
            out=[]
            for r in rows:
                x=dict(r); x['metadata']=json.loads(x['metadata']); out.append(x)
            return self.send_json(200,{'events':out})
        if path=='/api/notifications':
            user=self.require_auth()
            if not user:return
            with connect() as d: rows=d.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 100',(user['id'],)).fetchall()
            return self.send_json(200,{'notifications':[dict(x) for x in rows]})
        return self.send_json(404,{'error':'API route not found.'})
    def do_POST(self): self.api_write('POST')
    def do_PATCH(self): self.api_write('PATCH')
    def api_write(self,method):
        path=urlparse(self.path).path
        if not path.startswith('/api/'): return self.send_json(404,{'error':'Not found'})
        try: data=self.body()
        except ValueError as e:return self.send_json(400,{'error':str(e)})
        if path=='/api/auth/register' and method=='POST':
            name=str(data.get('name','')).strip(); email=str(data.get('email','')).strip().lower(); password=str(data.get('password',''))
            if len(name)<2 or len(name)>100 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email) or len(email)>254 or len(password)<12 or len(password)>128:return self.send_json(400,{'error':'Enter a name, valid email, and password of at least 12 characters.'})
            old_token=self.cookie_token(); token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32); uid=str(uuid.uuid4())
            try:
                with connect() as d:
                    d.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',(uid,name,email,password_hash(password),'citizen',now()))
                    if old_token: d.execute('DELETE FROM sessions WHERE token=?',(old_token,))
                    d.execute('INSERT INTO sessions VALUES(?,?,?,?)',(token,uid,csrf,time.time()+28800))
            except sqlite3.IntegrityError:return self.send_json(409,{'error':'An account with that email already exists.'})
            self.session_token=token; self.session_csrf=csrf
            self.set_cookie=f'samadhan.sid={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'
            return self.send_json(201,{'user':{'id':uid,'name':name,'email':email,'role':'citizen'},'csrfToken':csrf})
        if path=='/api/auth/login' and method=='POST':
            email=str(data.get('email','')).strip().lower(); password=str(data.get('password','')); role=data.get('role','citizen')
            if role not in ('citizen','admin'):return self.send_json(400,{'error':'Invalid account type.'})
            with connect() as d: user=d.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
            if not user or not verify_password(password,user['password_hash']) or user['role']!=role:return self.send_json(401,{'error':'Email, password, or account type is incorrect.'})
            old=self.cookie_token(); token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
            with connect() as d:
                if old:d.execute('DELETE FROM sessions WHERE token=?',(old,))
                d.execute('INSERT INTO sessions VALUES(?,?,?,?)',(token,user['id'],csrf,time.time()+28800))
            self.set_cookie=f'samadhan.sid={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'; self.session_token=token; self.session_csrf=csrf
            return self.send_json(200,{'user':public_user(user),'csrfToken':csrf})
        user=self.require_auth()
        if not user:return
        if method in ('POST','PATCH') and not self.csrf_ok(): return self.send_json(403,{'error':'Security token missing or expired. Refresh and try again.'})
        if path=='/api/auth/logout' and method=='POST':
            token=self.cookie_token()
            with connect() as d:d.execute('DELETE FROM sessions WHERE token=?',(token,))
            self.set_cookie='samadhan.sid=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'
            return self.send_json(204)
        if path=='/api/complaints' and method=='POST':
            if user['role']!='citizen':return self.send_json(403,{'error':'Only citizens can submit complaints.'})
            title=str(data.get('title','')).strip(); desc=str(data.get('description','')).strip(); cat=data.get('category'); locality=str(data.get('locality','')).strip(); landmark=str(data.get('landmark','')).strip()
            latitude=longitude=None; raw_lat=data.get('latitude'); raw_lon=data.get('longitude')
            if not (raw_lat is None and raw_lon is None):
                try:
                    latitude=float(raw_lat); longitude=float(raw_lon)
                    if not math.isfinite(latitude) or not math.isfinite(longitude) or not (-90<=latitude<=90) or not (-180<=longitude<=180): raise ValueError()
                except (TypeError,ValueError):
                    return self.send_json(400,{'error':'Location coordinates are invalid. Use the location button or leave both coordinates empty.'})
            if len(title)<5 or len(title)>120 or len(desc)<15 or len(desc)>4000 or cat not in CATEGORIES or len(locality)<2 or len(locality)>120 or len(landmark)>200:return self.send_json(400,{'error':'Check the complaint fields and try again.'})
            cid=str(uuid.uuid4()); ref='SS-GWL-'+secrets.token_hex(3).upper(); stamp=now()
            with connect() as d:
                d.execute('INSERT INTO complaints(id,reference_id,user_id,title,description,category,locality,landmark,status,department,created_at,updated_at,latitude,longitude) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,ref,user['id'],title,desc,cat,locality,landmark,'Submitted','Not confirmed',stamp,stamp,latitude,longitude))
                d.execute('INSERT INTO history(complaint_id,status,note,actor_id,actor_role,created_at) VALUES(?,?,?,?,?,?)',(cid,'Submitted','Complaint submitted by citizen.',user['id'],'citizen',stamp))
                d.execute('INSERT INTO audit(actor_id,actor_role,complaint_id,action,reason,metadata,created_at) VALUES(?,?,?,?,?,?,?)',(user['id'],'citizen',cid,'Complaint submitted','',json.dumps({'referenceId':ref}),stamp))
            with connect() as d: row=d.execute('SELECT c.*,u.name owner_name FROM complaints c JOIN users u ON u.id=c.user_id WHERE c.id=?',(cid,)).fetchone()
            return self.send_json(201,{'complaint':public_complaint(row)})
        match=re.fullmatch(r'/api/complaints/([^/]+)/reopen',path)
        if match and method=='POST':
            ident=unquote(match.group(1)); reason=str(data.get('reason','')).strip()
            if len(reason)<5 or len(reason)>1000:return self.send_json(400,{'error':'Please provide a reason of at least 5 characters.'})
            with connect() as d:
                row=d.execute('SELECT * FROM complaints WHERE reference_id=? OR id=?',(ident,ident)).fetchone()
                if not row or (user['role']!='admin' and row['user_id']!=user['id']):return self.send_json(404,{'error':'Complaint not found.'})
                stamp=now(); d.execute("UPDATE complaints SET status='Reopened',updated_at=? WHERE id=?",(stamp,row['id'])); d.execute('INSERT INTO history(complaint_id,status,note,actor_id,actor_role,created_at) VALUES(?,?,?,?,?,?)',(row['id'],'Reopened',reason,user['id'],user['role'],stamp)); d.execute('INSERT INTO audit(actor_id,actor_role,complaint_id,action,reason,metadata,created_at) VALUES(?,?,?,?,?,?,?)',(user['id'],user['role'],row['id'],'Complaint reopened',reason,'{}',stamp)); d.execute('INSERT INTO notifications(user_id,complaint_id,title,message,created_at) VALUES(?,?,?,?,?)',(row['user_id'],row['id'],'Complaint reopened',f'Your complaint {row["reference_id"]} was reopened.',stamp))
            return self.send_json(200,{'ok':True})
        match=re.fullmatch(r'/api/admin/complaints/([^/]+)',path)
        if match and method=='PATCH':
            if user['role']!='admin':return self.send_json(403,{'error':'Administrator access required.'})
            ident=unquote(match.group(1)); status=data.get('status'); dept=str(data.get('department','')).strip(); note=str(data.get('note','')).strip()
            if status not in STATUSES or len(note)<3 or len(note)>1000 or (dept and len(dept)>120):return self.send_json(400,{'error':'Check status, department, and update note.'})
            with connect() as d:
                row=d.execute('SELECT * FROM complaints WHERE reference_id=? OR id=?',(ident,ident)).fetchone()
                if not row:return self.send_json(404,{'error':'Complaint not found.'})
                stamp=now(); newdept=dept or row['department']; d.execute('UPDATE complaints SET status=?,department=?,updated_at=? WHERE id=?',(status,newdept,stamp,row['id'])); d.execute('INSERT INTO history(complaint_id,status,note,actor_id,actor_role,created_at) VALUES(?,?,?,?,?,?)',(row['id'],status,note,user['id'],'admin',stamp)); d.execute('INSERT INTO audit(actor_id,actor_role,complaint_id,action,reason,metadata,created_at) VALUES(?,?,?,?,?,?,?)',(user['id'],'admin',row['id'],'Complaint updated',note,json.dumps({'fromStatus':row['status'],'toStatus':status,'department':newdept}),stamp)); d.execute('INSERT INTO notifications(user_id,complaint_id,title,message,created_at) VALUES(?,?,?,?,?)',(row['user_id'],row['id'],'Complaint updated',f'Your complaint {row["reference_id"]} status is now {status}.',stamp)); updated=d.execute('SELECT c.*,u.name owner_name FROM complaints c JOIN users u ON u.id=c.user_id WHERE c.id=?',(row['id'],)).fetchone()
            return self.send_json(200,{'complaint':public_complaint(updated)})
        if path=='/api/notifications/' and method=='POST': return self.send_json(404,{'error':'Notification not found.'})
        match=re.fullmatch(r'/api/notifications/(\d+)/read',path)
        if match and method=='POST':
            with connect() as d: cur=d.execute('UPDATE notifications SET read_at=? WHERE id=? AND user_id=?',(now(),int(match.group(1)),user['id']))
            if not cur.rowcount:return self.send_json(404,{'error':'Notification not found.'})
            return self.send_json(204)
        if path=='/api/ai/suggest' and method=='POST':
            desc=str(data.get('description','')).strip(); title=str(data.get('title','')); language=data.get('language','en')
            if len(desc)<3 or len(desc)>4000:return self.send_json(400,{'error':'Description is required.'})
            return self.send_json(200,fallback_suggestion(title,desc,language if language in ('en','hi') else 'en'))
        return self.send_json(404,{'error':'API route not found.'})

def create_admin():
    import getpass
    email=input('Admin email: ').strip().lower(); name=input('Admin name: ').strip() or 'System Administrator'; password=getpass.getpass('Strong password (at least 14 characters): ')
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email) or len(password)<14: print('Use a valid email and password of at least 14 characters.'); return 2
    try:
        with connect() as d: d.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',(str(uuid.uuid4()),name,email,password_hash(password),'admin',now()))
        print('Administrator created. Admin accounts cannot be created through public registration.'); return 0
    except sqlite3.IntegrityError: print('That email already has an account.'); return 2

if __name__=='__main__':
    init_db()
    if '--create-admin' in sys.argv: raise SystemExit(create_admin())
    print(f'Samadhan Sathi running at http://{HOST}:{PORT} (SQLite: {DB_PATH})')
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()