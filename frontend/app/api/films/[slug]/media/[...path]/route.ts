// Serves one generated file from a film's outputs folder, so the board can show it.
//
// The board never decides which files exist: the list comes from `python -m core.status`.
// This route only hands over the bytes of a file that list names. It is read-only, serves
// nothing outside films/<name>/outputs, and serves only pictures, sound and video.

import { createReadStream } from "node:fs";
import { realpath, stat } from "node:fs/promises";
import path from "node:path";
import { Readable } from "node:stream";
import { isFilmName } from "@/lib/pipeline";

export const dynamic = "force-dynamic";

const REPO = path.resolve(process.cwd(), "..");
const TYPES: Record<string, string> = {
  ".jpg": "image/jpeg",
  ".png": "image/png",
  ".wav": "audio/wav",
  ".m4a": "audio/mp4",
  ".mp4": "video/mp4",
};

const refuse = (status: number, message: string) => new Response(message, { status });

export async function GET(request: Request, { params }: { params: Promise<{ slug: string; path: string[] }> }) {
  const { slug, path: parts } = await params;
  if (!isFilmName(slug)) return refuse(404, "Not found");
  if (parts.some((part) => part.startsWith(".") || part.includes("\\") || part.includes("/"))) {
    return refuse(404, "Not found");
  }
  const type = TYPES[path.extname(parts[parts.length - 1] ?? "").toLowerCase()];
  if (!type) return refuse(404, "Not found");

  const outputs = path.join(REPO, "films", slug, "outputs");
  let file: string;
  let size: number;
  try {
    // Resolve links before checking, so a link inside outputs cannot point somewhere else.
    file = await realpath(path.join(outputs, ...parts));
    const root = await realpath(outputs);
    if (!file.startsWith(root + path.sep)) return refuse(404, "Not found");
    const info = await stat(file);
    if (!info.isFile()) return refuse(404, "Not found");
    size = info.size;
  } catch {
    return refuse(404, "Not found");
  }

  const headers: Record<string, string> = {
    "Content-Type": type,
    "Accept-Ranges": "bytes",
    // The address carries ?v=<time the file changed>, so a given address never changes content.
    "Cache-Control": "private, max-age=3600",
  };

  // Video and audio players ask for a file in pieces, so they can seek.
  const range = /^bytes=(\d*)-(\d*)$/.exec(request.headers.get("range") ?? "");
  if (range && (range[1] || range[2])) {
    const start = range[1] ? Number(range[1]) : Math.max(0, size - Number(range[2]));
    const end = range[1] && range[2] ? Math.min(Number(range[2]), size - 1) : size - 1;
    if (start > end || start >= size) {
      return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${size}` } });
    }
    const body = Readable.toWeb(createReadStream(file, { start, end })) as ReadableStream;
    return new Response(body, {
      status: 206,
      headers: { ...headers, "Content-Range": `bytes ${start}-${end}/${size}`, "Content-Length": String(end - start + 1) },
    });
  }

  const body = Readable.toWeb(createReadStream(file)) as ReadableStream;
  return new Response(body, { headers: { ...headers, "Content-Length": String(size) } });
}
