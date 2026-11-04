# 追加調査：ESP32のI2SポートとGPIO競合

## Speaker 2 Hatの公式回路図で確認したピン

M5Stack公式のHat SPK2回路図（Sch_Hat_SPK2.pdf）より：

| M5StickCPlus2側 | Speaker 2 Hat側 |
|---|---|
| GPIO26 | BCLK |
| GPIO36/GPIO25 | SDATA |
| GPIO0 | LRCLK |

公式回路図：
https://m5stack-doc.oss-cn-shenzhen.aliyuncs.com/580/Sch_Hat_SPK2.pdf

## GPIO競合の再確認

M5StickCPlus2内蔵マイク SPM1423：

- GPIO0：CLK
- GPIO34：DATA

Speaker 2 Hat：

- GPIO0：LRCLK

したがってGPIO0を共有している。

## ESP32の音声周辺機能について

ESP32 Arduino I2S APIの資料では：

- PDM RXはI2S0のみ対応
- 通常のI2Sには送受信を同時に扱うモードがある

参考：
https://github.com/espressif/arduino-esp32/blob/master/docs/en/api/i2s.rst

## 検討中の構成

- I2S0：内蔵PDMマイク入力
- I2S1：Speaker 2 HatへのI2S出力

ただし、M5Unified 0.2.29で実現できるかは未確認。

## 未解決事項

1. M5Unified 0.2.29のMicとSpeakerが使用するI2Sポート番号
2. GPIOマトリクスを利用したLRCLKの出力先変更
3. Hat SPK2のGPIO0接続を変更せずに競合を回避できるか
4. GPIO0以外の出力候補
5. PDM入力とI2S出力を独立させた同時動作テスト

## 現在の判断

同時通話はまだ実現可能性が残っている。

GPIO0の物理的な共有が大きな課題だが、ESP32のI2S周辺機能とGPIOマトリクスを利用した独自実装を検討する価値がある。

現在動作しているトランシーバー形式のプログラムは維持し、同時通話の検証は別スケッチで行う。
