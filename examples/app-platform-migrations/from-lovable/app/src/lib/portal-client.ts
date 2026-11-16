export async function request(path: string, method = "GET", body?: unknown, headers: Record<string,string> = {}) {
  const response = await fetch(`/api/${path}`, {
    method, credentials: "same-origin",
    headers: body instanceof Blob ? headers : { "Content-Type": "application/json", ...headers },
    body: body === undefined ? undefined : body instanceof Blob ? body : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error ?? "Request failed");
  return data;
}
async function authRequest(path: string, body?: unknown) {
  try {
    const result = await request(path, "POST", body);
    return { data: { user: result.user, session: result.user ? {} : null }, error: null };
  } catch (error) {
    return { data: { user: null, session: null }, error: error as Error };
  }
}
export const portal = {
  auth: {
    signInWithPassword: (body: {email:string; password:string}) => authRequest("login", body),
    signUp: (body: {email:string; password:string; options?: unknown}) => authRequest("register", body),
    signOut: () => request("logout", "POST", {}),
    getUser: async () => {
      try { return {data:{user:(await request("account")).user},error:null}; }
      catch (error) { return {data:{user:null},error:error as Error}; }
    },
  },
};
