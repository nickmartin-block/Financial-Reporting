var SHEET_NAME = 'Sheet1';
var DASHBOARD_URL = 'https://blockcell.sqprod.co/sites/nmart-pacing-dashboard/';
var OWNER_EMAIL = 'nmart@block.xyz';
var DEFAULT_DOMAIN = 'block.xyz';

function doGet(e) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME);
  var callback = e.parameter.callback || '';

  if (e.parameter.action === 'clear') {
    var lastRow = sheet.getLastRow();
    if (lastRow > 1) {
      sheet.deleteRows(2, lastRow - 1);
    }
    return respond({ success: true, cleared: lastRow - 1 }, callback);
  }

  if (e.parameter.action === 'post') {
    var page = e.parameter.page;
    var author = e.parameter.author;
    var comment = e.parameter.comment;
    if (!page || !author || !comment) {
      return respond({ error: 'Missing required fields' }, callback);
    }
    sheet.appendRow([new Date().toISOString(), page, author, comment]);
    try {
      notifyOnComment(page, author, comment);
    } catch (err) {
      // don't fail the write if notification fails
    }
    return respond({ success: true }, callback);
  }

  var data = sheet.getDataRange().getValues();
  var rows = data.slice(1);
  var comments = rows
    .filter(function(row) { return row[3]; })
    .map(function(row) {
      return { timestamp: row[0], page: row[1], author: row[2], comment: row[3] };
    })
    .reverse();
  return respond({ comments: comments }, callback);
}

function respond(obj, callback) {
  var json = JSON.stringify(obj);
  if (callback) {
    return ContentService.createTextOutput(callback + '(' + json + ')')
      .setMimeType(ContentService.MimeType.JAVASCRIPT);
  }
  return ContentService.createTextOutput(json)
    .setMimeType(ContentService.MimeType.JSON);
}

function notifyOnComment(page, author, comment) {
  var notified = [];
  var authorEmail = author.toLowerCase().trim().replace(/\s+/g, '.') + '@' + DEFAULT_DOMAIN;

  if (authorEmail !== OWNER_EMAIL) {
    MailApp.sendEmail(
      OWNER_EMAIL,
      'Dashboard Comment: ' + author + ' on ' + page,
      author + ' commented on ' + page + ': ' + comment,
      { htmlBody: buildEmail(author, page, comment) }
    );
    notified.push(OWNER_EMAIL);
  }

  var mentions = extractMentions(comment);
  for (var i = 0; i < mentions.length; i++) {
    var email = mentions[i];
    if (notified.indexOf(email) === -1 && email !== authorEmail) {
      MailApp.sendEmail(
        email,
        author + ' mentioned you on the Block Performance Dashboard',
        author + ' mentioned you: ' + comment,
        { htmlBody: buildEmail(author, page, comment) }
      );
      notified.push(email);
    }
  }
}

function extractMentions(text) {
  var emails = [];
  var re = new RegExp('@([\\w.-]+(?:@[\\w.-]+\\.[\\w]+)?)', 'g');
  var match;
  while ((match = re.exec(text)) !== null) {
    var mention = match[1];
    if (mention.indexOf('@') === -1) {
      mention = mention + '@' + DEFAULT_DOMAIN;
    }
    emails.push(mention.toLowerCase());
  }
  return emails;
}

function buildEmail(author, page, comment) {
  return '<div style="font-family:Arial,sans-serif;max-width:600px;color:#1a1a1a">'
    + '<h3 style="font-size:14px;margin-bottom:4px">Block Performance Dashboard</h3>'
    + '<p style="color:#666;font-size:13px;margin:8px 0"><strong>' + author
    + '</strong> commented on <strong>' + page + '</strong>:</p>'
    + '<blockquote style="border-left:3px solid #1a1a1a;margin:12px 0;padding:8px 16px;'
    + 'color:#333;font-size:13px;background:#f8f9fa;border-radius:0 4px 4px 0">'
    + comment + '</blockquote>'
    + '<p style="margin-top:16px"><a href="' + DASHBOARD_URL
    + '" style="color:#1a73e8;font-size:13px;text-decoration:none">View Dashboard</a></p></div>';
}
