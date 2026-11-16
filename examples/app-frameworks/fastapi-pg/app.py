from contextlib import asynccontextmanager
from pathlib import Path
import os
import re
import psycopg
from psycopg_pool import PoolTimeout
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, Request, Response, HTTPException, Form, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import accounts
import database
import storage

ROOT=Path(__file__).resolve().parent
@asynccontextmanager
async def lifespan(app):
    database.open_pool()
    yield
    database.close_pool()

app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
app.mount('/assets',StaticFiles(directory=ROOT/'assets'),name='assets')

@app.middleware('http')
async def request_policy(request,call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        if request.headers.get('origin')!=os.environ['APP_ORIGIN']:
            return JSONResponse({'error':'Origin refused'},403,headers={'Cache-Control':'no-store'})
        # Bound the entire request, including chunked multipart bodies, before parsing.
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>9*1024*1024:
                return JSONResponse({'error':'Request is larger than 9 MiB'},413,headers={'Cache-Control':'no-store'})
        request._body=bytes(body)
    response=await call_next(request)
    # Only successful public files with content-hashed names are immutable.
    fingerprinted_asset = re.fullmatch(r'/assets/[^/]+\.[a-f0-9]{12}\.(?:css|js)', request.url.path)
    response.headers['Cache-Control'] = (
        'public, max-age=31536000, immutable'
        if request.method in ('GET', 'HEAD') and response.status_code in (200, 304) and fingerprinted_asset
        else 'no-store'
    )
    response.headers['X-Content-Type-Options']='nosniff'
    return response

@app.exception_handler(HTTPException)
async def http_error(request,error):
    return JSONResponse({'error':error.detail},error.status_code)

async def database_error(request,error):
    return JSONResponse({'error':'Database unavailable; check saved data before resubmitting'},503)
for error_type in (psycopg.OperationalError,psycopg.InterfaceError,psycopg.errors.QueryCanceled,PoolTimeout):
    app.add_exception_handler(error_type,database_error)
async def storage_error(request,error):
    return JSONResponse({'error':'Document storage unavailable'},503)
for error_type in (BotoCoreError,ClientError):app.add_exception_handler(error_type,storage_error)

@app.get('/',response_class=HTMLResponse)
def home():return (ROOT/'home.html').read_text()

@app.get('/healthz')
def health():
    with database.transaction() as c:c.execute('SELECT 1')
    return {'status':'ok'}

@app.post('/register')
def register(response:Response,email:str=Form(),password:str=Form()):
    email,password=accounts.credentials(email,password)
    encoded=accounts.hasher.hash(password)
    try:
        with database.transaction() as c:
            row=c.execute('INSERT INTO accounts(email,password_hash) VALUES(%s,%s) RETURNING id',(email,encoded)).fetchone()
            accounts.create_session(c,row['id'],response)
    except psycopg.errors.UniqueViolation:raise HTTPException(409,'Email is already registered')
    return {'status':'registered'}

@app.post('/login')
def login(response:Response,email:str=Form(),password:str=Form()):
    email,password=accounts.credentials(email,password)
    with database.transaction() as c:
        row=c.execute('SELECT id,password_hash FROM accounts WHERE email=%s',(email,)).fetchone()
        verified=accounts.matches(password,row['password_hash'] if row else DUMMY_HASH)
        if row is None or not verified:
            raise HTTPException(401,'Email or password refused')
        accounts.create_session(c,row['id'],response)
    return {'status':'logged in'}
DUMMY_HASH=accounts.hasher.hash('unusable random password')

@app.post('/logout')
def logout(request:Request,response:Response):
    with database.transaction() as c:
        c.execute('DELETE FROM sessions WHERE token_hash=%s',(accounts.digest(request.cookies.get('portal_session','')),))
    response.delete_cookie('portal_session',secure=True,httponly=True,samesite='lax',path='/')
    return {'status':'logged out'}

@app.get('/records')
def records(request:Request):
    with database.transaction() as c:
        owner=accounts.account(c,request)
        return c.execute('SELECT id,title,description FROM records WHERE account_id=%s ORDER BY id',(owner,)).fetchall()

def record_fields(title,description):
    if not 1<=len(title)<=200 or len(description)>10000:
        raise HTTPException(400,'Title must be 1 to 200 characters; description at most 10000')

@app.post('/records',status_code=201)
def create_record(request:Request,title:str=Form(),description:str=Form('')):
    record_fields(title,description)
    with database.transaction() as c:
        owner=accounts.account(c,request)
        return c.execute('INSERT INTO records(account_id,title,description) VALUES(%s,%s,%s) RETURNING id',(owner,title,description)).fetchone()

@app.post('/records/{identifier}/update')
def update_record(identifier:int,request:Request,title:str=Form(),description:str=Form('')):
    record_fields(title,description)
    with database.transaction() as c:
        owner=accounts.account(c,request)
        row=c.execute('UPDATE records SET title=%s,description=%s WHERE id=%s AND account_id=%s RETURNING id',(title,description,identifier,owner)).fetchone()
        if row is None:raise HTTPException(404,'Record not found')
        return row

@app.post('/records/{identifier}/delete')
def delete_record(identifier:int,request:Request):
    with database.transaction() as c:
        owner=accounts.account(c,request)
        row=c.execute('DELETE FROM records WHERE id=%s AND account_id=%s RETURNING id',(identifier,owner)).fetchone()
        if row is None:raise HTTPException(404,'Record not found')
        return row

@app.get('/documents')
def documents(request:Request):
    with database.transaction() as c:
        owner=accounts.account(c,request)
        return c.execute('SELECT id,filename,sha256,byte_count FROM documents WHERE account_id=%s ORDER BY id',(owner,)).fetchall()

@app.post('/documents',status_code=201)
def upload(request:Request,file:UploadFile=File()):
    data=file.file.read(8*1024*1024+1)
    if len(data)>8*1024*1024:raise HTTPException(413,'Document is larger than 8 MiB')
    filename=Path(file.filename or 'document').name
    if len(filename)>255:raise HTTPException(400,'Filename is longer than 255 characters')
    with database.transaction() as c:
        owner=accounts.account(c,request)
        values=storage.put_document(owner,filename,data)
        return c.execute('INSERT INTO documents(account_id,object_key,filename,sha256,byte_count) VALUES(%s,%s,%s,%s,%s) RETURNING id',values).fetchone()

@app.get('/documents/{identifier}')
def download(identifier:int,request:Request):
    with database.transaction() as c:
        owner=accounts.account(c,request)
        row=c.execute('SELECT * FROM documents WHERE id=%s AND account_id=%s',(identifier,owner)).fetchone()
        if row is None:raise HTTPException(404,'Document not found')
    return Response(storage.get_document(row),media_type='application/octet-stream',headers={'Content-Disposition':'attachment'})

@app.post('/reports',status_code=201)
def queue_report(request:Request):
    with database.transaction() as c:
        owner=accounts.account(c,request)
        return c.execute('INSERT INTO report_jobs(account_id) VALUES(%s) RETURNING id',(owner,)).fetchone()

@app.get('/reports')
def reports(request:Request):
    with database.transaction() as c:
        owner=accounts.account(c,request)
        return c.execute('SELECT id,output FROM report_jobs WHERE account_id=%s ORDER BY id',(owner,)).fetchall()

@app.get('/reports/{identifier}')
def report(identifier:int,request:Request):
    with database.transaction() as c:
        owner=accounts.account(c,request)
        row=c.execute('SELECT id,output FROM report_jobs WHERE id=%s AND account_id=%s',(identifier,owner)).fetchone()
        if row is None:raise HTTPException(404,'Report not found')
        return row
