"use client";

// Send a change to the board's server. On a public server a change needs the director's
// password: it is asked for once and kept for this browser tab only.

const KEY = "board-password";

function remembered(): string {
  try {
    return sessionStorage.getItem(KEY) || "";
  } catch {
    return "";
  }
}

export async function send(url: string, body: unknown): Promise<Response> {
  const post = (password: string) =>
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(password ? { "x-board-password": password } : {}) },
      body: JSON.stringify(body),
    });
  let response = await post(remembered());
  if (response.status === 401) {
    const typed = window.prompt("This server needs the director's password to change a film.");
    if (!typed) return response;
    response = await post(typed);
    if (response.status !== 401) {
      try {
        sessionStorage.setItem(KEY, typed);
      } catch {}
    }
  }
  return response;
}
