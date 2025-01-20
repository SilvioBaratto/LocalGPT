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

def create_qdrant_json(file_name: str, pdf_name: str, extracted_data: dict) -> list:
    """Creates the JSON structure from the extracted data for Qdrant upload."""
    qdrant_data = []
    
    for section in extracted_data.get("sections", []):
        qdrant_entry = {
            "file_name": file_name,
            "pdf_name": pdf_name,
            "title": section["title"],
            "content": section["content"].strip(),
            "page_idx": section["page_idx"]
        }
        qdrant_data.append(qdrant_entry)
    
    return qdrant_data

import requests

def prepare_documents(file_path: str) -> list:
    """Calls the API to extract content from the PDF and returns processed sections."""
    api_url = "http://localhost:5000/api/extract_to_qdrant/"
    files = {'file': open(file_path, 'rb')}
    
    try:
        response = requests.post(api_url, files=files)
        response.raise_for_status()
        extracted_data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error processing file {file_path}: {e}")
        return []
    
    return extracted_data.get("sections", [])

def process_nodes_and_upload(client: QdrantClient, collection_name: str, sections: list, calculate_embeddings, pdf_name: str, file_path: str):
    """Processes sections and uploads them to Qdrant."""
    # Check if the file has already been uploaded
    if document_exists_in_qdrant(client, collection_name, pdf_name):
        print(f"Skipping upload: Document '{pdf_name}' already exists in Qdrant collection '{collection_name}'")
        return
    
    points = []
    
    for section in sections:
        # Use dot notation to access the content attribute from the TextNode object
        dense_vector, sparse_vector = calculate_embeddings(section.text)

        # Handle sparse vector properly
        sparse_vec_object = sparse_vector[0].as_object() if sparse_vector else None

        # Prepare payload
        payload = {
            "file_name": file_path,
            "pdf_name": pdf_name,
            "title": section.metadata.get("title", ""),
            "text": section.text,
            "n_pag": section.metadata.get("page_idx", 0)
        }

        # Get node ID or generate one
        node_id = getattr(section, 'id_', uuid.uuid4().hex)

        # Create point struct for Qdrant
        point = models.PointStruct(
            id=node_id,
            vector={"text-dense": dense_vector, "text-sparse": sparse_vec_object},
            payload=payload
        )
        points.append(point)

    # Upload points to Qdrant in a single request for better performance
    client.upsert(
        collection_name=collection_name,
        points=points
    )

    print(f"Successfully uploaded {len(points)} documents to collection '{collection_name}'")

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

def initialize_embedding_models_and_splitter(embed_model: str, embed_sparse_model: str) -> tuple:
    """Initializes the embedding models and the semantic splitter."""
    dense_embed_model = HuggingFaceEmbedding(model_name=embed_model, trust_remote_code=True)
    sparse_embed_model = SparseTextEmbedding(model_name=embed_sparse_model)
    splitter = SemanticSplitterNodeParser(buffer_size=1, breakpoint_percentile_threshold=95, embed_model=dense_embed_model)
    return dense_embed_model, sparse_embed_model, splitter


def get_nodes_from_documents(documents: list, splitter: SemanticSplitterNodeParser) -> list:
    """Converts dictionaries to Document objects and gets nodes from the documents using the splitter."""

    # Convert each dictionary to a Document object
    document_objects = [
        Document(
            text=doc['content'],
            metadata={
                "file_name": doc['file_name'],
                "pdf_name": doc['pdf_name'],
                "title": doc['title'],
                "page_idx": doc['page_idx']
            }
        ) for doc in documents
    ]

    # Use the splitter to process the documents
    return splitter.get_nodes_from_documents(document_objects)


def define_calculate_embeddings(embed_model: HuggingFaceEmbedding, embed_sparse_model: SparseTextEmbedding):
    """Defines a function to calculate embeddings for a given text."""
    def calculate_embeddings(text: str) -> tuple:
        dense_vector = embed_model.get_text_embedding(text)
        sparse_vector = embed_sparse_model.embed(text)
        return dense_vector, list(sparse_vector)
    return calculate_embeddings

def document_exists_in_qdrant(client: QdrantClient, collection_name: str, pdf_name: str) -> bool:
    """Check if a document with the same pdf_name already exists in Qdrant."""
    query_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="pdf_name",
                match=models.MatchValue(value=pdf_name)
            )
        ]
    )

    # Check if any existing document matches the pdf_name
    existing_docs = client.scroll(
        collection_name=collection_name,
        scroll_filter=query_filter,
        limit=1  # Check only one document
    )
    return len(existing_docs[0]) > 0

def index_pdf(
        file_path: str, client: QdrantClient, embed_model: str, embed_sparse_model: str, collection_name: str, size: int
    ) -> list:
    """Indexes the PDF into a Qdrant collection."""
    
    if not collection_exists(client, collection_name):
        create_qdrant_collection(client, collection_name, size)
    
    pdf_name, file_name = extract_file_names(file_path)

    # Extract content from the API
    extracted_sections = prepare_documents(file_path)

    # Prepare JSON data for Qdrant
    qdrant_json = create_qdrant_json(file_name, pdf_name, {"sections": extracted_sections})

    # Initialize embeddings and splitter
    dense_embed_model, sparse_embed_model, splitter = initialize_embedding_models_and_splitter(embed_model, embed_sparse_model)

    # Prepare the nodes for indexing
    nodes = get_nodes_from_documents(qdrant_json, splitter)

    # Generate embeddings
    calculate_embeddings = define_calculate_embeddings(dense_embed_model, sparse_embed_model)

    # Upload to Qdrant
    process_nodes_and_upload(client, collection_name, nodes, calculate_embeddings, pdf_name, file_path)

    return nodes