/**
 * [Input] firmware-version.js pure helpers.
 * [Output] Regression coverage for older, equal, newer, suffixed, and invalid versions.
 * [Pos] test node in pc/src/lib.
 * [Sync] If this file changes, update `pc/src/.folder.md`.
 */

import test from "node:test";
import assert from "node:assert/strict";
import {
  compareFirmwareVersions,
  firmwareUpdateDisposition,
  parseFirmwareRevision,
  parseFirmwareVersion,
} from "./firmware-version.js";

test("S3 letter revisions never offer the older bundled firmware", () => {
  for (const revision of ["r13n", "r14b", "r14c"]) {
    const current = `0.7.103-s3-${revision}-80m-l320`;
    assert.equal(compareFirmwareVersions(current, "0.7.103-s3-r10-l320"), 1);
    assert.notEqual(firmwareUpdateDisposition(current, "0.7.103-s3-r10-l320"), "update");
  }
  assert.equal(parseFirmwareRevision("0.7.103-s3-r14c-80m-l320"), 14);
  assert.equal(compareFirmwareVersions("0.7.103-s3-r14b-80m-l320", "0.7.103-s3-r14c-80m-l320"), -1);
  assert.equal(compareFirmwareVersions("0.7.103-s3-r14c-80m-l320", "0.7.103-s3-r15-80m-l320"), -1);
});

test("automatic updates preserve S3 trial clock and landscape compatibility", () => {
  const current = "0.7.103-s3-r14c-80m-l320";
  assert.equal(firmwareUpdateDisposition(current, "0.7.104-s3-r15-l320"), "protected");
  assert.equal(firmwareUpdateDisposition(current, "0.7.104-s3-r15-80m"), "protected");
  assert.equal(firmwareUpdateDisposition(current, "0.7.104-s3-r15-80m-l320"), "update");
  for (const invalid of ["0.7.103-s3-r14beta-l320", "0.7.103-s3-r14c-r9-l320", "0.7.103-s3-rNext-80m-l320", "0.7.103-s3-r-80m-l320"]) {
    assert.equal(compareFirmwareVersions(invalid, "0.7.103-s3-r10-l320"), null);
    assert.equal(firmwareUpdateDisposition(invalid, "0.7.103-s3-r10-l320"), "unknown");
  }
});

test("same numeric core is ordered by the -rNNN build revision", () => {
  assert.equal(parseFirmwareRevision("0.7.103-p4-r144"), 144);
  assert.equal(parseFirmwareRevision("0.7.103-p4-r142-framework"), 142);
  assert.equal(parseFirmwareRevision("0.7.34-p4"), 0);
  assert.equal(compareFirmwareVersions("0.7.103-p4-r142-framework", "0.7.103-p4-r144"), -1);
  assert.equal(compareFirmwareVersions("0.7.103-p4-r144", "0.7.103-p4-r144"), 0);
  assert.equal(compareFirmwareVersions("0.7.103-p4-r66", "0.7.103-p4-r144"), -1);
  assert.equal(compareFirmwareVersions("0.7.104-p4-r1", "0.7.103-p4-r144"), 1);
  assert.equal(firmwareUpdateDisposition("0.7.103-p4-r142-framework", "0.7.103-p4-r144"), "update");
  assert.equal(firmwareUpdateDisposition("0.7.103-p4-r144", "0.7.103-p4-r144"), "latest");
  assert.equal(firmwareUpdateDisposition("0.7.103-p4-r66", "0.7.103-p4-r144"), "update");
});

test("firmware versions compare numerically and ignore product suffixes", () => {
  assert.deepEqual(parseFirmwareVersion("v0.7.29-p4"), [0, 7, 29]);
  assert.equal(compareFirmwareVersions("0.7.9-p4", "0.7.29-p4"), -1);
  assert.equal(compareFirmwareVersions("0.7.29", "0.7.29-p4"), 0);
  assert.equal(compareFirmwareVersions("0.8.0-p4", "0.7.29-p4"), 1);
});

test("firmware update disposition exposes update only for older devices", () => {
  assert.equal(firmwareUpdateDisposition("0.7.28-p4", "0.7.29-p4"), "update");
  assert.equal(firmwareUpdateDisposition("0.7.29-p4", "0.7.29-p4"), "latest");
  assert.equal(firmwareUpdateDisposition("0.7.30-p4", "0.7.29-p4"), "latest");
  assert.equal(firmwareUpdateDisposition("unknown", "0.7.29-p4"), "unknown");
});
