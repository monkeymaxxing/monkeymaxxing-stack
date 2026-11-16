<?php
namespace App\Http;
use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Validation\Rules\Password;
final class AccountController
{
 public function register(Request $request)
 {
     $data=$request->validate(['email'=>'required|email|max:254|unique:users','password'=>['required','string','min:12','max:72']]);
     $user=User::create($data); Auth::login($user); $request->session()->regenerate();
     return $request->expectsJson()?response()->json($user,201):redirect('/');
 }
 public function login(Request $request)
 {
     $data=$request->validate(['email'=>'required|email','password'=>'required|string|max:72']);
     if (!Auth::attempt($data)) return response()->json(['message'=>'Email or password is incorrect.'],422);
     $request->session()->regenerate();
     return $request->expectsJson()?response()->json(Auth::user()):redirect('/');
 }
 public function logout(Request $request)
 {
     Auth::logout(); $request->session()->invalidate(); $request->session()->regenerateToken();
     return $request->expectsJson()?response()->json(['message'=>'Signed out.']):redirect('/login');
 }
}
