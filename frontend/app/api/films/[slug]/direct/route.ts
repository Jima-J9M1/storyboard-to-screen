import { NextResponse } from "next/server";
import { refuse } from "@/lib/guard";
import { direct, DIRECTABLE, isFilmName, PipelineError, type Directable } from "@/lib/pipeline";

export const dynamic = "force-dynamic";
export const maxDuration = 600;

const fail = (status: number, error: string) => NextResponse.json({ error }, { status });

// The director's note on one thing a stage made. The Reviser agent rewrites that one field of
// the storyboard and remakes it; the note, the text before and the text after are recorded
// in the film's direction log. Besides starting a film, this is the only thing the board changes.
export async function POST(request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const refused = refuse(request);
  if (refused) return refused;
  const { slug } = await params;
  if (!isFilmName(slug)) return fail(404, "Not a film name.");

  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return fail(400, "The request was not valid JSON.");
  }
  const target = String(body.target ?? "") as Directable;
  if (!DIRECTABLE.includes(target)) return fail(400, "That cannot be directed.");
  const shot = typeof body.shot === "string" && /^s[0-9]{2}$/.test(body.shot) ? body.shot : undefined;
  const reroll = body.reroll === true;
  const note = typeof body.note === "string" ? body.note.trim().slice(0, 600) : "";
  if (!reroll && note.length < 5) return fail(400, "Write a note saying what is wrong and how to fix it.");
  if (note.startsWith("-")) return fail(400, "A note cannot start with a hyphen.");

  try {
    return NextResponse.json(await direct(slug, { target, shot, note, reroll }));
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return fail(err instanceof PipelineError ? 400 : 500, message.slice(-600));
  }
}
