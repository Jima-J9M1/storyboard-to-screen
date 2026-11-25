import Link from "next/link";
import { notFound } from "next/navigation";
import { Board } from "@/components/Board";
import { filmState, isFilmName } from "@/lib/pipeline";
import type { FilmState } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ stage?: string }>;
}) {
  const { slug } = await params;
  const { stage } = await searchParams;
  if (!isFilmName(slug)) notFound();

  let state: FilmState;
  try {
    state = await filmState(slug);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    if (message.startsWith("There is no film")) notFound();
    return <p className="fail">The board could not read this film: {message}</p>;
  }
  return (
    <>
      <div className="wrap">
        <Link className="back" href="/">
          All films
        </Link>
      </div>
      <Board initial={state} stage={stage} />
    </>
  );
}
