# admin.py
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from django.shortcuts import redirect
from django.contrib import messages
from .models import Hotel, Habitacion, Huesped, Reserva
from datetime import date, timedelta

# ============================================
# FILTROS PERSONALIZADOS
# ============================================

class HotelFilter(admin.SimpleListFilter):
    """Filtro por hotel"""
    title = 'Hotel'
    parameter_name = 'hotel'
    
    def lookups(self, request, model_admin):
        hoteles = Hotel.objects.all()
        return [(h.id, h.nombre) for h in hoteles]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(habitacion__hotel__id=self.value())
        return queryset


class FechaReservaFilter(admin.SimpleListFilter):
    """Filtro por fecha de reserva"""
    title = 'Fecha de reserva'
    parameter_name = 'fecha_reserva'
    
    def lookups(self, request, model_admin):
        return [
            ('hoy', 'Hoy'),
            ('manana', 'Mañana'),
            ('semana', 'Esta semana'),
            ('mes', 'Este mes'),
            ('proximas', 'Próximas 2 semanas'),
        ]
    
    def queryset(self, request, queryset):
        hoy = timezone.now().date()
        
        if self.value() == 'hoy':
            return queryset.filter(fecha_reserva=hoy)
        elif self.value() == 'manana':
            manana = hoy + timedelta(days=1)
            return queryset.filter(fecha_reserva=manana)
        elif self.value() == 'semana':
            fin_semana = hoy + timedelta(days=7)
            return queryset.filter(fecha_reserva__range=[hoy, fin_semana])
        elif self.value() == 'mes':
            fin_mes = hoy + timedelta(days=30)
            return queryset.filter(fecha_reserva__range=[hoy, fin_mes])
        elif self.value() == 'proximas':
            fin = hoy + timedelta(days=14)
            return queryset.filter(fecha_reserva__range=[hoy, fin])
        
        return queryset


# ============================================
# ACCIONES PERSONALIZADAS
# ============================================

@admin.action(description='✅ Confirmar reservas seleccionadas')
def confirmar_reservas(modeladmin, request, queryset):
    for reserva in queryset:
        if reserva.estado != 'confirmada':
            reserva.estado = 'confirmada'
            reserva.save()
            modeladmin.message_user(
                request,
                f'Reserva #{reserva.id} confirmada para {reserva.huesped.nombre}',
                messages.SUCCESS
            )


@admin.action(description='❌ Cancelar reservas seleccionadas')
def cancelar_reservas(modeladmin, request, queryset):
    for reserva in queryset:
        if reserva.estado != 'cancelada':
            reserva.estado = 'cancelada'
            reserva.save()
            modeladmin.message_user(
                request,
                f'Reserva #{reserva.id} cancelada',
                messages.WARNING
            )


@admin.action(description='📧 Enviar recordatorio por email')
def enviar_recordatorio(modeladmin, request, queryset):
    # Aquí iría la lógica para enviar emails
    # Por ahora solo muestra un mensaje
    count = queryset.count()
    modeladmin.message_user(
        request,
        f'Se enviarían recordatorios para {count} reservas',
        messages.INFO
    )


# ============================================
# ADMIN INLINE PARA HABITACIONES
# ============================================

class HabitacionInline(admin.TabularInline):
    """Habitaciones dentro del admin de Hotel"""
    model = Habitacion
    extra = 0
    fields = ['numero', 'cantidad_plazas', 'estado_badge', 'reservas_pendientes_count']
    readonly_fields = ['estado_badge', 'reservas_pendientes_count']
    
    def estado_badge(self, obj):
        hoy = timezone.now().date()
        if obj.esta_disponible(hoy):
            return format_html('<span class="badge bg-success">Disponible</span>')
        else:
            return format_html('<span class="badge bg-danger">Ocupada</span>')
    estado_badge.short_description = 'Estado hoy'
    
    def reservas_pendientes_count(self, obj):
        count = obj.reservas_pendientes().count()
        if count > 0:
            url = reverse('admin:reservas_reserva_changelist')
            url += f'?habitacion__id__exact={obj.id}&estado__exact=pendiente'
            return format_html('<a href="{}">{} pendiente(s)</a>', url, count)
        return "0"
    reservas_pendientes_count.short_description = 'Reservas pendientes'


class ReservaInline(admin.TabularInline):
    """Reservas dentro del admin de Habitación"""
    model = Reserva
    extra = 0
    fields = ['huesped', 'fecha_reserva', 'estado_badge', 'cantidad_personas']
    readonly_fields = ['estado_badge']
    
    def estado_badge(self, obj):
        colors = {
            'pendiente': 'warning',
            'confirmada': 'success',
            'cancelada': 'danger',
            'rechazada': 'secondary',
            'completada': 'info'
        }
        color = colors.get(obj.estado, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'


# ============================================
# ADMIN PARA HOTEL
# ============================================

@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'direccion_corta', 'habitaciones_count', 
                   'reservas_pendientes_count', 'acciones']
    list_filter = ['generar_habitaciones_auto']
    search_fields = ['nombre', 'direccion', 'reseña']
    readonly_fields = ['habitaciones_count', 'reservas_pendientes_count']
    inlines = [HabitacionInline]
    actions = ['generar_habitaciones_action']
    
    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'direccion', 'foto', 'reseña')
        }),
        ('Configuración', {
            'fields': ('cantidad_habitaciones', 'generar_habitaciones_auto')
        }),
        ('Estadísticas', {
            'fields': ('habitaciones_count', 'reservas_pendientes_count'),
            'classes': ('collapse',)
        }),
    )
    
    def direccion_corta(self, obj):
        if len(obj.direccion) > 40:
            return obj.direccion[:40] + '...'
        return obj.direccion
    direccion_corta.short_description = 'Dirección'
    
    def habitaciones_count(self, obj):
        count = obj.habitacion_set.count()
        url = reverse('admin:reservas_habitacion_changelist')
        url += f'?hotel__id__exact={obj.id}'
        return format_html('<a href="{}">{} habitaciones</a>', url, count)
    habitaciones_count.short_description = 'Habitaciones'
    
    def reservas_pendientes_count(self, obj):
        count = obj.reservas_pendientes_hotel().count()
        if count > 0:
            url = reverse('admin:reservas_reserva_changelist')
            url += f'?hotel={obj.id}&estado__exact=pendiente'
            return format_html(
                '<a href="{}" style="color: #d63384; font-weight: bold;">{} pendiente(s)</a>',
                url, count
            )
        return "0"
    reservas_pendientes_count.short_description = 'Reservas pendientes'
    
    def acciones(self, obj):
        # Botón para ver habitaciones disponibles hoy
        hoy = timezone.now().date().isoformat()
        url_disponibles = reverse('admin:reservas_habitacion_changelist')
        url_disponibles += f'?hotel__id__exact={obj.id}&disponible_hoy=1'
        
        # Botón para ver reservas del hotel
        url_reservas = reverse('admin:reservas_reserva_changelist')
        url_reservas += f'?hotel={obj.id}'
        
        return format_html(
            '''
            <div style="display: flex; gap: 5px;">
                <a href="{}" class="button" style="padding: 5px 10px; background: #0d6efd; color: white; border-radius: 4px; text-decoration: none;">
                    🏨 Habitaciones
                </a>
                <a href="{}" class="button" style="padding: 5px 10px; background: #198754; color: white; border-radius: 4px; text-decoration: none;">
                    📅 Reservas
                </a>
                <a href="{}" class="button" style="padding: 5px 10px; background: #6f42c1; color: white; border-radius: 4px; text-decoration: none;">
                    ✅ Disponibles hoy
                </a>
            </div>
            ''',
            url_disponibles.replace('&disponible_hoy=1', ''),
            url_reservas,
            url_disponibles
        )
    acciones.short_description = 'Acciones'
    
    @admin.action(description='🔄 Generar habitaciones para hoteles seleccionados')
    def generar_habitaciones_action(self, request, queryset):
        for hotel in queryset:
            if hotel.generar_habitaciones_auto:
                count = hotel.generar_habitaciones()
                self.message_user(
                    request,
                    f'Generadas {count} habitaciones para {hotel.nombre}',
                    messages.SUCCESS
                )


# ============================================
# ADMIN PARA HABITACIÓN
# ============================================

@admin.register(Habitacion)
class HabitacionAdmin(admin.ModelAdmin):
    list_display = ['numero', 'hotel_link', 'cantidad_plazas', 
                   'estado_hoy', 'reservas_pendientes_count', 'proximas_reservas']
    list_filter = ['hotel', 'cantidad_plazas']
    search_fields = ['numero', 'hotel__nombre']
    readonly_fields = ['estado_hoy', 'reservas_pendientes_count', 'proximas_reservas']
    inlines = [ReservaInline]
    
    fieldsets = (
        ('Información', {
            'fields': ('hotel', 'numero', 'cantidad_plazas')
        }),
        ('Disponibilidad', {
            'fields': ('estado_hoy', 'reservas_pendientes_count', 'proximas_reservas')
        }),
    )
    
    def hotel_link(self, obj):
        url = reverse('admin:reservas_hotel_change', args=[obj.hotel.id])
        return format_html('<a href="{}">{}</a>', url, obj.hotel.nombre)
    hotel_link.short_description = 'Hotel'
    
    def estado_hoy(self, obj):
        hoy = timezone.now().date()
        if obj.esta_disponible(hoy):
            return format_html(
                '<span class="badge bg-success" style="font-size: 12px;">✅ Disponible</span>'
            )
        else:
            # Verificar si está reservada
            reserva = Reserva.objects.filter(
                habitacion=obj,
                fecha_reserva=hoy,
                estado__in=['confirmada', 'pendiente']
            ).first()
            if reserva:
                url = reverse('admin:reservas_reserva_change', args=[reserva.id])
                return format_html(
                    '<span class="badge bg-danger" style="font-size: 12px;">'
                    '❌ Ocupada - <a href="{}" style="color: white;">Ver reserva</a>'
                    '</span>',
                    url
                )
            return format_html(
                '<span class="badge bg-secondary" style="font-size: 12px;">No disponible</span>'
            )
    estado_hoy.short_description = 'Estado hoy'
    
    def reservas_pendientes_count(self, obj):
        count = obj.reservas_pendientes().count()
        if count > 0:
            url = reverse('admin:reservas_reserva_changelist')
            url += f'?habitacion__id__exact={obj.id}&estado__exact=pendiente'
            return format_html(
                '<a href="{}" style="color: #d63384; font-weight: bold;">{} pendiente(s)</a>',
                url, count
            )
        return "0"
    reservas_pendientes_count.short_description = 'Reservas pendientes'
    
    def proximas_reservas(self, obj):
        reservas = obj.proximas_reservas()[:3]  # Solo las próximas 3
        if reservas:
            html = '<ul style="margin: 0; padding-left: 20px;">'
            for r in reservas:
                url = reverse('admin:reservas_reserva_change', args=[r.id])
                estado_color = 'success' if r.estado == 'confirmada' else 'warning'
                html += f'''
                <li style="margin-bottom: 3px;">
                    <a href="{url}">{r.fecha_reserva}</a>
                    <span class="badge bg-{estado_color}" style="font-size: 10px; margin-left: 5px;">
                        {r.get_estado_display()}
                    </span>
                </li>
                '''
            html += '</ul>'
            return format_html(html)
        return "Sin reservas futuras"
    proximas_reservas.short_description = 'Próximas reservas'


# ============================================
# ADMIN PARA HUÉSPED
# ============================================

@admin.register(Huesped)
class HuespedAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'email', 'telefono', 'reservas_activas_count', 'ultima_reserva']
    search_fields = ['nombre', 'email', 'telefono']
    readonly_fields = ['reservas_activas_count', 'historial_reservas_list']
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre', 'email', 'telefono')
        }),
        ('Historial', {
            'fields': ('reservas_activas_count', 'historial_reservas_list'),
            'classes': ('collapse',)
        }),
    )
    
    def reservas_activas_count(self, obj):
        count = obj.reservas_activas().count()
        if count > 0:
            url = reverse('admin:reservas_reserva_changelist')
            url += f'?huesped__id__exact={obj.id}&estado__in=confirmada,pendiente'
            return format_html('<a href="{}">{} reserva(s) activa(s)</a>', url, count)
        return "0"
    reservas_activas_count.short_description = 'Reservas activas'
    
    def ultima_reserva(self, obj):
        ultima = obj.reserva_set.order_by('-fecha_reserva').first()
        if ultima:
            url = reverse('admin:reservas_reserva_change', args=[ultima.id])
            return format_html(
                '<a href="{}">{}</a> - <span class="badge bg-{}">{}</span>',
                url,
                ultima.fecha_reserva,
                'success' if ultima.estado == 'confirmada' else 'warning',
                ultima.get_estado_display()
            )
        return "Sin reservas"
    ultima_reserva.short_description = 'Última reserva'
    
    def historial_reservas_list(self, obj):
        reservas = obj.historial_reservas()[:10]
        if reservas:
            html = '<table style="width: 100%; border-collapse: collapse;">'
            html += '''
            <thead>
                <tr style="background: #f8f9fa;">
                    <th style="padding: 8px; border: 1px solid #dee2e6;">Fecha</th>
                    <th style="padding: 8px; border: 1px solid #dee2e6;">Hotel</th>
                    <th style="padding: 8px; border: 1px solid #dee2e6;">Habitación</th>
                    <th style="padding: 8px; border: 1px solid #dee2e6;">Estado</th>
                </tr>
            </thead>
            <tbody>
            '''
            for r in reservas:
                estado_color = {
                    'confirmada': 'success',
                    'pendiente': 'warning',
                    'cancelada': 'danger',
                    'completada': 'info'
                }.get(r.estado, 'secondary')
                
                url = reverse('admin:reservas_reserva_change', args=[r.id])
                html += f'''
                <tr>
                    <td style="padding: 8px; border: 1px solid #dee2e6;">
                        <a href="{url}">{r.fecha_reserva}</a>
                    </td>
                    <td style="padding: 8px; border: 1px solid #dee2e6;">
                        {r.habitacion.hotel.nombre if r.habitacion else '-'}
                    </td>
                    <td style="padding: 8px; border: 1px solid #dee2e6;">
                        {r.habitacion.numero if r.habitacion else '-'}
                    </td>
                    <td style="padding: 8px; border: 1px solid #dee2e6;">
                        <span class="badge bg-{estado_color}">
                            {r.get_estado_display()}
                        </span>
                    </td>
                </tr>
                '''
            html += '</tbody></table>'
            return format_html(html)
        return "No hay historial de reservas"
    historial_reservas_list.short_description = 'Historial (últimas 10)'


# ============================================
# ADMIN PARA RESERVA (EL MÁS IMPORTANTE)
# ============================================

@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ['id', 'huesped_link', 'hotel_info', 'habitacion_info',
                   'fecha_reserva', 'dias_restantes_badge', 'estado_badge',
                   'acciones_rapidas']
    list_filter = [HotelFilter, FechaReservaFilter, 'estado']
    search_fields = ['huesped__nombre', 'huesped__email', 
                    'habitacion__hotel__nombre', 'habitacion__numero']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion', 
                      'dias_restantes_display', 'total_estimado_display']
    list_per_page = 50
    actions = [confirmar_reservas, cancelar_reservas, enviar_recordatorio]
    
    fieldsets = (
        ('Información Principal', {
            'fields': ('huesped', 'fecha_reserva', 'cantidad_personas', 'estado')
        }),
        ('Alojamiento', {
            'fields': ('habitacion', 'hotel_info_display')
        }),
        ('Administración', {
            'fields': ('notas_admin', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
        ('Información Adicional', {
            'fields': ('dias_restantes_display', 'total_estimado_display'),
            'classes': ('collapse',)
        }),
    )
    
    def huesped_link(self, obj):
        url = reverse('admin:reservas_huesped_change', args=[obj.huesped.id])
        return format_html('<a href="{}">{}</a>', url, obj.huesped.nombre)
    huesped_link.short_description = 'Huésped'
    
    def hotel_info(self, obj):
        if obj.habitacion:
            url = reverse('admin:reservas_hotel_change', args=[obj.habitacion.hotel.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.habitacion.hotel.nombre[:20]
            )
        return "-"
    hotel_info.short_description = 'Hotel'
    
    def hotel_info_display(self, obj):
        if obj.habitacion:
            return obj.habitacion.hotel.nombre
        return "Sin habitación asignada"
    hotel_info_display.short_description = 'Hotel'
    
    def habitacion_info(self, obj):
        if obj.habitacion:
            url = reverse('admin:reservas_habitacion_change', args=[obj.habitacion.id])
            return format_html(
                '<a href="{}">Hab. {} ({})</a>',
                url,
                obj.habitacion.numero,
                obj.habitacion.cantidad_plazas
            )
        return format_html(
            '<span style="color: #dc3545; font-weight: bold;">⚠️ SIN ASIGNAR</span>'
        )
    habitacion_info.short_description = 'Habitación'
    
    def dias_restantes_badge(self, obj):
        dias = obj.dias_restantes()
        if dias < 0:
            return format_html(
                '<span class="badge bg-secondary">Pasada</span>'
            )
        elif dias == 0:
            return format_html(
                '<span class="badge bg-warning" style="color: black;">HOY</span>'
            )
        elif dias <= 3:
            return format_html(
                '<span class="badge bg-danger">En {} días</span>',
                dias
            )
        elif dias <= 7:
            return format_html(
                '<span class="badge bg-warning" style="color: black;">En {} días</span>',
                dias
            )
        else:
            return format_html(
                '<span class="badge bg-success">En {} días</span>',
                dias
            )
    dias_restantes_badge.short_description = 'Falta'
    
    def dias_restantes_display(self, obj):
        dias = obj.dias_restantes()
        if dias > 0:
            return f"{dias} días"
        elif dias == 0:
            return "HOY"
        else:
            return f"Hace {abs(dias)} días (pasada)"
    dias_restantes_display.short_description = 'Días restantes'
    
    def estado_badge(self, obj):
        colors = {
            'pendiente': 'warning',
            'confirmada': 'success',
            'cancelada': 'danger',
            'rechazada': 'secondary',
            'completada': 'info'
        }
        color = colors.get(obj.estado, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def total_estimado_display(self, obj):
        return f"${obj.total_estimado()}"
    total_estimado_display.short_description = 'Total estimado'
    
    def acciones_rapidas(self, obj):
        html = '<div style="display: flex; gap: 5px; flex-wrap: nowrap;">'
        
        # Botón confirmar
        if obj.estado != 'confirmada':
            confirm_url = reverse('admin:reserva_confirmar', args=[obj.id])
            html += f'''
            <a href="{confirm_url}" 
               class="button" 
               style="padding: 3px 8px; background: #198754; color: white; border-radius: 4px; text-decoration: none; font-size: 12px;">
               ✅
            </a>
            '''
        
        # Botón cancelar
        if obj.estado not in ['cancelada', 'rechazada']:
            cancel_url = reverse('admin:reserva_cancelar', args=[obj.id])
            html += f'''
            <a href="{cancel_url}" 
               class="button" 
               style="padding: 3px 8px; background: #dc3545; color: white; border-radius: 4px; text-decoration: none; font-size: 12px;">
               ❌
            </a>
            '''
        
        # Botón cambiar habitación
        change_room_url = reverse('admin:reserva_cambiar_habitacion', args=[obj.id])
        html += f'''
        <a href="{change_room_url}" 
           class="button" 
           style="padding: 3px 8px; background: #0dcaf0; color: white; border-radius: 4px; text-decoration: none; font-size: 12px;">
           🔄
        </a>
        '''
        
        html += '</div>'
        return format_html(html)
    acciones_rapidas.short_description = 'Acciones'
    
    # Vistas personalizadas para acciones rápidas
    def get_urls(self):
        from django.urls import path
        
        urls = super().get_urls()
        custom_urls = [
            path('<int:reserva_id>/confirmar/',
                 self.admin_site.admin_view(self.confirmar_reserva),
                 name='reserva_confirmar'),
            path('<int:reserva_id>/cancelar/',
                 self.admin_site.admin_view(self.cancelar_reserva),
                 name='reserva_cancelar'),
            path('<int:reserva_id>/cambiar-habitacion/',
                 self.admin_site.admin_view(self.cambiar_habitacion),
                 name='reserva_cambiar_habitacion'),
        ]
        return custom_urls + urls
    
    def confirmar_reserva(self, request, reserva_id):
        """Vista para confirmar una reserva"""
        reserva = Reserva.objects.get(id=reserva_id)
        
        # Verificar disponibilidad
        if not reserva.habitacion.esta_disponible(reserva.fecha_reserva):
            # Buscar habitaciones alternativas
            habitaciones_alternativas = reserva.habitacion.hotel.habitaciones_disponibles(
                reserva.fecha_reserva
            ).filter(cantidad_plazas__gte=reserva.cantidad_personas)
            
            if habitaciones_alternativas.exists():
                self.message_user(
                    request,
                    f'La habitación {reserva.habitacion.numero} no está disponible. '
                    f'Hay {habitaciones_alternativas.count()} alternativas.',
                    messages.WARNING
                )
                # Redirigir a página de selección de habitación alternativa
                return redirect('admin:reserva_cambiar_habitacion', reserva_id=reserva.id)
            else:
                self.message_user(
                    request,
                    f'No hay habitaciones disponibles en {reserva.habitacion.hotel.nombre} '
                    f'para el {reserva.fecha_reserva}',
                    messages.ERROR
                )
                return redirect('admin:reservas_reserva_change', reserva_id)
        
        # Confirmar la reserva
        reserva.estado = 'confirmada'
        reserva.save()
        
        self.message_user(
            request,
            f'✅ Reserva #{reserva.id} confirmada para {reserva.huesped.nombre}',
            messages.SUCCESS
        )
        
        return redirect('admin:reservas_reserva_changelist')
    
    def cancelar_reserva(self, request, reserva_id):
        """Vista para cancelar una reserva"""
        reserva = Reserva.objects.get(id=reserva_id)
        reserva.estado = 'cancelada'
        reserva.save()
        
        self.message_user(
            request,
            f'❌ Reserva #{reserva.id} cancelada',
            messages.WARNING
        )
        
        return redirect('admin:reservas_reserva_changelist')
    
    def cambiar_habitacion(self, request, reserva_id):
        """Vista para cambiar la habitación de una reserva"""
        from django.shortcuts import render
        reserva = Reserva.objects.get(id=reserva_id)
        hotel = reserva.habitacion.hotel if reserva.habitacion else None
        
        if not hotel:
            self.message_user(
                request,
                'La reserva no tiene un hotel asignado',
                messages.ERROR
            )
            return redirect('admin:reservas_reserva_change', reserva_id)
        
        # Obtener habitaciones disponibles para esa fecha
        habitaciones_disponibles = hotel.habitaciones_disponibles(
            reserva.fecha_reserva
        ).filter(cantidad_plazas__gte=reserva.cantidad_personas)
        
        if request.method == 'POST':
            nueva_habitacion_id = request.POST.get('habitacion_id')
            if nueva_habitacion_id:
                nueva_habitacion = Habitacion.objects.get(id=nueva_habitacion_id)
                reserva.habitacion = nueva_habitacion
                reserva.save()
                
                self.message_user(
                    request,
                    f'🔄 Habitación cambiada a {nueva_habitacion.numero}',
                    messages.SUCCESS
                )
                return redirect('admin:reservas_reserva_change', reserva_id)
        
        context = {
            'reserva': reserva,
            'hotel': hotel,
            'habitaciones_disponibles': habitaciones_disponibles,
            'opts': self.model._meta,
            'title': f'Cambiar habitación - Reserva #{reserva.id}',
        }
        
        return render(request, 'admin/reservas/cambiar_habitacion.html', context)


# ============================================
# CONFIGURACIÓN GLOBAL DEL ADMIN
# ============================================

# Título del admin
admin.site.site_header = "🏨 Sistema de Reservas - TresVagos"
admin.site.site_title = "Administración de Reservas"
admin.site.index_title