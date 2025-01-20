# localgpt_api/apps.py

from django.apps import AppConfig
import logging

class LocalgptApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'localgpt_api'

    def ready(self):
        from . import services
        try:
            services.init_app()
            logging.getLogger(__name__).info("LocalGPT services initialized successfully.")
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to initialize LocalGPT services: {e}")
