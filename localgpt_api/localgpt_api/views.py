# localgpt_api/views.py

import json
import logging
import traceback
import os

from django.http import JsonResponse, StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from . import services
from .serializers import NewAskSerializer, AskQuestionSerializer
from llama_index.core import Settings  # Import this to switch models

logger = logging.getLogger(__name__)

# Define manual schema for streaming responses if needed
streaming_response_schema = openapi.Schema(
    type=openapi.TYPE_STRING,
    description="Streamed response from the chatbot.",
)

@swagger_auto_schema(
    method='post',
    request_body=NewAskSerializer,
    responses={
        200: openapi.Response(
            description="Conversation reset successfully.",
            examples={"application/json": {"valid": True}}
        ),
        500: openapi.Response(
            description="Failed to reset conversation.",
            examples={"application/json": {"valid": False}}
        ),
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def new_ask(request):
    """
    Endpoint to start a fresh conversation by clearing the chat memory.
    """
    serializer = NewAskSerializer(data=request.data)
    if not serializer.is_valid():
        logger.error("Invalid data for new_ask: %s", serializer.errors)
        return JsonResponse(serializer.errors, status=400)
    
    try:
        conversation_id = serializer.validated_data.get("conversation_id", "default")

        data_dir = os.path.join(os.path.dirname(__file__), "data")
        # Ensure that localgpt_api/data/History folder exists
        os.makedirs(os.path.join(data_dir, "History"), exist_ok=True)

        services.reset_chat_memory(data_dir, conversation_id)

        logger.info("New conversation started with conversation_id: %s", conversation_id)
        return JsonResponse({"valid": True}, status=200)
    except Exception as ex:
        logger.error("Error New Chat: %s. Trace: %s", str(ex), traceback.format_exc())
        return JsonResponse({"valid": False}, status=500)

@swagger_auto_schema(
    method='post',
    request_body=AskQuestionSerializer,
    responses={
        200: openapi.Response(
            description="Streamed response from the chatbot.",
            schema=streaming_response_schema
        ),
        400: openapi.Response(
            description="Bad request, invalid parameters.",
            examples={"application/json": {"response": "No 'question' provided in the request.", "fonti": None}}
        ),
        500: openapi.Response(
            description="Internal server error.",
            examples={"application/json": {"response": "Error message", "fonti": None}}
        ),
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def ask_question(request):
    """
    Endpoint to get a response from the chat engine using RAG and memory.
    Streams the response back to the client.
    """
    serializer = AskQuestionSerializer(data=request.data)
    if not serializer.is_valid():
        logger.error("Invalid data for ask_question: %s", serializer.errors)
        return JsonResponse(serializer.errors, status=400)
    
    try:
        user_message = serializer.validated_data.get("question")
        conversation_id = serializer.validated_data.get("conversation_id", "default")
        model_name = serializer.validated_data.get("model_name", "phi3")

        # Ensure chat engine is initialized
        if not services.chat_engine:
            services.build_chat_engine()

        # Switch model if user requests a different one
        if model_name != services.actual_model_name and model_name in services.llm_collection:
            Settings.llm = services.llm_collection[model_name]
            services.build_chat_engine()
            services.actual_model_name = model_name
            logger.info(f"Switched chat engine model to '{model_name}'")
        elif model_name not in services.llm_collection:
            logger.warning(f"Requested model '{model_name}' not found. Using default model '{services.actual_model_name}'.")

        # Ensure that localgpt_api/data/History folder exists
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(os.path.join(data_dir, "History"), exist_ok=True)

        # Retrieve chat memory
        memory_path, memory = services.build_chat_memory(data_dir=data_dir, conversation_id=conversation_id)
        chat_history = memory.chat_store.get_messages("chat_history")

        LAST_K_MESSAGES = int(os.getenv("LAST_K_MESSAGES", 3))
        last_k_messages = chat_history[-LAST_K_MESSAGES:]

        # Get the streaming response
        response = services.chat_engine.stream_chat(user_message, last_k_messages)

        def event_stream():
            try:
                full_response = ''
                for token in response.response_gen:
                    full_response += token
                    yield token

                # Persist chat memory after finishing
                services.chat_engine._memory.chat_store.persist(persist_path=memory_path)
                logger.info("Chat memory persisted for conversation_id: %s", conversation_id)

                resources = {}
                # If "[--]" is a delimiter that indicates no sources, adjust as needed
                if "[--]" not in full_response:
                    RESOURCE_CONFIDENCE_SCORE = float(os.getenv("RESOURCE_CONFIDENCE_SCORE", 0.5))
                    resources = services.get_resources(
                        source_nodes=response.source_nodes,
                        confidence_score=RESOURCE_CONFIDENCE_SCORE
                    )

                # Append sources in JSON format at the end
                fonti_text = json.dumps({
                    "response": " ",  # placeholder or final chunk
                    "sources": resources or {"Info:": ["No sources available."]}
                })
                yield fonti_text
            except Exception as ex:
                logger.error("Error Chat: %s. Trace: %s", str(ex), traceback.format_exc())
                yield "\nThere was an error while processing the request."

        logger.info("Processing ask request for conversation_id: %s", conversation_id)
        return StreamingHttpResponse(event_stream(), content_type='text/plain', status=200)

    except Exception as ex:
        logger.error("Error Chat: %s. Trace: %s", str(ex), traceback.format_exc())
        return JsonResponse({
            "response": f"Error Chat: {str(ex)}. Trace: {traceback.format_exc()}",
            "fonti": None,
        }, status=500)
