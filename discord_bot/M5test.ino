#include <M5Unified.h>
#include <WiFi.h>
#include <ArduinoWebsockets.h>

using namespace websockets;
const char* WIFI_SSID = "Buffalo-2G-3180";
const char* WIFI_PASSWORD = "password";

WebsocketsClient client;

void setup() {
  M5.begin();

  Serial.begin(115200);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }

  Serial.println("Wi-Fi connected");

  // DNS確認
  IPAddress serverIP;

  if (WiFi.hostByName("gateway.discord.gg", serverIP)) {
    Serial.print("DNS OK: ");
    Serial.println(serverIP);
  } else {
    Serial.println("DNS FAILED");
  }

  // TCP接続確認（暗号化通信はまだ行わない）
  WiFiClient tcp;

  if (tcp.connect("gateway.discord.gg", 443)) {
    Serial.println("TCP OK!");
    tcp.stop();
  } else {
    Serial.println("TCP FAILED");
  }

  client.onEvent([](WebsocketsEvent event, String data) {
    Serial.print("WebSocket Event: ");
    Serial.println((int)event);
    Serial.print("Data: ");
    Serial.println(data);
  });

  client.onMessage([](WebsocketsMessage message) {
    Serial.println("Message received:");
    Serial.println(message.data());
  });

  Serial.println("Connecting to Discord Gateway...");

  bool connected = client.connect(
    "wss://gateway.discord.gg/?v=10&encoding=json"
  );

  if (connected) {
    Serial.println("WebSocket connected!");
  } else {
    Serial.println("WebSocket connection failed.");
  }
}

void loop() {
  client.poll();
  delay(10);
}
