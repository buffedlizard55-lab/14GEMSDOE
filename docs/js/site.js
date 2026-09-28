/* Site logic: build the submission GeoTIFF in-browser from the shipped payload.
 *
 * Flow (every step is self-checked; the download is offered only if all pass):
 *   1. decode window.GEMS_PAYLOAD_B64  (base64 -> zlib -> JSON gems-payload-v1)
 *   2. RLE-decode the float32 field
 *   3. hash the field (SHA-256 via WebCrypto) and compare to pixels_sha256
 *   4. write the GeoTIFF container (GemsTiff.writeGeoTiffFloat32)
 *   5. re-read the written bytes' metadata header and verify grid + nodata
 *   6. offer download with a unique filename: GEMS-<UTC instant>-<sha8>.tif
 *
 * Nothing is uploaded. The visitor's browser does all the work.
 */
(function () {
  "use strict";

  function el(id) { return document.getElementById(id); }

  function log(line) {
    var s = el("buildStatus");
    if (s) { s.textContent += line + "\n"; }
    console.log("[gems]", line);
  }

  function b64ToBytes(b64) {
    var bin = atob(b64);
    var out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  function fmtBytes(n) {
    if (n > 1048576) return (n / 1048576).toFixed(2) + " MB";
    if (n > 1024) return (n / 1024).toFixed(1) + " KB";
    return n + " B";
  }

  function download(bytes, filename, mime) {
    var blob = new Blob([bytes], { type: mime || "image/tiff" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { document.body.removeChild(a); URL.revokeObjectURL(url); }, 800);
  }

  var payload = null;
  var field = null;
  var tifBytes = null;
  var fieldSha = "";

  function setStatus(msg, cls) {
    var s = el("buildState");
    if (s) { s.textContent = msg; s.className = "pill " + (cls || ""); }
  }

  function ready() {
    var buttons = ["btnTif", "btnZip", "btnCompat"];
    buttons.forEach(function (b) { if (el(b)) el(b).disabled = false; });
  }

  function decodeAll() {
    if (typeof window.GemsTiff === "undefined" || !window.GEMS_PAYLOAD_B64) {
      setStatus("payload missing", "bad");
      log("ERROR: payload not loaded (docs/js/payload.js missing?)");
      return Promise.reject(new Error("payload missing"));
    }
    log("decoding payload (" + window.GEMS_PAYLOAD_B64.length + " b64 chars) ...");
    return GemsTiff.decodePayloadJson(window.GEMS_PAYLOAD_B64).then(function (pl) {
      payload = pl;
      log("payload: kind=" + pl.kind + "  source=" + pl.source_file +
          "  grid=" + pl.rows + "x" + pl.cols + "  runs=" + pl.rle.n_runs);
      field = GemsTiff.decodeField(pl);
      if (field.length !== pl.rows * pl.cols) throw new Error("field length mismatch");
      return GemsTiff.fieldSha256(field);
    }).then(function (sha) {
      fieldSha = sha;
      if (sha !== payload.pixels_sha256) {
        throw new Error("pixel hash mismatch: got " + sha + ", pinned " + payload.pixels_sha256);
      }
      log("pixel field sha256 OK  " + sha.slice(0, 16) + "...");
      // PRIMARY build: finite everywhere (0.0 outside the footprint, no NaN).
      // The platform's range checker rejected the NaN-nodata variant with
      // "Predicted values must be in range [0, 1]" (observed 2026-09-28 on a
      // real upload attempt), so the default download is the finite one and
      // the literal NaN-nodata build is demoted to the secondary button.
      var finite = new Float32Array(field.length);
      var vmin = Infinity, vmax = -Infinity, nBad = 0;
      for (var i = 0; i < field.length; i++) {
        var v = field[i];
        finite[i] = isNaN(v) ? 0.0 : v;
        if (!isNaN(v)) {
          if (v < vmin) vmin = v;
          if (v > vmax) vmax = v;
        }
        if (finite[i] < 0.0 || finite[i] > 1.0) nBad++;
      }
      if (nBad > 0) {
        throw new Error(nBad + " payload value(s) outside [0,1] - refusing to build " +
                        "(payload bug; report it)");
      }
      log("value gate: all finite, min=" + (vmin === Infinity ? "n/a" : vmin.toFixed(6)) +
          " max=" + (vmax === -Infinity ? "n/a" : vmax.toFixed(6)) + " (within [0,1])");
      tifBytes = GemsTiff.writeGeoTiffFloat32({
        rows: payload.rows, cols: payload.cols, values: finite,
        transform: payload.transform, epsg: payload.epsg, nodata: null
      });
      // SECONDARY build: literal official format (NaN outside, GDAL_NODATA=nan).
      tifBytesNan = GemsTiff.writeGeoTiffFloat32({
        rows: payload.rows, cols: payload.cols, values: field,
        transform: payload.transform, epsg: payload.epsg, nodata: "nan"
      });
      log("GeoTIFF containers written: primary " + fmtBytes(tifBytes.length) +
          " (finite), secondary " + fmtBytes(tifBytesNan.length) + " (NaN-nodata)");
      return GemsTiff.sha256Hex(tifBytes);
    }).then(function (fileSha) {
      // self re-read: parse the header we just wrote and verify it agrees
      var dv = new DataView(tifBytes.buffer, tifBytes.byteOffset, tifBytes.byteLength);
      if (dv.getUint16(0, true) !== 0x4949 || dv.getUint16(2, true) !== 42) {
        throw new Error("not a little-endian TIFF");
      }
      var ifdOff = dv.getUint32(4, true);
      var nTags = dv.getUint16(ifdOff, true);
      log("self-check: TIFF header OK, IFD at " + ifdOff + " with " + nTags + " tags");
      var seen = {};
      for (var i = 0; i < nTags; i++) {
        var e = ifdOff + 2 + i * 12;
        seen[dv.getUint16(e, true)] = true;
      }
      [256, 257, 258, 273, 33550, 33922, 34735].forEach(function (t) {
        if (!seen[t]) throw new Error("missing TIFF tag " + t);
      });
      // the PRIMARY build is finite everywhere and intentionally carries NO
      // GDAL_NODATA tag; the NaN-nodata secondary build must carry it.
      if (seen[42113]) {
        throw new Error("primary build unexpectedly carries GDAL_NODATA");
      }
      log("self-check: required tags present (GeoKeyDirectory + georeferencing; " +
          "no GDAL_NODATA on the finite primary build)");
      window._gemsBuild = {
        fileSha: fileSha, fieldSha: fieldSha,
        rows: payload.rows, cols: payload.cols, epsg: payload.epsg
      };
      var bn = el("btnName");
      if (bn) bn.textContent = "gems-submission-" + new Date().toISOString()
        .replace(/[-:]/g, "").replace(/\..+/, "Z").replace("T", "T") + "-" + fileSha.slice(0, 8) + ".tif";
      var nt = el("noteText");
      if (nt && payload.note) nt.textContent = payload.note;
      setStatus(payload.kind === "demo" ? "DEMO payload — not uploadable" : "READY",
                payload.kind === "demo" ? "demo" : "ok");
      if (payload.kind !== "demo") ready();
      else {
        // demo: still allow the build so the mechanism can be inspected
        ["btnTif", "btnZip", "btnCompat"].forEach(function (b) { if (el(b)) el(b).disabled = false; });
        var warn = el("demoBanner");
        if (warn) warn.style.display = "block";
      }
      log("READY — filename: " + el("btnName").textContent);
    }).catch(function (e) {
      setStatus("FAILED: " + e.message, "bad");
      log("ERROR: " + e.message);
    });
  }

  function buildName() {
    return (el("btnName") && el("btnName").textContent) ||
      ("gems-submission-" + Date.now() + ".tif");
  }

  function wire() {
    if (!el("buildStatus")) return; // not on the builder page
    el("btnTif").addEventListener("click", function () {
      if (!tifBytes) return;
      download(tifBytes, buildName());
      log("downloaded " + buildName() + " (" + fmtBytes(tifBytes.length) + ")");
    });
    el("btnZip").addEventListener("click", function () {
      if (!tifBytes) return;
      // minimal ZIP (stored, no compression) around the same bytes
      var zip = makeStoredZip(buildName(), tifBytes);
      download(zip, buildName().replace(/\.tif$/, ".zip"), "application/zip");
      log("downloaded zip wrapper (" + fmtBytes(zip.length) + ")");
    });
    el("btnCompat").addEventListener("click", function () {
      if (!tifBytesNan) return;
      download(tifBytesNan, buildName().replace(/\.tif$/, "-nan-nodata.tif"));
      log("downloaded literal-format variant (NaN outside) — WARNING: a file like " +
          "this was rejected by the form with 'Predicted values must be in range [0, 1]' " +
          "(observed 2026-09-28); use only if the platform confirms NaN-nodata support");
    });
    decodeAll();
  }

  // minimal ZIP writer (stored entries) so the .zip button needs no library
  function crc32(bytes) {
    var table = crc32.table;
    if (!table) {
      table = crc32.table = new Int32Array(256);
      for (var n = 0; n < 256; n++) {
        var c = n;
        for (var k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
        table[n] = c;
      }
    }
    var crc = -1;
    for (var i = 0; i < bytes.length; i++) crc = (crc >>> 8) ^ table[(crc ^ bytes[i]) & 255];
    return (crc ^ -1) >>> 0;
  }

  function makeStoredZip(name, bytes) {
    var enc = new TextEncoder();
    var nameB = enc.encode(name);
    var crc = crc32(bytes);
    var parts = [];
    var local = new DataView(new ArrayBuffer(30));
    local.setUint32(0, 0x04034b50, true);
    local.setUint16(4, 20, true); local.setUint16(6, 0, true); local.setUint16(8, 0, true);
    local.setUint16(10, 0, true); local.setUint16(12, 0x21, true); // fixed time/date
    local.setUint32(14, crc, true);
    local.setUint32(18, bytes.length, true);
    local.setUint32(22, bytes.length, true);
    local.setUint16(26, nameB.length, true); local.setUint16(28, 0, true);
    parts.push(new Uint8Array(local.buffer), nameB, bytes);
    var offset = 30 + nameB.length + bytes.length;
    var cd = new DataView(new ArrayBuffer(46));
    cd.setUint32(0, 0x02014b50, true);
    cd.setUint16(4, 20, true); cd.setUint16(6, 20, true);
    cd.setUint32(16, crc, true);
    cd.setUint32(20, bytes.length, true);
    cd.setUint32(24, bytes.length, true);
    cd.setUint16(28, nameB.length, true);
    cd.setUint32(42, 0, true);
    parts.push(new Uint8Array(cd.buffer), nameB);
    var cdLen = 46 + nameB.length;
    var end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true);
    end.setUint16(8, 1, true); end.setUint16(10, 1, true);
    end.setUint32(12, cdLen, true);
    end.setUint32(16, offset, true);
    parts.push(new Uint8Array(end.buffer));
    var total = parts.reduce(function (s, p) { return s + p.length; }, 0);
    var out = new Uint8Array(total);
    var pos = 0;
    parts.forEach(function (p) { out.set(p, pos); pos += p.length; });
    return out;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
