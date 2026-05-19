from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from .models import OST, CTe


def _badge(text, bg, fg):
    return format_html(
        '<span style="background:{};color:{};padding:2px 10px;border-radius:20px;'
        'font-size:0.78em;font-weight:600;white-space:nowrap">{}</span>',
        bg, fg, text,
    )



# ── OST ───────────────────────────────────────────────────────────────────────

@admin.register(OST)
class OSTAdmin(admin.ModelAdmin):
    list_display = (
        'numero_ost', 'data_manifesto_fmt', 'motorista', 'placa_cavalo',
        'placa_carreta', 'remetente_curto', 'destinatario_curto',
        'nota_fiscal_display', 'peso', 'pdf_link',
    )
    list_filter    = ('data_manifesto',)
    search_fields  = (
        'filial', 'serie', 'documento', 'remetente', 'destinatario',
        'chave_acesso', 'motorista', 'placa_cavalo', 'placa_carreta',
    )
    readonly_fields = ('criado_em', 'pdf_storage_key')
    date_hierarchy  = 'criado_em'
    list_per_page   = 50

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        term = (search_term or '').strip()
        if term:
            from django.db.models import Q
            q_nf = Q(nota_fiscal__contains=[term])
            try:
                q_nf |= Q(nota_fiscal__contains=[int(term)])
            except ValueError:
                pass
            qs_nf = self.model.objects.filter(q_nf)
            queryset = (queryset | qs_nf).distinct()
            use_distinct = True
        return queryset, use_distinct

    @admin.display(description='OST', ordering='documento')
    def numero_ost(self, obj):
        partes = [obj.filial, obj.serie, obj.documento]
        return '.'.join(p for p in partes if p) or f'#{obj.pk}'

    @admin.display(description='Data', ordering='data_manifesto')
    def data_manifesto_fmt(self, obj):
        if obj.data_manifesto:
            s = obj.data_manifesto.strftime('%d/%m/%Y')
            if obj.hora_manifesto:
                s += format_html(' <span style="color:#9ca3af">{}</span>', obj.hora_manifesto.strftime('%H:%M'))
            return format_html('{}', s) if not obj.hora_manifesto else format_html(
                '{} <span style="color:#9ca3af">{}</span>',
                obj.data_manifesto.strftime('%d/%m/%Y'),
                obj.hora_manifesto.strftime('%H:%M'),
            )
        return '—'

    @admin.display(description='Remetente')
    def remetente_curto(self, obj):
        r = obj.remetente or ''
        return format_html('<span title="{}">{}</span>', r, r[:30] + '…' if len(r) > 30 else r) if r else '—'

    @admin.display(description='Destinatário')
    def destinatario_curto(self, obj):
        d = obj.destinatario or ''
        return format_html('<span title="{}">{}</span>', d, d[:30] + '…' if len(d) > 30 else d) if d else '—'

    @admin.display(description='Nota(s) fiscal')
    def nota_fiscal_display(self, obj):
        if not obj.nota_fiscal:
            return '—'
        if isinstance(obj.nota_fiscal, list):
            return ', '.join(str(x) for x in obj.nota_fiscal[:3]) + ('…' if len(obj.nota_fiscal) > 3 else '')
        return str(obj.nota_fiscal)

    @admin.display(description='PDF')
    def pdf_link(self, obj):
        if obj.pdf_storage_key:
            url = reverse('ost_download_pdf', args=[obj.pk]) + '?inline=1'
            return format_html(
                '<a href="{}" target="_blank" style="color:#2563eb;font-weight:700;font-size:.85em">'
                '⬇ PDF</a>', url
            )
        return format_html('<span style="color:#d1d5db">—</span>')


# ── CTe ───────────────────────────────────────────────────────────────────────

@admin.register(CTe)
class CTeAdmin(admin.ModelAdmin):
    list_display = (
        'numero_cte', 'data_emissao_fmt', 'motorista', 'placa_cavalo',
        'placa_carreta', 'remetente_curto', 'destinatario_curto',
        'nota_fiscal', 'valor_total', 'pdf_link',
    )
    list_filter    = ('data_emissao',)
    search_fields  = (
        'filial', 'serie', 'numero_cte', 'remetente', 'destinatario',
        'motorista', 'nota_fiscal', 'chave_nfe', 'placa_cavalo', 'placa_carreta',
    )
    readonly_fields = ('criado_em', 'pdf_storage_key')
    date_hierarchy  = 'data_emissao'
    list_per_page   = 50

    @admin.display(description='CT-e', ordering='numero_cte')
    def numero_cte(self, obj):
        partes = [obj.filial, obj.serie, obj.numero_cte]
        return '/'.join(p for p in partes if p) or f'#{obj.pk}'

    @admin.display(description='Data', ordering='data_emissao')
    def data_emissao_fmt(self, obj):
        if obj.data_emissao:
            if obj.hora_emissao:
                return format_html(
                    '{} <span style="color:#9ca3af">{}</span>',
                    obj.data_emissao.strftime('%d/%m/%Y'),
                    obj.hora_emissao.strftime('%H:%M'),
                )
            return obj.data_emissao.strftime('%d/%m/%Y')
        return '—'

    @admin.display(description='Remetente')
    def remetente_curto(self, obj):
        r = obj.remetente or ''
        return format_html('<span title="{}">{}</span>', r, r[:30] + '…' if len(r) > 30 else r) if r else '—'

    @admin.display(description='Destinatário')
    def destinatario_curto(self, obj):
        d = obj.destinatario or ''
        return format_html('<span title="{}">{}</span>', d, d[:30] + '…' if len(d) > 30 else d) if d else '—'

    @admin.display(description='PDF')
    def pdf_link(self, obj):
        if obj.pdf_storage_key:
            url = reverse('cte_download_pdf', args=[obj.pk]) + '?inline=1'
            return format_html(
                '<a href="{}" target="_blank" style="color:#2563eb;font-weight:700;font-size:.85em">'
                '⬇ PDF</a>', url
            )
        return format_html('<span style="color:#d1d5db">—</span>')
