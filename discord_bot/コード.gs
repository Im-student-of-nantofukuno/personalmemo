
/**
 * Discord Memo Assistant
 * リクエスト受付・処理振り分け
 */

function doPost(e) {
  try {
    // POSTデータの確認
    if (!e || !e.postData || !e.postData.contents) {
      return jsonResponse({
        success: false,
        error: "リクエストが空です。"
      });
    }

    // JSON解析
    const data = JSON.parse(e.postData.contents);

    // スクリプトプロパティ取得
    const properties = PropertiesService.getScriptProperties();
    const apiSecret = properties.getProperty("API_SECRET");

    if (!apiSecret) {
      throw new Error("API_SECRETが設定されていません。");
    }

    // 認証
    if (data.secret !== apiSecret) {
      return jsonResponse({
        success: false,
        error: "Unauthorized"
      });
    }

    // action確認
    if (!data.action) {
      return jsonResponse({
        success: false,
        error: "actionが指定されていません。"
      });
    }

    // 処理振り分け
    switch (data.action) {

      case "save_memo":
        return saveMemo(data);

      case "save_dates":
        return saveDates(data);

      case "get_memos":
        return getMemos(data);

      default:
        return jsonResponse({
          success: false,
          error: "不明なactionです。"
        });
    }

  } catch (error) {
    console.error(error);

    return jsonResponse({
      success: false,
      error: "処理中にエラーが発生しました。"
    });
  }
}


/**
 * メモ保存
 */
function saveMemo(data) {
  const properties = PropertiesService.getScriptProperties();
  const spreadsheetId = properties.getProperty("SpreadsheetID");

  if (!spreadsheetId) {
    throw new Error("SpreadsheetIDが設定されていません。");
  }

  // 必須項目確認
  if (
    typeof data.content !== "string" ||
    !data.content.trim() ||
    !data.discord_message_id ||
    !data.source_user_id ||
    !data.created_at
  ) {
    return jsonResponse({
      success: false,
      error: "必須項目が不足しています。"
    });
  }

  // Discord送信日時を解析
  const createdAt = new Date(data.created_at);

  if (isNaN(createdAt.getTime())) {
    return jsonResponse({
      success: false,
      error: "created_atの形式が不正です。"
    });
  }

  const spreadsheet = SpreadsheetApp.openById(spreadsheetId);
  const sheet = spreadsheet.getSheetByName("Memos");

  if (!sheet) {
    throw new Error("Memosシートが見つかりません。");
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);

  try {
    const lastRow = sheet.getLastRow();

    // 二重保存チェック
    if (lastRow >= 2) {
      const rows = sheet
        .getRange(2, 1, lastRow - 1, 6)
        .getValues();

      const duplicate = rows.find(row =>
        String(row[5]) === String(data.discord_message_id)
      );

      if (duplicate) {
        return jsonResponse({
          success: true,
          duplicated: true,
          memo_id: duplicate[0],
          status: "already_saved"
        });
      }
    }

    // メモID生成
    const memoId = Utilities.getUuid();
    const now = new Date();

    // メモ保存
    sheet.appendRow([
      memoId,
      data.content,
      "NORMAL",
      createdAt,
      now,
      String(data.discord_message_id),
      String(data.source_user_id),
      "",
      "ACTIVE"
    ]);

    return jsonResponse({
      success: true,
      duplicated: false,
      memo_id: memoId,
      status: "saved"
    });

  } finally {
    lock.releaseLock();
  }
}


/**
 * 日付情報保存（後で実装）
 */
function saveDates(data) {
  const memoId = data.memo_id;
  const mentions = data.date_mentions;

  // 入力チェック
  if (!memoId || typeof memoId !== "string") {
    return jsonResponse({
      success: false,
      error: "invalid_memo_id"
    });
  }

  if (!Array.isArray(mentions)) {
    return jsonResponse({
      success: false,
      error: "invalid_date_mentions"
    });
  }

  const validRoles = [
    "plan", "deadline", "event", "historical", "other"
  ];

  const validKinds = ["date", "period"];

  const validPrecisions = [
    "day", "month", "year", "period", "unknown"
  ];

  const validStatuses = [
    "certain", "approximate", "ambiguous", "unresolved"
  ];

  // 日付情報を検証
  for (const item of mentions) {
    if (
      !item.expression ||
      !validRoles.includes(item.role) ||
      !validKinds.includes(item.kind) ||
      !validPrecisions.includes(item.precision) ||
      !validStatuses.includes(item.status)
    ) {
      return jsonResponse({
        success: false,
        error: "invalid_date_data"
      });
    }

    const datePattern = /^\d{4}-\d{2}-\d{2}$/;

    for (const date of [item.start_date, item.end_date]) {
      if (date !== null && date !== undefined && date !== "") {
        if (
          typeof date !== "string" ||
          !datePattern.test(date) ||
          isNaN(Date.parse(date + "T00:00:00Z"))
        ) {
          return jsonResponse({
            success: false,
            error: "invalid_date_format"
          });
        }
      }
    }

    if (
      item.start_date &&
      item.end_date &&
      item.start_date > item.end_date
    ) {
      return jsonResponse({
        success: false,
        error: "invalid_date_range"
      });
    }
  }

  const properties = PropertiesService.getScriptProperties();
  const spreadsheetId = properties.getProperty("SpreadsheetID");

  if (!spreadsheetId) {
    return jsonResponse({
      success: false,
      error: "spreadsheet_id_not_found"
    });
  }

  const lock = LockService.getScriptLock();

  try {
    lock.waitLock(10000);

    const spreadsheet = SpreadsheetApp.openById(spreadsheetId);
    const sheet = spreadsheet.getSheetByName("MemoDates");

    if (!sheet) {
      return jsonResponse({
        success: false,
        error: "memo_dates_sheet_not_found"
      });
    }

    const lastRow = sheet.getLastRow();

    // 既存データを取得
    let existingRows = [];

    if (lastRow >= 2) {
      existingRows = sheet
        .getRange(2, 1, lastRow - 1, 9)
        .getValues();
    }

    // 対象メモ以外のデータを残す
    const remainingRows = existingRows.filter(
      row => row[0] !== memoId
    );

    // 新しい日付情報を作成
    const newRows = mentions.map(item => [
      memoId,
      item.expression,
      item.role,
      item.kind,
      item.start_date || "",
      item.end_date || "",
      item.precision,
      item.status,
      item.note || ""
    ]);

    const allRows = remainingRows.concat(newRows);

    // データ部分を更新
    if (lastRow >= 2) {
      sheet.getRange(2, 1, lastRow - 1, 9).clearContent();
    }

    if (allRows.length > 0) {
      sheet.getRange(2, 1, allRows.length, 9).setValues(allRows);
    }

    return jsonResponse({
      success: true,
      memo_id: memoId,
      saved_count: newRows.length,
      status: "saved"
    });

  } catch (error) {
    console.error("saveDates error: " + error);

    return jsonResponse({
      success: false,
      error: "save_dates_failed"
    });

  } finally {
    if (lock.hasLock()) {
      lock.releaseLock();
    }
  }
}


/**
 * メモ取得（後で実装）
 */
function getMemos(data) {
  return jsonResponse({
    success: false,
    error: "get_memosはまだ実装されていません。"
  });
}


/**
 * JSONレスポンス
 */
function jsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}


/**
 * save_memoの入力検証テスト
 * Spreadsheetには書き込まない
 */
function testSaveMemoValidation() {

  const validData = {
    action: "save_memo",
    content: "テスト用メモ",
    discord_message_id: "test_message_001",
    source_user_id: "test_user_001",
    created_at: "2026-11-23T10:20:00+09:00"
  };

  const invalidData = {
    action: "save_memo",
    content: "",
    discord_message_id: "test_message_002",
    source_user_id: "test_user_001",
    created_at: "2026-11-23T10:20:00+09:00"
  };

  // 正常データの検証
  const validDate = new Date(validData.created_at);

  console.log(
    "正常データ:",
    !isNaN(validDate.getTime()) &&
    validData.content.trim() !== ""
  );

  // 不正データの検証
  const invalidDate = new Date(invalidData.created_at);

  console.log(
    "空のメモ:",
    !invalidData.content.trim()
  );

  console.log(
    "日時形式:",
    !isNaN(invalidDate.getTime())
  );
}

/**
 * saveMemoの保存テスト
 */
function testSaveMemo() {

  const testData = {
    content: "保存テスト用メモ",
    discord_message_id: "test_saveMemo_001",
    source_user_id: "test_user_001",
    created_at: "2026-11-23T21:00:00+09:00"
  };

  const result = saveMemo(testData);

  console.log(result.getContent());
}


function testSaveDates() {
  const memoId = "test_dates_001";

  // テスト1：2件保存
  const firstResult = JSON.parse(
    saveDates({
      memo_id: memoId,
      date_mentions: [
        {
          expression: "3日後",
          role: "plan",
          kind: "date",
          start_date: "2026-11-26",
          end_date: "2026-11-26",
          precision: "day",
          status: "certain",
          note: "3日後の予定"
        },
        {
          expression: "来週",
          role: "event",
          kind: "period",
          start_date: "2026-11-30",
          end_date: "2026-12-06",
          precision: "period",
          status: "certain",
          note: "来週の期間"
        }
      ]
    }).getContent()
  );

  console.log("テスト1：2件保存");
  console.log(JSON.stringify(firstResult));

  // テスト2：1件に置き換え
  const secondResult = JSON.parse(
    saveDates({
      memo_id: memoId,
      date_mentions: [
        {
          expression: "明日",
          role: "plan",
          kind: "date",
          start_date: "2026-11-24",
          end_date: "2026-11-24",
          precision: "day",
          status: "certain",
          note: "明日の予定"
        }
      ]
    }).getContent()
  );

  console.log("テスト2：置き換え");
  console.log(JSON.stringify(secondResult));

  // テスト3：0件に置き換え
  const thirdResult = JSON.parse(
    saveDates({
      memo_id: memoId,
      date_mentions: []
    }).getContent()
  );

  console.log("テスト3：0件に置き換え");
  console.log(JSON.stringify(thirdResult));
}
