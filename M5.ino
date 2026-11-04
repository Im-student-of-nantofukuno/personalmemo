#include <M5StickCPlus2.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <HTTPClient.h>

// ==================================================
// Wi-Fi
// ==================================================

const char* WIFI_SSID = "Buffalo-2G-";
const char* WIFI_PASSWORD = "";

// ==================================================
// GAS,LINE
// ==================================================
const char* GAS_URL =
  "https://script.google.com/macros/s/AK...vwa-w/exec";

const unsigned long LINE_COOLDOWN = 60000;

unsigned long lastLineSentTime = 0;
// ==================================================
// スマホIP
// ==================================================

// 192.168.1.XXX
char SMARTPHONE_IP[16] = "192.168.1.0";

// ==================================================
// UDP
// ==================================================

// M5 → Android
const uint16_t ANDROID_PORT = 5000;

// Android → M5
const uint16_t M5_PORT = 5001;

WiFiUDP udpSend;
WiFiUDP udpReceive;

// ==================================================
// Audio
// ==================================================

const uint32_t SAMPLE_RATE = 16000;

// 256 samples = 16 ms
const size_t SAMPLE_COUNT = 256;

// 256 samples × 2 bytes = 512 bytes
const size_t PACKET_SIZE =
SAMPLE_COUNT * sizeof(int16_t);

// ==================================================
// M5 → Android
// ==================================================

int16_t micBuffer[SAMPLE_COUNT];

uint32_t recordSuccessCount = 0;
uint32_t recordFailCount = 0;
uint32_t sendCount = 0;
uint32_t sendByteCount = 0;

// ==================================================
// Android → M5
// ==================================================

// 3つの再生バッファ
int16_t audioBuffer[3][SAMPLE_COUNT];

int currentBuffer = 0;

uint32_t receiveCount = 0;
uint32_t receiveByteCount = 0;
uint32_t invalidPacketCount = 0;
uint32_t playSuccessCount = 0;
uint32_t playFailCount = 0;

unsigned long lastPrint = 0;

// ==================================================
// Display
// ==================================================

void displayStatus() {

StickCP2.Display.fillScreen(BLACK);

StickCP2.Display.setCursor(10, 10);
StickCP2.Display.setTextSize(4);

StickCP2.Display.println("Anywhere Interphone");

StickCP2.Display.setTextSize(2);

StickCP2.Display.println();

StickCP2.Display.print("Android: ");
StickCP2.Display.println(SMARTPHONE_IP);

StickCP2.Display.print("M5     : ");
StickCP2.Display.println(WiFi.localIP());

StickCP2.Display.print("OUT: ");
StickCP2.Display.print(ANDROID_PORT);
StickCP2.Display.print("  IN: ");
StickCP2.Display.println(M5_PORT);

}

// ==================================================
// スマホIP設定画面
// ==================================================

void selectSmartphoneIP() {

int lastNumber = 0;

bool lastAState = false;
bool lastBState = false;

while (true) {

    StickCP2.update();

    bool currentAState = M5.BtnA.isPressed();
    bool currentBState = M5.BtnB.isPressed();


    // ==========================================
    // Bボタン
    // 末尾を+1
    // ==========================================

    if (currentBState && !lastBState) {

        lastNumber++;

        if (lastNumber > 255) {
            lastNumber = 0;
        }
    }


    // ==========================================
    // 画面表示
    // ==========================================

    StickCP2.Display.fillScreen(BLACK);

    StickCP2.Display.setCursor(10, 10);

    StickCP2.Display.setTextSize(2);

    StickCP2.Display.println("SMARTPHONE IP");

    StickCP2.Display.println();

    StickCP2.Display.setTextSize(3);

    StickCP2.Display.print("192.168.1.");
    StickCP2.Display.println(lastNumber);

    StickCP2.Display.println();

    StickCP2.Display.setTextSize(1);

    StickCP2.Display.println("B: +1");
    StickCP2.Display.println("A: SET");


    // ==========================================
    // Aボタン
    // IP決定
    // ==========================================

    if (currentAState && !lastAState) {

        snprintf(
            SMARTPHONE_IP,
            sizeof(SMARTPHONE_IP),
            "192.168.1.%d",
            lastNumber
        );

        Serial.println();
        Serial.println("==============================");
        Serial.println("SMARTPHONE IP SET");
        Serial.print("Android IP: ");
        Serial.println(SMARTPHONE_IP);
        Serial.println("==============================");
        Serial.println();

        delay(300);

        break;
    }


    lastAState = currentAState;
    lastBState = currentBState;

    delay(30);
}
}

// ==================================================
// Setup
// ==================================================

void setup() {


// ------------------------------------------------
// M5
// ------------------------------------------------

auto cfg = M5.config();

// Speaker 2 Hat
cfg.external_speaker.hat_spk2 = true;

StickCP2.begin(cfg);

StickCP2.Speaker.setVolume(200);

StickCP2.Display.setRotation(1);

Serial.begin(115200);

delay(500);


// ------------------------------------------------
// Serial
// ------------------------------------------------

Serial.println();
Serial.println("==============================");
Serial.println("M5 <-> Android VOICE CALL");
Serial.println("==============================");
Serial.println();


// ------------------------------------------------
// Wi-Fi
// ------------------------------------------------

Serial.print("Wi-Fi connecting");

WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

while (WiFi.status() != WL_CONNECTED) {

    delay(500);

    Serial.print(".");
}

Serial.println();

Serial.println("Wi-Fi connected");

Serial.print("M5 IP: ");
Serial.println(WiFi.localIP());


// ------------------------------------------------
// スマホIP設定
// ------------------------------------------------

selectSmartphoneIP();


// ------------------------------------------------
// 設定結果表示
// ------------------------------------------------

Serial.print("Android IP: ");
Serial.println(SMARTPHONE_IP);


// ------------------------------------------------
// Display
// ------------------------------------------------

displayStatus();


// ------------------------------------------------
// UDP
// ------------------------------------------------

// M5 → Android
udpSend.begin(5000);

// Android → M5
udpReceive.begin(M5_PORT);


Serial.println();

Serial.print("M5 -> Android UDP port: ");
Serial.println(ANDROID_PORT);

Serial.print("Android -> M5 UDP port: ");
Serial.println(M5_PORT);

Serial.println();

Serial.println("Starting voice communication...");

}

// ==================================================
// M5 → Android
// ==================================================

void sendMicToAndroid() {

// ------------------------------------------------
// マイク録音
// ------------------------------------------------

bool recordSuccess =
    StickCP2.Mic.record(
        micBuffer,
        SAMPLE_COUNT,
        SAMPLE_RATE
    );


if (!recordSuccess) {

    recordFailCount++;

    return;
}


recordSuccessCount++;


// ------------------------------------------------
// UDP開始
// ------------------------------------------------

int beginResult =
    udpSend.beginPacket(
        SMARTPHONE_IP,
        ANDROID_PORT
    );


if (beginResult != 1) {

    Serial.println("UDP beginPacket ERROR");

    return;
}


// ------------------------------------------------
// PCM送信
// ------------------------------------------------

size_t written =
    udpSend.write(
        (uint8_t*)micBuffer,
        PACKET_SIZE
    );


// ------------------------------------------------
// UDP終了
// ------------------------------------------------

int endResult =
    udpSend.endPacket();


if (
    endResult == 1 &&
    written == PACKET_SIZE
) {

    sendCount++;

    sendByteCount += PACKET_SIZE;

} else {

    Serial.println("UDP send ERROR");
}

}

// ==================================================
// Android → M5
// ==================================================

void receiveAndroidAudio() {

// ------------------------------------------------
// UDPパケット確認
// ------------------------------------------------

int packetSize =
    udpReceive.parsePacket();


if (packetSize <= 0) {

    return;
}


// ------------------------------------------------
// サイズ確認
// ------------------------------------------------

if (packetSize == PACKET_SIZE) {

    int len =
        udpReceive.read(
            (uint8_t*)audioBuffer[currentBuffer],
            PACKET_SIZE
        );


    if (len == PACKET_SIZE) {

        receiveCount++;

        receiveByteCount += len;


        // ----------------------------------------
        // 音声再生
        // ----------------------------------------

        bool result =
            StickCP2.Speaker.playRaw(
                audioBuffer[currentBuffer],
                SAMPLE_COUNT,
                SAMPLE_RATE,
                false,
                1,
                0,
                false
            );


        if (result) {

            playSuccessCount++;


            // 次のバッファへ
            currentBuffer++;

            if (currentBuffer >= 3) {

                currentBuffer = 0;
            }

        } else {

            playFailCount++;
        }

    } else {

        invalidPacketCount++;
    }


} else {

    // サイズが違うパケットを読み捨てる

    invalidPacketCount++;

    uint8_t dummy[64];

    while (udpReceive.available()) {

        udpReceive.read(
            dummy,
            sizeof(dummy)
        );
    }
}

}

// ==================================================
// GAS
// ==================================================
void sendLineNotification() {

    if (WiFi.status() != WL_CONNECTED) {

        Serial.println(
            "LINE: WiFi未接続"
        );

        return;
    }


    HTTPClient http;


    // ==================================================
    // GASの302リダイレクトを追従
    // ==================================================

    http.setFollowRedirects(
        HTTPC_FORCE_FOLLOW_REDIRECTS
    );


    // ==================================================
    // 通知専用URL
    // ==================================================

    String url =
        String(GAS_URL) +
        "?notify=1";


    Serial.println(
        "LINE: 来客通知をGASへ送信"
    );


    Serial.print(
        "LINE: URL = "
    );

    Serial.println(
        url
    );


    if (!http.begin(url)) {

        Serial.println(
            "LINE: http.begin失敗"
        );

        return;
    }


    // ==================================================
    // GET
    // ==================================================

    int httpCode =
        http.GET();


    Serial.print(
        "LINE通知 HTTP Code: "
    );

    Serial.println(
        httpCode
    );


    // ==================================================
    // 応答
    // ==================================================

    if (httpCode > 0) {

        String response =
            http.getString();

        Serial.print(
            "LINE通知 Response: "
        );

        Serial.println(
            response
        );
    }


    http.end();
}

// ==================================================
// Loop
// ==================================================

bool lastButtonState = false;

void loop() {

StickCP2.update();

bool currentButtonState =
    M5.BtnA.isPressed();


// ------------------------------------------------
// 受信 → 送信
// Aボタンを押した瞬間
// ------------------------------------------------

if (currentButtonState && !lastButtonState) {

    Serial.println("MODE: RECEIVE -> SEND");

    // ==============================
    // LINE通知
    // ==============================

    unsigned long now = millis();

    if (
        lastLineSentTime == 0 ||
        now - lastLineSentTime >= LINE_COOLDOWN
    ) {

        Serial.println("LINE: 通知送信");

        sendLineNotification();

        lastLineSentTime = now;

    } else {

        unsigned long remaining =
            LINE_COOLDOWN - (now - lastLineSentTime);

        Serial.print(
            "LINE: クールダウン中 残り "
        );

        Serial.print(
            remaining / 1000
        );

        Serial.println(" 秒");
    }

    // ==============================
    // 音声送信モードへ
    // ==============================

    StickCP2.Speaker.end();
    StickCP2.Mic.begin();

    delay(10);
}


// ------------------------------------------------
// 送信 → 受信
// Aボタンを離した瞬間
// ------------------------------------------------

if (
    !currentButtonState &&
    lastButtonState
) {

    Serial.println(
        "MODE: SEND -> RECEIVE"
    );


    // マイクを終了
    StickCP2.Mic.end();


    // スピーカーを開始
    StickCP2.Speaker.begin();

    delay(10);
}


// ------------------------------------------------
// 現在のモードを実行
// ------------------------------------------------

if (currentButtonState) {

    // M5 -> Android
    sendMicToAndroid();

} else {

    // Android -> M5
    receiveAndroidAudio();
}


// ボタン状態を保存
lastButtonState = currentButtonState;


// ------------------------------------------------
// Statistics
// ------------------------------------------------

if (millis() - lastPrint >= 1000) {

    Serial.println(
        "--------------------------------"
    );


    // M5 → Android
    Serial.print("SEND: ");
    Serial.print(sendCount);

    Serial.print(" / RECORD OK: ");
    Serial.print(recordSuccessCount);

    Serial.print(" / RECORD FAIL: ");
    Serial.print(recordFailCount);


    // Android → M5
    Serial.print(" / RECEIVE: ");
    Serial.print(receiveCount);

    Serial.print(" / PLAY OK: ");
    Serial.print(playSuccessCount);

    Serial.print(" / PLAY FAIL: ");
    Serial.print(playFailCount);

    Serial.print(" / INVALID: ");
    Serial.println(invalidPacketCount);


    lastPrint = millis();
}

}

