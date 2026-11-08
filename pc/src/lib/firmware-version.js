/**
 * [Input] Device and bundled firmware version strings such as `0.7.34-p4` or `0.7.103-p4-r144`.
 * [Output] Numeric comparison (the `-rNNN` build revision breaks ties between equal
 *          numeric cores) plus update/latest/unknown sidebar disposition.
 * [Pos] Pure firmware-version helper in pc/src/lib.
 * [Sync] If this file changes, update `pc/src/.folder.md`.
 */

export function parseFirmwareVersion(value) {
  const normalized = String(value || "").trim().replace(/^v/i, "");
  const core = normalized.split("-", 1)[0];
  if (!/^\d+(?:\.\d+){0,3}$/.test(core)) return null;
  return core.split(".").map(Number);
}

// S3 trial revisions also use a letter, e.g. r13n and r14c. A malformed
// revision must not silently become revision 0 and permit a downgrade.
function firmwareRevisionKey(value) {
  let key = null;
  for (const segment of String(value || "").trim().split("-").slice(1)) {
    if (!/^r/i.test(segment)) continue;
    const match = /^r(\d{1,6})([a-z]?)$/i.exec(segment);
    if (!match || key) return null;
    key = { revision: Number(match[1]), suffix: match[2].toLowerCase() };
  }
  return key || { revision: 0, suffix: "" };
}

export function parseFirmwareRevision(value) {
  return firmwareRevisionKey(value)?.revision ?? null;
}

export function compareFirmwareVersions(left, right) {
  const leftParts = parseFirmwareVersion(left);
  const rightParts = parseFirmwareVersion(right);
  const leftRevision = firmwareRevisionKey(left);
  const rightRevision = firmwareRevisionKey(right);
  if (!leftParts || !rightParts || !leftRevision || !rightRevision) return null;
  const width = Math.max(leftParts.length, rightParts.length);
  for (let index = 0; index < width; index += 1) {
    const delta = (leftParts[index] || 0) - (rightParts[index] || 0);
    if (delta < 0) return -1;
    if (delta > 0) return 1;
  }
  const revisionDelta = leftRevision.revision - rightRevision.revision;
  if (revisionDelta < 0) return -1;
  if (revisionDelta > 0) return 1;
  if (leftRevision.suffix < rightRevision.suffix) return -1;
  if (leftRevision.suffix > rightRevision.suffix) return 1;
  return 0;
}

export function firmwareUpdateDisposition(currentVersion, bundledVersion) {
  const comparison = compareFirmwareVersions(currentVersion, bundledVersion);
  if (comparison === null) return "unknown";
  if (comparison >= 0) return "latest";
  const currentMarkers = String(currentVersion).split("-");
  const bundledMarkers = String(bundledVersion).split("-");
  if (currentMarkers.includes("s3") && ["80m", "l320"].some(
    marker => currentMarkers.includes(marker) && !bundledMarkers.includes(marker)
  )) return "protected";
  return "update";
}
