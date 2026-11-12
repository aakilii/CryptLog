import PyPDF2

# Check simple test PDF
print('=== Simple Test PDF ===')
reader = PyPDF2.PdfReader('simple_test.pdf')
print(f'Pages: {len(reader.pages)}')
text = ''
for page in reader.pages:
    text += page.extract_text() or ''
print(f'Extracted text length: {len(text)}')
print(f'Text preview: {text[:300]}')
print()

# Check our report PDF
print('=== Report PDF ===')
reader = PyPDF2.PdfReader('test_output.pdf')
print(f'Pages: {len(reader.pages)}')
text = ''
for i, page in enumerate(reader.pages):
    page_text = page.extract_text() or ''
    text += page_text
    if i < 3:
        print(f'Page {i+1}: {len(page_text)} chars')
        print(f'  Preview: {page_text[:100]}...')
print(f'\nTotal extracted text: {len(text)} chars')
