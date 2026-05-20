from django import forms
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.db.models import Q, Case, When, Value, IntegerField, F, CharField
from django.utils.html import format_html
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
    CidadeEntrega,
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
        try:
            atual = Motorista.objects.get(cavalo=obj)
            if atual != novo:
                atual.cavalo = None
                atual.save()
        except Motorista.DoesNotExist:
            pass
        if novo:
            if novo.cavalo_id and novo.cavalo_id != obj.pk:
                Motorista.objects.filter(pk=novo.pk).update(cavalo=None)
            novo.cavalo = obj
            novo.save()


# ── Carreta ───────────────────────────────────────────────────────────────────

# ── Filtro de disponibilidade de carretas ────────────────────────────────────

class _CarretaDisponivelFilter(admin.SimpleListFilter):
    title        = 'Disponibilidade'
    parameter_name = 'disponivel'

    def lookups(self, request, model_admin):
        return [
            ('sim', 'Disponíveis (agregamento sem cavalo)'),
            ('nao', 'Já agregadas (com cavalo vinculado)'),
        ]

    def queryset(self, request, queryset):
        # Apenas carretas de agregamento
        qs = queryset.filter(classificacao='agregado')
        # IDs de carretas que têm um Cavalo vinculado
        from .models import Cavalo as _Cavalo
        placas_usadas = set(
            _Cavalo.objects.filter(carreta__isnull=False)
            .values_list('carreta_id', flat=True)
        )
        if self.value() == 'sim':
            return qs.exclude(pk__in=placas_usadas)
        if self.value() == 'nao':
            return qs.filter(pk__in=placas_usadas)
        return queryset


@admin.register(Carreta)
class CarretaAdmin(admin.ModelAdmin):
    list_display   = ("placa", "marca", "classificacao", "situacao", "disponivel_display", "emissao_laudo")
    list_filter    = ("classificacao", "situacao", _CarretaDisponivelFilter)
    search_fields  = ("placa",)
    exclude        = ("cones", "localizador", "step", "local", "modelo")
    inlines        = [CarretaDocumentoInline]
    change_list_template = "admin/core/carreta/change_list.html"

    def disponivel_display(self, obj):
        if obj.classificacao != 'agregado':
            return '—'
        disp = obj.disponivel
        if disp:
            return format_html(
                '<span style="color:#15803d;font-weight:700;">'
                '<i class="fas fa-check-circle"></i> Disponível</span>'
            )
        return format_html(
            '<span style="color:#6b7280;">'
            '<i class="fas fa-link"></i> Agregada</span>'
        )
    disponivel_display.short_description = 'Status'

    def get_search_results(self, request, queryset, search_term):
        import re
        cleaned    = re.sub(r"[^\w\s]", " ", search_term).strip()
        tokens     = [t for t in cleaned.upper().split() if t not in _UFS_BR]
        normalized = " ".join(tokens) if tokens else cleaned
        return super().get_search_results(request, queryset, normalized)

    def changelist_view(self, request, extra_context=None):
        from .models import Cavalo as _Cavalo
        total_agr = Carreta.objects.filter(classificacao='agregado').count()
        usadas_ids = set(
            _Cavalo.objects.filter(carreta__isnull=False)
            .values_list('carreta_id', flat=True)
        )
        ja_agregadas  = Carreta.objects.filter(classificacao='agregado', pk__in=usadas_ids).count()
        disponiveis   = total_agr - ja_agregadas
        extra_context = extra_context or {}
        extra_context.update({
            'carreta_cards': {
                'total_agr':    total_agr,
                'ja_agregadas': ja_agregadas,
                'disponiveis':  disponiveis,
            }
        })
        return super().changelist_view(request, extra_context=extra_context)


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
    list_display = ("gestor", "cavalo", "data_inicio", "data_fim")


# ── CidadeEntrega ────────────────────────────────────────────────────────────

class _ColorPickerWidget(forms.TextInput):
    input_type = 'color'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({
            'style': 'width:56px;height:36px;padding:2px 4px;border:1px solid #ccc;'
                     'border-radius:6px;cursor:pointer;vertical-align:middle',
        })


_DIAGRAM_HTML = (
    '<div style="margin:12px 0 4px;max-width:340px;font-size:12px;">'
    '<div style="background:#f0f9ff;border:2px solid #3b82f6;border-radius:8px;'
    'padding:10px 14px;line-height:2;">'
    '<strong style="color:#1e40af;">Como preencher o polígono:</strong><br>'
    'Pense na cidade como um <strong>retângulo no mapa</strong>.<br>'
    'Abra o <a href="https://www.google.com/maps" target="_blank" style="color:#2563eb;">Google Maps</a>, '
    'clique nos 4 cantos da área e copie as coordenadas.<br><br>'
    '<span style="font-family:monospace;background:#dbeafe;padding:2px 6px;border-radius:4px;">'
    '↖ Sup. Esq.</span> &nbsp;&nbsp;&nbsp; '
    '<span style="font-family:monospace;background:#dbeafe;padding:2px 6px;border-radius:4px;">'
    'Sup. Dir. ↗</span><br>'
    '<span style="font-family:monospace;background:#dbeafe;padding:2px 6px;border-radius:4px;">'
    '↙ Inf. Esq.</span> &nbsp;&nbsp;&nbsp; '
    '<span style="font-family:monospace;background:#dbeafe;padding:2px 6px;border-radius:4px;">'
    'Inf. Dir. ↘</span><br><br>'
    '<strong>Dica:</strong> No Google Maps, clique com o botão direito num ponto '
    'e selecione a coordenada que aparece — ela copia automaticamente.<br>'
    '<strong>Lat</strong> = primeiro número (ex.: -19.47) &nbsp;|&nbsp; '
    '<strong>Long</strong> = segundo número (ex.: -42.54)'
    '</div></div>'
)


def _coord_field(label, placeholder_lat, placeholder_lng, axis):
    ph = placeholder_lat if axis == 'lat' else placeholder_lng
    return forms.FloatField(
        label=label,
        required=False,
        widget=forms.NumberInput(attrs={
            'step': 'any',
            'placeholder': ph,
            'style': 'width:160px;',
        }),
    )


class _CidadeEntregaForm(forms.ModelForm):
    """
    Form simplificado: 4 pares lat/lng nomeados pelos cantos do retângulo.
    Ordem interna do polígono: [sup_esq, sup_dir, inf_dir, inf_esq].
    """

    # Ponta superior esquerda (noroeste)
    lat1 = _coord_field('Latitude',  '-19.460', '-42.550', 'lat')
    lng1 = _coord_field('Longitude', '-19.460', '-42.580', 'lng')
    # Ponta superior direita (nordeste)
    lat2 = _coord_field('Latitude',  '-19.460', '-42.510', 'lat')
    lng2 = _coord_field('Longitude', '-19.460', '-42.510', 'lng')
    # Ponta inferior direita (sudeste)
    lat3 = _coord_field('Latitude',  '-19.490', '-42.510', 'lat')
    lng3 = _coord_field('Longitude', '-19.490', '-42.510', 'lng')
    # Ponta inferior esquerda (sudoeste)
    lat4 = _coord_field('Latitude',  '-19.490', '-42.580', 'lat')
    lng4 = _coord_field('Longitude', '-19.490', '-42.580', 'lng')

    class Meta:
        model   = CidadeEntrega
        fields  = ('nome', 'cor', 'ativa_semana')
        widgets = {'cor': _ColorPickerWidget()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.poligono:
            for i, ponto in enumerate(self.instance.poligono[:4], start=1):
                if len(ponto) >= 2:
                    self.fields[f'lat{i}'].initial = ponto[0]
                    self.fields[f'lng{i}'].initial = ponto[1]

    def save(self, commit=True):
        instance = super().save(commit=False)
        pontos = []
        for i in range(1, 5):
            lat = self.cleaned_data.get(f'lat{i}')
            lng = self.cleaned_data.get(f'lng{i}')
            if lat is not None and lng is not None:
                pontos.append([lat, lng])
        instance.poligono = pontos
        if commit:
            instance.save()
        return instance


@admin.register(CidadeEntrega)
class CidadeEntregaAdmin(admin.ModelAdmin):
    form          = _CidadeEntregaForm
    list_display  = ("nome", "cor_preview", "ativa_semana", "atualizado_em")
    list_filter   = ("ativa_semana",)
    search_fields = ("nome",)
    list_editable = ("ativa_semana",)
    ordering      = ("nome",)

    fieldsets = (
        (None, {
            'fields': ('nome', 'cor', 'ativa_semana'),
        }),
        ('Área no Mapa — 4 Cantos do Retângulo', {
            'description': _DIAGRAM_HTML,
            'fields': (
                ('lat1', 'lng1'),
                ('lat2', 'lng2'),
                ('lat3', 'lng3'),
                ('lat4', 'lng4'),
            ),
            'classes': ('wide',),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        fs = super().get_fieldsets(request, obj)
        # Renomeia as subseções com os nomes dos cantos
        labels = [
            '↖ Superior Esquerda (Noroeste)',
            '↗ Superior Direita (Nordeste)',
            '↘ Inferior Direita (Sudeste)',
            '↙ Inferior Esquerda (Sudoeste)',
        ]
        for i, lbl in enumerate(labels, start=1):
            self.form.declared_fields[f'lat{i}'].label = lbl + ' — Latitude'
            self.form.declared_fields[f'lng{i}'].label = lbl + ' — Longitude'
        return fs

    def cor_preview(self, obj):
        return format_html(
            '<span style="display:inline-block;width:22px;height:22px;'
            'background:{};border:1px solid #ccc;border-radius:4px;'
            'vertical-align:middle;margin-right:6px"></span>{}',
            obj.cor, obj.cor,
        )
    cor_preview.short_description = "Cor"


# ── LogEntry (historico de acoes do admin) ────────────────────────────────────

@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display   = ("action_time", "user", "content_type", "object_repr", "action_flag_display", "change_message")
    list_filter    = ("action_flag", "content_type")
    search_fields  = ("user__username", "object_repr", "change_message")
    date_hierarchy = "action_time"
    readonly_fields = (
        "action_time", "user", "content_type", "object_id",
        "object_repr", "action_flag", "change_message",
    )

    def action_flag_display(self, obj):
        flags = {1: "Adicao", 2: "Alteracao", 3: "Exclusao"}
        return flags.get(obj.action_flag, obj.action_flag)
    action_flag_display.short_description = "Acao"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
