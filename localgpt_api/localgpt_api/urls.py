# localgpt_api/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('new_ask/', views.new_ask, name='new_ask'),
    path('ask/', views.ask_question, name='ask_question'),
]
