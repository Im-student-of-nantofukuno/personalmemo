# M5StickCPlus2 全二重化調査：現在のプログラムとI2S設定

## 現在の音声通信方式

現在のプログラムはAボタンによる半二重方式。

### Aボタンを押したとき
- `Speaker.end()`
- `Mic.begin()`
- `sendMicToAndroid()`を実行
- M5のマイク音声をUDPでAndroidへ送信
- LINE来客通知も実行

### Aボタンを離したとき
- `Mic.end()`
- `Speaker.begin()`
- `receiveAndroidAudio()`を実行
- AndroidからのUDP音声をM5で再生

## M5Unified 0.2.29のI2S設定

ZIP内の`src/M5Unified.inl`を確認。

| 機能 | I2Sポート | GPIO |
|---|---|---|
| M5StickCPlus2内蔵マイク | I2S_NUM_0 | DATA=34、CLK=0 |
| Speaker 2 Hat | I2S_NUM_1 | DATA=25、BCLK=26、LRCLK=0 |

- マイクとSpeaker 2 Hatは別々のI2Sポートを使用する設定。
- ただし、GPIO0を共有している。
- GPIO0の競合はI2Sポートを分けるだけでは解決しない。

## 現時点の方針

1. 現在の半二重プログラムは維持する。
2. 初期化部分を確認する。
3. GPIO0の競合を解消する方法を調査する。
4. 別々のI2Sポートで同時録音・再生が可能か、実験用プログラムで検証する。

※I2Sポートが別々であることはソースコードで確認済み。同時動作の実証はまだ行っていない。
