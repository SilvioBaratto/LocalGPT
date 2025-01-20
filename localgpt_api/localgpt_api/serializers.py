# localgpt_api/serializers.py

from rest_framework import serializers

class NewAskSerializer(serializers.Serializer):
    conversation_id = serializers.CharField(
        max_length=100, 
        required=False, 
        default="default",
        help_text="Unique identifier for the conversation."
    )

class AskQuestionSerializer(serializers.Serializer):
    question = serializers.CharField(
        max_length=1000, 
        help_text="The question to ask the chatbot."
    )
    conversation_id = serializers.CharField(
        max_length=100, 
        required=False, 
        default="default",
        help_text="Unique identifier for the conversation."
    )
    model_name = serializers.CharField(
        max_length=100, 
        required=False, 
        default="phi3",
        help_text="Name of the model to use (e.g., 'phi3', 'llama3.2')."
    )
