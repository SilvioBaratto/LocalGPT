import pdfplumber
import numpy as np
from cleaning import clean_text
from sklearn.cluster import KMeans
import os
import json
from pathlib import Path
import glob
import re
from extract_title import extract_titles_from_pdf

import pdfplumber
import numpy as np
from sklearn.cluster import KMeans

import pdfplumber
import re

class PDFTextExtractor:
    def __init__(self):
        self.elements = []

    def _clean_text(self, text: str) -> str:
        pattern = (
            r"(?s)Documento e informazioni per circolazione e uso esclusivamente interni[\s\u00A0\n]*"
            r"Agenzia delle Entrate[\s\u00A0\n]*"
            r"Divisione Risorse \- Direzione Centrale Tecnologie e Innovazione[\s\u00A0\n]*"
            r"Settore Infrastrutture e Sicurezza \- Ufficio Sicurezza Informatica[\s\u00A0\n]*"
            r"Via Giorgione, 159 – 00147 Roma – Tel\. 06 50543028 \-email: dc\.ti\.sicurezzainformatica@agenziaentrate\.it[\s\u00A0\n]*"
            r"(ID: \w{2}-\d{2} pag\. \d+ di \d+)?[\s\u00A0\n]*"
        )
        cleaned_text = re.sub(pattern, "", text)
        return cleaned_text.strip()

    def _extract_table_bboxes(self, page):
        table_bboxes = []
        try:
            tables = page.find_tables()
            for tbl in tables:
                table_bboxes.append(tbl.bbox)  # (x0, top, x1, bottom)
        except Exception as e:
            print(f"Error extracting table bboxes on page {page.page_number}: {e}")
        return table_bboxes

    def _find_titles_on_page(self, titles: list, page_number: int) -> list:
        """Return the subset of titles that appear on a given page, sorted by vertical position."""
        found_titles = [
            {
                'content': title['text'],
                'page': title['page'],
                'bbox': title['bbox']
            }
            for title in titles if title['page'] == page_number
        ]
        found_titles.sort(key=lambda t: t['bbox'][1])
        return found_titles

    def _is_line_in_table(self, line_bbox, table_bboxes):
        lx0, ltop, lx1, lbottom = line_bbox
        for (tx0, ttop, tx1, tbottom) in table_bboxes:
            # Check overlap
            if not (lx1 < tx0 or lx0 > tx1) and not (lbottom < ttop or ltop > tbottom):
                return True
        return False

    def _group_words_into_lines(self, words, vertical_tolerance=3):
        """
        Groups words into lines based on their vertical positions.
        
        Args:
            words (list): A list of word dicts from extract_words().
            vertical_tolerance (float): Tolerance in vertical distance to consider words on the same line.

        Returns:
            list: A list of line dicts, each with keys: text, x0, x1, top, bottom.
        """
        words = sorted(words, key=lambda w: (round(w['top']), w['x0']))

        lines = []
        current_line = {
            'text': [],
            'x0': None,
            'x1': None,
            'top': None,
            'bottom': None
        }

        for w in words:
            if current_line['top'] is None:
                # start a new line
                current_line['top'] = w['top']
                current_line['bottom'] = w['bottom']
                current_line['x0'] = w['x0']
                current_line['x1'] = w['x1']
                current_line['text'].append(w['text'])
            else:
                # Check if the current word is on the same line
                if abs(w['top'] - current_line['top']) <= vertical_tolerance:
                    # same line
                    current_line['text'].append(w['text'])
                    # update x1 and bottom if needed
                    current_line['x1'] = max(current_line['x1'], w['x1'])
                    current_line['bottom'] = max(current_line['bottom'], w['bottom'])
                else:
                    # finish current line and start a new one
                    lines.append({
                        'text': ' '.join(current_line['text']),
                        'x0': current_line['x0'],
                        'x1': current_line['x1'],
                        'top': current_line['top'],
                        'bottom': current_line['bottom']
                    })
                    current_line = {
                        'text': [w['text']],
                        'x0': w['x0'],
                        'x1': w['x1'],
                        'top': w['top'],
                        'bottom': w['bottom']
                    }

        # Append the last line if exists
        if current_line['text']:
            lines.append({
                'text': ' '.join(current_line['text']),
                'x0': current_line['x0'],
                'x1': current_line['x1'],
                'top': current_line['top'],
                'bottom': current_line['bottom']
            })

        return lines

    def _collect_all_lines_and_titles(self, pdf_path, titles):
        """
        Extracts all lines and titles from the PDF in a single pass.
        Returns a structure that can be processed afterward.
        """
        all_pages_data = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                words = page.extract_words()
                if not words:
                    # Even if no words, record empty lines for continuity
                    all_pages_data.append({
                        'page_number': page_number,
                        'lines': [],
                        'titles': []
                    })
                    continue

                lines = self._group_words_into_lines(words)
                table_bboxes = self._extract_table_bboxes(page)
                
                # Filter out lines that appear inside tables
                filtered_lines = []
                for line in lines:
                    line_bbox = (line['x0'], line['top'], line['x1'], line['bottom'])
                    if not self._is_line_in_table(line_bbox, table_bboxes):
                        filtered_lines.append(line)
                
                # Find titles on this page
                page_titles = self._find_titles_on_page(titles, page_number)

                # Store data for this page
                all_pages_data.append({
                    'page_number': page_number,
                    'lines': filtered_lines,
                    'titles': page_titles
                })
        
        return all_pages_data

    def _process_text(self, pdf_path, titles):
        """
        Extracts text between titles, handling cases where the text continues
        seamlessly across multiple pages by performing a two-pass approach.
        """
        all_pages_data = self._collect_all_lines_and_titles(pdf_path, titles)

        # Create a global ordered list of all titles found in the doc
        all_titles_in_order = []
        for page_data in all_pages_data:
            for t in page_data['titles']:
                all_titles_in_order.append({
                    "text": t['content'],
                    "page": t['page'],
                    "bbox": t['bbox']
                })

        # Sort all titles by (page, bbox_top)
        all_titles_in_order.sort(key=lambda x: (x['page'], x['bbox'][1]))

        results = []
        if not all_titles_in_order:
            # If no titles are found, return all text
            all_text = "\n".join([l['text'] for p in all_pages_data for l in p['lines']])
            results.append({
                "title": None,
                "n_pag": None,
                "text": self._clean_text(all_text)
            })
            return results

        # Assign lines to each section defined by these titles
        for i, current_title in enumerate(all_titles_in_order):
            current_title_page = current_title['page']
            current_title_top = current_title['bbox'][1]

            # Handle next title for all titles except the last
            if i + 1 < len(all_titles_in_order):
                next_title = all_titles_in_order[i + 1]
                next_title_page = next_title['page']
                next_title_top = next_title['bbox'][1]
            else:
                next_title = None  # No next title since this is the last title
                next_title_page = float('inf')
                next_title_top = float('inf')

            section_lines = []
            for page_data in all_pages_data:
                pnum = page_data['page_number']
                for line in page_data['lines']:
                    # **Special Handling for the Last Title**
                    # If this is the last title, collect all remaining text
                    if not next_title:
                        if (pnum > current_title_page) or (pnum == current_title_page and line['top'] >= current_title_top):
                            section_lines.append(line['text'])
                        continue  # Skip the rest of the logic since there's no next_title
                    
                    # **Existing Conditions**
                    # Stop collecting lines if we encounter the next title's text
                    if line['text'].strip() == next_title['text'].strip():
                        break  # Stop collecting lines as we've hit the next title

                    if (pnum > current_title_page and pnum < next_title_page):
                        # Between the two titles' pages: all lines included
                        section_lines.append(line['text'])
                    elif pnum == current_title_page:
                        # On the title's page, only include lines that come after the title
                        if line['top'] >= current_title_top:
                            section_lines.append(line['text'])
                    elif pnum == next_title_page:
                        # On the page of the next title, only include lines before next_title_top
                        if line['bottom'] < next_title_top:
                            section_lines.append(line['text'])
                    elif pnum > current_title_page and next_title_page == float('inf'):
                        # If there's no next title, all subsequent pages are included
                        section_lines.append(line['text'])

                    # If pnum > next_title_page, we have passed the boundary for this section
                    if pnum > next_title_page:
                        break

            section_text = self._clean_text("\n".join(section_lines).strip())
            results.append({
                "title": {
                    "text": current_title['text'],
                    "page": current_title['page'],
                    "bbox": current_title['bbox']
                },
                "n_pag": current_title_page,
                "text": section_text
            })

        return results
    
def align_working_directory():
    """Aligns the working directory with the script's directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

def find_files_in_data_directory(extension: str) -> list:
    """Finds files with the given extension in the 'data' directory."""
    return glob.glob(os.path.join(".", "data", f"*.{extension}"))

def main():
    try:
        # Step 1: Align working directory
        align_working_directory()

        # Step 2: Find PDF files in the 'data' directory
        pdf_files = find_files_in_data_directory("pdf")
        if not pdf_files:
            print("No PDF files found to process.")
            return

        # Step 3: Create 'extracted' directory to store results
        os.makedirs("extracted", exist_ok=True)

        # Process each PDF file
        for pdf_path in pdf_files:
            print(f"\nProcessing PDF: {pdf_path}\n")

            # Extract titles from the PDF
            titles = extract_titles_from_pdf(pdf_path)

            try:
                # Create an instance of the PDFTextExtractor
                extractor = PDFTextExtractor()

                # Extract text and titles from the PDF file
                json_content = extractor._process_text(pdf_path, titles)

                # Save the extracted JSON content to a file
                output_path = os.path.join("extracted", f"{Path(pdf_path).stem}_content.json")
                with open(output_path, "w", encoding="utf-8") as output_file:
                    json.dump(json_content, output_file, indent=4, ensure_ascii=False)
                print(f"Extracted content saved to: {output_path}")

            except Exception as e:
                print(f"Error processing {pdf_path}: {e}")

    except Exception as e:
        print(f"An error occurred during the execution of the main function: {e}")


if __name__ == "__main__":
    main()