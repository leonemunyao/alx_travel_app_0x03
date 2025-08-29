import os
import requests
import time
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .models import Listing, Booking, Review, Payment
from .serializers import ListingSerializer, BookingSerializer, ReviewSerializer
from django.conf import settings


class ListingViewSet(viewsets.ModelViewSet):
    """
    A viewset for viewing and editing listings.
    """
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class BookingViewSet(viewsets.ModelViewSet):
    """
    A viewset for viewing and editing bookings.
    """
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only bookings for the current user"""
        return Booking.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        booking = serializer.save(user=self.request.user)
        # Send booking confirmation email asynchronously
        from .tasks import send_booking_confirmation_email
        subject = 'Booking Confirmation'
        message = f'Thank you for your booking, {self.request.user.username}! Your booking ID is {booking.id}.'
        to_email = self.request.user.email
        send_booking_confirmation_email.delay(to_email, subject, message)


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]


# --- Payment API Views ---
class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        booking_id = request.data.get('booking_id')
        amount = request.data.get('amount')
        user = request.user

        try:
            booking = Booking.objects.get(id=booking_id, user=user)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

        chapa_url = 'https://api.chapa.co/v1/transaction/initialize'
        headers = {
            'Authorization': f'Bearer {os.getenv("CHAPA_SECRET_KEY", getattr(settings, "CHAPA_SECRET_KEY", ""))}',
            'Content-Type': 'application/json',
        }

        unique_tx_ref = f'booking_{booking.id}_{int(time.time())}'

        data = {
            'amount': str(amount),
            'currency': 'ETB',
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'tx_ref': unique_tx_ref,
            'callback_url': request.build_absolute_uri('/api/payments/verify/'),
            'return_url': request.build_absolute_uri('/api/payments/verify/'),
        }


        try:
            response = requests.post(chapa_url, json=data, headers=headers)

            print(f"Chapa Response Status: {response.status_code}")
            print(f"Chapa Response: {response.text}")
            
            if response.status_code == 200:
                resp_data = response.json()
                if resp_data.get('status') == 'success':
                    transaction_id = unique_tx_ref
                    
                    payment = Payment.objects.create(
                        booking=booking,
                        amount=amount,
                        transaction_id=transaction_id,
                        status='pending'
                    )
                    
                    payment_url = resp_data['data']['checkout_url']
                    return Response({
                        'payment_url': payment_url, 
                        'transaction_id': transaction_id,
                        'status': 'pending'
                    }, status=200)
                else:
                    return Response({
                        'error': resp_data.get('message', 'Payment initiation failed.')
                    }, status=400)
            else:
                return Response({
                    'error': f'Chapa API error: {response.status_code} - {response.text}'
                }, status=500)
                
        except requests.exceptions.RequestException as e:
            return Response({'error': f'Network error: {str(e)}'}, status=500)
        except Exception as e:
            return Response({'error': f'Unexpected error: {str(e)}'}, status=500)


class VerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        transaction_id = request.data.get('transaction_id')
        user = request.user

        try:
            payment = Payment.objects.get(transaction_id=transaction_id, booking__user=user)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

        chapa_url = f'https://api.chapa.co/v1/transaction/verify/{transaction_id}'
        headers = {
            'Authorization': f'Bearer {os.getenv("CHAPA_SECRET_KEY", getattr(settings, "CHAPA_SECRET_KEY", ""))}',
        }
        response = requests.get(chapa_url, headers=headers)
        if response.status_code == 200:
            resp_data = response.json()
            if resp_data.get('status') == 'success' and resp_data['data']['status'] == 'success':
                payment.status = 'completed'
                payment.save()
                # TODO: Trigger Celery task to send confirmation email
                return Response({'status': 'completed'}, status=200)
            else:
                payment.status = 'failed'
                payment.save()
                return Response({'status': 'failed'}, status=200)
        return Response({'error': 'Failed to verify payment.'}, status=500)


# --- User Management API Views ---
class UserRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')

        if not username or not email or not password:
            return Response({'error': 'Username, email, and password are required.'}, 
                          status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already exists.'}, 
                          status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({'error': 'Email already exists.'}, 
                          status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'token': token.key
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({'error': 'Username and password are required.'}, 
                          status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        if user:
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'token': token.key
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid credentials.'}, 
                          status=status.HTTP_401_UNAUTHORIZED)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': user.date_joined
        })

    def put(self, request):
        user = request.user
        user.email = request.data.get('email', user.email)
        user.first_name = request.data.get('first_name', user.first_name)
        user.last_name = request.data.get('last_name', user.last_name)
        
        if 'password' in request.data:
            user.set_password(request.data['password'])
        
        user.save()
        return Response({
            'message': 'Profile updated successfully',
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name
        })

    def patch(self, request):
        user = request.user
        user.email = request.data.get('email', user.email)
        user.first_name = request.data.get('first_name', user.first_name)
        user.last_name = request.data.get('last_name', user.last_name)

        if 'password' in request.data:
            user.set_password(request.data['password'])

        user.save()
        return Response({
            'message': 'Profile updated successfully',
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name
        })

    def delete(self, request):
        user = request.user
        user.delete()
        return Response({'message': 'Account deleted successfully'}, 
                       status=status.HTTP_204_NO_CONTENT)
