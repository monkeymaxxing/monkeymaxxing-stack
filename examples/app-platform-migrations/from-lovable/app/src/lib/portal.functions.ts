import { createServerFn } from "@tanstack/react-start";
import { getRequest } from "@tanstack/react-start/server";
export const getAccountSummary = createServerFn({method:"GET"}).handler(async () => {
  const {account} = await import("../../backend.mjs");
  return account(getRequest());
});
export const runPendingReport = createServerFn({method:"POST"}).handler(async () => {
  const {currentUser,runJob} = await import("../../backend.mjs");
  const user = await currentUser(getRequest());
  return runJob(user.id);
});
