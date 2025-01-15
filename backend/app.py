import os
import logging
import traceback
import json
from flask import Flask, request, jsonify, stream_with_context, Response
from flask_cors import CORS

# llama_index imports
from llama_index.llms.ollama import Ollama
from llama_index.core.llms import ChatMessage
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.storage.chat_store import SimpleChatStore
from llama_index.core.schema import NodeWithScore
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# Qdrant
from qdrant_client import QdrantClient, AsyncQdrantClient

# .env handling
from dotenv import load_dotenv

# Python typing
from typing import Tuple, List

# Initialize global variables
global chat_engine, logger, actual_model_name, llm_collection
chat_engine = None
logger = None
actual_model_name = None
llm_collection = {}

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'secret_key')
CORS(app, resources={r"/*": {"origins": "*"}})

def init_app() -> None:
    """Initialize the application with all dependencies (env variables, logging, LLMs, vector store, etc.)."""
    try:
        load_dotenv()
        init_logger()

        # 1) Initialize embedding models, Qdrant, etc.
        initialize_embedding_models()

        # 2) Initialize multiple LLMs
        initialize_multiple_llms()

        # 3) Set the default LLM to avoid using OpenAI's default
        if "phi3" in llm_collection:
            Settings.llm = llm_collection["phi3"]
            global actual_model_name
            actual_model_name = "phi3"
            logger.info("Default LLM set to 'phi3'")
        else:
            raise ValueError("Default LLM 'phi3' not found in llm_collection.")

        # 4) Build the default chat engine (e.g., uses phi3 by default)
        build_chat_engine()
    except Exception as e:
        logger.error("Failed to initialize application: %s", str(e))
        raise

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
        QDRANT_HOST = f"{os.getenv('QDRANT_HOST', 'localhost')}"
        QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333)) if QDRANT_HOST == "localhost" else None
        COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "test_collection")
        QDRANT_BATCH_SIZE = int(os.getenv("QDRANT_BATCH_SIZE", 20))

        client = QdrantClient(url=QDRANT_HOST, port=QDRANT_PORT)
        aclient = AsyncQdrantClient(url=QDRANT_HOST, port=QDRANT_PORT)

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
    confidece_score: float = 0.7
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
            if result.score >= confidece_score:
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
    global chat_engine, index, llm_collection

    try:
        SIMILARITY_TOP_K = int(os.getenv("SIMILARITY_TOP_K", 5))
        SPARSE_TOP_K = int(os.getenv("SPARSE_TOP_K", 7))

        # Context prompt
        CONTEXT_TEMPLATE = (
            "You are an AI assistant tasked with retrieving and summarizing relevant information from structured documents. "
            "Answer the question: {query} using the following context:\n{context}\n"
            "Provide a concise and accurate response. If context is insufficient, indicate the need for more information."
        )


        # Refine template
        REFINE_TEMPLATE = (
            "Refine the draft response below using the additional context provided. "
            "Draft response:\n{existing_answer}\n"
            "Additional context:\n{additional_context}\n"
            "Update the response for accuracy and completeness or retain it if unchanged."
        )

        # System prompt
        SYSTEM_PROMPT = (
            "You are an AI assistant summarizing data from structured documents. Guidelines:\n"
            "- Provide specific, accurate, and concise answers.\n"
            "- Flag incomplete or ambiguous information and suggest follow-up.\n"
            "- Avoid assumptions and maintain a formal tone.\n"
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

@app.route('/new_ask', methods=['POST']) 
def new_ask():
    """
    Endpoint to start a fresh conversation by clearing the chat memory.
    """
    try:
        data = request.get_json()  # Retrieve JSON data from the request
        conversation_id = data.get("conversation_id", "default")

        data_dir = os.path.join(os.path.dirname(__file__), "data")
        reset_chat_memory(data_dir, conversation_id)

        logger.info("New conversation started with conversation_id: %s", conversation_id)
        return jsonify({"valid": True}), 200
    except Exception as ex:
        logger.error("Error New Chat: %s. Trace: %s", str(ex), traceback.format_exc())
        return jsonify({"valid": False}), 200

@app.route('/ask', methods=['POST']) 
def ask_question():
    """
    Endpoint to get a response from the chat engine using RAG and memory.
    Streams the response back to the client.
    """
    try:
        global chat_engine, llm_collection, actual_model_name

        data = request.get_json()  # Retrieve JSON data from the request
        user_message = data.get("domanda")
        conversation_id = data.get("conversation_id", "default")
        model_name = data.get("model_name", "phi3")  # default to 'phi3'

        # Validate user_message
        if not user_message:
            return jsonify({
                "response": "No 'domanda' provided in the request.",
                "fonti": None,
            }), 400

        # Ensure chat engine is initialized
        if not chat_engine:
            build_chat_engine()

        # Switch model if user requests a different one
        if model_name != actual_model_name and model_name in llm_collection:
            Settings.llm = llm_collection[model_name]
            build_chat_engine()
            actual_model_name = model_name
            logger.info(f"Switched chat engine model to '{model_name}'")
        elif model_name not in llm_collection:
            logger.warning(f"Requested model '{model_name}' not found. Using default model '{actual_model_name}'.")
            # Optionally, you can return an error or continue with the default model

        data_dir = os.path.join(os.path.dirname(__file__), "data")

        # Retrieve chat memory
        memory_path, memory = build_chat_memory(data_dir=data_dir, conversation_id=conversation_id)
        chat_history = memory.chat_store.get_messages("chat_history")

        LAST_K_MESSAGES = int(os.getenv("LAST_K_MESSAGES", 3))
        last_k_messages = chat_history[-LAST_K_MESSAGES:]

        # Stream-based response
        response = chat_engine.stream_chat(user_message, last_k_messages)

        def event_stream():
            try:
                full_response = ''
                for token in response.response_gen:
                    full_response += token
                    yield token

                # Persist chat after finishing
                chat_engine._memory.chat_store.persist(persist_path=memory_path)
                logger.info("Chat memory persisted for conversation_id: %s", conversation_id)

                resources = {}
                # If "[--]" is a delimiter you use to detect no sources, adjust as needed
                if "[--]" not in full_response:
                    RESOURCE_CONFIDENCE_SCORE = float(os.getenv("RESOURCE_CONFIDENCE_SCORE", 0.5))
                    resources = get_resources(
                        source_nodes=response.source_nodes,
                        confidece_score=RESOURCE_CONFIDENCE_SCORE
                    )

                # Append sources to the end in JSON format
                fonti_text = json.dumps({
                    "response": " ",  # placeholder or real final chunk
                    "sources": resources or {"Info:" ["No sources available."]}
                })
                yield fonti_text
            except Exception as ex:
                logger.error("Error Chat: %s. Trace: %s", str(ex), traceback.format_exc())
                yield "\nThere was an error while processing the request."

        logger.info("Processing ask request for conversation_id: %s", conversation_id)
        return Response(stream_with_context(event_stream()), content_type='text/plain'), 200

    except Exception as ex:
        logger.error("Error Chat: %s. Trace: %s", str(ex), traceback.format_exc())
        return jsonify({
            "response": f"Error Chat: {str(ex)}. Trace: {traceback.format_exc()}",
            "fonti": None,
        }), 500

# Initialize the application at module load
try:
    init_app()
except Exception as e:
    print(f"Application failed to initialize: {e}")

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=8080)
    except Exception as e:
        logger.error("Failed to run the Flask app: %s", str(e))
