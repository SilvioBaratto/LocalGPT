import os
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from fastembed import SparseTextEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import Settings,load_index_from_storage
from indicizzazione_testo_tabelle import indicizzazione_pdf
from qdrant_client import QdrantClient

import os
import glob
import indicizzazione_testo_tabelle
import qdrant_client
from qdrant_client.http import models

import dotenv

dotenv.load_dotenv()

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333)) if QDRANT_HOST=="localhost" else None
QDRANT_API_KEY=os.environ.get("QDRANT_API_KEY")

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "test_collection")


# Construct the path to the 'data' directory inside 'backend'
data_dir = os.path.join(os.path.dirname(__file__), "..", "backend", "data")

# Normalize the path to handle any redundant separators
data_dir = os.path.abspath(data_dir)

storage_dir = os.path.join(data_dir,"storage")

HUGGING_FACE_EMBEDDING_SPARSE_ENDPOINT = os.getenv('HUGGING_FACE_EMBEDDING_SPARSE_ENDPOINT') # ex. "prithivida/Splade_PP_en_v1" "Qdrant/bm42-all-minilm-l6-v2-attentions"
HUGGING_FACE_EMBEDDING_ENDPOINT = os.getenv('HUGGING_FACE_EMBEDDING_ENDPOINT') # ex. "sentence-transformers/paraphrase-multilingual-mpnet-base-v2" "Snowflake/snowflake-arctic-embed-l-v2.0"
HUGGING_FACE_EMBEDDING_SIZE = int(os.getenv('HUGGING_FACE_EMBEDDING_SIZE'))

def align_working_directory():
    """Aligns the working directory with the script's directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

def find_files_in_data_directory(extension) -> list:
    """Finds files with the given extension in the 'data' directory."""
    return glob.glob(f"../backend/data/*.{extension}")

def process_pdf_files(client: QdrantClient, embed_model: str, embed_sparse_model: str, pdf_files: list) -> list:
    """Processes each PDF file found in the data directory and indexes it into Qdrant."""
    nodes = []

    if not pdf_files:
        print("No PDF files found to process.")
        return nodes

    if not client:
        print("Qdrant client is not initialized.")
        return nodes

    for pdf_path in pdf_files:
        print(f"Processing PDF: {pdf_path}")
        
        # Call the indicizzazione_pdf function to process the current PDF
        try:
            pdf_nodes = indicizzazione_pdf(
                file_path=pdf_path, 
                client=client, 
                embed_model=embed_model, 
                embed_sparse_model=embed_sparse_model, 
                collection_name=COLLECTION_NAME, 
                size=HUGGING_FACE_EMBEDDING_SIZE
            )
            
            if pdf_nodes:
                nodes.extend(pdf_nodes)  # Properly extend nodes to avoid overwriting

        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")
    
    return nodes


# --- Embeddings ---
class HybridEmbedding:
    """
    A custom embedding class that combines a dense embedding model and a sparse embedding model
    into a single interface for hybrid indexing with QdrantVectorStore.

    QdrantVectorStore (enable_hybrid=True) expects embeddings that return both dense and sparse.
    We'll use the HuggingFaceEmbedding for dense and SparseTextEmbedding for sparse vectors.
    """
    def __init__(self, dense_model: HuggingFaceEmbedding, sparse_model: SparseTextEmbedding):
        self.dense_model = dense_model
        self.sparse_model = sparse_model

    def embed(self, text: str):
        # Return a dict with 'dense' and 'sparse' keys as expected by llama_index for hybrid indexing
        dense_vector = self.dense_model.get_text_embedding(text)
        sparse_vector = self.sparse_model.embed(text)  # returns a list of ScoredVector
        # Convert the first sparse vector to a dict format
        sparse_vec_object = sparse_vector[0].as_object() if sparse_vector else None
        return {"dense": dense_vector, "sparse": sparse_vec_object}

    def embed_documents(self, texts):
        # Embed a list of texts
        return [self.embed(t) for t in texts]

    def embed_query(self, text):
        # Embed a single query text
        return self.embed(text)

def main():
    # Align the working directory with the script's directory
    align_working_directory()

    # Find PDF files in the 'data' directory
    pdf_files = find_files_in_data_directory("pdf")

    # Debugging output
    print("PDFs to process:", pdf_files)

    # initialize qdrant client:
    client = indicizzazione_testo_tabelle.initialize_qdrant_client(
        QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY
    )

    # Chunk documents into nodes
    nodes = process_pdf_files(client, HUGGING_FACE_EMBEDDING_ENDPOINT, HUGGING_FACE_EMBEDDING_SPARSE_ENDPOINT, pdf_files)

    print("Indexing complete. The index is persisted on disk.")

if __name__ == "__main__":
    main()