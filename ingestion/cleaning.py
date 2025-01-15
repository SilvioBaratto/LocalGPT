def clean_text( 
        page_number, 
        page_text
    ) -> str:
    """
    Cleans the extracted text by:
    - Converting it to lowercase
    - Removing headers from the first page
    - Removing footers from all pages
    This process produces cleaner text for subsequent processing.
    """
    text = page_text.lower()
    if page_number == 1:
        text = _remove_first_page_header(text)
    text = _remove_footer(text)
    return text

def _remove_first_page_header(
        text
    ) -> str:
    """
    Removes a known header string from the first page's text if present.
    """
    header = "security office information security"
    index = text.find(header)
    if index != -1:
        text = text[index + len(header):]
    return text

def _remove_footer(
        text
    ) -> str:
    """
    Removes a known footer from the text if present.
    """
    footer = "document and information for internal circulation and exclusive use"
    index = text.find(footer)
    if index != -1:
        text = text[:index]
    return text
