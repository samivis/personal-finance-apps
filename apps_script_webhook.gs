/**
 * Daily Budget webhook — paste this into the budget sheet's Apps Script editor
 * (Extensions -> Apps Script), then Deploy -> New deployment -> Web app.
 *
 * Deploy settings:
 *   - Execute as: Me (the sheet owner)
 *   - Who has access: Anyone with the link
 * Copy the resulting /exec URL and a SHARED_SECRET into the runner config.
 *
 * The runner POSTs JSON: { "secret": "...", "rows": [[...9 cols...], ...] }
 * Rows are appended to the tab whose gid matches GID below.
 */

// Set this to a long random string, and put the same value in the runner config.
var SHARED_SECRET = 'CHANGE_ME_TO_A_LONG_RANDOM_STRING';

// gid of the tab to append to (the #gid=... in the sheet URL).
var GID = 1509499529;

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    if (body.secret !== SHARED_SECRET) {
      return json_({ ok: false, error: 'bad secret' });
    }
    var rows = body.rows || [];
    if (!rows.length) {
      return json_({ ok: true, appended: 0 });
    }
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = null;
    var tabs = ss.getSheets();
    for (var i = 0; i < tabs.length; i++) {
      if (tabs[i].getSheetId() === GID) { sheet = tabs[i]; break; }
    }
    if (!sheet) sheet = ss.getSheets()[0];

    var start = sheet.getLastRow() + 1;
    sheet.getRange(start, 1, rows.length, rows[0].length).setValues(rows);
    return json_({ ok: true, appended: rows.length });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
