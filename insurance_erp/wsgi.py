"""
WSGI config for insurance_erp project.

Exposes the WSGI callable as a module-level variable named ``application``.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "insurance_erp.settings")

application = get_wsgi_application()
