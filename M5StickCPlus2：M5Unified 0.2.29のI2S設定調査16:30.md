# M5StickCPlus2：M5Unified 0.2.29のI2S設定調査

## 調査対象
- M5StickCPlus2
- M5Unified 0.2.29
- 内蔵マイク：SPM1423
- 外部スピーカー：M5Stack Speaker 2 Hat

## 1. I2Sポート設定

M5Unifiedのソースコードでは、MicとSpeakerそれぞれに`i2s_port`の設定項目がある。

M5StickCPlus2の内蔵マイクはI2S_NUM_0を使用する設定。
Speaker 2 Hatの設定例ではI2S_NUM_1を使用する設定。

したがって、ライブラリにはマイクとスピーカーを別々のI2Sポートに割り当てる仕組みが存在する。

## 2. GPIO設定

### 内蔵マイク
- GPIO0：PDMクロック
- GPIO34：マイクデータ入力

### Speaker 2 Hat
- GPIO0：I2S LRCLK
- GPIO26：I2S BCLK
- GPIO25：I2S DATA出力

GPIO0がマイクとスピーカーの両方で使用されるため、物理的な信号競合が発生する。

## 3. 現時点の結論

- I2Sポートを分ける仕組みはM5Unifiedに存在する。
- しかし、GPIO0の競合はポートを分けるだけでは解消しない。
- GPIO0の競合を解消したうえで、マイク入力とスピーカー出力を同時に動作させられるかは未検証。
- 実際の同時動作には、I2Sポートの割り当て、GPIOの配線、ESP32のドライバ仕様を確認する必要がある。

## 4. 参照したソースコード

- `src/M5Unified.inl`
  - 内蔵マイクのGPIO設定
  - Speaker 2 HatのGPIO設定
  - I2Sポートの割り当て
- `src/utility/Mic_Class.hpp`
  - マイクのI2S設定項目
- `src/utility/Mic_Class.inl`
  - マイクのI2S初期化処理
- `src/utility/Speaker_Class.hpp`
  - スピーカーのI2S設定項目
- `src/utility/Speaker_Class.inl`
  - スピーカーのI2S初期化処理

※この調査はM5Unified 0.2.29のソースコードに基づく。ハードウェアの同時動作を実証したものではない。
