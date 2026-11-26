// The only place the frontend touches the pipeline.
//
// The board does not read the repo's files itself. It asks the pipeline's own status command,
// so "done", "blocked" and every validation message are decided in one place: the Python code.
// Commands are run without a shell, with each argument passed separately.

import { execFile } from "node:child_process";
import path from "node:path";

const REPO = path.resolve(process.cwd(), "..");
// On a server the Python that has the pipeline's packages is named in BOARD_PYTHON.
const PYTHON = process.env.BOARD_PYTHON || path.join(REPO, ".venv", "bin", "python");

export class PipelineError extends Error {}

function run(module: string, args: string[], timeoutMs = 20_000): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(
      PYTHON,
      ["-m", module, ...args],
      { cwd: REPO, timeout: timeoutMs, maxBuffer: 16 * 1024 * 1024 },
      (error, stdout, stderr) => {
        if (!error) return resolve(stdout);
        const missing = (error as NodeJS.ErrnoException).code === "ENOENT";
        // A command that explains its own failure prints it as JSON on standard output.
        const said = /\{"error": "((?:[^"\\]|\\.)*)"\}/.exec(stdout);
        if (said) return reject(new PipelineError(JSON.parse(`"${said[1]}"`)));
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

export type NewFilm = { title: string; audience: string; feeling: string; languages: string[]; story: string };

export async function createFilm(film: NewFilm): Promise<string> {
  const out = await run("core.films", [
    "new",
    "--title", film.title,
    "--audience", film.audience,
    "--feeling", film.feeling,
    "--languages", ...film.languages,
    "--story", film.story,
  ]);
  return out.trim();
}

export const DIRECTABLE = ["picture", "line", "motion", "score", "look", "world"] as const;
export type Directable = (typeof DIRECTABLE)[number];

export type Direction = { target: Directable; shot?: string; note: string; reroll?: boolean };

// Hand one of the director's notes to the Reviser agent, which changes that one thing in the
// storyboard and remakes it. This calls models and can take a minute or two.
export async function direct(slug: string, direction: Direction) {
  if (!isFilmName(slug)) throw new PipelineError(`"${slug}" is not a film name.`);
  const args = ["--film", slug, "--target", direction.target, "--json"];
  if (direction.shot) args.push("--shot", direction.shot);
  if (direction.reroll) args.push("--reroll");
  else args.push("--note", direction.note);
  const out = await run("agents.reviser", args, 8 * 60_000);
  const marker = out.lastIndexOf("@@RESULT@@");
  if (marker < 0) throw new PipelineError("The Reviser finished without a result.");
  return JSON.parse(out.slice(marker + "@@RESULT@@".length));
}

// Start one stage of a film. The pipeline decides what running it means; the board only names it.
export async function runStage(slug: string, stage: string): Promise<{ ok: boolean; lines: string[] }> {
  if (!isFilmName(slug)) throw new PipelineError(`"${slug}" is not a film name.`);
  if (!/^[a-z_]+$/.test(stage)) throw new PipelineError("That is not a stage.");
  return new Promise((resolve, reject) => {
    execFile(
      PYTHON,
      ["-m", "core.run_stage", "--film", slug, "--stage", stage],
      { cwd: REPO, timeout: 30 * 60_000, maxBuffer: 16 * 1024 * 1024 },
      (error, stdout, stderr) => {
        const marker = stdout.lastIndexOf("@@RESULT@@");
        if (marker >= 0) return resolve(JSON.parse(stdout.slice(marker + "@@RESULT@@".length)));
        reject(new PipelineError(stderr.trim().slice(-400) || error?.message || "The stage ended without a result."));
      },
    );
  });
}
