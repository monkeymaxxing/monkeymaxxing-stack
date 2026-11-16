#!/usr/bin/env python3
"""Run after migrations and seed, before workers. Uses only synthetic staging data."""
import http.cookiejar,json,os,re,urllib.request,urllib.error,uuid
A=os.environ.get('PORTAL_URL_A','').rstrip('/')
B=os.environ.get('PORTAL_URL_B','').rstrip('/')
PASSWORD=os.environ.get('FIXTURE_PASSWORD','')
class Browser:
 def __init__(self):
  self.cookies=http.cookiejar.CookieJar()
  self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
  self.token=''
 def request(self,method,path,data=None,base=None,expected=200,multipart=None):
  base=base or A
  headers={'Accept':'application/json'}
  if self.token:headers['X-CSRF-TOKEN']=self.token
  body=None
  if data is not None:body=json.dumps(data).encode();headers['Content-Type']='application/json'
  if multipart is not None:
   boundary='portal-'+uuid.uuid4().hex
   body=(f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="synthetic.bin"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()+multipart+f'\r\n--{boundary}--\r\n'.encode())
   headers['Content-Type']='multipart/form-data; boundary='+boundary
  request=urllib.request.Request(base+path,data=body,headers=headers,method=method)
  try:response=self.opener.open(request,timeout=20)
  except urllib.error.HTTPError as error:response=error
  result=response.read()
  assert response.status==expected,(method,path,response.status,expected,result[:200])
  if not path.startswith('/healthz'):assert 'no-store' in response.headers.get('Cache-Control','')
  return result
 def csrf(self):
  page=self.request('GET','/login')
  self.token=re.search(rb'name="_token" value="([^"]+)"',page).group(1).decode()
 def login(self,email):
  self.csrf();self.request('POST','/login',{'email':email,'password':PASSWORD})
  self.csrf() # Login rotates the session and CSRF token.
 def portal(self,base=A):return json.loads(self.request('GET','/portal',base=base))

def main():
 a=Browser();b=Browser();a.login('barbara@example.com');b.login('michael@example.com')
 initial=a.portal(B);foreign=b.portal();record=foreign['records'][0]['id'];document=foreign['documents'][0]['id'];report=foreign['reports'][0]['id']
 assert initial['user']['email']=='barbara@example.com'
 assert len(initial['records'])==len(initial['documents'])==len(initial['reports'])==1
 assert initial['records'][0]['description']=='First synthetic record'
 assert a.request('GET',f"/documents/{initial['documents'][0]['id']}")==b'Barbara synthetic document\n'
 for method,path,data in [('GET',f'/records/{record}',None),('PATCH',f'/records/{record}',{'title':'stolen'}),('DELETE',f'/records/{record}',None),('GET',f'/documents/{document}',None),('GET',f'/reports/{report}',None)]:a.request(method,path,data,expected=404)
 missing=Browser();missing.csrf();missing.request('POST','/records',{'title':'refused'},expected=401)
 # An authenticated state-changing request without a CSRF token must fail.
 old=a.token;a.token='';a.request('POST','/records',{'title':'refused'},expected=419);a.token=old
 row=json.loads(a.request('POST','/records',{'title':'HTTP record','description':'HTTP description'},expected=201))
 a.request('PATCH',f"/records/{row['id']}",{'title':'Updated HTTP record','description':'Updated description'})
 assert json.loads(a.request('GET',f"/records/{row['id']}",base=B))['title']=='Updated HTTP record'
 a.request('DELETE',f"/records/{row['id']}",expected=204)
 payload=b'Private upload\x00\xff\n'
 uploaded=json.loads(a.request('POST','/documents',multipart=payload,expected=201))
 assert a.request('GET',f"/documents/{uploaded['id']}",base=B)==payload
 b.request('GET',f"/documents/{uploaded['id']}",expected=404)
 # Preserve a separate client with the pre-logout cookie to test server-side revocation.
 import copy
 stale=Browser();[stale.cookies.set_cookie(copy.copy(cookie)) for cookie in a.cookies];stale.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(stale.cookies))
 a.request('POST','/logout',{})
 stale.request('GET','/portal',base=B,expected=401)
 registration=Browser();registration.csrf()
 registration.request('POST','/register',{'email':'registration-'+uuid.uuid4().hex+'@example.com','password':PASSWORD},expected=201)
 assert registration.portal(B)['records']==[]
 print('PASS HTTP: registration, login, shared sessions, logout revocation, ownership, CSRF, CRUD, private S3 byte equality')
if __name__=='__main__':main()
