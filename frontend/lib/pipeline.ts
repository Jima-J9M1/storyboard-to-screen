// The only place the frontend touches the pipeline.
//
// The board does not read the repo's files itself. It asks the pipeline's own status command,
// so "done", "blocked" and every validation message are decided in one place: the Python code.
// Commands are run without a shell, with each argument passed separately.

import { execFile } from "node:child_process";
import path from "node:path";

const REPO = path.resolve(process.cwd(), "..");
const PYTHON = path.join(REPO, ".venv", "bin", "python");

export class PipelineError extends Error {}

function run(module: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(
      PYTHON,
      ["-m", module, ...args],
      { cwd: REPO, timeout: 20_000, maxBuffer: 16 * 1024 * 1024 },
      (error, stdout, stderr) => {
        if (!error) return resolve(stdout);
        const missing = (error as NodeJS.ErrnoException).code === "ENOENT";
        reject(
          new PipelineError(
            missing
              ? "The Python environment is missing. Run make setup in the repo."
              : stderr.trim() || error.message,
          ),
        );
      },
    );
  });
}

// A film's folder name. Checked here as well as in Python, before it reaches a command line.
export const isFilmName = (name: string) => /^[a-z0-9]+(-[a-z0-9]+)*$/.test(name);

export async function repoState() {
  return JSON.parse(await run("core.status", []));
}

export async function filmState(slug: string) {
  if (!isFilmName(slug)) throw new PipelineError(`"${slug}" is not a film name.`);
  return JSON.parse(await run("core.status", ["--film", slug]));
}

export type NewFilm = { title: string; audience: string; feeling: string; languages: string[] };

export async function createFilm(film: NewFilm): Promise<string> {
  const out = await run("core.films", [
    "new",
    "--title", film.title,
    "--audience", film.audience,
    "--feeling", film.feeling,
    "--languages", ...film.languages,
  ]);
  return out.trim();
}
