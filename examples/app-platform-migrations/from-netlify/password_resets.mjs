import { randomBytes, randomUUID, createHash } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import nodemailer from 'nodemailer';
import bcrypt from 'bcryptjs';
import { pool, transaction } from './database.mjs';
const hash=value=>createHash('sha256').update(value).digest('hex');
export const resetMessage='If the account exists, a password-reset link will be sent to its email address.';
export function validPassword(password){return typeof password==='string'&&password.length>=12&&Buffer.byteLength(password)<=72;}
export function validateResetDelivery(){
 const url=new URL(process.env.PUBLIC_APP_URL);
 if(url.protocol!=='https:'&&!(url.protocol==='http:'&&['127.0.0.1','localhost'].includes(url.hostname)))throw Error('PUBLIC_APP_URL must use HTTPS outside loopback rehearsal.');
 if(process.env.PASSWORD_RESET_EMAIL_DIR){
  if(process.env.APP_ENV!=='staging')throw Error('PASSWORD_RESET_EMAIL_DIR is a staging-only mail sink. Configure SMTP_URL for production.');
 }else {
  if(!process.env.SMTP_URL||!process.env.MAIL_FROM)throw Error('Set SMTP_URL and MAIL_FROM for password-reset delivery.');
  if(!['smtp:','smtps:'].includes(new URL(process.env.SMTP_URL).protocol))throw Error('SMTP_URL must use smtp or smtps.');
 }
}
export async function requestPasswordReset(email){
 const normalized=typeof email==='string'?email.trim().toLowerCase():'';
 if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(normalized)||normalized.length>320)return;
 // One request per email per minute limits inbox flooding, shared across web processes.
 await pool.query("INSERT INTO password_reset_requests(email) VALUES($1) ON CONFLICT(email) DO UPDATE SET requested_at=now(),pending=true,next_attempt_at=now() WHERE password_reset_requests.requested_at<now()-interval '1 minute'",[normalized]);
}
async function sendResetEmail(email,token){
 const link=new URL('/reset-password',process.env.PUBLIC_APP_URL);link.hash=new URLSearchParams({token}).toString();
 const message={from:process.env.MAIL_FROM||'portal@example.com',to:email,subject:'Set your portal password',text:`Use this one-time link to set your password:\n${link.href}\n\nThe link expires in 30 minutes. Ignore this message if you did not request it.\n`};
 if(process.env.PASSWORD_RESET_EMAIL_DIR){
  const directory=process.env.PASSWORD_RESET_EMAIL_DIR;await mkdir(directory,{recursive:true,mode:0o700});
  const transport=nodemailer.createTransport({streamTransport:true,buffer:true,newline:'unix'});
  const mail=await transport.sendMail(message);
  await writeFile(join(directory,randomUUID()+'.eml'),mail.message,{mode:0o600,flag:'wx'});
 }else{
  const smtp=new URL(process.env.SMTP_URL);
  const transport=nodemailer.createTransport({host:smtp.hostname,port:Number(smtp.port||(smtp.protocol==='smtps:'?465:587)),secure:smtp.protocol==='smtps:',requireTLS:true,auth:{user:decodeURIComponent(smtp.username),pass:decodeURIComponent(smtp.password)},connectionTimeout:10000,greetingTimeout:10000,socketTimeout:10000});
  try{await transport.sendMail(message);}finally{transport.close();}
 }
}
export async function deliverPasswordReset(){
 let email;
 try{return await transaction(async client=>{
  const request=(await client.query('SELECT email FROM password_reset_requests WHERE pending AND next_attempt_at<=now() ORDER BY requested_at FOR UPDATE SKIP LOCKED LIMIT 1')).rows[0];
  if(!request)return false;email=request.email;
  const user=(await client.query('SELECT id,email FROM users WHERE email=$1 FOR UPDATE',[email])).rows[0];
  if(user){
   const token=randomBytes(32).toString('base64url');
   await client.query('UPDATE password_reset_tokens SET used_at=now() WHERE owner_id=$1 AND used_at IS NULL',[user.id]);
   await client.query("INSERT INTO password_reset_tokens(token_hash,owner_id,expires_at) VALUES($1,$2,now()+interval '30 minutes')",[hash(token),user.id]);
   await sendResetEmail(user.email,token);
  }
  await client.query('UPDATE password_reset_requests SET pending=false WHERE email=$1',[email]);return true;
 });}catch(error){
  if(email)await pool.query("UPDATE password_reset_requests SET next_attempt_at=now()+interval '1 minute' WHERE email=$1",[email]);
  throw error;
 }
}
export async function completePasswordReset(token,password){
 if(typeof token!=='string'||! /^[A-Za-z0-9_-]{43}$/.test(token)||!validPassword(password))return false;
 return transaction(async client=>{
  const found=(await client.query('SELECT owner_id FROM password_reset_tokens WHERE token_hash=$1',[hash(token)])).rows[0];
  if(!found)return false;
  // Always lock the user before token rows, including issuance, to serialize reset races.
  await client.query('SELECT id FROM users WHERE id=$1 FOR UPDATE',[found.owner_id]);
  const row=(await client.query('SELECT * FROM password_reset_tokens WHERE token_hash=$1 AND used_at IS NULL AND expires_at>now() FOR UPDATE',[hash(token)])).rows[0];
  if(!row)return false;
  await client.query('UPDATE users SET password_hash=$2 WHERE id=$1',[row.owner_id,await bcrypt.hash(password,12)]);
  await client.query('UPDATE password_reset_tokens SET used_at=now() WHERE owner_id=$1 AND used_at IS NULL',[row.owner_id]);
  await client.query('UPDATE sessions SET revoked_at=now() WHERE owner_id=$1 AND revoked_at IS NULL',[row.owner_id]);
  return true;
 });
}
