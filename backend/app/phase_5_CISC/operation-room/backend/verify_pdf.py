try:
    from pypdf import PdfReader
    
    reader = PdfReader('manual_test.pdf')
    print(f'Pages: {len(reader.pages)}')
    
    text = ''
    for page in reader.pages:
        text += page.extract_text()
    
    print(f'Extracted text length: {len(text)} chars')
    print(f'First 200 chars: {text[:200]}')
    
except ImportError:
    print('pypdf not installed, trying PyPDF2')
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader('manual_test.pdf')
        print(f'Pages: {len(reader.pages)}')
        text = ''
        for page in reader.pages:
            text += page.extract_text() or ''
        print(f'Extracted text length: {len(text)}')
        print(f'First 200 chars: {text[:200]}')
    except ImportError:
        print('Neither pypdf nor PyPDF2 installed')
        print('Installing pypdf...')
