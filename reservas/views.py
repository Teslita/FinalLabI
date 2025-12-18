from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
import random
from .models import Hotel, Habitacion, Huesped, Reserva

# ========== PÁGINA PRINCIPAL ==========
def home(request):
    """Página principal - lista de hoteles"""
    return lista_hoteles(request)

def lista_hoteles(request):
    """Muestra todos los hoteles con paginación"""
    # Obtener todos los hoteles
    hoteles_list = Hotel.objects.all().order_by('nombre')
    
    # Configurar paginación (20 hoteles por página)
    paginator = Paginator(hoteles_list, 20)
    
    # Obtener el número de página de la URL
    page_number = request.GET.get('page')
    
    try:
        hoteles = paginator.page(page_number)
    except PageNotAnInteger:
        # Si page no es un entero, mostrar primera página
        hoteles = paginator.page(1)
    except EmptyPage:
        # Si page está fuera de rango, mostrar última página
        hoteles = paginator.page(paginator.num_pages)
    
    context = {
        'hoteles': hoteles,
    }
    return render(request, 'lista_hoteles.html', context)  # SIN CARPETA

# ========== PROCESO DE RESERVA ==========
def reservar_hotel(request, hotel_id):
    """Paso 1: Seleccionar fecha y cantidad de personas"""
    hotel = get_object_or_404(Hotel, id=hotel_id)
    
    # Fechas por defecto
    fecha_minima = timezone.now().date()
    fecha_maxima = fecha_minima + timedelta(days=365)  # 1 año máximo
    
    if request.method == 'POST':
        fecha_reserva = request.POST.get('fecha_reserva')
        cantidad_personas = request.POST.get('cantidad_personas')
        
        if fecha_reserva and cantidad_personas:
            try:
                # Convertir fecha
                fecha_obj = datetime.strptime(fecha_reserva, '%Y-%m-%d').date()
                
                # Validar fecha
                if fecha_obj < fecha_minima:
                    messages.error(request, 'La fecha no puede ser anterior a hoy.')
                elif fecha_obj > fecha_maxima:
                    messages.error(request, 'La fecha no puede ser mayor a 1 año.')
                else:
                    # Guardar en sesión
                    request.session['fecha_reserva'] = fecha_reserva
                    request.session['cantidad_personas'] = int(cantidad_personas)
                    request.session['hotel_id'] = hotel_id
                    
                    return redirect('seleccionar_habitacion')
            except ValueError:
                messages.error(request, 'Fecha inválida.')
        else:
            messages.error(request, 'Por favor completa todos los campos.')
    
    context = {
        'hotel': hotel,
        'fecha_minima': fecha_minima.strftime('%Y-%m-%d'),
        'fecha_maxima': fecha_maxima.strftime('%Y-%m-%d'),
        'fecha_hoy': fecha_minima.strftime('%Y-%m-%d'),
    }
    return render(request, 'seleccionar_fecha.html', context)  # SIN CARPETA

def seleccionar_habitacion(request):
    """Paso 2: Seleccionar habitación disponible"""
    # Recuperar datos de sesión
    fecha_reserva = request.session.get('fecha_reserva')
    cantidad_personas = request.session.get('cantidad_personas')
    hotel_id = request.session.get('hotel_id')
    
    if not all([fecha_reserva, cantidad_personas, hotel_id]):
        messages.error(request, 'Por favor selecciona fecha y cantidad de personas primero.')
        return redirect('home')
    
    hotel = get_object_or_404(Hotel, id=hotel_id)
    fecha_obj = datetime.strptime(fecha_reserva, '%Y-%m-%d').date()
    
    # Obtener habitaciones disponibles para esa fecha
    # 1. Habitaciones del hotel con capacidad suficiente
    habitaciones_capacidad = Habitacion.objects.filter(
        hotel=hotel,
        cantidad_plazas__gte=cantidad_personas
    ).order_by('cantidad_plazas', 'numero')
    
    # 2. Excluir las que ya tienen reserva para esa fecha
    habitaciones_reservadas = Reserva.objects.filter(
        fecha_reserva=fecha_obj,
        estado__in=['confirmada', 'pendiente']
    ).values_list('habitacion_id', flat=True)
    
    # 3. Habitaciones disponibles
    habitaciones_disponibles = habitaciones_capacidad.exclude(
        id__in=habitaciones_reservadas
    )
    
    # Agrupar por cantidad de plazas
    habitaciones_por_plazas = {}
    for habitacion in habitaciones_disponibles:
        plazas = habitacion.cantidad_plazas
        if plazas not in habitaciones_por_plazas:
            habitaciones_por_plazas[plazas] = []
        habitaciones_por_plazas[plazas].append(habitacion)
    
    if request.method == 'POST':
        habitacion_id = request.POST.get('habitacion_id')
        if habitacion_id:
            habitacion = get_object_or_404(Habitacion, id=habitacion_id)
            
            # Guardar habitación seleccionada en sesión
            request.session['habitacion_id'] = habitacion_id
            
            # Redirigir a formulario de datos del huésped
            return redirect('completar_reserva')
    
    context = {
        'hotel': hotel,
        'fecha_reserva': fecha_obj,
        'fecha_formateada': fecha_obj.strftime('%d/%m/%Y'),
        'cantidad_personas': cantidad_personas,
        'habitaciones_disponibles': habitaciones_disponibles,
        'habitaciones_por_plazas': dict(sorted(habitaciones_por_plazas.items())),
        'total_disponibles': habitaciones_disponibles.count(),
        'habitaciones_reservadas': len(habitaciones_reservadas),
    }
    return render(request, 'seleccionar_habitacion.html', context)  # SIN CARPETA

def completar_reserva(request):
    """Paso 3: Completar datos del huésped"""
    # Recuperar datos de sesión
    fecha_reserva = request.session.get('fecha_reserva')
    cantidad_personas = request.session.get('cantidad_personas')
    hotel_id = request.session.get('hotel_id')
    habitacion_id = request.session.get('habitacion_id')
    
    if not all([fecha_reserva, cantidad_personas, hotel_id, habitacion_id]):
        messages.error(request, 'Información de reserva incompleta.')
        return redirect('home')
    
    hotel = get_object_or_404(Hotel, id=hotel_id)
    habitacion = get_object_or_404(Habitacion, id=habitacion_id)
    fecha_obj = datetime.strptime(fecha_reserva, '%Y-%m-%d').date()
    
    if request.method == 'POST':
        # Crear o buscar huésped
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        telefono = request.POST.get('telefono')
        
        # Buscar huésped existente por email o crear nuevo
        huesped, created = Huesped.objects.get_or_create(
            email=email,
            defaults={'nombre': nombre, 'telefono': telefono}
        )
        
        # Si existe pero los datos son diferentes, actualizar
        if not created:
            if huesped.nombre != nombre or huesped.telefono != telefono:
                huesped.nombre = nombre
                huesped.telefono = telefono
                huesped.save()
        
        # Crear reserva
        reserva = Reserva.objects.create(
            huesped=huesped,
            fecha_reserva=fecha_obj,
            cantidad_personas=cantidad_personas,
            habitacion=habitacion,
            estado='pendiente'
        )
        
        # Limpiar sesión
        for key in ['fecha_reserva', 'cantidad_personas', 'hotel_id', 'habitacion_id']:
            if key in request.session:
                del request.session[key]
        
        messages.success(request, f'✅ Reserva creada exitosamente. Número de reserva: #{reserva.id}')
        return redirect('detalle_reserva', reserva_id=reserva.id)
    
    context = {
        'hotel': hotel,
        'habitacion': habitacion,
        'fecha_reserva': fecha_obj,
        'fecha_formateada': fecha_obj.strftime('%d/%m/%Y'),
        'cantidad_personas': cantidad_personas,
    }
    return render(request, 'completar_reserva.html', context)  # SIN CARPETA

def detalle_reserva(request, reserva_id):
    """Paso 4: Mostrar confirmación de reserva"""
    reserva = get_object_or_404(Reserva, id=reserva_id)
    
    context = {
        'reserva': reserva,
    }
    return render(request, 'detalle_reserva.html', context)  # SIN CARPETA