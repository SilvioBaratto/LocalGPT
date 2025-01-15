import os
import re
import tqdm
import uuid
import string
import pdfplumber
import fitz
import numpy as np
import statistics

from qdrant_client.http import models
from qdrant_client import QdrantClient
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from fastembed import SparseTextEmbedding
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.core import Document
from extract_title import extract_titles_from_pdf
from try_pdfplumber import (
    prepare_table_entry, 
    prepare_text_entry, 
    merge_and_sort_content, 
    create_qdrant_json, 
    extract_string_coordinates_and_tables
)


def initialize_qdrant_client(qdrant_host: str, qdrant_port: int, qdtrant_api_key: str) -> QdrantClient:
    """Initializes and returns the Qdrant client."""
    api_key = None if qdrant_host == "localhost" else qdtrant_api_key
    return QdrantClient(url=qdrant_host, port=qdrant_port, api_key=api_key)


def collection_exists(client: QdrantClient, collection_name: str) -> bool:
    """Checks if the collection exists in Qdrant."""
    return client.collection_exists(collection_name=collection_name)


def create_qdrant_collection(client: QdrantClient, collection_name: str, size: int) -> None:
    """Creates a new collection in Qdrant with the specified configuration."""
    client.create_collection(
        collection_name=collection_name,
        vectors_config={"text-dense": models.VectorParams(size=size, distance=models.Distance.COSINE)},
        sparse_vectors_config={"text-sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)}
    )


def extract_file_names(file_path: str) -> tuple:
    """Extracts the PDF name and file name from the given path."""
    pdf_name = os.path.basename(file_path).split('.')[0]
    file_name = ' '.join(os.path.splitext(os.path.basename(file_path))[0].split()[1:])
    return pdf_name, file_name


def prepare_documents(testi: list) -> list:
    """Prepares documents from the extracted texts, including all relevant metadata."""
    if not isinstance(testi, list):
        raise ValueError("Expected 'testi' to be a list of dictionaries.")
    
    prepared_docs = []
    for entry in testi:
        text = entry.get('text', '')
        page_number = entry.get('n_pag', -1)
        title = entry.get('title', 'No Title')
        
        # Assume 'title' can be a string or a dictionary
        if isinstance(title, dict):
            title_text = title.get('text', 'No Title')
            title_page = title.get('page', page_number)
            title_bbox = title.get('bbox', [])
            title_info = {
                "text": title_text,
                "page": title_page,
                "bbox": title_bbox
            }
        else:
            title_info = {
                "text": title,
                "page": page_number,
                "bbox": []
            }
        
        # Include all relevant metadata
        metadata = {
            "page_number": page_number,
            "title": title_info
        }
        
        prepared_docs.append(Document(text=text, metadata=metadata))
    
    return prepared_docs

def initialize_embedding_models_and_splitter(embed_model: str, embed_sparse_model: str) -> tuple:
    """Initializes the embedding models and the semantic splitter."""
    dense_embed_model = HuggingFaceEmbedding(model_name=embed_model, trust_remote_code=True)
    sparse_embed_model = SparseTextEmbedding(model_name=embed_sparse_model)
    splitter = SemanticSplitterNodeParser(buffer_size=1, breakpoint_percentile_threshold=95, embed_model=dense_embed_model)
    return dense_embed_model, sparse_embed_model, splitter


def get_nodes_from_documents(documents: list, splitter: SemanticSplitterNodeParser) -> list:
    """Gets nodes from the documents using the splitter."""
    return splitter.get_nodes_from_documents(documents)


def define_calculate_embeddings(embed_model: HuggingFaceEmbedding, embed_sparse_model: SparseTextEmbedding):
    """Defines a function to calculate embeddings for a given text."""
    def calculate_embeddings(text: str) -> tuple:
        dense_vector = embed_model.get_text_embedding(text)
        sparse_vector = embed_sparse_model.embed(text)
        return dense_vector, list(sparse_vector)
    return calculate_embeddings


def process_nodes_and_upload(
    client: QdrantClient,
    collection_name: str,
    nodes: list,
    calculate_embeddings,
    pdf_name: str,
    file_path: str
) -> None:
    """Processes each node, calculates embeddings, and uploads to Qdrant."""
    for node in tqdm.tqdm(nodes, desc="Uploading Nodes"):
        try:
            # Access attributes using dot notation
            text = getattr(node, 'text', None)
            if text is None:
                continue

            metadata = getattr(node, 'metadata', {})
            
            # Extract page_number
            page_number = metadata.get('page_number', -1)
            
            # Extract title details
            title_info = metadata.get('title', {})
            title_text = title_info.get('text', 'No Title')
            title_page = title_info.get('page', page_number)  # Fallback to page_number if 'page' not present
            title_bbox = title_info.get('bbox', [])  # Empty list if 'bbox' not present

            # Generate embeddings
            dense_vector, sparse_vector = calculate_embeddings(text)
            sparse_vec_object = sparse_vector[0].as_object() if sparse_vector else None

            # Create a unique ID if node doesn't have one
            node_id = getattr(node, 'id', uuid.uuid4().hex)

            # Prepare payload with all metadata
            payload = {
                "text": text,
                "n_pag": page_number,
                "file_path": file_path,
                "file_name": pdf_name,
                "title": title_text,
            }

            # Create PointStruct
            point = models.PointStruct(
                id=node_id,  # Use existing ID or generate a new one
                vector={"text-dense": dense_vector, "text-sparse": sparse_vec_object},
                payload=payload
            )

            # Upload to Qdrant
            client.upload_points(
                collection_name=collection_name,
                points=[point]
            )
        
        except Exception as e:
            print(f"Error processing node: {e}")

def process_tables_and_upload(
    client: QdrantClient,
    collection_name: str,
    data_list: list,
    calculate_embeddings,
    pdf_name: str,
    file_path: str,
) -> None:
    """Processes each table, calculates embeddings, and uploads to Qdrant in batches."""
    points_batch = []
    
    for entry in tqdm.tqdm(data_list, desc="Uploading Tables"):
        try:
            title = entry.get('title', 'Unknown Title')
            page_number = entry.get('n_pag', -1)
            table_content = entry.get('text', '')
            table_json = entry.get('json', {})
    
            if not table_content and not table_json:
                continue
    
            # Generate embeddings
            dense_vector, sparse_vector = calculate_embeddings(f"{title}: {str(table_content)}")
            sparse_vec_object = sparse_vector[0].as_object() if sparse_vector else None
            
            # Create PointStruct
            point = models.PointStruct(
                id=uuid.uuid4().hex,
                vector={"text-dense": dense_vector, "text-sparse": sparse_vec_object},
                payload={
                    "title": title,
                    "json": table_json,  # Include the raw table data
                    "text": f"{title}: {str(table_content)}",
                    "file_path": file_path,
                    "file_name": pdf_name,
                    "n_pag": page_number
                }
            )
            
            points_batch.append(point)
        
        except Exception as e:
            print(f"Error processing table: {e}")
    
    # Upload any remaining points
    if points_batch:
        client.upload_points(collection_name=collection_name, points=points_batch)

def indicizzazione_pdf(
        file_path: str, client: QdrantClient, embed_model: str, embed_sparse_model: str, collection_name: str, size: int
    ) -> list:
    """Indexes the PDF into a Qdrant collection."""
    if not collection_exists(client, collection_name):
        create_qdrant_collection(client, collection_name, size)
    
    pdf_name, file_name = extract_file_names(file_path)
    json_text, json_tables = extract_string_coordinates_and_tables(file_path)
    sorted_entries = merge_and_sort_content(
        [prepare_text_entry(text) for text in json_text],
        [prepare_table_entry(table) for table in json_tables]
    )
    
    qdrant_json = create_qdrant_json(sorted_entries, file_name, pdf_name)
    dense_embed_model, sparse_embed_model, splitter = initialize_embedding_models_and_splitter(embed_model, embed_sparse_model)
    
    nodes = get_nodes_from_documents(prepare_documents(json_text), splitter)
    calculate_embeddings = define_calculate_embeddings(dense_embed_model, sparse_embed_model)
    
    process_nodes_and_upload(client, collection_name, nodes, calculate_embeddings, pdf_name, file_path)
    process_tables_and_upload(client, collection_name, qdrant_json, calculate_embeddings, pdf_name, file_path)
    
    return nodes
