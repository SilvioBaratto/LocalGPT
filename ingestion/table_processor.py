import re
from typing import Any, List, Optional, Tuple, Dict
import pdfplumber
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar
import pandas as pd
import json
import os
import math
from pathlib import Path
import glob

# If you have a custom module for extracting titles, uncomment and ensure it's available
from extract_title import extract_titles_from_pdf

# Helper Functions

def _classify_table_type(data: list) -> str:
    """
    Classifies a table as either a 'Key-Value Table' or 'Row-by-Column Table' based on its structure.

    Args:
    - data (list): Table data as a list of lists.

    Returns:
    - str: The type of table ('Key-Value Table' or 'Row-by-Column Table').
    """
    # Check if the table has exactly two columns
    if len(data[0]) == 2:
        # Analyze the content of the first row
        first_row = data[0]
        second_row = data[1] if len(data) > 1 else []

        # If the first row looks like keys and the second row has longer text, classify as key-value
        if is_key_value_pair(first_row, second_row):
            return "Key-Value Table"

        # Otherwise, classify as row-by-column
        return "Row-by-Column Table"
    
    if len(data[0]) == 1:
        return "Row-Only Table"

    # Default classification for tables with more than two columns
    return "Row-by-Column Table"

def is_key_value_pair(first_row: list, second_row: list) -> bool:
    """
    Determines if the first and second rows form a key-value pair.

    Args:
    - first_row (list): The first row of the table.
    - second_row (list): The second row of the table.

    Returns:
    - bool: True if the rows represent a key-value pair, False otherwise.
    """
    # Check if the first column has shorter text and the second column has longer text
    if len(first_row[0]) < len(first_row[1]) and (not second_row or len(second_row[0]) < len(second_row[1])):
        return True
    return False

def _convert_row_column_table_to_json(df: pd.DataFrame, metadata: Optional[Dict] = None) -> List[Dict]:
    """
    Convert a row-by-column DataFrame to JSON.

    Args:
    - df (pd.DataFrame): The DataFrame to convert.
    - metadata (Optional[Dict]): Additional metadata.

    Returns:
    - List[Dict]: The JSON representation of the table.
    """
    return df.to_dict(orient='records')

def _convert_key_value_table_to_json(df: pd.DataFrame, metadata: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Convert a key-value DataFrame to JSON.

    Args:
    - df (pd.DataFrame): The DataFrame to convert.
    - metadata (Optional[Dict]): Additional metadata.

    Returns:
    - Dict[str, Any]: The JSON representation of the table.
    """
    return dict(zip(df['Key'], df['Value']))

def _convert_row_only_table_to_json(df: pd.DataFrame, metadata: Optional[Dict] = None) -> List[str]:
    """
    Convert a row-only DataFrame to JSON.

    Args:
    - df (pd.DataFrame): The DataFrame to convert.
    - metadata (Optional[Dict]): Additional metadata.

    Returns:
    - List[str]: The JSON representation of the table.
    """
    return df['Row Content'].tolist()

# Main Class Implementation

class PDFTableExtractor:
    def __init__(self, snap_tolerance: int = 10, footer_threshold: int = 50):
        """
        Initializes the PDFTableExtractor with the given parameters.

        Args:
        - snap_tolerance (int): Tolerance for snapping table lines.
        - footer_threshold (int): Threshold to identify footers.
        """
        self._snap_tolerance = snap_tolerance
        self._footer_threshold = footer_threshold

    def _text_extraction(self, element: LTTextContainer) -> Tuple[str, List[Tuple[str, float]]]:
        """
        Extracts text from a layout element, along with its formatting information.

        Args:
            element (LTTextContainer): A layout element from pdfminer.

        Returns:
            Tuple[str, List[Tuple[str, float]]]: Extracted text and a list of unique formatting attributes.
        """
        try:
            line_text = element.get_text()
            line_formats = []
            for text_line in element:
                if isinstance(text_line, LTTextContainer):
                    for character in text_line:
                        if isinstance(character, LTChar):
                            line_formats.append((character.fontname, character.size))
            format_per_line = list(set(line_formats))
            return line_text, format_per_line
        except Exception as e:
            raise Exception(f"Error in text extraction: {e}")

    def _merge_table(
        self, 
        page_num: int, 
        table: pdfplumber.table.Table, 
        prev_page_num: Optional[int], 
        prev_table: Optional[Dict[str, Any]], 
        page_content: pdfplumber.page.Page,
        text_between: bool
    ) -> Tuple[pd.DataFrame, str, bool, Optional[Dict[str, Any]]]:
        """
        Merges tables that should be combined based on the presence of intervening text.
        
        Args:
        - page_num (int): Current page number.
        - table (pdfplumber.table.Table): Current table object from pdfplumber.
        - prev_page_num (Optional[int]): Previous page number where a table was found.
        - prev_table (Optional[Dict[str, Any]]): Previous table data.
        - page_content (pdfplumber.page.Page): Current page content from pdfplumber.
        - text_between (bool): Indicator if there's text between the current and previous table.
        
        Returns:
        - Tuple containing:
            - pd.DataFrame: Merged or current table DataFrame.
            - str: Type of the table.
            - bool: Indicator if merged from previous.
            - Optional[Dict[str, Any]]: New previous table data.
        """
        try:
            # Extract table data as list of lists
            data_table = table.extract()
            if not data_table:
                return pd.DataFrame(), "Unknown", False, prev_table

        
            table_bbox_0 = round(table.bbox[0]) if table.bbox[0] % 1 < 0.5 else math.ceil(table.bbox[0])
            table_bbox_2 = round(table.bbox[2]) if table.bbox[2] % 1 < 0.5 else math.ceil(table.bbox[2])
            merged_from_previous = False

            if prev_table and not text_between:
                prev_table_bbox_0 = round(prev_table["bbox"][0]) if prev_table["bbox"][0] % 1 < 0.5 else math.ceil(prev_table["bbox"][0])

                if (
                    prev_page_num is not None
                    and prev_page_num == page_num - 1
                    and prev_table_bbox_0 == table_bbox_0
                ):
                    prev_data_table = prev_table["data"]
                    # Merge the tables by concatenating the data
                    data_table = prev_data_table + data_table
                    merged_from_previous = True

            df = pd.DataFrame(data_table)
            df = df.replace('\n', '  ', regex=True)

            table_type = _classify_table_type(df.values.tolist())
            if table_type == "Row-by-Column Table":
                header = df.iloc[0]
                df = df[1:]
                df.columns = header
                df = df.reset_index(drop=True)
            elif table_type == "Key-Value Table":
                df = pd.DataFrame(df.values.tolist(), columns=["Key", "Value"])
            elif table_type == "Row-Only Table":
                df = pd.DataFrame(df.values.tolist(), columns=["Row Content"])
            else:
                df = pd.DataFrame(data_table)

            if merged_from_previous:
                # Update the bounding box to cover both tables
                new_bbox = (
                    table_bbox_0, 
                    min(prev_table["bbox"][1], table.bbox[1]), 
                    table_bbox_2, 
                    max(prev_table["bbox"][3], table.bbox[3])
                )
                # Create a new dictionary to represent the merged table
                merged_table = {
                    "data": data_table,
                    "bbox": new_bbox
                }
                return df, table_type, merged_from_previous, merged_table
            else:
                # Create a new dictionary to represent the current table
                current_table = {
                    "data": data_table,
                    "bbox": table.bbox
                }
                return df, table_type, merged_from_previous, current_table

        except Exception as e:
            raise Exception(f"Error in merging tables: {e}")

    def _clean_text(self, text: str) -> str:
        """
        Cleans the extracted text by removing unwanted patterns.

        Args:
        - text (str): The raw extracted text.

        Returns:
        - str: Cleaned text.
        """
        pattern = re.compile(
            r"(?s)Documento e informazioni per circolazione e uso esclusivamente interni[\s\u00A0\n]*"
            r"Agenzia delle Entrate[\s\u00A0\n]*"
            r"Divisione Risorse\s*-\s*Direzione Centrale Tecnologie e Innovazione[\s\u00A0\n]*"
            r"Settore Infrastrutture e Sicurezza\s*-\s*Ufficio Sicurezza Informatica[\s\u00A0\n]*"
            r"Via Giorgione,\s*159\s*–\s*00147 Roma\s*–\s*Tel\.\s*06 50543028\s*-\s*email:\s*dc\.ti\.sicurezzainformatica@agenziaentrate\.it[\s\u00A0\n]*"
            r"(ID:\s*\w{2}-\d{2}\s*pag\.\s*\d+\s*di\s*\d+)?[\s\u00A0\n]*",
            re.MULTILINE
        )
        cleaned_text = pattern.sub("", text)
        return cleaned_text

    def _remove_text_from_page(self, page: pdfplumber.page.Page, cleaned_text: str) -> pdfplumber.page.Page:
        """
        Removes the cleaned text from the page content to isolate tables.

        Args:
        - page (pdfplumber.page.Page): The current page object from pdfplumber.
        - cleaned_text (str): The text to remove.

        Returns:
        - pdfplumber.page.Page: Modified page content with text removed.
        """
        # pdfplumber does not provide a direct method to remove text,
        # so this function can be customized based on specific requirements.
        # For simplicity, we'll return the page as-is.
        return page
    
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
                # Start a new line
                current_line['top'] = w['top']
                current_line['bottom'] = w['bottom']
                current_line['x0'] = w['x0']
                current_line['x1'] = w['x1']
                current_line['text'].append(w['text'])
            else:
                # Check if the current word is on the same line
                if abs(w['top'] - current_line['top']) <= vertical_tolerance:
                    # Same line
                    current_line['text'].append(w['text'])
                    # Update x1 and bottom if needed
                    current_line['x1'] = max(current_line['x1'], w['x1'])
                    current_line['bottom'] = max(current_line['bottom'], w['bottom'])
                else:
                    # Finish current line and start a new one
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

    def _extract_table_bboxes(self, page):
        """
        Extracts bounding boxes of tables in the page.
        
        Args:
            page (pdfplumber.page.Page): The PDF page object.

        Returns:
            list: A list of bounding boxes for tables.
        """
        table_bboxes = []
        try:
            tables = page.find_tables()
            for tbl in tables:
                table_bboxes.append(tbl.bbox)  # (x0, top, x1, bottom)
        except Exception as e:
            print(f"Error extracting table bboxes on page {page.page_number}: {e}")
        return table_bboxes

    def _is_line_in_table(self, line_bbox, table_bboxes):
        """
        Determines if a line is within any of the table bounding boxes.
        
        Args:
            line_bbox (tuple): The bounding box of the line (x0, top, x1, bottom).
            table_bboxes (list): A list of table bounding boxes.

        Returns:
            bool: True if the line is within a table, False otherwise.
        """
        for table_bbox in table_bboxes:
            tx0, ttop, tx1, tbottom = table_bbox
            lx0, ltop, lx1, lbottom = line_bbox
            # Check overlap
            if not (lx1 < tx0 or lx0 > tx1) and not (lbottom < ttop or ltop > tbottom):
                return True
        return False

    def _clean_text(self, text: str) -> str:
        """
        Cleans the extracted text by removing unwanted patterns and lines.

        Args:
            text (str): The raw extracted text.

        Returns:
            str: Cleaned text.
        """
        # Define a list of regex patterns to remove unwanted text
        patterns = [
            re.compile(r"Documento e informazioni per circolazione e uso esclusivamente interni", re.IGNORECASE),
            re.compile(r"Agenzia delle Entrate", re.IGNORECASE),
            re.compile(r"Divisione Risorse\s*-\s*Direzione Centrale Tecnologie e Innovazione", re.IGNORECASE),
            re.compile(r"Settore Infrastrutture e Sicurezza\s*-\s*Ufficio Sicurezza Informatica", re.IGNORECASE),
            re.compile(r"Via Giorgione,\s*159\s*–\s*00147 Roma\s*–\s*Tel\.\s*06\s*\d{8}\s*-\s*email:\s*[\w\.-]+@[\w\.-]+", re.IGNORECASE),
            re.compile(r"ID:\s*\w{2}-\d{2}\s*pag\.\s*\d+\s*di\s*\d+", re.IGNORECASE),
            re.compile(r"allegato a AGE\.AGEDC\d{3}\.REGISTRO UFFICIALE\.\d{7}\.\d{2}-\d{2}-\d{4}\.U", re.IGNORECASE),
            re.compile(r"_{5,}", re.IGNORECASE),  # Lines with multiple underscores
            re.compile(r"-{5,}", re.IGNORECASE),  # Lines with multiple hyphens
            # Add more patterns as needed
        ]

        cleaned_text = text
        for pattern in patterns:
            cleaned_text = pattern.sub("", cleaned_text)
        
        # Remove extra spaces and trim
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        return cleaned_text

    def _is_unwanted_line(self, text: str) -> bool:
        """
        Determines if a line is unwanted based on predefined keywords or patterns.

        Args:
            text (str): The text of the line.

        Returns:
            bool: True if the line is unwanted, False otherwise.
        """
        # Define a list of unwanted keywords or phrases
        unwanted_keywords = [
            "documento e informazioni per circolazione",  # Partial match
            "agenzia delle entrate",
            "divisione risorse",
            "direzione centrale tecnologie e innovazione",
            "settore infrastrutture e sicurezza",
            "ufficio sicurezza informatica",
            "via giorgione",
            "id:",
            "allegato a age.agedc",
            # Add more keywords as needed
        ]

        text_lower = text.lower()
        for keyword in unwanted_keywords:
            if keyword in text_lower:
                return True
        return False

    def _collect_all_lines(self, pdf_path):
        """
        Extracts all lines and titles from the PDF in a single pass.
        Returns a structure that can be processed afterward.
        """
        all_pages_data = []
        header_lines = {}
        footer_lines = {}

        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                words = page.extract_words()
                if not words:
                    # Even if no words, record empty lines for continuity
                    all_pages_data.append({
                        'page_number': page_number,
                        'lines': []
                    })
                    continue

                lines = self._group_words_into_lines(words)
                table_bboxes = self._extract_table_bboxes(page)

                # Filter out lines that appear inside tables and clean the text
                filtered_lines = []
                for line in lines:
                    line_bbox = (line['x0'], line['top'], line['x1'], line['bottom'])
                    if self._is_line_in_table(line_bbox, table_bboxes):
                        continue  # Skip lines inside tables

                    # Clean the text
                    cleaned_text = self._clean_text(line['text'])

                    if not cleaned_text:
                        continue  # Skip empty lines after cleaning

                    # Additional filtering based on content
                    if self._is_unwanted_line(cleaned_text):
                        continue  # Skip unwanted lines based on keywords

                    # Optionally, remove headers/footers based on position
                    page_height = page.height
                    top_margin = 50  # Adjust as needed
                    bottom_margin = 50  # Adjust as needed

                    if line['top'] < top_margin:
                        continue  # Likely a header
                    if (page_height - line['bottom']) < bottom_margin:
                        continue  # Likely a footer

                    # Append the cleaned and filtered line
                    filtered_lines.append({
                        'text': cleaned_text,
                        'x0': line['x0'],
                        'x1': line['x1'],
                        'top': line['top'],
                        'bottom': line['bottom']
                    })

                # Store data for this page
                all_pages_data.append({
                    'page_number': page_number,
                    'lines': filtered_lines,
                })

        return all_pages_data

    def _process_tables(self, file_path: str) -> List[dict]:
        """
        Processes tables in the PDF file, merging them based on the presence of intervening text.
        Stops merging if text is detected on the current page after processing a table.

        Args:
        - file_path (str): Path to the PDF file.

        Returns:
        - List[dict]: A list of JSON objects representing the processed tables.
        """
        try:
            all_pages_data = self._collect_all_lines(file_path)
            merged_tables = []
            prev_table = None
            prev_page_num = None

            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text()
                    cleaned_text = self._clean_text(page_text) if page_text else ""
                    page_content = self._remove_text_from_page(page, cleaned_text)
                    tables = page_content.find_tables(
                        table_settings={"snap_tolerance": self._snap_tolerance}
                    )

                    # Extract all text lines with their positions
                    lines = all_pages_data[page_num - 1]['lines'] if page_num - 1 < len(all_pages_data) else []

                    if not tables:
                        continue

                    # Sort tables top to bottom based on their 'top' position
                    sorted_tables = sorted(tables, key=lambda tbl: tbl.bbox[1])

                    for table_num, table in enumerate(sorted_tables):
                        try:
                            text_between = False  # Default to no intervening text

                            # Merge tables or process them individually
                            df, table_type, merged_from_previous, new_prev_table = self._merge_table(
                                page_num, table, prev_page_num, prev_table, page_content, text_between
                            )

                            # Always check for leftover text after processing a table
                            leftover_text_detected = False
                            for line in lines:
                                # Check for text below the current table or merged table
                                table_bottom = new_prev_table["bbox"][3] if merged_from_previous else table.bbox[3]
                                if line['top'] > table_bottom:  # Text below the table
                                    leftover_text_detected = True
                                    break

                            # If leftover text is detected, reset merging references
                            if leftover_text_detected:
                                prev_table = None
                                prev_page_num = None
                            else:
                                # Update references for merging if no leftover text
                                prev_table = new_prev_table
                                prev_page_num = page_num

                            if merged_from_previous and merged_tables:
                                merged_tables.pop()

                            # Append the table information
                            merged_tables.append({
                                "df": df,
                                "table_type": table_type,
                                "top": table.bbox[1] if hasattr(table, 'bbox') else None,
                                "page": page_num,
                            })

                        except Exception as e:
                            print(f"Error processing table on page {page_num}, table {table_num}: {e}")

                # Convert merged tables to JSON
                json_tables = self._convert_to_json(merged_tables)

        except Exception as e:
            raise Exception(f"Error in loading data from PDF: {e}")

        return json_tables

    def _convert_to_json(self, unique_tables: List[dict]) -> List[dict]:
        """
        Converts cleaned, unique tables into JSON format.

        Args:
        - unique_tables (List[dict]): A list of unique table dictionaries.

        Returns:
        - List[dict]: A list of JSON objects for the tables.
        """
        json_tables = []
        for table_entry in unique_tables:
            try:
                df = table_entry["df"]
                table_type = table_entry["table_type"]
                top = table_entry["top"]
                page_num = table_entry["page"]

                # Convert the DataFrame to JSON based on its type
                if table_type == "Row-by-Column Table":
                    table_json = _convert_row_column_table_to_json(df, None)
                elif table_type == "Key-Value Table":
                    table_json = _convert_key_value_table_to_json(df, None)
                elif table_type == "Row-Only Table":
                    table_json = _convert_row_only_table_to_json(df, None)
                else:
                    table_json = df.to_dict(orient='records')

                # Create the JSON object
                table_json_entry = {
                    "type": "table",
                    "top": top,
                    "structure": table_type,  # Changed from 'struttura' to 'structure' for consistency
                    "json": table_json,
                    "page_number": page_num,  # Changed from 'n_pag' to 'page_number' for clarity
                }
                json_tables.append(table_json_entry)
            except Exception as e:
                print(f"Error converting table on page {page_num} to JSON: {e}")

        return json_tables

def align_working_directory():
    """Aligns the working directory with the script's directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)


def find_files_in_data_directory(extension: str) -> list:
    """Finds files with the given extension in the 'data' directory."""
    return glob.glob(os.path.join(".", "data", f"*.{extension}"))

def main():
    """
    Main function to extract tables and text from all PDF files in the 'data' directory.
    """
    try:
        # Align the working directory to the script's directory
        align_working_directory()

        # Find all PDF files in the 'data' directory
        pdf_files = find_files_in_data_directory("pdf")

        # If no PDF files are found, exit the script
        if not pdf_files:
            print("No PDF files found to process.")
            return

        # Create an 'extracted' directory to save the output
        os.makedirs("extracted", exist_ok=True)

        # Process each PDF file
        for pdf_path in pdf_files:
            print(f"\nProcessing PDF: {pdf_path}\n")

            titles = extract_titles_from_pdf(pdf_path)

            try:
                # Create an instance of the PDF Table Extractor
                extractor = PDFTableExtractor()

                # Extract the tables and text from the PDF file
                json_content = extractor._process_tables(pdf_path)

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