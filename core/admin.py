from django import forms
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.db.models import Q, Case, When, Value, IntegerField, F, CharField
from .models import (
    Proprietario,
    Gestor,
    Cavalo,
    Carreta,
    Motorista,
    LogCarreta,
    HistoricoGestor,
    CavaloDocumento,
    CarretaDocumento,
    ProprietarioDocumento,
    MotoristaDocumento,
)


_UFS_BR = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


# ── Inlines de documentos ─────────────────────────────────────────────────────

class ProprietarioDocumentoInline(admin.TabularInline):
    model = ProprietarioDocumento
    extra = 1


class CavaloDocumentoInline(admin.TabularInline):
    model = CavaloDocumento
    extra = 1


class CarretaDocumentoInline(admin.TabularInline):
    model = CarretaDocumento
    extra = 1


class MotoristaDocumentoInline(admin.TabularInline):
    model = MotoristaDocumento
    extra = 1


# ── Helpers de ordenacao ──────────────────────────────────────────────────────

def _cavalos_queryset_ordenado(queryset, filtrar_apenas_com_carreta=False):
    qs = queryset
    if filtrar_apenas_com_carreta:
        qs = qs.filter(Q(carreta__isnull=False) | Q(tipo="bi_truck")).exclude(situacao="desagregado")
    return qs.annotate(
        ordem_classificacao=Case(
            When(classificacao="agregado", then=Value(0)),
            When(classificacao="frota", then=Value(1)),
            When(classificacao="terceiro", then=Value(2)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        ordem_situacao=Case(
            When(situacao="ativo", then=Value(0)),
            When(situacao="parado", then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        ),
        ordem_fluxo=Case(
            When(fluxo="escoria", then=Value(0)),
            When(fluxo="minerio", then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        ),
        ordem_tipo=Case(
            When(tipo="toco", then=Value(0)),
            When(tipo="trucado", then=Value(1)),
            When(tipo="bi_truck", then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        ),
        motorista_nome_ordem=Case(
            When(motorista__isnull=False, then=F("motorista__nome")),
            default=Value(""),
            output_field=CharField(),
        ),
    ).order_by(
        "ordem_classificacao", "ordem_situacao", "ordem_fluxo",
        "ordem_tipo", "motorista_nome_ordem",
    )


# ── Form customizado do Cavalo (adiciona campo motorista) ─────────────────────

class CavaloAdminForm(forms.ModelForm):
    motorista = forms.ModelChoiceField(
        queryset=Motorista.objects.order_by("nome"),
        required=False,
        label="Motorista",
    )

    class Meta:
        model = Cavalo
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            try:
                self.fields["motorista"].initial = self.instance.motorista
            except Motorista.DoesNotExist:
                pass


# ── Proprietario ──────────────────────────────────────────────────────────────

@admin.register(Proprietario)
class ProprietarioAdmin(admin.ModelAdmin):
    list_display   = ("codigo", "nome_razao_social", "tipo", "status", "whatsapp")
    search_fields  = ("nome_razao_social", "codigo")
    inlines        = [ProprietarioDocumentoInline]


# ── Gestor ────────────────────────────────────────────────────────────────────

@admin.register(Gestor)
class GestorAdmin(admin.ModelAdmin):
    list_display = ("nome", "meta_faturamento")


# ── Cavalo ────────────────────────────────────────────────────────────────────

class _MotoristaRel:
    """Objeto fake de relacao para o RelatedFieldWidgetWrapper apontar para Motorista."""
    model = Motorista
    field_name = "id"
    limit_choices_to = {}

    def get_related_field(self):
        return Motorista._meta.get_field("id")


@admin.register(Cavalo)
class CavaloAdmin(admin.ModelAdmin):
    form                = CavaloAdminForm
    list_display        = ("placa", "tipo", "classificacao", "situacao", "proprietario", "gestor", "carreta", "emissao_laudo")
    list_filter         = ("tipo", "classificacao", "situacao", "fluxo")
    search_fields       = ("placa", "motorista__nome", "carreta__placa")
    list_select_related = ("motorista", "carreta", "gestor", "proprietario")
    inlines             = [CavaloDocumentoInline]
    fields = (
        "placa", "ano", "cor", "fluxo", "tipo", "classificacao",
        "foto", "carreta", "situacao", "proprietario", "motorista", "gestor",
        "documento", "emissao_laudo", "observacoes",
    )

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)
        # Aplica RelatedFieldWidgetWrapper ao campo motorista
        # para que tenha os botoes de adicionar, editar e visualizar
        form_class.base_fields["motorista"].widget = RelatedFieldWidgetWrapper(
            form_class.base_fields["motorista"].widget,
            _MotoristaRel(),
            self.admin_site,
            can_add_related=True,
            can_change_related=True,
            can_delete_related=False,
            can_view_related=True,
        )
        return form_class

    def get_search_results(self, request, queryset, search_term):
        import re
        cleaned    = re.sub(r"[^\w\s]", " ", search_term).strip()
        tokens     = [t for t in cleaned.upper().split() if t not in _UFS_BR]
        normalized = " ".join(tokens) if tokens else cleaned
        return super().get_search_results(request, queryset, normalized)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("motorista", "carreta", "gestor")
        return _cavalos_queryset_ordenado(qs, filtrar_apenas_com_carreta=False)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        novo = form.cleaned_data.get("motorista")
        # Desvincula motorista anterior se trocou
        try:
            atual = Motorista.objects.get(cavalo=obj)
            if atual != novo:
                atual.cavalo = None
                atual.save()
        except Motorista.DoesNotExist:
            pass
        # Vincula novo motorista
        if novo:
            # Se estava vinculado a outro cavalo, desvincula primeiro
            if novo.cavalo_id and novo.cavalo_id != obj.pk:
                Motorista.objects.filter(pk=novo.pk).update(cavalo=None)
            novo.cavalo = obj
            novo.save()


# ── Carreta ───────────────────────────────────────────────────────────────────

@admin.register(Carreta)
class CarretaAdmin(admin.ModelAdmin):
    list_display   = ("placa", "marca", "classificacao", "situacao", "emissao_laudo")
    list_filter    = ("classificacao", "situacao")
    search_fields  = ("placa",)
    exclude        = ("cones", "localizador", "step", "local", "modelo")
    inlines        = [CarretaDocumentoInline]

    def get_search_results(self, request, queryset, search_term):
        import re
        cleaned    = re.sub(r"[^\w\s]", " ", search_term).strip()
        tokens     = [t for t in cleaned.upper().split() if t not in _UFS_BR]
        normalized = " ".join(tokens) if tokens else cleaned
        return super().get_search_results(request, queryset, normalized)


# ── Motorista ─────────────────────────────────────────────────────────────────

@admin.register(Motorista)
class MotoristaAdmin(admin.ModelAdmin):
    list_display  = ("nome", "cpf", "whatsapp", "cavalo")
    search_fields = ("nome", "cpf")
    inlines       = [MotoristaDocumentoInline]

    def get_inline_instances(self, request, obj=None):
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)


# ── LogCarreta ────────────────────────────────────────────────────────────────

@admin.register(LogCarreta)
class LogCarretaAdmin(admin.ModelAdmin):
    list_display  = ("data_hora", "tipo", "placa_cavalo", "carreta_anterior", "carreta_nova")
    list_filter   = ("tipo",)
    date_hierarchy = "data_hora"


# ── HistoricoGestor ───────────────────────────────────────────────────────────

@admin.register(HistoricoGestor)
class HistoricoGestorAdmin(admin.ModelAdmin):
    list_display =