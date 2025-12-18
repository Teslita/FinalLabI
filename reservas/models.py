# models.py
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import random
from datetime import date, timedelta

# ============================================
# MODELO HOTEL
# ============================================

class Hotel(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=200)
    foto = models.ImageField(upload_to='hoteles/', default='hoteles/default.jpg', blank=True)
    reseña = models.TextField()
    cantidad_habitaciones = models.IntegerField()
    
    generar_habitaciones_auto = models.BooleanField(
        default=True, 
        verbose_name="Generar habitaciones automáticamente"
    )

    def __str__(self):
        return self.nombre
    
    def generar_habitaciones(self):
        """Genera la cantidad exacta de habitaciones especificada"""
        # Verificar si ya tiene habitaciones
        if self.habitacion_set.exists():
            return self.habitacion_set.count()
        
        habitaciones_creadas = 0
        tipos_plazas = [1, 2, 2, 3, 4]  # Más probabilidad para 2 plazas
        
        for i in range(1, self.cantidad_habitaciones + 1):
            # Crear número de habitación simple: 1, 2, 3, etc.
            numero = str(i)
            
            # Seleccionar cantidad de plazas aleatoria
            plazas = random.choice(tipos_plazas)
            
            # Crear la habitación
            Habitacion.objects.create(
                hotel=self,
                numero=numero,
                cantidad_plazas=plazas
            )
            habitaciones_creadas += 1
        
        return habitaciones_creadas
    
    def habitaciones_disponibles(self, fecha=None):
        """Devuelve las habitaciones disponibles para una fecha específica"""
        if fecha is None:
            fecha = timezone.now().date()
        
        # Habitaciones reservadas para esa fecha
        habitaciones_reservadas = Reserva.objects.filter(
            fecha_reserva=fecha,
            estado__in=['confirmada', 'pendiente'],
            habitacion__hotel=self
        ).values_list('habitacion_id', flat=True)
        
        # Todas las habitaciones del hotel excepto las reservadas
        return self.habitacion_set.exclude(id__in=habitaciones_reservadas)
    
    def reservas_pendientes(self):
        """Devuelve las reservas pendientes de este hotel"""
        return self.reservas_pendientes_hotel()
    
    def reservas_pendientes_hotel(self):
        """Reservas pendientes para todas las habitaciones del hotel"""
        reservas_ids = self.habitacion_set.values_list('reserva__id', flat=True)
        return Reserva.objects.filter(
            id__in=reservas_ids,
            estado='pendiente'
        )
    
    def habitaciones_count(self):
        """Número total de habitaciones"""
        return self.habitacion_set.count()
    
    def proximas_reservas(self):
        """Próximas reservas del hotel"""
        return Reserva.objects.filter(
            habitacion__hotel=self,
            fecha_reserva__gte=timezone.now().date()
        ).order_by('fecha_reserva')
    
    class Meta:
        verbose_name = "Hotel"
        verbose_name_plural = "Hoteles"
        ordering = ['nombre']


# ============================================
# MODELO HABITACIÓN
# ============================================

class Habitacion(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE)
    numero = models.CharField(max_length=10)
    cantidad_plazas = models.IntegerField()

    def __str__(self):
        return f'Habitación {self.numero} - {self.hotel.nombre} - {self.cantidad_plazas} plazas'
    
    def esta_disponible(self, fecha):
        """Verifica si la habitación está disponible para una fecha"""
        return not Reserva.objects.filter(
            habitacion=self,
            fecha_reserva=fecha,
            estado__in=['confirmada', 'pendiente']
        ).exists()
    
    def proximas_reservas(self):
        """Próximas reservas de esta habitación"""
        return self.reserva_set.filter(
            fecha_reserva__gte=timezone.now().date()
        ).order_by('fecha_reserva')
    
    def reservas_pendientes(self):
        """Reservas pendientes para esta habitación"""
        return self.reserva_set.filter(estado='pendiente')
    
    def reservas_count(self):
        """Número total de reservas"""
        return self.reserva_set.count()
    
    def ultima_reserva(self):
        """Última reserva de esta habitación"""
        return self.reserva_set.order_by('-fecha_reserva').first()
    
    class Meta:
        verbose_name = "Habitación"
        verbose_name_plural = "Habitaciones"
        ordering = ['hotel', 'numero']
        unique_together = ['hotel', 'numero']


# ============================================
# MODELO HUÉSPED
# ============================================

class Huesped(models.Model):
    nombre = models.CharField(max_length=100)
    email = models.EmailField()
    telefono = models.CharField(max_length=15)

    def __str__(self):
        return f'{self.nombre} ({self.email})'
    
    def reservas_activas(self):
        """Reservas activas del huésped"""
        return self.reserva_set.filter(
            fecha_reserva__gte=timezone.now().date(),
            estado__in=['confirmada', 'pendiente']
        )
    
    def historial_reservas(self):
        """Todas las reservas del huésped"""
        return self.reserva_set.all().order_by('-fecha_reserva')
    
    def reservas_count(self):
        """Número total de reservas"""
        return self.reserva_set.count()
    
    def ultima_reserva(self):
        """Última reserva del huésped"""
        return self.reserva_set.order_by('-fecha_reserva').first()
    
    def tiene_reservas_pendientes(self):
        """Verifica si tiene reservas pendientes"""
        return self.reserva_set.filter(estado='pendiente').exists()
    
    class Meta:
        verbose_name = "Huésped"
        verbose_name_plural = "Huéspedes"
        ordering = ['nombre']


# ============================================
# MODELO RESERVA
# ============================================

class Reserva(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('confirmada', 'Confirmada'),
        ('cancelada', 'Cancelada'),
        ('rechazada', 'Rechazada'),
        ('completada', 'Completada'),
    ]
    
    huesped = models.ForeignKey(Huesped, on_delete=models.CASCADE)
    fecha_reserva = models.DateField()
    cantidad_personas = models.IntegerField()
    habitacion = models.ForeignKey(Habitacion, on_delete=models.SET_NULL, null=True, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='pendiente')
    
    # Campos adicionales para administración
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    notas_admin = models.TextField(blank=True, verbose_name="Notas del administrador")

    def __str__(self):
        return f'Reserva #{self.id} - {self.huesped.nombre} - {self.fecha_reserva}'
    
    def save(self, *args, **kwargs):
        """Sobreescribir save para lógica de negocio"""
        # Si la reserva se confirma, verificar disponibilidad
        if self.estado == 'confirmada' and self.pk and self.habitacion:
            # Verificar que la habitación siga disponible
            reservas_conflictivas = Reserva.objects.filter(
                habitacion=self.habitacion,
                fecha_reserva=self.fecha_reserva,
                estado__in=['confirmada', 'pendiente']
            ).exclude(id=self.id)
            
            if reservas_conflictivas.exists():
                raise ValueError("La habitación ya está reservada para esta fecha")
        
        super().save(*args, **kwargs)
    
    def dias_restantes(self):
        """Días restantes para la reserva"""
        hoy = timezone.now().date()
        return (self.fecha_reserva - hoy).days
    
    def esta_proxima(self):
        """¿Es una reserva próxima? (menos de 7 días)"""
        return 0 <= self.dias_restantes() <= 7
    
    def esta_pasada(self):
        """¿Es una reserva pasada?"""
        return self.dias_restantes() < 0
    
    def total_estimado(self):
        """Total estimado de la reserva"""
        # Precio base: $50 por plaza por noche
        if self.habitacion:
            return self.habitacion.cantidad_plazas * 50
        return 0
    
    def hotel(self):
        """Hotel de la reserva"""
        if self.habitacion:
            return self.habitacion.hotel
        return None
    
    def puede_confirmar(self):
        """Verifica si la reserva puede confirmarse"""
        if not self.habitacion:
            return False
        return self.habitacion.esta_disponible(self.fecha_reserva) and self.estado == 'pendiente'
    
    def puede_cancelar(self):
        """Verifica si la reserva puede cancelarse"""
        return self.estado in ['pendiente', 'confirmada']
    
    def obtener_alternativas(self):
        """Obtiene habitaciones alternativas disponibles"""
        if not self.habitacion:
            return Habitacion.objects.none()
        
        hotel = self.habitacion.hotel
        return hotel.habitaciones_disponibles(self.fecha_reserva).filter(
            cantidad_plazas__gte=self.cantidad_personas
        ).exclude(id=self.habitacion.id)
    
    class Meta:
        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"
        ordering = ['-fecha_reserva', '-fecha_creacion']


# ============================================
# SIGNALS (SEÑALES)
# ============================================

@receiver(post_save, sender=Hotel)
def crear_habitaciones_al_guardar_hotel(sender, instance, created, **kwargs):
    """
    Signal que se ejecuta después de guardar un hotel.
    Genera las habitaciones automáticamente si está activada la opción.
    """
    if created and instance.generar_habitaciones_auto:
        instance.generar_habitaciones()


# ============================================
# MÉTODOS ADICIONALES PARA EL PANEL DE ADMIN
# ============================================

def get_reservas_pendientes_count():
    """Total de reservas pendientes en el sistema"""
    return Reserva.objects.filter(estado='pendiente').count()

def get_reservas_hoy():
    """Reservas para hoy"""
    hoy = timezone.now().date()
    return Reserva.objects.filter(fecha_reserva=hoy, estado='confirmada')

def get_reservas_proximas():
    """Reservas próximas (próximos 7 días)"""
    hoy = timezone.now().date()
    proxima_semana = hoy + timedelta(days=7)
    return Reserva.objects.filter(
        fecha_reserva__range=[hoy, proxima_semana],
        estado='confirmada'
    )

def get_hoteles_con_reservas_pendientes():
    """Hoteles que tienen reservas pendientes"""
    return Hotel.objects.filter(
        habitacion__reserva__estado='pendiente'
    ).distinct()

def get_habitaciones_sin_reservas(fecha=None):
    """Habitaciones sin reservas para una fecha específica"""
    if fecha is None:
        fecha = timezone.now().date()
    
    habitaciones_reservadas = Reserva.objects.filter(
        fecha_reserva=fecha,
        estado__in=['confirmada', 'pendiente']
    ).values_list('habitacion_id', flat=True)
    
    return Habitacion.objects.exclude(id__in=habitaciones_reservadas)


# ============================================
# MÉTODOS DE CONVENIENCIA
# ============================================

def crear_reserva_desde_admin(huesped_id, fecha_reserva, cantidad_personas, hotel_id, habitacion_id=None):
    """
    Crea una reserva desde el panel de administración
    """
    try:
        huesped = Huesped.objects.get(id=huesped_id)
        hotel = Hotel.objects.get(id=hotel_id)
        
        if habitacion_id:
            habitacion = Habitacion.objects.get(id=habitacion_id)
        else:
            # Buscar habitación disponible automáticamente
            habitaciones_disponibles = hotel.habitaciones_disponibles(fecha_reserva).filter(
                cantidad_plazas__gte=cantidad_personas
            )
            if not habitaciones_disponibles.exists():
                return None, "No hay habitaciones disponibles"
            habitacion = habitaciones_disponibles.first()
        
        # Verificar que la habitación esté disponible
        if not habitacion.esta_disponible(fecha_reserva):
            return None, "La habitación seleccionada no está disponible"
        
        reserva = Reserva.objects.create(
            huesped=huesped,
            fecha_reserva=fecha_reserva,
            cantidad_personas=cantidad_personas,
            habitacion=habitacion,
            estado='confirmada'  # Confirmada automáticamente desde admin
        )
        
        return reserva, "Reserva creada exitosamente"
        
    except Exception as e:
        return None, f"Error: {str(e)}"

def cambiar_habitacion_reserva(reserva_id, nueva_habitacion_id):
    """
    Cambia la habitación de una reserva
    """
    try:
        reserva = Reserva.objects.get(id=reserva_id)
        nueva_habitacion = Habitacion.objects.get(id=nueva_habitacion_id)
        
        # Verificar disponibilidad
        if not nueva_habitacion.esta_disponible(reserva.fecha_reserva):
            return False, "La nueva habitación no está disponible"
        
        # Verificar capacidad
        if nueva_habitacion.cantidad_plazas < reserva.cantidad_personas:
            return False, "La habitación no tiene capacidad suficiente"
        
        reserva.habitacion = nueva_habitacion
        reserva.save()
        
        return True, "Habitación cambiada exitosamente"
        
    except Exception as e:
        return False, f"Error: {str(e)}"

def confirmar_reserva_masiva(reserva_ids):
    """
    Confirma múltiples reservas a la vez
    """
    exitosas = 0
    fallidas = []
    
    for reserva_id in reserva_ids:
        try:
            reserva = Reserva.objects.get(id=reserva_id)
            if reserva.puede_confirmar():
                reserva.estado = 'confirmada'
                reserva.save()
                exitosas += 1
            else:
                fallidas.append(f"Reserva #{reserva_id} no se puede confirmar")
        except Exception as e:
            fallidas.append(f"Reserva #{reserva_id}: {str(e)}")
    
    return exitosas, fallidas

# ============================================
# PROPIEDADES DE DISPLAY PARA ADMIN
# ============================================

@property
def reserva_estado_color(self):
    """Color para el estado de la reserva"""
    colores = {
        'pendiente': 'warning',
        'confirmada': 'success',
        'cancelada': 'danger',
        'rechazada': 'secondary',
        'completada': 'info'
    }
    return colores.get(self.estado, 'secondary')

@property
def reserva_prioridad(self):
    """Prioridad de la reserva para el admin"""
    if self.esta_pasada():
        return 0
    elif self.dias_restantes() == 0:
        return 3  # Alta prioridad: es hoy
    elif self.dias_restantes() <= 2:
        return 2  # Media prioridad: próximos 2 días
    elif self.dias_restantes() <= 7:
        return 1  # Baja prioridad: próxima semana
    return 0  # Sin prioridad

# Asignar propiedades dinámicamente
Reserva.estado_color = reserva_estado_color
Reserva.prioridad = reserva_prioridad