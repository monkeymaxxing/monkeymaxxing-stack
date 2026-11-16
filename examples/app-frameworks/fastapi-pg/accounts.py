import hashlib
import re
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException

hasher=PasswordHasher()
def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()
def credentials(email,password):
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email)>254:
        raise HTTPException(400,'Enter a valid email address')
    if not 12<=len(password.encode())<=72:
        raise HTTPException(400,'Password must be 12 to 72 bytes')
    return email.lower(),password

def matches(password, encoded):
    try:return hasher.verify(encoded,password)
    except VerificationError:return False

def create_session(connection,account_id,response):
    token=secrets.token_hex(32)
    connection.execute("INSERT INTO sessions VALUES (%s,%s,now()+interval '7 days')",(digest(token),account_id))
    response.set_cookie('portal_session',token,max_age=604800,secure=True,httponly=True,samesite='lax',path='/')

def account(connection,request):
    token=request.cookies.get('portal_session','')
    row=connection.execute('SELECT a.id,a.email FROM accounts a JOIN sessions s ON s.account_id=a.id WHERE s.token_hash=%s AND s.expires_at>now()',(digest(token),)).fetchone()
    if row is None:raise HTTPException(401,'Log in first')
    return row['id']
