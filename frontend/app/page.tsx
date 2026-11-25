import { Home } from "@/components/Home";
import { repoState } from "@/lib/pipeline";
import type { RepoState } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function Page() {
  let state: RepoState;
  try {
    state = await repoState();
  } catch (err) {
    return <p className="fail">The board could not read the repo: {err instanceof Error ? err.message : String(err)}</p>;
  }
  return <Home initial={state} />;
}
