import os

from qdrant_client.http import models
import qdrant_client
import json
from fastembed import SparseTextEmbedding
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

import dotenv

dotenv.load_dotenv()

# Specifica il percorso del file JSON
file_path = "./qdrant_integration/base_dati.json"

# Collection name
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333)) if QDRANT_HOST=="localhost" else None
QDRANT_API_KEY= None if QDRANT_HOST=="localhost" else os.environ.get("QDRANT_API_KEY")

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "test_collection")

HUGGING_FACE_EMBEDDING_SPARSE_ENDPOINT = os.getenv('HUGGING_FACE_EMBEDDING_SPARSE_ENDPOINT') # ex. "prithivida/Splade_PP_en_v1" "Qdrant/bm42-all-minilm-l6-v2-attentions"
HUGGING_FACE_EMBEDDING_ENDPOINT = os.getenv('HUGGING_FACE_EMBEDDING_ENDPOINT') # ex. "sentence-transformers/paraphrase-multilingual-mpnet-base-v2" "Snowflake/snowflake-arctic-embed-l-v2.0"
HUGGING_FACE_EMBEDDING_SIZE = int(os.getenv('HUGGING_FACE_EMBEDDING_SIZE'))

# Modelli da utilizzare
embed_model = HuggingFaceEmbedding(model_name=HUGGING_FACE_EMBEDDING_ENDPOINT, trust_remote_code=True)
embed_sparse_model = SparseTextEmbedding(model_name=HUGGING_FACE_EMBEDDING_SPARSE_ENDPOINT)


client = qdrant_client.QdrantClient(url=QDRANT_HOST, port=QDRANT_PORT, api_key=QDRANT_API_KEY)


if not client.collection_exists(collection_name=COLLECTION_NAME):
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "text-dense": models.VectorParams(size=HUGGING_FACE_EMBEDDING_SIZE, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={
            "text-sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)
        }
    )

def calculate_embeddings(testo):
    dense_vector = embed_model.get_text_embedding(testo)
    #sparse_vector = embed_sparse_model.embed(testo)
    sparse_vector = embed_sparse_model.query_embed([testo])
    return dense_vector, list(sparse_vector)  
    

# Apri e leggi il file JSON
json_file =  open(file_path, "r", encoding="utf-8")
json_file = json.load(json_file)


for node in json_file['points']:
    if node['payload']['text'] != '':
        dense_vector, sparse_vector = calculate_embeddings(node['payload']['text'])
        client.upload_points(
            collection_name=COLLECTION_NAME,
            points=[models.PointStruct(id=node['id'],
            vector={
                "text-dense": dense_vector,
                "text-sparse": sparse_vector[0].as_object()
            },
            payload={
                "text": node['payload']['text'],
                "n_pag": node['payload']['n_pag'],
                "file_path": node['payload']['file_path'],
                "file_name": node['payload']['file_name']
            }
        )])

print("Processo completato!")