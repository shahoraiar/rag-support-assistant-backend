from rest_framework import serializers

from accountssu.choices import UserRole, UserSource
from accountssu.models import User
from meapi.serializers.profile import UserSerializer


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    name = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(
        choices=[UserRole.CUSTOMER, UserRole.AGENT],
        required=False,
        default=UserRole.CUSTOMER,
    )

    class Meta:
        model = User
        fields = ("email", "password", "name", "role")

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return email

    def create(self, validated_data):
        name = validated_data.pop("name")
        email = validated_data.pop("email")
        password = validated_data.pop("password")
        role = validated_data.pop("role", UserRole.CUSTOMER)
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name,
            role=role,
            source=UserSource.EMAIL,
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class GoogleLoginSerializer(serializers.Serializer):
    credential = serializers.CharField(help_text="Google ID token from GIS / GoogleLogin")


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=6)


class PasswordResetRequestResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    reset_url = serializers.CharField(required=False, allow_blank=True)


class PasswordResetConfirmResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class AuthResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    tokens = TokenPairSerializer()
