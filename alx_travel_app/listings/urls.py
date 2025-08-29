from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (ListingViewSet, BookingViewSet, InitiatePaymentView, VerifyPaymentView,
                   UserRegistrationView, UserLoginView, UserProfileView)

router = DefaultRouter()
router.register(r'listings', ListingViewSet)
router.register(r'bookings', BookingViewSet, basename='booking')

urlpatterns = [
    path('', include(router.urls)),
    path('payments/initiate/', InitiatePaymentView.as_view(), name='initiate-payment'),
    path('payments/verify/', VerifyPaymentView.as_view(), name='verify-payment'),
    path('auth/register/', UserRegistrationView.as_view(), name='user-register'),
    path('auth/login/', UserLoginView.as_view(), name='user-login'),
    path('auth/profile/', UserProfileView.as_view(), name='user-profile'),
]
