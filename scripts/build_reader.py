#!/usr/bin/env python3
"""Render curated PDF/Chinese block pairs using the accepted two-column reading style."""
import argparse
from collections import defaultdict
from html import escape
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import shutil

import pdfplumber
from PIL import Image, ImageChops

SKILL_DIR = Path(__file__).resolve().parents[1]
KINDS = {'title', 'authors', 'heading', 'paragraph', 'abstract', 'continuation',
         'footnote', 'bullet', 'step', 'step-body', 'figure', 'table', 'equation'}
TAGS = {'p', 'b', 'strong', 'em', 'i', 'sup', 'sub', 'var', 'br', 'span', 'div', 'code'}


class FragmentCheck(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.words = []

    def handle_starttag(self, tag, attrs):
        if tag not in TAGS:
            raise ValueError(f'Unsupported HTML tag <{tag}>; escape literal paper placeholders as &lt;...&gt;.')
        if any(name != 'class' for name, value in attrs):
            raise ValueError('Translation HTML accepts only class attributes.')
        if tag != 'br':
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise ValueError(f'Unbalanced translation HTML near </{tag}>.')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag != 'br':
            self.handle_endtag(tag)

    def handle_data(self, data):
        self.words.append(data)


def check_fragment(value):
    parser = FragmentCheck()
    parser.feed(value)
    parser.close()
    if parser.stack:
        raise ValueError(f'Unclosed HTML tags: {parser.stack}.')
    if not ''.join(parser.words).strip():
        raise ValueError('Translation has no readable text.')


def validate(document, pdf):
    if not isinstance(document, dict) or not isinstance(document.get('title_en'), str) or not document['title_en'].strip():
        raise ValueError('The JSON object needs a non-empty title_en.')
    rows = document.get('blocks')
    if not isinstance(rows, list) or not rows:
        raise ValueError('The JSON object needs a non-empty blocks array.')
    seen = set()
    for row in rows:
        key = row.get('id', '')
        if not isinstance(key, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', key) or key in seen:
            raise ValueError(f'Invalid or duplicate block id: {key!r}.')
        seen.add(key)
        kind = row.get('kind')
        if kind not in KINDS:
            raise ValueError(f'{key}: unknown kind {kind!r}.')
        if kind != 'equation':
            value = row.get('zh')
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{key}: the Chinese translation is missing.')
            try:
                check_fragment(value)
            except ValueError as exc:
                raise ValueError(f'{key}: {exc}') from exc
        if kind == 'heading' and row.get('level', 2) not in (2, 3):
            raise ValueError(f'{key}: use heading level 2 or 3; inline subsections can be bold paragraph prefixes.')
        source = row.get('source', [])
        if not isinstance(source, list) or (kind != 'title' and not source):
            raise ValueError(f'{key}: source needs PDF rectangles.')
        for rect in source:
            if not isinstance(rect, list) or len(rect) != 5:
                raise ValueError(f'{key}: each rectangle must be [page, x0, top, x1, bottom].')
            number, x0, top, x1, bottom = rect
            if not isinstance(number, int) or number < 1 or number > len(pdf.pages):
                raise ValueError(f'{key}: invalid source page {number!r}.')
            if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in rect[1:]):
                raise ValueError(f'{key}: PDF coordinates must be finite numbers.')
            page = pdf.pages[number - 1]
            if not (0 <= x0 < x1 <= page.width and 0 <= top < bottom <= page.height):
                raise ValueError(f'{key}: rectangle outside page {number}: {rect}.')
    return rows


def source_alt(page, rect, row, index):
    if index == 0 and row.get('en'):
        return row['en']
    _, x0, top, x1, bottom = rect
    chars = [c for c in page.chars if x0 <= c['x0'] and c['x1'] <= x1
             and top <= c['top'] and c['bottom'] <= bottom]
    text = pdfplumber.utils.extract_text(chars, x_tolerance=1.5, y_tolerance=3) if chars else ''
    return re.sub(r'\s+', ' ', re.sub(r'-\n(?=[a-z])', '', text)).strip()


def render_sources(pdf, rows, output, scale):
    tasks = defaultdict(list)
    assets = {}
    for row in rows:
        assets[row['id']] = []
        if row['kind'] == 'title':
            continue
        for index, rect in enumerate(row['source']):
            tasks[rect[0]].append((row, index, rect))
    for number in sorted(tasks):
        page = pdf.pages[number - 1]
        original = page.to_image(resolution=72 * scale, antialias=True, force_mediabox=True).original.convert('RGB')
        for row, index, rect in tasks[number]:
            _, x0, top, x1, bottom = rect
            crop = original.crop(tuple(round(v * scale) for v in (x0, top, x1, bottom)))
            if row['kind'] in ('figure', 'table'):
                ink = ImageChops.difference(crop, Image.new('RGB', crop.size, 'white'))
                bounds = ink.convert('L').point(lambda v: 255 if v > 20 else 0).getbbox()
                if bounds:
                    edge = max(2, round(2 * scale))
                    crop = crop.crop((max(0, bounds[0] - edge), max(0, bounds[1] - edge),
                                      min(crop.width, bounds[2] + edge), min(crop.height, bounds[3] + edge)))
            relative = f'assets/{row["id"]}-{index + 1:02d}.webp'
            crop.save(output / relative, 'WEBP', lossless=True, method=6)
            assets[row['id']].append({
                'src': relative, 'width': crop.width, 'height': crop.height,
                'alt': source_alt(page, rect, row, index), 'part': index,
            })
        del original
    for items in assets.values():
        items.sort(key=lambda item: item['part'])
    return assets


def image_tag(asset, alt, eager=False):
    return (f'<img src="{escape(asset["src"], quote=True)}" width="{asset["width"]}" '
            f'height="{asset["height"]}" alt="{escape(str(alt), quote=True)}" '
            f'loading="{"eager" if eager else "lazy"}" decoding="async">')


def compose(document, rows, assets):
    title = document['title_en']
    name = document.get('short_title') or title
    source_lang = escape(document.get('source_lang', 'en'), quote=True)
    parts = [
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,">',
        '<meta name="description" content="论文原文与中文译文逐段对照，保留原始公式和图表。">',
        '<title>' + escape(name) + ' — 原文与中文对照</title>',
        '<link rel="stylesheet" href="reader.css"></head><body>',
        '<main aria-label="论文原文与中文逐段对照">',
    ]
    for index, row in enumerate(rows):
        kind = row['kind']
        level = row.get('level', 2)
        level_attr = f' data-level="{level}"' if kind == 'heading' else ''
        parts.append(f'<section class="pair {kind}" id="{row["id"]}"{level_attr}>')
        parts.append(f'<div class="cell original" lang="{source_lang}"><div class="inner">')
        if kind == 'title':
            parts.append(f'<h1 lang="{source_lang}">{escape(title)}</h1>')
        else:
            for asset in assets[row['id']]:
                if kind == 'equation':
                    alt = f'Equation ({row.get("number", "")}): {row.get("label", asset["alt"])}'
                elif kind in ('figure', 'table'):
                    alt = f'{kind.title()} {row.get("number", "")}. {asset["alt"]}'
                else:
                    alt = asset['alt']
                parts.append('<div class="source-fragment">' + image_tag(asset, alt, index < 6) + '</div>')
        parts.append('</div></div><div class="cell translation" lang="zh-CN"><div class="inner">')
        if kind == 'equation':
            for asset in assets[row['id']]:
                alt = f'公式（{row.get("number", "")}）：{row.get("label", asset["alt"])}'
                parts.append(image_tag(asset, alt))
        elif kind == 'title':
            parts.append('<h1>' + row['zh'] + '</h1>')
        elif kind == 'heading':
            parts.append(f'<h{level}>' + row['zh'] + f'</h{level}>')
        elif re.search(r'<(?:p|div)(?:\s|>)', row['zh']):
            parts.append(row['zh'])
        else:
            parts.append('<p>' + row['zh'] + '</p>')
        parts.append('</div></div></section>')
    parts.append('</main></body></html>')
    return '\n'.join(parts)


def build(pdf_path, blocks_path, output, scale=4):
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('Scale must be positive and finite.')
    pdf_path = Path(pdf_path).expanduser().resolve()
    blocks_path = Path(blocks_path).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    document = json.loads(blocks_path.read_text(encoding='utf-8'))
    with pdfplumber.open(pdf_path) as pdf:
        rows = validate(document, pdf)
        (output / 'assets').mkdir(parents=True, exist_ok=True)
        assets = render_sources(pdf, rows, output, scale)
    shutil.copyfile(SKILL_DIR / 'assets/reader.css', output / 'reader.css')
    (output / 'index.html').write_text(compose(document, rows, assets), encoding='utf-8')
    return {
        'output': str(output / 'index.html'), 'blocks': len(rows),
        'source_crops': sum(map(len, assets.values())),
        'figures': sum(row['kind'] == 'figure' for row in rows),
        'tables': sum(row['kind'] == 'table' for row in rows),
        'equations': sum(row['kind'] == 'equation' for row in rows),
        'source_pages': sorted({r[0] for row in rows for r in row.get('source', [])}),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', required=True)
    parser.add_argument('--blocks', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--scale', type=float, default=4)
    args = parser.parse_args()
    try:
        result = build(args.pdf, args.blocks, args.output, args.scale)
    except (ValueError, OSError) as exc:
        parser.exit(2, f'Error: {exc}\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
