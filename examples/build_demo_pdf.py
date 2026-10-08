"""Generate a two-page, text-only DEMO PDF with the standard library."""
from pathlib import Path

DEMO_PAGES = [
    ["DEMO ONLY - fictional semiconductor supply chain, not factual research.",
     "MATERIAL_M1: demonstration resin, grade DEMO_GRADE.",
     "PRODUCT_P1: demonstration photoresist, grade DEMO_PRODUCT.",
     "COMPANY_C1: fictional photoresist producer.",
     "Scenario relationship: demonstration resin is used to make demonstration photoresist."],
    ["DEMO ONLY - all numbers below are illustrative scenario inputs.",
     "Resin price: 100 CNY/kg on 2026-10-01; 110 CNY/kg on 2026-10-08.",
     "Assumed raw_material_cost_share: 0.30 (ratio).",
     "Assumed revenue: 100000 CNY; period: 2026-DEMO.",
     "These inputs must not be presented as a real company's disclosed data."],
]


def write_pdf(path, pages):
    font_id = 3 + 2 * len(pages)
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>']
    kids = ' '.join(f'{3 + 2*i} 0 R' for i in range(len(pages)))
    objects.append(f'<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>'.encode())
    for i, lines in enumerate(pages):
        content_id = 4 + 2*i
        objects.append((f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
                        f'/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>').encode())
        commands = ['BT', '/F1 10 Tf', '40 750 Td']
        for line in lines:
            escaped = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            commands.extend([f'({escaped}) Tj', '0 -18 Td'])
        commands.append('ET')
        content = '\n'.join(commands).encode('ascii')
        objects.append(f'<< /Length {len(content)} >>\nstream\n'.encode() + content + b'\nendstream')
    objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    result = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f'{index} 0 obj\n'.encode() + obj + b'\nendobj\n')
    start = len(result)
    result.extend(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        result.extend(f'{offset:010d} 00000 n \n'.encode())
    result.extend(f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == result:
        return path
    path.write_bytes(result)
    return path


if __name__ == '__main__':
    print(write_pdf(Path(__file__).parent / 'demo_data' / 'demo.pdf', DEMO_PAGES))
