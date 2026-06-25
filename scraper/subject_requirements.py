"""
山东省普通高校招生专业选考科目要求导入。

数据源：
- 山东省教育招生考试院《2024通用版普通高校拟在山东招生专业（类）选考科目要求》
- 适用于 2025 年和 2026 年参加高考的考生

说明：
该数据只用于判断专业是否满足考生选科，不参与分数/位次换算，也不生成
任何 2026 院校录取线。
"""
import os
import re
import sys
import tempfile
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from pypdf import PdfReader

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import bulk_insert_subject_requirements, init_db


SOURCE_VERSION = "2024通用版"
APPLIES_TO = "2025,2026"
NOTICE_URL = "https://www.sdzk.cn/NewsInfo.aspx?NewsID=6819"
OFFICIAL_PDFS = {
    "本科": "https://www.sdzk.cn/Floadup/file/20250317/6387782010007663213616549.pdf",
    "专科": "https://www.sdzk.cn/Floadup/file/20250317/6387782010723289868336614.pdf",
}
SUBJECTS = ("思想政治", "历史", "地理", "物理", "化学", "生物")
SUBJECT_PATTERN = "|".join(SUBJECTS)

REQUIREMENT_RE = re.compile(
    r"(不提科目要求|"
    r"(?:(?:思想政治|历史|地理|物理|化学|生物)"
    r"(?:,(?:思想政治|历史|地理|物理|化学|生物))*)"
    r"\(\d门科目考生(?:均须|必须)选考.*?方\s*可\s*报\s*考\))",
    re.S,
)
ROW_START_RE = re.compile(
    r"^(\d{5})\s+(.+?)\s+([A-Z0-9]{3,8})(?:\s+(.*))?$"
)
HEADER_MARKERS = (
    "2024通用版普通高校拟在山东招生专业",
    "（适用于2025年和2026年参加高考的考生）",
    "院校",
    "代码 院校名称 专业",
    "代码 专业（类） 选考科目要求 院校所",
    "在省份",
)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def extract_required_subjects(requirement_text: str) -> str:
    if not requirement_text or "不提科目要求" in requirement_text:
        return ""
    subjects = []
    for subject in re.findall(SUBJECT_PATTERN, requirement_text):
        if subject not in subjects:
            subjects.append(subject)
    return ",".join(subjects)


def download_pdf(url: str) -> str:
    """Download a source PDF to a temp file and return its path."""
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=60,
        verify=False,
    )
    response.raise_for_status()
    fd, path = tempfile.mkstemp(suffix=".pdf")
    with os.fdopen(fd, "wb") as fh:
        fh.write(response.content)
    return path


def iter_pdf_blocks(path: str) -> Iterable[Dict[str, object]]:
    """Yield raw row blocks from the official text PDF."""
    reader = PdfReader(path)
    current = None

    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = normalize_space(raw_line)
            if not line:
                continue
            if any(marker in line for marker in HEADER_MARKERS):
                continue

            match = ROW_START_RE.match(line)
            if match:
                if current:
                    yield current
                current = {
                    "school_code": match.group(1),
                    "school_name": match.group(2),
                    "major_code": match.group(3),
                    "parts": [match.group(4) or ""],
                    "page": page_index,
                }
            elif current:
                current["parts"].append(line)

    if current:
        yield current


def parse_block(
    block: Dict[str, object],
    education_level: str,
    source_url: str,
) -> Tuple[Optional[Dict[str, object]], Optional[str]]:
    blob = normalize_space(" ".join(part for part in block["parts"] if part))
    match = REQUIREMENT_RE.search(blob)
    if not match:
        return None, blob

    major_name = normalize_space(blob[:match.start()])
    requirement_text = normalize_space(match.group(1))
    province_tail = normalize_space(blob[match.end():])
    province = province_tail.split()[0] if province_tail else None

    return {
        "source_version": SOURCE_VERSION,
        "applies_to": APPLIES_TO,
        "education_level": education_level,
        "school_code": block["school_code"],
        "school_name": block["school_name"],
        "major_code": block["major_code"],
        "major_name": major_name,
        "requirement_text": requirement_text,
        "required_subjects": extract_required_subjects(requirement_text),
        "province": province,
        "source_url": source_url,
    }, None


def parse_pdf(path: str, education_level: str, source_url: str) -> List[Dict[str, object]]:
    records = []
    failures = []
    for block in iter_pdf_blocks(path):
        record, failure = parse_block(block, education_level, source_url)
        if record:
            records.append(record)
        else:
            failures.append((block, failure))

    if failures:
        sample = "; ".join(
            f"{item[0]['school_code']} {item[0]['school_name']} {item[0]['major_code']}: {item[1][:80]}"
            for item in failures[:3]
        )
        raise ValueError(
            f"{education_level}选科要求解析失败 {len(failures)} 条，示例：{sample}"
        )

    return records


def load_records(paths: Optional[Dict[str, str]] = None) -> List[Dict[str, object]]:
    """Load all official requirement records from local paths or official URLs."""
    all_records = []
    temp_paths = []

    try:
        for level, url in OFFICIAL_PDFS.items():
            path = paths.get(level) if paths else None
            if not path:
                print(f"[选科要求] 下载{level}官方PDF...")
                path = download_pdf(url)
                temp_paths.append(path)

            print(f"[选科要求] 解析{level}PDF: {path}")
            records = parse_pdf(path, level, url)
            all_records.extend(records)
            print(f"[选科要求] {level}解析完成：{len(records)} 条")
    finally:
        for path in temp_paths:
            try:
                os.unlink(path)
            except OSError:
                pass

    return all_records


def save_records(records: List[Dict[str, object]]) -> int:
    init_db()
    return bulk_insert_subject_requirements(records)


def run(paths: Optional[Dict[str, str]] = None):
    records = load_records(paths)
    saved = save_records(records)
    print(f"[选科要求] 导入完成：{len(records)} 条，数据库写入/更新 {saved} 条")
    return {"records": len(records), "saved": saved}


if __name__ == "__main__":
    args = sys.argv[1:]
    local_paths = {}
    if len(args) >= 1:
        local_paths["本科"] = args[0]
    if len(args) >= 2:
        local_paths["专科"] = args[1]
    run(local_paths or None)
