import { NextResponse } from "next/server";
import { refuse } from "@/lib/guard";
import { createFilm, isFilmName, PipelineError, repoState } from "@/lib/pipeline";

export const dynamic = "force-dynamic";

const fail = (status: number, error: string) => NextResponse.json({ error }, { status });

// Every film in brief, plus the repo's paperwork.
export async function GET() {
  try {
    return NextResponse.json(await repoState());
  } catch (err) {
    return fail(500, err instanceof Error ? err.message : String(err));
  }
}

// Start a new film. This is the only thing the board can change, so it is checked twice:
// here, and again by the pipeline before anything is written.
export async function POST(request: Request) {
  const refused = refuse(request);
  if (refused) return refused;

  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return fail(400, "The request was not valid JSON.");
  }

  const text = (value: unknown, limit: number) => (typeof value === "string" ? value.trim().slice(0, limit) : "");
  const title = text(body.title, 120);
  const languages = Array.isArray(body.languages)
    ? body.languages.filter((l): l is string => typeof l === "string" && /^[a-z]{2,3}$/.test(l))
    : [];

  if (title.length < 2) return fail(400, "Give the film a title.");
  if (title.startsWith("-")) return fail(400, "A title cannot start with a hyphen.");
  if (text(body.story, 8000).startsWith("-")) return fail(400, "A story cannot start with a hyphen.");
  if (!languages.length) return fail(400, "Give at least one language code, such as en or am.");

  try {
    const slug = await createFilm({
      title,
      audience: text(body.audience, 400),
      feeling: text(body.feeling, 400),
      languages,
      story: text(body.story, 8000),
    });
    if (!isFilmName(slug)) return fail(500, "The pipeline did not return a film name.");
    return NextResponse.json({ slug }, { status: 201 });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return fail(err instanceof PipelineError ? 400 : 500, message);
  }
}
