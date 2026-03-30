#!/usr/bin/env python3
"""勤務報告画像をOCRで読み取り、CSVに変換するツール。"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import cv2
import pytesseract


@dataclass
class AttendanceRecord:
    name: str
    date: str
    clock_in: str
    clock_out: str
    source_file: str


DATE_PATTERNS = [
    re.compile(r"(?P<y>20\d{2})[/-](?P<m>\d{1,2})[/-](?P<d>\d{1,2})"),
    re.compile(r"(?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日"),
]

TIME_PATTERN = re.compile(r"(?<!\d)([01]?\d|2[0-3])[:時](?:\s*)?([0-5]\d)(?:分)?")
NAME_PATTERN = re.compile(r"(?:氏名|名前|Name)\s*[:：]\s*([\w\u3040-\u30ff\u3400-\u9fff\s]+)")


def preprocess_image(image_path: Path):
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"画像を読み込めませんでした: {image_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, None, h=15)
    binary = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        10,
    )
    return binary


def run_ocr(preprocessed_image, tesseract_lang: str) -> str:
    config = "--oem 3 --psm 6"
    text = pytesseract.image_to_string(preprocessed_image, lang=tesseract_lang, config=config)
    return text


def normalize_date(text: str) -> str:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            y = int(match.group("y"))
            m = int(match.group("m"))
            d = int(match.group("d"))
            return f"{y:04d}-{m:02d}-{d:02d}"
    return ""


def normalize_time(hour: str, minute: str) -> str:
    return f"{int(hour):02d}:{int(minute):02d}"


def extract_name(text: str) -> str:
    match = NAME_PATTERN.search(text)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()

    # ラベルがない場合、先頭数行から日本語らしい行を推定
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in lines[:6]:
        if len(line) <= 20 and re.search(r"[\u3040-\u30ff\u3400-\u9fff]", line):
            if not re.search(r"(年|月|日|出勤|退勤|時)", line):
                return line
    return ""


def extract_times(text: str) -> tuple[str, str]:
    # 優先: 出勤/退勤ラベル
    in_match = re.search(r"(?:出勤|始業|IN)\s*[:：]?\s*([01]?\d|2[0-3])[:時]\s*([0-5]\d)", text)
    out_match = re.search(r"(?:退勤|終業|OUT)\s*[:：]?\s*([01]?\d|2[0-3])[:時]\s*([0-5]\d)", text)

    if in_match:
        clock_in = normalize_time(in_match.group(1), in_match.group(2))
    else:
        clock_in = ""

    if out_match:
        clock_out = normalize_time(out_match.group(1), out_match.group(2))
    else:
        clock_out = ""

    if clock_in and clock_out:
        return clock_in, clock_out

    # フォールバック: 出現順の最初と最後
    matches = TIME_PATTERN.findall(text)
    times = [normalize_time(h, m) for h, m in matches]
    if not clock_in and times:
        clock_in = times[0]
    if not clock_out and len(times) >= 2:
        clock_out = times[-1]

    return clock_in, clock_out


def parse_attendance(text: str, source_file: str) -> AttendanceRecord:
    name = extract_name(text)
    date = normalize_date(text)
    clock_in, clock_out = extract_times(text)
    return AttendanceRecord(
        name=name,
        date=date,
        clock_in=clock_in,
        clock_out=clock_out,
        source_file=source_file,
    )


def iter_images(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"):
        for file in sorted(path.glob(ext)):
            yield file


def write_csv(records: list[AttendanceRecord], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "date", "clock_in", "clock_out", "source_file"])
        for r in records:
            writer.writerow([r.name, r.date, r.clock_in, r.clock_out, r.source_file])


def process_images(input_path: Path, output_csv: Path, tesseract_lang: str) -> None:
    records: list[AttendanceRecord] = []
    files = list(iter_images(input_path))

    if not files:
        raise FileNotFoundError(f"画像が見つかりません: {input_path}")

    for image_file in files:
        pre = preprocess_image(image_file)
        text = run_ocr(pre, tesseract_lang=tesseract_lang)
        record = parse_attendance(text, source_file=image_file.name)
        records.append(record)

    write_csv(records, output_csv)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="勤務報告画像をOCRでCSVに変換")
    parser.add_argument("input", help="画像ファイルまたは画像フォルダ")
    parser.add_argument("output", help="出力CSVパス")
    parser.add_argument(
        "--lang",
        default="jpn",
        help="Tesseract言語コード (例: jpn, jpn+eng)",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_csv = Path(args.output)

    process_images(input_path, output_csv, tesseract_lang=args.lang)
    print(f"CSVを出力しました: {output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
