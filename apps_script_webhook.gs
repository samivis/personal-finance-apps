var SHARED_SECRET = 'CHANGE_ME_TO_A_LONG_RANDOM_STRING';
var GID = 1509499529;
var HEADERS = ["Description", "Cost", "Type", "Category", "Date", "Notes", "Feelings"];
var TYPE_VALUES = ["Fixed", "Variable"];
var CATEGORY_VALUES = ["Food", "Transportation", "Shopping", "Other", "Health"];

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    if (body.secret !== SHARED_SECRET) return json_({ ok: false, error: 'bad secret' });
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    switch (body.action) {
      case 'list_tabs': return json_({ ok: true, tabs: ss.getSheets().map(function (s) { return s.getName(); }) });
      case 'read': return read_(ss, body);
      case 'ensure_tab': return ensureTab_(ss, body);
      case 'append': return append_(ss, body);
      case 'delete_rows': return deleteRows_(ss, body);
      case 'move_tab': return moveTab_(ss, body);
      default: return appendLegacy_(ss, body); // back-compat: {rows:[...]} -> default tab
    }
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function tabByName_(ss, name) {
  var t = ss.getSheetByName(name);
  return t;
}

function read_(ss, body) {
  var rng = ss.getRange(body.range);
  var values = rng.getValues();
  var notes = rng.getNotes();
  return json_({ ok: true, values: values, notes: notes });
}

function ensureTab_(ss, body) {
  var name = body.tab;
  if (ss.getSheetByName(name)) return json_({ ok: true, created: false });
  var sheet = ss.insertSheet(name, 1);  // index 1 = second tab (right after Monthly Budget)
  sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]).setFontWeight('bold');
  sheet.setFrozenRows(1);
  sheet.getRange('H9:I9').setValues([['Weekly Budget', body.weekly_budget]]);
  sheet.getRange('H10').setValue('Total Left');
  sheet.getRange('I10').setFormula(body.total_left_formula);
  // dropdowns on C (Type) and D (Category), rows 2..1000
  sheet.getRange(2, 3, 999, 1).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(TYPE_VALUES, true).build());
  sheet.getRange(2, 4, 999, 1).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(CATEGORY_VALUES, true).build());
  return json_({ ok: true, created: true });
}

function append_(ss, body) {
  var sheet = ss.getSheetByName(body.tab);
  if (!sheet) return json_({ ok: false, error: 'tab not found: ' + body.tab });
  var rows = body.rows || [];
  if (!rows.length) return json_({ ok: true, appended: 0 });
  var start = body.start_row;
  sheet.getRange(start, 1, rows.length, rows[0].length).setValues(rows);
  if (body.notes) {
    for (var i = 0; i < body.notes.length; i++) {
      if (body.notes[i]) sheet.getRange(start + i, 1).setNote(body.notes[i]);
    }
  }
  sheet.getRange(start, 2, rows.length, 1).setNumberFormat('"$"#,##0.00'); // Cost
  sheet.getRange(start, 5, rows.length, 1).setNumberFormat('m/d/yyyy');    // Date
  return json_({ ok: true, appended: rows.length });
}

function deleteRows_(ss, body) {
  var sheet = ss.getSheetByName(body.tab);
  if (!sheet) return json_({ ok: false, error: 'tab not found: ' + body.tab });
  sheet.deleteRows(body.start_row, body.num_rows);
  return json_({ ok: true, deleted: body.num_rows });
}

function moveTab_(ss, body) {
  var sheet = ss.getSheetByName(body.tab);
  if (!sheet) return json_({ ok: false, error: 'tab not found: ' + body.tab });
  ss.setActiveSheet(sheet);
  ss.moveActiveSheet(body.position);  // 1-based position
  return json_({ ok: true, moved: body.tab, position: body.position });
}

function appendLegacy_(ss, body) {
  var rows = body.rows || [];
  var sheet = null, tabs = ss.getSheets();
  for (var i = 0; i < tabs.length; i++) { if (tabs[i].getSheetId() === GID) { sheet = tabs[i]; break; } }
  if (!sheet) sheet = ss.getSheets()[0];
  if (!rows.length) return json_({ ok: true, appended: 0 });
  var start = sheet.getLastRow() + 1;
  sheet.getRange(start, 1, rows.length, rows[0].length).setValues(rows);
  return json_({ ok: true, appended: rows.length });
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
