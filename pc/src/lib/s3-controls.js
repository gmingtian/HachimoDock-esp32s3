/** A4: reuse the official physical control model, with a fresh local preference
 * identity so old three-key settings cannot silently remap the new controls. */
export function s3ButtonRows(officialRows) {
 return officialRows.map(row => ({...row,
  id:row.id.replace(/^p4_/, 's3j_'),
  controlId:row.controlId.replace(/^p4_/, 's3j_'),
 }));
}
