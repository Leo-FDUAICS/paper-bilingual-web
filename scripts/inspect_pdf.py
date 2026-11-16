#!/usr/bin/env python3
"""Export page text, line coordinates, and selected page renders for bilingual mapping."""
import argparse
import json
from pathlib import Path
import pdfplumber


def page_selection(value, count):
    selected = set()
    for term in value.split(','):
        term = term.strip()
        if not term:
            continue
        if '-' in term:
            first, last = map(int, term.split('-', 1))
            if first > last:
                raise ValueError('Page ranges must be ascending.')
            selected.update(range(first, last + 1))
        else:
            selected.add(int(term))
    if any(n < 1 or n > count for n in selected):
        raise ValueError(f'Rendered pages must be between 1 and {count}.')
    return selected


def inspect(pdf_path, output, render_pages='1', dpi=135):
    pdf_path = Path(pdf_path).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    if dpi <= 0:
        raise ValueError('DPI must be positive.')
    with pdfplumber.open(pdf_path) as pdf:
        selected = page_selection(render_pages, len(pdf.pages))
        for directory in ['text', 'lines', 'pages']:
            (output / directory).mkdir(parents=True, exist_ok=True)
        inventory = {'filename': pdf_path.name, 'page_count': len(pdf.pages), 'pages': []}
        for number, page in enumerate(pdf.pages, 1):
            text = page.extract_text(layout=True, x_tolerance=1.5, y_tolerance=3) or ''
            (output / 'text' / f'page-{number:03d}.txt').write_text(text, encoding='utf-8')
            lines = []
            for line in page.extract_text_lines(x_tolerance=1.5, y_tolerance=3):
                lines.append({
                    'text': line['text'],
                    'bbox': [round(line[k], 3) for k in ['x0', 'top', 'x1', 'bottom']],
                    'font_sizes': sorted({round(c['size'], 2) for c in line['chars']}),
                })
            (output / 'lines' / f'page-{number:03d}.json').write_text(
                json.dumps(lines, ensure_ascii=False, indent=2), encoding='utf-8')
            inventory['pages'].append({
                'page': number, 'width': page.width, 'height': page.height,
                'characters': len(page.chars), 'raster_objects': len(page.images),
            })
            if number in selected:
                page.to_image(resolution=dpi, antialias=True, force_mediabox=True).save(
                    output / 'pages' / f'page-{number:03d}.png')
        (output / 'inventory.json').write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'page_count': inventory['page_count'], 'rendered_pages': sorted(selected),
            'output': str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--render-pages', default='1', help='One-based pages, e.g. 1,3-5; empty for text only.')
    parser.add_argument('--dpi', type=float, default=135)
    args = parser.parse_args()
    try:
        result = inspect(args.pdf, args.output, args.render_pages, args.dpi)
    except (ValueError, OSError) as exc:
        parser.exit(2, f'Error: {exc}\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
