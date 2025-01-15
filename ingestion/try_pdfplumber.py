import json
import os
import glob
import numpy as np
from table_processor import PDFTableExtractor
from parser import PDFTextExtractor
from extract_title import extract_titles_from_pdf


def extract_tables_from_page(pdf_path) -> list:
    """Extract tables from a single PDF page and return them as Qdrant-compatible JSON."""
    try:
        table_extractor = PDFTableExtractor()
        json_tables = table_extractor._process_tables(pdf_path)
        return json_tables
    except Exception as e:
        print(f"Error extracting tables from PDF: {e}")
        return []


def extract_text_from_page(pdf_path, titles) -> dict:
    """Extract text from a single PDF page and return it as a structured JSON."""
    try:
        text_extractor = PDFTextExtractor()
        text_json = text_extractor._process_text(pdf_path, titles)
        return text_json
    except Exception as e:
        print(f"Error extracting text from page: {e}")
        return {}


def extract_string_coordinates_and_tables(pdf_path) -> tuple:
    """Main function to orchestrate the reading of the PDF and extraction of text and tables."""
    try:
        titles = extract_titles_from_pdf(pdf_path)
        json_tables = extract_tables_from_page(pdf_path)
        json_text = extract_text_from_page(pdf_path, titles)
        return json_text, json_tables
    except Exception as e:
        print(f"Error extracting data from PDF: {e}")
        return {}, []


def prepare_text_entry(text_data):
    """Prepare text entry for Qdrant format."""
    return {
        'type': 'text',
        'page': text_data.get('n_pag'),
        'position': text_data['title'].get('bbox', [0, 0, 0, 0])[1] if text_data.get('title') else 0,
        'title': text_data['title']['text'] if text_data.get('title') else None,
        'content': text_data['text']
    }


def prepare_table_entry(table_data):
    """Prepare table entry for Qdrant format."""
    title_text = table_data['title'] if table_data.get('title') else None
    return {
        'type': 'table',
        'page': table_data.get('page_number'),
        'position': table_data.get('top', 0),
        'title': title_text,
        'content': table_data['json']
    }


def merge_and_sort_content(text_entries, table_entries):
    """Combine and sort text and table entries by page and position."""
    combined_entries = text_entries + table_entries
    combined_entries.sort(key=lambda x: (x['page'], x['position']))
    return combined_entries


def create_qdrant_json(processed_data_dict, file_path, file_name): 
    """
    Format Qdrant JSON structure from processed data dictionary.
    
    Args:
    - processed_data_dict (list): List of dictionaries, where each dictionary represents a text or table entry.
    - file_path (str): The path to the PDF file.
    - file_name (str): The name of the PDF file.
    
    Returns:
    - qdrant_json (list): The Qdrant-compatible list of dictionaries.
    """
    qdrant_json = []
    last_text_title = None  # This will store the most recent text title to use for table entries with null titles
    
    for index, entry in enumerate(processed_data_dict):
        try:
            entry_type = entry.get('type')
            page_number = entry.get('page')
            title = entry.get('title')  # Get the title directly from the entry
            file_path = file_path
            file_name = file_name

            # Check if the current entry is NOT the first entry
            if index != 0:
                prefix_title = f"{processed_data_dict[0]['title']}: "
            else:
                prefix_title = ""  # Do not prepend for the first entry

            if entry_type == 'text':
                # Store the title of the current text entry
                last_text_title = title if title else last_text_title
                qdrant_json.append({
                    "text": prefix_title + entry.get('content', ''),
                    "n_pag": page_number,
                    "file_path": file_path,
                    "file_name": file_name,
                    "title": title if title else "Unknown Title"
                })
            elif entry_type == 'table':
                # If table title is null, use the last seen text title
                table_title = title if title else last_text_title
                table_content = entry.get('content', 'table')
                
                # Convert the table content to a human-readable string if it is a dictionary
                if isinstance(table_content, dict):
                    table_content_str = ', '.join(f'{key}: {value}' for key, value in table_content.items())
                else:
                    table_content_str = str(table_content)
                
                qdrant_json.append({
                    "text": prefix_title + table_content_str,
                    "n_pag": page_number,
                    "file_path": file_path,
                    "file_name": file_name,
                    "title": table_title if table_title else "Unknown Title",
                    "json": table_content
                })
            else:
                print(f"Warning: Unexpected type '{entry_type}' for entry: {entry}")
        except Exception as e:
            print(f"Error processing entry: {entry}. Error: {e}")
    
    return qdrant_json

def save_json(data, output_path):
    """Save data to a JSON file."""
    with open(output_path, 'w', encoding='utf-8') as outfile:
        json.dump(data, outfile, ensure_ascii=False, indent=4)


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

        for pdf_path in pdf_files:
            print(f"Processing PDF: {pdf_path}")
            
            # Step 4: Extract text and tables from PDF
            json_text, json_tables = extract_string_coordinates_and_tables(pdf_path)

            # Step 5: Save extracted text and tables as intermediate JSON files
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            text_path = os.path.join("extracted", f"{base_name}_text.json")
            table_path = os.path.join("extracted", f"{base_name}_tables.json")
            qdrant_path = os.path.join("extracted", f"{base_name}_qdrant.json")

            with open(text_path, 'w', encoding='utf-8') as text_file:
                json.dump(json_text, text_file, ensure_ascii=False, indent=4)
            
            with open(table_path, 'w', encoding='utf-8') as table_file:
                json.dump(json_tables, table_file, ensure_ascii=False, indent=4)

            # Step 6: Prepare text and table entries for Qdrant
            text_entries = [prepare_text_entry(text) for text in json_text]
            table_entries = [prepare_table_entry(table) for table in json_tables]

            # Step 7: Merge and sort entries by page and position
            sorted_entries = merge_and_sort_content(text_entries, table_entries)

            # Step 8: Create Qdrant-compatible JSON
            qdrant_json = create_qdrant_json(sorted_entries, pdf_path, base_name)

            # Step 9: Save Qdrant JSON to a file
            save_json(qdrant_json, qdrant_path)

            print(f"Qdrant JSON successfully saved to {qdrant_path}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
