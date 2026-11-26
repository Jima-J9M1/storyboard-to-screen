import { NextResponse } from "next/server";
import { isFilmName, PipelineError, runStage } from "@/lib/pipeline";

export const dynamic = "force-dynamic";
export const maxDuration = 1800;

const fail = (status: number, error: string) => NextResponse.json({ error }, { status });

// Start one stage of a film from the board. Which stages may be started here, and what
// starting one does, is decided by the pipeline (core/run_stage.py), not by this page.
export async function POST(request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const origin = request.headers.get("origin");
  if (origin && new URL(origin).host !== request.headers.get("host")) {
    return fail(403, "This request did not come from the board.");
  }
  const { slug } = await params;
  if (!isFilmName(slug)) return fail(404, "Not a film name.");
  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return fail(400, "The request was not valid JSON.");
  }
  const stage = typeof body.stage === "string" ? body.stage : "";
  try {
    return NextResponse.json(await runStage(slug, stage));
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return fail(err instanceof PipelineError ? 400 : 500, message);
  }
}
