/* GeoTIFF writer for the site's one-click "Build submission .tif" button.
 *
 * Writes a single-band float32 GeoTIFF (uncompressed, north-up), with
 *   - ModelPixelScale / ModelTiepoint (geotransform),
 *   - GeoKeyDirectory carrying EPSG:32611,
 *   - GDAL_NODATA = "nan"  (NaN outside the scored footprint),
 * byte-compatible with what scripts/build_submission.py writes on the Python
 * side (tests/test_tif_writer.py round-trips a payload through BOTH writers and
 * requires identical pixels and metadata).
 *
 * No dependencies. Payload format: gems-payload-v1 (see
 * scripts/build_site_payload.py): base64(zlib(JSON{rle: values_b64, lengths_b64})).
 */
(function (global) {
  "use strict";

  // ---- little-endian byte sink --------------------------------------------
  function Sink() {
    this.bytes = [];
  }
  Sink.prototype.u16le = function (v) { this.bytes.push(v & 255, (v >> 8) & 255); };
  Sink.prototype.u32le = function (v) {
    this.bytes.push(v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255);
  };
  Sink.prototype.f64le = function (v) {
    var b = new Uint8Array(8);
    new DataView(b.buffer).setFloat64(0, v, true);
    for (var i = 0; i < 8; i++) this.bytes.push(b[i]);
  };
  Sink.prototype.ascii = function (s) {
    for (var i = 0; i < s.length; i++) this.bytes.push(s.charCodeAt(i) & 255);
    if (s.charCodeAt(s.length - 1) !== 0) this.bytes.push(0);
  };
  Sink.prototype.padTo = function (align) {
    while (this.bytes.length % align !== 0) this.bytes.push(0);
  };
  Sink.prototype.toUint8 = function () { return new Uint8Array(this.bytes); };

  // ---- TIFF types ----------------------------------------------------------
  var T_SHORT = 3, T_LONG = 4, T_ASCII = 2, T_DOUBLE = 12;

  function ifdEntry(sink, tag, type, count, valueIsOffset, valueOrOffset) {
    sink.u16le(tag); sink.u16le(type); sink.u32le(count);
    if (valueIsOffset) {
      sink.u32le(valueOrOffset);
    } else if (type === T_SHORT && count === 1) {
      sink.u16le(valueOrOffset); sink.u16le(0);
    } else if (type === T_LONG && count === 1) {
      sink.u32le(valueOrOffset);
    } else {
      sink.u32le(valueOrOffset);
    }
  }

  // ASCII values of 4 bytes or fewer (incl. NUL) are stored INLINE in the
  // entry's value field per the TIFF spec; longer ones are offsets.
  function ifdEntryAscii(sink, tag, str) {
    var bytes = [];
    for (var i = 0; i < str.length; i++) bytes.push(str.charCodeAt(i) & 255);
    bytes.push(0);
    sink.u16le(tag); sink.u16le(T_ASCII); sink.u32le(bytes.length);
    if (bytes.length <= 4) {
      while (bytes.length < 4) bytes.push(0);
      for (var j = 0; j < 4; j++) sink.bytes.push(bytes[j]);
      return -1; // no out-of-line data
    }
    throw new Error("out-of-line ASCII not implemented (nodata too long)");
  }

  /**
   * Write a float32 north-up raster as GeoTIFF bytes.
   * opts = { rows, cols, values: Float32Array (row-major, NaN outside ok),
   *          transform: [a, b, c, d, e, f] (rasterio Affine order:
   *            x = a*col + b*row + c, y = d*col + e*row + f),
   *          epsg: 32611, nodata: "nan" }
   * Returns Uint8Array.
   */
  function writeGeoTiffFloat32(opts) {
    var rows = opts.rows, cols = opts.cols;
    var tr = opts.transform || [100, 0, 500000, 0, -100, 4500000];
    var a = tr[0], b = tr[1], c = tr[2], d = tr[3], e = tr[4], f = tr[5];
    if (b !== 0 || d !== 0) {
      throw new Error("only north-up (b=d=0) geotransforms are supported");
    }
    var values = opts.values;
    if (values.length !== rows * cols) {
      throw new Error("values length " + values.length + " != " + rows * cols);
    }
    var epsg = opts.epsg || 32611;
    var scale = [Math.abs(a), Math.abs(e), 0];
    var tie = [0, 0, 0, c, f, 0];

    // GeoKeyDirectory: 4 keys
    var keys = [
      1024, 0, 1, 1,      // GTModelTypeGeoKey = 1 (Projected)
      1025, 0, 1, 1,      // GTRasterTypeGeoKey = 1 (RasterPixelIsArea)
      3072, 0, 1, epsg,   // ProjectedCSTypeGeoKey = EPSG
      3076, 0, 1, 9001    // ProjLinearUnitsGeoKey = 9001 (metre)
    ];
    var geoDir = [1, 1, 0, 4].concat(keys);
    var nodata = (opts.nodata === undefined) ? "nan" : opts.nodata;

    // ---- layout: header | IFD | out-of-line data | pixels
    var baseTags = 14;   // 256..34735 (GeoKeyDirectory is the 14th)
    var nTags = baseTags + ((nodata !== null && nodata !== undefined) ? 1 : 0);
    var headerLen = 8;
    var ifdLen = 2 + nTags * 12 + 4;
    var ifdOff = headerLen;

    // out-of-line blocks
    var cur = headerLen + ifdLen;
    var geoDirOff = cur; cur += geoDir.length * 2;
    var pixelScaleOff = cur; cur += 3 * 8;
    var tieOff = cur; cur += 6 * 8;
    while (cur % 8 !== 0) cur++;   // keep pixel doubles/floats aligned
    var pixOff = cur;

    var sink = new Sink();
    // header: 'II', magic 42, offset of IFD
    sink.bytes.push(0x49, 0x49);
    sink.u16le(42);
    sink.u32le(ifdOff);

    // IFD
    sink.u16le(nTags);
    ifdEntry(sink, 256, T_LONG, 1, false, cols);            // ImageWidth
    ifdEntry(sink, 257, T_LONG, 1, false, rows);            // ImageLength
    ifdEntry(sink, 258, T_SHORT, 1, false, 32);             // BitsPerSample
    ifdEntry(sink, 259, T_SHORT, 1, false, 1);              // Compression=none
    ifdEntry(sink, 262, T_SHORT, 1, false, 1);              // Photometric=minisblack
    ifdEntry(sink, 273, T_LONG, 1, false, pixOff);          // StripOffsets
    ifdEntry(sink, 277, T_SHORT, 1, false, 1);              // SamplesPerPixel
    ifdEntry(sink, 278, T_LONG, 1, false, rows);            // RowsPerStrip
    ifdEntry(sink, 279, T_LONG, 1, false, rows * cols * 4); // StripByteCounts
    ifdEntry(sink, 284, T_SHORT, 1, false, 1);              // PlanarConfiguration
    ifdEntry(sink, 339, T_SHORT, 1, false, 3);              // SampleFormat=float
    ifdEntry(sink, 33550, T_DOUBLE, 3, true, pixelScaleOff);  // ModelPixelScale
    ifdEntry(sink, 33922, T_DOUBLE, 6, true, tieOff);          // ModelTiepoint
    ifdEntry(sink, 34735, T_SHORT, geoDir.length, true, geoDirOff); // GeoKeyDirectory
    if (nodata !== null && nodata !== undefined) {
      ifdEntryAscii(sink, 42113, String(nodata));   // GDAL_NODATA (inline "nan\0")
    }
    sink.u32le(0); // next IFD

    // out-of-line data
    while (sink.bytes.length < geoDirOff) sink.bytes.push(0);
    for (var i = 0; i < geoDir.length; i++) sink.u16le(geoDir[i]);
    for (var i = 0; i < 3; i++) sink.f64le(scale[i]);
    for (var i = 0; i < 6; i++) sink.f64le(tie[i]);
    while (sink.bytes.length < pixOff) sink.bytes.push(0);

    // pixels (float32 little endian)
    var pix = new Uint8Array(rows * cols * 4);
    var dv = new DataView(pix.buffer);
    for (var p = 0; p < values.length; p++) dv.setFloat32(p * 4, values[p], true);
    for (var p = 0; p < pix.length; p++) sink.bytes.push(pix[p]);

    return sink.toUint8();
  }

  // ---- gems-payload-v1 decode ---------------------------------------------
  function b64ToBytes(b64) {
    var bin = atob(b64);
    var out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  function decodePayloadJson(zlibbedB64) {
    // base64 -> zlib -> JSON  (async: uses DecompressionStream when present)
    var zbytes = b64ToBytes(zlibbedB64);
    if (typeof DecompressionStream === "undefined") {
      return Promise.reject(new Error("DecompressionStream not available in this browser"));
    }
    var ds = new DecompressionStream("deflate");
    var stream = new Blob([zbytes]).stream().pipeThrough(ds);
    return new Response(stream).text().then(function (txt) {
      return JSON.parse(txt);
    });
  }

  function decodeField(payload) {
    var values = new DataView(b64ToBytes(payload.rle.values_b64).buffer);
    var lengths = new DataView(b64ToBytes(payload.rle.lengths_b64).buffer);
    var nRuns = payload.rle.n_runs;
    var field = new Float32Array(payload.rle.n);
    var pos = 0;
    for (var r = 0; r < nRuns; r++) {
      var v = values.getFloat32(r * 4, true);
      var len = Number(lengths.getBigInt64(r * 8, true));
      for (var k = 0; k < len; k++) field[pos++] = v;
    }
    if (pos !== payload.rle.n) {
      throw new Error("RLE length mismatch: " + pos + " != " + payload.rle.n);
    }
    return field;
  }

  function sha256Hex(bytes) {
    // async via WebCrypto (browser + node >= 18 with globalThis.crypto)
    return crypto.subtle.digest("SHA-256", bytes).then(function (buf) {
      var arr = new Uint8Array(buf);
      var hex = "";
      for (var i = 0; i < arr.length; i++) {
        hex += arr[i].toString(16).padStart(2, "0");
      }
      return hex;
    });
  }

  // re-encode field to check the round trip is bit-identical
  function fieldSha256(field) {
    return sha256Hex(new Uint8Array(field.buffer, field.byteOffset, field.byteLength));
  }

  global.GemsTiff = {
    writeGeoTiffFloat32: writeGeoTiffFloat32,
    decodePayloadJson: decodePayloadJson,
    decodeField: decodeField,
    fieldSha256: fieldSha256,
    sha256Hex: sha256Hex
  };
})(typeof window !== "undefined" ? window : globalThis);
