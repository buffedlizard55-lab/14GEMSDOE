#!/usr/bin/env node
/* Headless check of the site's in-browser "Build submission.tif" flow.
 *
 * WHY THIS EXISTS
 * ---------------
 * The builder in docs/js/site.js runs only in a browser, so a JavaScript error
 * inside it is invisible to the repository's Python test suite.  On 2026-09-29
 * the published site could not produce a file at all: docs/js/site.js assigned
 * `tifBytesNan` without declaring it (only `var tifBytes = null;` was
 * declared).  The script is a strict-mode IIFE, so the assignment threw
 *
 *     ReferenceError: tifBytesNan is not defined
 *
 * inside the promise chain; `.catch()` swallowed it, the download buttons were
 * never enabled, and the visitor saw "FAILED: tifBytesNan is not defined" with
 * no file to download.  This harness runs the real scripts under a minimal DOM
 * shim so that class of bug fails here instead of on the published site.
 *
 * WHAT IT CHECKS (exit code is non-zero if any step fails)
 *   1. payload.js, tif_writer.js and site.js load in a strict-mode context.
 *   2. site.js reaches READY and enables all three download buttons.
 *   3. The payload decodes (base64 -> zlib -> gems-payload-v1 JSON).
 *   4. The decoded float32 field hashes to the payload's pinned pixels_sha256.
 *   5. Clicking "Build submission.tif" hands over a little-endian TIFF whose
 *      tags, grid, GeoKeyDirectory and pixel payload re-read correctly.
 *   6. Every pixel of the primary (default) build is finite and inside [0, 1].
 *   7. The TIFF written by the JS writer is byte-identical to the one written
 *      by the Python writer used by scripts/build_submission.py, so the two
 *      routes to a submission cannot drift apart.
 *
 * Usage:
 *   node scripts/check_site_build.mjs                  # human-readable report
 *   node scripts/check_site_build.mjs --json           # machine-readable
 *   node scripts/check_site_build.mjs --out FILE.tif   # save the built file
 */

import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { inflateSync } from "node:zlib";
import { fileURLToPath } from "node:url";
import path from "node:path";
import vm from "node:vm";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const JS = path.join(ROOT, "docs", "js");
const argv = process.argv.slice(2);
const argVal = (flag) => { const i = argv.indexOf(flag); return i >= 0 ? argv[i + 1] : null; };

const steps = [];
const step = (name, ok, detail) => {
  steps.push({ name, ok: !!ok, detail: detail === undefined ? "" : String(detail) });
  return !!ok;
};
const sha256Hex = (bytes) => createHash("sha256").update(Buffer.from(bytes)).digest("hex");

// ---------------------------------------------------------------- DOM shim --
// A Blob that keeps the bytes (so the harness can inspect what would be
// downloaded) and still exposes .stream(), which tif_writer.js needs in order
// to pipe the payload through DecompressionStream.
class ShimBlob {
  constructor(parts, opts) {
    this.parts = (parts || []).map((p) => {
      if (p instanceof Uint8Array) return p;
      if (p instanceof ArrayBuffer) return new Uint8Array(p);
      return new Uint8Array(Buffer.from(String(p)));
    });
    this.type = (opts && opts.type) || "";
  }
  stream() {
    const parts = this.parts.slice();
    return new ReadableStream({
      start(c) { for (const p of parts) c.enqueue(p); c.close(); },
    });
  }
}

const ELEMENT_IDS = ["buildStatus", "buildState", "btnTif", "btnZip", "btnCompat",
                     "btnName", "noteText", "demoBanner", "demoPixels",
                     "dlDirectName", "dlDirectSha", "payloadStats"];

function makeShim(opts) {
  opts = opts || {};
  const nodes = new Map();
  const downloads = [];
  const node = (id) => ({
    id, textContent: "", className: "", style: {}, disabled: true, _listeners: {},
    addEventListener(ev, fn) { (this._listeners[ev] = this._listeners[ev] || []).push(fn); },
    click() { (this._listeners.click || []).forEach((f) => f()); },
  });
  for (const id of ELEMENT_IDS) nodes.set(id, node(id));
  const sandbox = {
    console,
    document: {
      readyState: "complete",
      getElementById: (id) => nodes.get(id) || null,
      querySelectorAll: () => [],
      createElement: (tag) => node("created-" + tag),
      body: { appendChild() {}, removeChild() {} },
      addEventListener() {},
    },
    atob: (b64) => Buffer.from(b64, "base64").toString("binary"),
    TextEncoder,
    CompressionStream,
    DecompressionStream,
    Response,
    ReadableStream,
    Blob: ShimBlob,
    URL: {
      createObjectURL: (b) => { downloads.push(b); return "blob:mock/" + downloads.length; },
      revokeObjectURL() {},
    },
    setTimeout: (fn) => { fn(); return 0; },
    // WebCrypto across the vm realm boundary: copy into a main-realm Buffer.
    crypto: {
      subtle: {
        digest(alg, data) {
          const u8 = data instanceof Uint8Array ? data : new Uint8Array(data);
          return globalThis.crypto.subtle.digest(alg, Buffer.from(u8));
        },
      },
    },
    Promise,
    DataView, Uint8Array, Uint16Array, Uint32Array, Float32Array, Int32Array,
    ArrayBuffer, Math, JSON, Date, String, Number, isNaN, Infinity, NaN,
  };
  if (opts.allowCompression === false) {
    // Simulate an older/embedded browser: no CompressionStream, so site.js must
    // fall back to the uncompressed writer and still deliver a usable file.
    delete sandbox.CompressionStream;
  }
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  return { sandbox, nodes, downloads };
}

function runSite(opts) {
  const shim = makeShim(opts);
  const ctx = vm.createContext(shim.sandbox);
  for (const f of ["payload.js", "tif_writer.js", "site.js"]) {
    try {
      vm.runInContext(readFileSync(path.join(JS, f), "utf8"), ctx, { filename: "docs/js/" + f });
    } catch (e) {
      return { shim, error: new Error(f + ": " + e.message) };
    }
  }
  return { shim, error: null };
}

// site.js starts decodeAll() during wire() and resolves on later macrotasks.
async function settle(nodes, maxMs = 30000) {
  const t0 = Date.now();
  while (Date.now() - t0 < maxMs) {
    const s = nodes.get("buildState").textContent;
    if (s && s !== "decoding…") return s;
    await new Promise((r) => setTimeout(r, 5));
  }
  return nodes.get("buildState").textContent;
}

// ---------------------------------------------------------- TIFF inspector --
function inspectTiff(bytes) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const out = { ok: true, problems: [], tags: {} };
  if (dv.byteLength < 8) { out.ok = false; out.problems.push("shorter than a TIFF header"); return out; }
  if (dv.getUint16(0, true) !== 0x4949) { out.ok = false; out.problems.push("not little-endian ('II')"); }
  if (dv.getUint16(2, true) !== 42) { out.ok = false; out.problems.push("magic != 42"); }
  const ifdOff = dv.getUint32(4, true);
  const nTags = dv.getUint16(ifdOff, true);
  const TYPE_SIZE = { 1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 11: 4, 12: 8 };
  for (let i = 0; i < nTags; i++) {
    const e = ifdOff + 2 + i * 12;
    const tag = dv.getUint16(e, true);
    const type = dv.getUint16(e + 2, true);
    const count = dv.getUint32(e + 4, true);
    out.tags[tag] = { type, count, entry: e };
  }
  for (const t of [256, 257, 258, 259, 262, 273, 277, 278, 279, 339, 33550, 33922, 34735]) {
    if (!(t in out.tags)) { out.ok = false; out.problems.push("missing TIFF tag " + t); }
  }
  if (!out.ok) return out;
  const inlineOrOffset = (tag) => {
    const { type, count, entry } = out.tags[tag];
    return TYPE_SIZE[type] * count <= 4 ? entry + 8 : dv.getUint32(entry + 8, true);
  };
  out.cols = dv.getUint32(inlineOrOffset(256), true);
  out.rows = dv.getUint32(inlineOrOffset(257), true);
  out.bitsPerSample = dv.getUint16(inlineOrOffset(258), true);
  out.sampleFormat = dv.getUint16(inlineOrOffset(339), true);
  out.pixOff = dv.getUint32(inlineOrOffset(273), true);
  out.byteCount = dv.getUint32(inlineOrOffset(279), true);
  out.compression = dv.getUint16(inlineOrOffset(259), true);
  const gk = inlineOrOffset(34735);
  const nKeys = dv.getUint16(gk + 6, true);
  out.geoKeys = {};
  for (let k = 0; k < nKeys; k++) {
    const o = gk + 8 + k * 8;
    out.geoKeys[dv.getUint16(o, true)] = dv.getUint16(o + 6, true);
  }
  out.epsg = out.geoKeys[3072];
  const ps = inlineOrOffset(33550);
  out.pixelScale = [dv.getFloat64(ps, true), dv.getFloat64(ps + 8, true), dv.getFloat64(ps + 16, true)];
  const tp = inlineOrOffset(33922);
  out.tiepoint = [0, 1, 2].map((i) => dv.getFloat64(tp + i * 8, true))
    .concat([3, 4, 5].map((i) => dv.getFloat64(tp + i * 8, true)));
  out.georef = [out.pixelScale[0], 0, out.tiepoint[3], 0, -out.pixelScale[1], out.tiepoint[4]];
  out.nodata = 42113 in out.tags ? "GDAL_NODATA tag present" : null;
  if (out.bitsPerSample !== 32) { out.ok = false; out.problems.push("BitsPerSample " + out.bitsPerSample + " != 32"); }
  if (out.sampleFormat !== 3) { out.ok = false; out.problems.push("SampleFormat " + out.sampleFormat + " != 3 (float)"); }
  if (![1, 8].includes(out.compression)) {
    out.ok = false;
    out.problems.push("unsupported Compression " + out.compression);
  }
  if (out.pixOff + out.byteCount > bytes.byteLength) {
    out.ok = false;
    out.problems.push("pixel block runs past end of file");
  }
  if (!out.ok) return out;

  let block;
  if (out.compression === 1) {
    if (out.byteCount !== out.rows * out.cols * 4) {
      out.ok = false;
      out.problems.push("uncompressed StripByteCounts " + out.byteCount + " != rows*cols*4 (" + out.rows * out.cols * 4 + ")");
      return out;
    }
    block = bytes.subarray(out.pixOff, out.pixOff + out.byteCount);
  } else {
    try {
      block = inflateSync(bytes.subarray(out.pixOff, out.pixOff + out.byteCount));
    } catch (e) {
      out.ok = false;
      out.problems.push("deflate block does not inflate: " + e.message);
      return out;
    }
    if (block.length !== out.rows * out.cols * 4) {
      out.ok = false;
      out.problems.push("inflated pixel block is " + block.length + " B, expected " + out.rows * out.cols * 4);
      return out;
    }
  }
  out.pixels = new Float32Array(out.rows * out.cols);
  const bdv = new DataView(block.buffer, block.byteOffset, block.byteLength);
  for (let p = 0; p < out.pixels.length; p++) out.pixels[p] = bdv.getFloat32(p * 4, true);
  return out;
}

// ------------------------------------------------------------------- main ---
async function checkMode(label, allowCompression, outPath) {
  const tag = "[" + label + "] ";
  const { shim, error } = runSite({ allowCompression });
  step(tag + "scripts load and run under strict mode", !error,
    error ? error.message : "no exception");
  if (error) return null;

  const { nodes, downloads } = shim;
  const state = await settle(nodes);
  const tail = nodes.get("buildStatus").textContent.trim().split("\n").slice(-3).join(" | ");
  if (!step(tag + "reaches READY and enables all three buttons",
        state === "READY" && ["btnTif", "btnZip", "btnCompat"].every((b) => !nodes.get(b).disabled),
        "buildState = " + JSON.stringify(state) +
        "  buttons = " + (["btnTif", "btnZip", "btnCompat"].filter((b) => !nodes.get(b).disabled).join(",") || "none") +
        "  log tail = " + JSON.stringify(tail))) {
    return null;
  }

  const b64 = shim.sandbox.GEMS_PAYLOAD_B64;
  const payload = JSON.parse(inflateSync(Buffer.from(b64, "base64")).toString("utf8"));
  const writer = shim.sandbox.GemsTiff;
  const field = writer.decodeField(payload);
  const fieldSha = await writer.fieldSha256(field);
  step(tag + "decoded field sha256 == payload.pixels_sha256", fieldSha === payload.pixels_sha256,
    fieldSha.slice(0, 16) + "… vs " + String(payload.pixels_sha256).slice(0, 16) + "…");

  nodes.get("btnTif").click();
  if (!step(tag + "pressing 'Build submission.tif' produces a download", downloads.length >= 1,
            downloads.length + " object URL(s) created")) return null;
  const tifBytes = downloads[0].parts[0];

  const t = inspectTiff(tifBytes);
  step(tag + "built file is a structurally valid float32 GeoTIFF", t.ok,
    t.ok ? `${t.cols}x${t.rows} px, EPSG:${t.epsg}, Compression=${t.compression}, ` +
           `${tifBytes.length.toLocaleString("en-US")} B`
         : t.problems.join("; "));
  if (!t.ok || !t.pixels) return null;

  step(tag + "grid, EPSG and geotransform match the payload",
    t.cols === payload.cols && t.rows === payload.rows && t.epsg === payload.epsg &&
    t.georef.every((v, i) => Math.abs(v - payload.transform[i]) < 1e-9),
    `${t.cols}x${t.rows} EPSG:${t.epsg} [${t.georef.join(", ")}]`);

  let nNan = 0, nOut = 0, vmin = Infinity, vmax = -Infinity, nPos = 0;
  for (let i = 0; i < t.pixels.length; i++) {
    const v = t.pixels[i];
    if (Number.isNaN(v)) { nNan++; continue; }
    if (v < 0 || v > 1) nOut++;
    if (v < vmin) vmin = v;
    if (v > vmax) vmax = v;
    if (v > 0) nPos++;
  }
  step(tag + "no NaN anywhere and every value inside [0, 1]", nNan === 0 && nOut === 0,
    nNan + " NaN, " + nOut + " out of range; min=" + vmin + " max=" + vmax);
  step(tag + "pixels are bit-identical to the shipped payload",
    t.pixels.length === field.length &&
    new Uint8Array(t.pixels.buffer, t.pixels.byteOffset, t.pixels.byteLength)
      .every((b, i) => b === new Uint8Array(field.buffer, field.byteOffset, field.byteLength)[i]),
    t.pixels.length.toLocaleString("en-US") + " px compared");
  step(tag + "no GDAL_NODATA tag on the primary (finite) build", t.nodata === null,
    t.nodata === null ? "absent, as intended" : String(t.nodata));

  const fileSha = sha256Hex(tifBytes);
  if (outPath) {
    writeFileSync(outPath, Buffer.from(tifBytes));
    console.log("[gems] wrote " + outPath + " (" + tifBytes.length.toLocaleString("en-US") +
                " B, sha256 " + fileSha.slice(0, 16) + "…)");
  }
  return { tifBytes, fileSha, fieldSha, payload, t, nNan, nOut, vmin, vmax, nPos,
           name: nodes.get("btnName").textContent, note: nodes.get("noteText").textContent };
}

async function main() {
  // The shipped path: every current browser has CompressionStream, so the build
  // is deflate-compressed (small file, same container shape as the Python route).
  const primary = await checkMode("deflate", true, argVal("--out"));
  // The fallback path: an older/embedded browser has no CompressionStream; the
  // writer must fall back to storing the pixels uncompressed — bigger, still valid.
  const fallback = await checkMode("no-compression", false, null);

  if (!primary) { report(); return false; }

  if (primary.t.compression !== 8) {
    step("[deflate] primary build is deflate-compressed (Compression=8)", false,
      "Compression=" + primary.t.compression + " — the browser build would be ~47 MB");
  } else {
    step("[deflate] primary build is deflate-compressed (Compression=8)", true,
      primary.tifBytes.length.toLocaleString("en-US") + " B instead of " +
      (primary.payload.rows * primary.payload.cols * 4).toLocaleString("en-US") + " B");
  }
  if (fallback) {
    step("[no-compression] fallback still produces a usable file",
      fallback.t.compression === 1 && fallback.nNan === 0 && fallback.nOut === 0,
      "Compression=" + fallback.t.compression + ", " +
      fallback.tifBytes.length.toLocaleString("en-US") + " B");
  }

  report({ bytes: primary.tifBytes.length, fileSha: primary.fileSha, fieldSha: primary.fieldSha,
           payload: primary.payload, rows: primary.t.rows, cols: primary.t.cols,
           epsg: primary.t.epsg, transform: primary.t.georef,
           nNan: primary.nNan, nOut: primary.nOut, vmin: primary.vmin, vmax: primary.vmax,
           nPos: primary.nPos, name: primary.name, note: primary.note,
           fallback_bytes: fallback ? fallback.tifBytes.length : null });
  return steps.every((s) => s.ok);
}

function report(extra) {
  if (argv.includes("--json")) {
    const j = { steps, verdict: steps.every((s) => s.ok) ? "PASS" : "FAIL" };
    if (extra) Object.assign(j, { filename: extra.name, note: extra.note,
      file_sha256: extra.fileSha, bytes: extra.bytes,
      rows: extra.rows, cols: extra.cols, epsg: extra.epsg, transform: extra.transform,
      nan_pixels: extra.nNan, out_of_range_pixels: extra.nOut, positive_pixels: extra.nPos,
      source_file: extra.payload.source_file, pixels_sha256: extra.payload.pixels_sha256 });
    console.log(JSON.stringify(j, null, 2));
    return;
  }
  console.log("== site build check ==");
  for (const s of steps) {
    console.log((s.ok ? " PASS  " : " FAIL  ") + s.name + (s.detail ? "\n         " + s.detail : ""));
  }
  const nOk = steps.filter((s) => s.ok).length;
  console.log(steps.every((s) => s.ok)
    ? `\nverdict: PASS (${nOk}/${steps.length} steps)`
    : `\nverdict: FAIL (${steps.length - nOk} of ${steps.length} steps failed)`);
}

main()
  .then((ok) => { process.exit(ok === false ? 1 : 0); })
  .catch((e) => {
    step("harness completed without throwing", false, e && e.stack ? e.stack.split("\n")[0] : String(e));
    report();
    process.exit(1);
  });
