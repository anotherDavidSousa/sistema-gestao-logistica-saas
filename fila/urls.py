from django.urls import path
from . import views
from . import n8n_api

urlpatterns = [
    # Downloads de PDF (usados pelo admin via links diretos)
    path('ost/<int:pk>/download-pdf/', views.ost_download_pdf, name='ost_download_pdf'),
    path('cte/<int:pk>/download-pdf/', views.cte_download_pdf, name='cte_download_pdf'),

    # API integracao n8n
    path('api/n8n/ost/', n8n_api.api_n8n_ost_sync, name='api_n8n_ost_sync'),
    path('api/n8n/cte/', n8n_api.api_n8n_cte_sync, name='api_n8n_cte_sync'),
]
