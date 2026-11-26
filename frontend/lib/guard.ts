// Who may change the repo through the board.
//
// On the director's own machine the board listens on 127.0.0.1 and every change is allowed.
// On a server (BOARD_PUBLIC=1) anyone can open the board, and a change can spend the
// director's API keys, so every change needs the password in BOARD_PASSWORD. With no
// password set, a public board is read-only.

import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";

const fail = (status: number, error: string) => NextResponse.json({ error }, { status });

function same(a: string, b: string) {
  const x = Buffer.from(a);
  const y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}

// Returns a refusal, or null when the request may go ahead.
export function refuse(request: Request): NextResponse | null {
  // Refuse requests that another website made the browser send.
  const origin = request.headers.get("origin");
  const hosts = [request.headers.get("host"), request.headers.get("x-forwarded-host")];
  if (origin && !hosts.includes(new URL(origin).host)) {
    return fail(403, "This request did not come from the board.");
  }
  if (process.env.BOARD_PUBLIC !== "1") return null;
  const password = process.env.BOARD_PASSWORD || "";
  if (!password) return fail(403, "This is a public copy of the board. It shows the films but cannot change them.");
  if (!same(request.headers.get("x-board-password") || "", password)) {
    return fail(401, "Changing a film on this server needs the director's password.");
  }
  return null;
}
