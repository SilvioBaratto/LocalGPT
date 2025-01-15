# import os
# from langchain_community.document_loaders import PyPDFium2Loader
# from llama_index.core import VectorStoreIndex, StorageContext
# from llama_index.embeddings.huggingface import HuggingFaceEmbedding
# from llama_index.core.node_parser import TokenTextSplitter
# from fastembed import SparseTextEmbedding
# from llama_index.vector_stores.qdrant import QdrantVectorStore
# from qdrant_client import QdrantClient, AsyncQdrantClient
# from qdrant_client import QdrantClient
# from llama_index.core import Document, Settings,load_index_from_storage
# from llama_index.embeddings.azure_inference import AzureAIEmbeddingsModel as LlamaAzureAIEmbeddingsModel
# from llama_index.embeddings.ollama import OllamaEmbedding
# import dotenv

# dotenv.load_dotenv()

# QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
# QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
# COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "test_collection")

# data_dir = os.path.join(os.path.dirname(__file__), "data")
# storage_dir = os.path.join(data_dir,"storage")

# # OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
# # OLLAMA_PORT = int(os.getenv("OLLAMA_PORT", 11434))
# # OLLAMA_BASE_URL = f"{OLLAMA_HOST}:{OLLAMA_PORT}"

# # embedding_llm = OllamaEmbedding(
# #     base_url=OLLAMA_BASE_URL,
# #     model_name="snowflake-arctic-embed2",
# #     request_timeout=360,
# # )

# embedding_model_name = os.getenv('HUGGING_FACE_EMBEDDING_ENDPOINT')
# embedding_llm = HuggingFaceEmbedding(model_name=embedding_model_name, trust_remote_code=True)

# Settings.embed_model = embedding_llm

# # --- Load PDF and Create Documents ---
# def load_pdf_as_documents(pdf_path):
#     """
#     Uses LangChain's PDFPlumberLoader to extract text from the PDF.
#     Each page in the PDF will be a Document.
#     """
#     documents = []

#     for path in os.listdir(pdf_path):
#         loader = PyPDFium2Loader(os.path.join(pdf_path, path))
#         langchain_docs = loader.load()

#         # Convert LangChain Documents to LlamaIndex Documents
#         for d in langchain_docs:
#             # Each page_content -> text, metadata includes {page_number: ...}
#             doc=Document.from_langchain_format(d)
#             doc.metadata["FileName"]=path
#             documents.append(doc)
#     return documents

# # --- Chunking Documents ---
# def chunk_documents(documents):
#     """
#     Uses a SimpleNodeParser from llama_index to split documents into smaller nodes.
#     Adjust if you prefer a different splitter (e.g., SentenceSplitter).
#     """
#     parser = TokenTextSplitter(
#         chunk_overlap=100,
#         chunk_size=1000,
#     )
#     nodes = parser.get_nodes_from_documents(documents)
#     return nodes

# # --- Embeddings ---
# class HybridEmbedding:
#     """
#     A custom embedding class that combines a dense embedding model and a sparse embedding model
#     into a single interface for hybrid indexing with QdrantVectorStore.

#     QdrantVectorStore (enable_hybrid=True) expects embeddings that return both dense and sparse.
#     We'll use the HuggingFaceEmbedding for dense and SparseTextEmbedding for sparse vectors.
#     """
#     def __init__(self, dense_model: HuggingFaceEmbedding, sparse_model: SparseTextEmbedding):
#         self.dense_model = dense_model
#         self.sparse_model = sparse_model

#     def embed(self, text: str):
#         # Return a dict with 'dense' and 'sparse' keys as expected by llama_index for hybrid indexing
#         dense_vector = self.dense_model.get_text_embedding(text)
#         sparse_vector = self.sparse_model.embed(text)  # returns a list of ScoredVector
#         # Convert the first sparse vector to a dict format
#         sparse_vec_object = sparse_vector[0].as_object() if sparse_vector else None
#         return {"dense": dense_vector, "sparse": sparse_vec_object}

#     def embed_documents(self, texts):
#         # Embed a list of texts
#         return [self.embed(t) for t in texts]

#     def embed_query(self, text):
#         # Embed a single query text
#         return self.embed(text)

# # --- Qdrant Setup ---
# def initialize_qdrant_vector_store(collection_name):
#     """
#     Initialize QdrantVectorStore with hybrid indexing enabled.
#     Make sure Qdrant is running at localhost:6333.
#     """
#     if QDRANT_HOST== "localhost":
#         client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
#         aclient = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
#     else:
#         client = QdrantClient(url=QDRANT_HOST, port=QDRANT_PORT)
#         aclient = AsyncQdrantClient(url=QDRANT_HOST, port=QDRANT_PORT)
        
#     vector_store = QdrantVectorStore(
#         collection_name=collection_name,
#         client=client,
#         aclient=aclient,
#         enable_hybrid=True,
#         batch_size=20,
#         fastembed_sparse_model="Qdrant/bm42-all-minilm-l6-v2-attentions",
#     )
#     return vector_store

# def main():
#     # Load PDF as documents
#     documents = load_pdf_as_documents(data_dir)

#     # Chunk documents into nodes
#     nodes = chunk_documents(documents)

#     # Initialize QdrantVectorStore with hybrid indexing
#     vector_store = initialize_qdrant_vector_store(collection_name=COLLECTION_NAME)

#     os.makedirs(data_dir, exist_ok=True)
#     os.makedirs(os.path.join(data_dir,"storage"),exist_ok=True)
#     # Create a StorageContext that uses our vector store
#     if os.path.exists(os.path.join(data_dir,"storage","index_store.json")):
#         storage_context = StorageContext.from_defaults(
#             persist_dir=storage_dir,vector_store=vector_store
#         )
#         index = load_index_from_storage(
#         storage_context=storage_context, 
#         index_id="vector_id", 
#         store_nodes_override=True,
#         fastembed_sparse_model="Qdrant/bm42-all-minilm-l6-v2-attentions"
#         )
#         index.insert_nodes(nodes,store_nodes_override=True)
#     else:
#         storage_context = StorageContext.from_defaults(
#             vector_store=vector_store
#             )
#         index = VectorStoreIndex(
#         nodes=nodes,
#         storage_context=storage_context,
#         store_nodes_override=True,
#         fastembed_sparse_model="Qdrant/bm42-all-minilm-l6-v2-attentions"
#         )


#     # Optionally, set an index ID to identify this index later
#     index.set_index_id("vector_id")

#     # Persist the index so we can reload later without re-building
#     storage_context.persist(persist_dir=storage_dir)
#     vector_store._client.close()
#     vector_store._aclient.close()

#     print("Indexing complete. The index is persisted on disk.")

# if __name__ == "__main__":
#     main()
