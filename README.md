# OCR Attendance CSV Tool

紙の勤務報告をスマホ写真から読み取り、以下の項目をCSV出力するツールです。

- 名前
- 日付
- 出勤時間
- 退勤時間

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> 別途、ローカルにTesseract OCR本体と言語データ（`jpn`）のインストールが必要です。

## 使い方

単一ファイル:

```bash
python ocr_to_csv.py ./samples/report1.jpg ./out/result.csv --lang jpn
```

フォルダ一括処理:

```bash
python ocr_to_csv.py ./samples ./out/result.csv --lang jpn
```

## 出力形式

```csv
name,date,clock_in,clock_out,source_file
山田 太郎,2026-03-29,09:00,18:00,report1.jpg
```

## 抽出ロジック（MVP）

- 日付: `YYYY/MM/DD`, `YYYY-MM-DD`, `YYYY年M月D日` を認識して `YYYY-MM-DD` に正規化
- 時刻: ラベル（出勤/退勤）を優先して抽出、無ければテキスト内の最初と最後の時刻を採用
- 名前: `氏名:` / `名前:` ラベルを優先、無ければ先頭行から推定

必要に応じて、帳票フォーマットに合わせて正規表現を調整してください。
