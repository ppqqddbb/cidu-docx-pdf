from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ComparisonConfig:
    min_anchor_chars: int = 8
    min_list_body_anchor_chars: int = 1
    min_section_anchor_chars: int = 1
    exact_anchor_enabled: bool = True
    fuzzy_anchor_enabled: bool = False
    fuzzy_anchor_threshold: float = 0.92

    char_weight: float = 0.45
    ngram_weight: float = 0.20
    number_weight: float = 0.15
    length_weight: float = 0.10
    position_weight: float = 0.0

    match_threshold: float = 0.48
    insert_cost: float = 0.92
    delete_cost: float = 0.92
    merge_penalty: float = 0.035
    max_merge_blocks: int = 3

    large_replace_min_blocks: int = 2
    large_replace_rescue_threshold: float = 0.60
    common_ratio_threshold: float = 0.60
    common_content_threshold: float = 0.45
    replace_rescue_threshold: float = 0.40
    key_value_match_enabled: bool = True
    strip_markdown_formatting: bool = True
    strip_html_formatting: bool = True
    strip_list_number_for_matching: bool = True
    dp_full_matrix_limit: int = 20000
    adaptive_dp_band_width: int = 64
    normalize_numeric_format_for_matching: bool = True
    report_numeric_format_change: bool = False

    header_footer_enabled: bool = True
    compare_page_auxiliary: bool = True
    compare_whitespace: bool = False
    compare_punctuation: bool = True

    debug_enabled: bool = False
    debug_dir: Path | None = None

    min_quality_chars: int = 100
    pages_without_text_warning_ratio: float = 0.5
    short_block_chars: int = 4
