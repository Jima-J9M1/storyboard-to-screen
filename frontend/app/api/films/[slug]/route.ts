import { NextResponse } from "next/server";
import { filmState, isFilmName } from "@/lib/pipeline";

export const dynamic = "force-dynamic";

// One film in full.
export async function GET(_request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!isFilmName(slug)) return NextResponse.json({ error: "Not a film name." }, { status: 404 });
  try {
    return NextResponse.json(await filmState(slug));
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: message }, { status: message.startsWith("There is no film") ? 404 : 500 });
  }
}
