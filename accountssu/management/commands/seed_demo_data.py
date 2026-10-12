from django.core.management.base import BaseCommand

from accountssu.models import User


class Command(BaseCommand):
    help = "Seed demo data matching frontend mock data"

    def handle(self, *args, **options):
        if User.objects.filter(email="admin8080@gmail.com").exists():
            self.stdout.write(self.style.WARNING("Data already seeded. Skipping."))
            return

        User.objects.create_user(
            username="admin8080@gmail.com", email="admin8080@gmail.com",
            password="123", first_name="Admin", last_name="User", role="admin",
        )
        User.objects.create_user(
            username="rahim@gmail.com", email="rahim@gmail.com",
            password="123", first_name="Rahim", last_name="Ahmed", role="customer",
        )
        User.objects.create_user(
            username="karim@gmail.com", email="karim@gmail.com",
            password="123", first_name="Karim", last_name="Hassan", role="customer",
        )
        User.objects.create_user(
            username="agent1@gmail.com", email="agent1@gmail.com",
            password="123", first_name="Sara", last_name="Khan", role="agent",
            max_open_tickets=10, is_available=False,
        )
        User.objects.create_user(
            username="agent2@gmail.com", email="agent2@gmail.com",
            password="123", first_name="Jamal", last_name="Uddin", role="agent",
            max_open_tickets=10, is_available=False,
        )

        self.stdout.write(self.style.SUCCESS("Demo users seeded successfully!"))
        self.stdout.write("Login: rahim@gmail.com / 123 (customer)")
        self.stdout.write("Login: karim@gmail.com / 123 (customer)")
        self.stdout.write("Login: agent1@gmail.com / 123 (agent)")
        self.stdout.write("Login: agent2@gmail.com / 123 (agent)")
        self.stdout.write("Login: admin8080@gmail.com / 123 (admin)")
