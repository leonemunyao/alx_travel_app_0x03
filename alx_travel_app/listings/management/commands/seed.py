from django.core.management.base import BaseCommand
from listings.models import Listing
from decimal import Decimal
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = 'Seed the database with initial data for listings'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=5, help='Number of listings to create')
        parser.add_argument('--clear', action='store_true', help='Clear existing listings before seeding')

    def handle(self, *args, **kwargs):
        count = kwargs['count']
        clear = kwargs['clear']

        if clear:
            Listing.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Cleared existing listings.'))
        
        sample_data = self.get_sample_data()

        self.stdout.write(f'Creating {count} sample listings...')

        created_listings = []
        for i in range(count):
            listing_data = self.generate_listing_data(sample_data, i)
            listing = Listing.objects.create(**listing_data)
            created_listings.append(listing)
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {len(created_listings)} listings.'))

        self.stdout.write('\nSample Listings Created:')
        for listing in created_listings[:4]:
            self.stdout.write(f'{listing.title} in {listing.location} is ${listing.price_per_night} per night')

    def get_sample_data(self):
        return [
            {
                'title': 'Jumeirah Beach Hotel',
                'description': 'One of the biggests beach hotels in Kenya',
                'price_per_night': Decimal('100000.00'),
                'available_from': datetime.now().date(),
                'available_to': datetime.now().date() + timedelta(days=30),
                'location': 'Nyali, Mombasa',
                'max_guests': 30,
            },
            {
                'title': 'Mombasa Beach Hotel',
                'description': 'A luxurious villa with a beachfront view.',
                'price_per_night': Decimal('30000.00'),
                'available_from': datetime.now().date(),
                'available_to': datetime.now().date() + timedelta(days=60),
                'location': 'Nyali, Mombasa',
                'max_guests': 50,
            },
            {
                'title': 'Sarova Whitesands Hotel',
                'description': 'A luxurious resort with stunning ocean views in Mombasa.',
                'price_per_night': Decimal('25000.00'),
                'available_from': datetime.now().date(),
                'available_to': datetime.now().date() + timedelta(days=45),
                'location': 'Mombasa, Kenya',
                'max_guests': 40,
            },
        ]

    def generate_listing_data(self, sample_data, index):
        data = sample_data[index % len(sample_data)]
        return {
            'title': data['title'],
            'description': data['description'],
            'price_per_night': data['price_per_night'],
            'available_from': data['available_from'],
            'available_to': data['available_to'],
            'location': data['location'],
            'max_guests': data['max_guests'],
        }
