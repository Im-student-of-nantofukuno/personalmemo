
/**
 * Discord Memo Assistant
 * メッセージ受信・保存処理
 */

function doPost(e) {
  try {
    // スクリプトプロパティを取得
    const properties = PropertiesService.getScriptProperties();

    const apiSecret = properties.getProperty("API_SECRET");
    const spreadsheetId = properties.getProperty("SpreadsheetID");

    if (!apiSecret || !spreadsheetId) {
      throw new Error("必要なスクリプトプロパティが設定されていません。");
    }

    // リクエスト本文をJSONとして解析
    const data = JSON.parse(e.postData.contents);

    // 認証
    if (data.secret !== apiSecret) {
      return jsonResponse({
        success: false,
        error: "Unauthorized"
      });
    }

    // 必須項目の確認
    if (
      !data.content ||
      !data.discord_message_id ||
      !data.source_user_id
    ) {
      throw new Error("必須項目が不足しています。");
    }

    // Spreadsheetを取得
    const spreadsheet = SpreadsheetApp.openById(spreadsheetId);
    const sheet = spreadsheet.getSheetByName("Memos");

    if (!sheet) {
      throw new Error("Memosシートが見つかりません。");
    }

    // 同じDiscordメッセージの二重保存を防止
    const lock = LockService.getScriptLock();
    lock.waitLock(10000);

    try {
      const lastRow = sheet.getLastRow();

      if (lastRow >= 2) {
        const messageIds = sheet
          .getRange(2, 6, lastRow - 1, 1)
          .getValues()
          .flat();

        if (messageIds.includes(String(data.discord_message_id))) {
          return jsonResponse({
            success: true,
            duplicated: true,
            message: "既に保存されています。"
          });
        }
      }

      // メモ情報を作成
      const now = new Date();
      const memoId = Utilities.getUuid();

      sheet.appendRow([
        memoId,
        data.content,
        "NORMAL",
        now,
        now,
        String(data.discord_message_id),
        String(data.source_user_id),
        "",
        "ACTIVE"
      ]);

      // 保存位置を取得
      const savedRow = sheet.getLastRow();

      // 通知内容をGAS側で生成
      const notification = [
        "メモを保存しました。",
        `メモID: ${memoId}`,
        "分類: NORMAL",
        `保存先: Memos!A${savedRow}:I${savedRow}`
      ].join("\n");

      return jsonResponse({
        success: true,
        duplicated: false,
        memo_id: memoId,
        row: savedRow,
        notification: notification
      });

    } finally {
      lock.releaseLock();
    }

  } catch (error) {
    console.error(error);

    return jsonResponse({
      success: false,
      error: error.message
    });
  }
}


/**
 * JSONレスポンスを生成
 */
function jsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
