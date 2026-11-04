# M5StickCPlus2 同時通話に関するハードウェア調査

## 目的
M5StickCPlus2とスマートフォン間の音声通信を、現在のトランシーバー形式から同時通話（全二重通信）に変更できるか調査する。

## 現在の使用部品
- M5StickCPlus2
- 内蔵マイク：SPM1423
- 外部スピーカー：M5StickC Plus用 Speaker 2 Hat（U055-B）
- スピーカーアンプ：MAX98357A
- Aボタン・Bボタン
- Wi-Fi

加速度センサー、ジャイロセンサーなどは使用予定なし。

## 開発環境
- M5StickCPlus2 by M5Stack：1.0.1
- M5Unified by M5Stack：0.2.29

## 内蔵マイクのGPIO
M5StickCPlus2公式回路図より：

| GPIO | 信号 |
|---|---|
| GPIO0 | マイク CLK |
| GPIO34 | マイク DATA |

マイク：SPM1423（PDM方式）

## Speaker 2 HatのGPIO
M5Stack公式回路図より：

| GPIO | 信号 |
|---|---|
| GPIO26 | BCLK |
| GPIO25 / GPIO36表記 | SDATA |
| GPIO0 | LRCLK |

アンプ：MAX98357A（I2S方式）

## 発見した問題
GPIO0がマイクとSpeaker 2 Hatで共有されている。

- マイク側：PDM CLK
- スピーカー側：I2S LRCLK

異なるクロック信号を同じGPIOから同時に出力することはできないため、現状の配線のままでは同時使用に大きな制約がある。

I2Sコントローラーの系統を分けるだけでは、この物理的なGPIO競合は解消されない。

## 今後の調査項目
1. ESP32-PICO-V3-02でPDM入力とI2S出力を独立して動作させられるか
2. Speaker 2 HatのLRCLKをGPIO0以外に変更できるか
3. M5StickCPlus2の空きGPIOを確認
4. M5Unified 0.2.29のマイク・スピーカー内部実装を確認
5. 独自実装で同時動作できる可能性を検証

## 注意事項
- 現在動作しているトランシーバー形式のプログラムは変更前にバックアップする。
- 検証は本番プログラムとは別のスケッチで行う。
- GPIO競合の解消だけで同時通話が完成するわけではない。音声バッファ、UDP通信、遅延、エコーなども別途検証する。

## 公式資料
- M5StickCPlus2公式資料：https://docs.m5stack.com/ja/core/StickC-Plus2
- M5StickCPlus2回路図：https://m5stack.oss-cn-shenzhen.aliyuncs.com/resource/docs/static/pdf/static/ja/core/M5StickC%20PLUS2.pdf
- Speaker 2 Hat公式資料：https://docs.m5stack.com/ja/hat/Hat-SPK2
- Speaker 2 Hat回路図：https://m5stack-doc.oss-cn-shenzhen.aliyuncs.com/580/Sch_Hat_SPK2.pdf
