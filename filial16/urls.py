from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from fila import views as fila_views
from fila import n8n_api
from core.views_dashboard import (
    dashboard_api,
    global_search_api,
    mapa_veiculos_api,
    mapa_cidades_api,
    mapa_cidade_toggle,
    frota_ultima_posicao,
    frota_historico_view,
    frota_historico_api,
)

urlpatterns = [
    # Raiz -> painel admin
    path('', RedirectView.as_view(url='/admin/', permanent=False)),

    # -- Dashboard & busca global ----------------------------------------------
    path('admin/dashboard-api/', dashboard_api, name='admin_dashboard_api'),
    path('admin/global-search/', global_search_api, name='admin_global_search'),

    # -- APIs do mapa (usadas pelo dashboard) ----------------------------------
    path('admin/mapa-api/veiculos/', mapa_veiculos_api, name='admin_mapa_veiculos'),
    path('admin/mapa-api/cidades/', mapa_cidades_api, name='admin_mapa_cidades'),
    path('admin/mapa-api/cidades/<int:pk>/toggle/', mapa_cidade_toggle, name='admin_mapa_cidade_toggle'),
    path('admin/mapa-api/posicao/<str:placa>/', frota_ultima_posicao, name='admin_frota_ultima_posicao'),

    # -- Historico de frota ----------------------------------------------------
    path('admin/frota/historico/', frota_historico_view, name='admin_frota_historico'),
    path('admin/frota/historico/api/', frota_historico_api, name='admin_frota_historico_api'),

    path('admin/', admin.site.urls),

    # -- Downloads de PDF (OST e CT-e) -----------------------------------------
    path('ost/<int:pk>/download-pdf/', fila_views.ost_download_pdf, name='ost_download_pdf'),
    path('cte/<int:pk>/download-pdf/', fila_views.cte_download_pdf, name='cte_download_pdf'),

    # -- API integracao n8n ----------------------------------------------------
    path('api/n8n/ost/', n8n_api.api_n8n_ost_sync, name='api_n8n_ost_sync'),
    path('api/n8n/cte/', n8n_api.api_n8n_cte_sync, name='api_n8n_cte_sync'),
]
