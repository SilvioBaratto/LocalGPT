# localgpt_api/services.py

import os
import logging
import traceback
import json
from pathlib import Path

from llama_index.llms.ollama import Ollama
from llama_index.core.llms import ChatMessage
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.storage.chat_store import SimpleChatStore
from llama_index.core.schema import NodeWithScore
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from qdrant_client import QdrantClient, AsyncQdrantClient
from llama_index.core import Settings, VectorStoreIndex

from dotenv import load_dotenv

from typing import Tuple, List

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize global variables
chat_engine = None
actual_model_name = None
llm_collection = {}

def init_logger():
    """Initialize logger from environment variables or defaults."""
    global logger
    try:
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
    except Exception as e:
        print(f"Failed to initialize logger: {e}")
        raise

def initialize_embedding_models() -> None:
    """Initialize HuggingFace embedding models from environment variables."""
    try:
        embedding_model_name = os.getenv('HUGGING_FACE_EMBEDDING_ENDPOINT')
        if not embedding_model_name:
            raise ValueError("HUGGING_FACE_EMBEDDING_ENDPOINT not set in environment variables.")
        logger.info("Initializing Embedding model: %s", embedding_model_name)
        embedding_llm = HuggingFaceEmbedding(
            model_name=embedding_model_name,
            trust_remote_code=True
        )
        Settings.embed_model = embedding_llm
        logger.info("Embedding model initialized: %s", embedding_model_name)
    except Exception as e:
        logger.error("Failed to initialize embedding models: %s", str(e))
        raise

def initialize_multiple_llms():
    """
    Initialize different Ollama-based LLMs and store references in a global dictionary.
    This allows for dynamically switching between multiple local models.
    """
    global llm_collection
    try:
        # Example 1: phi3 (Local via Ollama)
        phi3_model_name = "phi3:latest"
        phi3_llm = Ollama(model=phi3_model_name, request_timeout=300.0)
        logger.info("Initialized Ollama model: %s", phi3_model_name)

        # Example 2: llama3.2 (Local via Ollama)
        llama3_2_model_name = "llama3.2:latest"
        llama3_2_llm = Ollama(model=llama3_2_model_name, request_timeout=300.0)
        logger.info("Initialized Ollama model: %s", llama3_2_model_name)

        # Add more Ollama models here if needed
        llm_collection = {
            "phi3": phi3_llm,
            "llama3.2": llama3_2_llm
        }
    except Exception as e:
        logger.error("Failed to initialize multiple LLMs: %s", str(e))
        raise

def initialize_qdrant_vector_store() -> QdrantVectorStore:
    """
    Create and return a Qdrant-based vector store.
    """
    try:
        HUGGING_FACE_EMBEDDING_SPARSE_ENDPOINT = os.getenv('HUGGING_FACE_EMBEDDING_SPARSE_ENDPOINT', '')
        QDRANT_HOST = os.getenv('QDRANT_HOST', 'localhost')
        QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333)) if QDRANT_HOST == "localhost" else None
        COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "test_collection")
        QDRANT_BATCH_SIZE = int(os.getenv("QDRANT_BATCH_SIZE", 20))

        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        aclient = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

        vector_store = QdrantVectorStore(
            collection_name=COLLECTION_NAME,
            client=client,
            aclient=aclient,
            enable_hybrid=True,  # Allows combined dense + sparse queries
            batch_size=QDRANT_BATCH_SIZE,
            fastembed_sparse_model=HUGGING_FACE_EMBEDDING_SPARSE_ENDPOINT,
        )

        logger.info("Qdrant vector store initialized: %s", COLLECTION_NAME)
        return vector_store
    except Exception as e:
        logger.error("Failed to initialize Qdrant vector store: %s", str(e))
        raise

def build_chat_memory(data_dir: str, conversation_id: str) -> Tuple[str, ChatMemoryBuffer]:
    """
    Build (or load) a ChatMemoryBuffer for a given conversation_id.

    :param data_dir: Path to data directory (where the 'History' folder resides).
    :param conversation_id: Unique identifier for the conversation.
    :return: memory_path and memory buffer
    """
    try:
        MEMORY_BUFFER_TOKEN_LIMIT = int(os.getenv("MEMORY_BUFFER_TOKEN_LIMIT", 32000))
        memory_path = os.path.join(
            data_dir, "History", "_".join([str(conversation_id), "chat_store.json"])
        )
        chat_store = (
            SimpleChatStore.from_persist_path(memory_path)
            if os.path.exists(memory_path)
            else SimpleChatStore()
        )
        memory = ChatMemoryBuffer.from_defaults(
            token_limit=MEMORY_BUFFER_TOKEN_LIMIT, chat_store=chat_store
        )
        logger.info("Chat memory built for conversation_id: %s", conversation_id)
        return memory_path, memory
    except Exception as e:
        logger.error("Failed to build chat memory: %s", str(e))
        raise

def reset_chat_memory(data_dir: str, conversation_id: str) -> None:
    """
    Reset a conversation's memory by deleting its associated JSON file.
    """
    try:
        memory_path = os.path.join(
            data_dir, "History", "_".join([conversation_id, "chat_store.json"])
        )
        if os.path.exists(memory_path):
            os.remove(memory_path)
            logger.info("Chat memory reset for conversation_id: %s", conversation_id)
    except Exception as e:
        logger.error("Failed to reset chat memory: %s", str(e))
        raise

def get_resources(
    source_nodes: List[NodeWithScore],
    confidence_score: float = 0.7
) -> dict:
    """
    Extract relevant documents (with page references) from RAG results
    if the results exceed a certain confidence threshold.
    """
    try:
        if not source_nodes:
            return {}

        lista_fonti = {}

        for result in source_nodes:
            if result.score >= confidence_score:
                documento = result.metadata.get('file_name') or result.metadata.get('source')
                pagina = result.metadata.get('n_pag') or result.metadata.get('page')

                # Create a single key that aggregates pages
                key = documento + ', pag: '
                if key in lista_fonti:
                    if pagina not in lista_fonti[key]:
                        lista_fonti[key].append(pagina)
                else:
                    lista_fonti[key] = [pagina]
                
                lista_fonti[key].sort()
            else:
                logger.debug("Skipping low-confidence chunk or missing 'text' field.")

        logger.info("Resources extracted: %s", lista_fonti)
        return lista_fonti
    except Exception as e:
        logger.error("Failed to get resources: %s", str(e))
        raise

def build_chat_engine() -> None:
    """
    Build or rebuild the chat engine using the currently active LLM in Settings.llm.
    """
    global chat_engine, actual_model_name, llm_collection

    try:
        SIMILARITY_TOP_K = int(os.getenv("SIMILARITY_TOP_K", 5))
        SPARSE_TOP_K = int(os.getenv("SPARSE_TOP_K", 7))

        # Context prompt
        CONTEXT_TEMPLATE = (
            "Use the following contextual information to provide a comprehensive, accurate, and well-structured response to the user's query.\n"
            "Ensure the response is concise, factual, and relevant to the user's needs.\n"
            "If the provided context lacks sufficient details, clearly acknowledge any gaps without speculation.\n"
            "--------------------\n"
            "{context_str}\n"
            "--------------------\n"
            "Your response should align with the provided context and avoid introducing unrelated information."
        )

        # Refine template
        REFINE_TEMPLATE = (
            "Using the provided contextual information, improve the existing response to better address the user's query.\n"
            "Ensure accuracy, coherence, and adherence to the user's intent.\n"
            "--------------------\n"
            "{context_msg}\n"
            "--------------------\n"
            "Existing Response:\n"
            "{existing_answer}\n"
            "--------------------\n"
            "If the context does not provide additional useful information, maintain the original response without unnecessary changes."
        )

        # System prompt
        SYSTEM_PROMPT = (
            "You are an AI assistant designed to provide helpful, accurate, and concise responses to user inquiries.\n"
            "Utilize the provided context effectively to formulate answers that address the user's needs.\n"
            "Maintain clarity, professionalism, and focus while avoiding irrelevant details.\n"
            "If uncertain, indicate the need for further clarification without guessing."
        )

        ENGINE_CHAT_MODE = os.getenv("ENGINE_CHAT_MODE", "context")
        VECTOR_STORE_QUERY_MODE = os.getenv("VECTOR_STORE_QUERY_MODE", "hybrid")

        # Re-initialize embeddings to ensure they are set
        initialize_embedding_models()

        vector_store = initialize_qdrant_vector_store()

        # Set the context window for the model
        Settings.context_window = int(os.getenv("CONTEXT_WINDOW_SIZE", 4096))

        # Create an index that uses our vector store
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

        # Create the chat engine
        chat_engine = index.as_chat_engine(
            chat_mode=ENGINE_CHAT_MODE,
            similarity_top_k=SIMILARITY_TOP_K,
            sparse_top_k=SPARSE_TOP_K,
            vector_store_query_mode=VECTOR_STORE_QUERY_MODE,
            context_template=CONTEXT_TEMPLATE,
            context_refine_template=REFINE_TEMPLATE,
            system_prompt=SYSTEM_PROMPT,
        )

        logger.info("Chat engine built successfully.")
    except Exception as e:
        logger.error("Failed to build chat engine: %s", str(e))
        raise

def init_app():
    """Initialize the application with all dependencies."""
    try:
        # Initialize logger
        init_logger()

        # Initialize embedding models, Qdrant, etc.
        initialize_embedding_models()

        # Initialize multiple LLMs
        initialize_multiple_llms()

        # Set the default LLM to avoid using OpenAI's default
        if "phi3" in llm_collection:
            Settings.llm = llm_collection["phi3"]
            global actual_model_name
            actual_model_name = "phi3"
            logger.info("Default LLM set to 'phi3'")
        else:
            raise ValueError("Default LLM 'phi3' not found in llm_collection.")

        # Build the default chat engine (e.g., uses phi3 by default)
        build_chat_engine()
    except Exception as e:
        logger.error("Failed to initialize application: %s", str(e))
        raise
