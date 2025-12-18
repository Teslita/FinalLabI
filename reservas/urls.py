from django.urls import path
from . import views

urlpatterns = [
    # URL raíz va a la vista home
    path('', views.home, name='home'),
    
    # También puedes mantener la ruta hoteles/ por si acaso
    path('hoteles/', views.lista_hoteles, name='lista_hoteles'),
    
    # Proceso de reservas
    path('reservar/<int:hotel_id>/', views.reservar_hotel, name='reservar_hotel'),
    path('seleccionar-habitacion/', views.seleccionar_habitacion, name='seleccionar_habitacion'),
    path('completar-reserva/', views.completar_reserva, name='completar_reserva'),
    path('reserva/<int:reserva_id>/', views.detalle_reserva, name='detalle_reserva'),
    
    # Opcional: Vista para debug
    # path('debug/', views.debug_templates, name='debug'),
]