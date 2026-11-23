
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
  return jsonResponse({
    success: false,
    error: "save_datesはまだ実装されていません。"
  });
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
