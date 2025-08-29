from rest_framework import serializers
from .models import Listing, Booking, Review
from django.contrib.auth.models import User


class ListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = '__all__'
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']

    def validate(self, data):
        """Check that available_from is before available_to."""

        if data['available_from'] >= data['available_to']:
            raise serializers.ValidationError("available_from must be before available_to")
        return data
    

class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate(self, data):
        """Check that check_in_date is before check_out_date and that
        the dates are within the listing's availability."""

        if data['check_in_date'] >= data['check_out_date']:
            raise serializers.ValidationError("check_in_date must be before check_out_date")
        
        listing = data['listing']
        if not (listing.available_from <= data['check_in_date'] < listing.available_to and
                listing.available_from < data['check_out_date'] <= listing.available_to):
            raise serializers.ValidationError("Booking dates must be within the listing's availability")
        
        return data    
        
class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Check that the rating is between 1 and 5."""
        
        if not (1 <= data['rating'] <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return data
