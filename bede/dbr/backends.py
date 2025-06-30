# dbr/backends.py

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

UserModel = get_user_model()

class CustomAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # We look up the user by their username
            user = UserModel.objects.get(username__iexact=username)
        except UserModel.DoesNotExist:
            # Run the default password hasher once to reduce timing attacks
            UserModel().set_password(password)
            return None

        # Check if the user is currently locked out
        if user.lockout_until and user.lockout_until > timezone.now():
            return None  # Return None to indicate failed authentication

        # Use the built-in `check_password` which handles the secure hashing
        if user.check_password(password):
            # If login is successful, reset attempts and lockout time
            user.login_attempts = 0
            user.lockout_until = None
            user.save(update_fields=['login_attempts', 'lockout_until'])
            return user
        else:
            # If login fails, increment the attempt counter
            user.login_attempts += 1
            # If attempts reach the maximum, set a lockout time
            if user.login_attempts >= 5:
                user.lockout_until = timezone.now() + timedelta(minutes=15)
            user.save(update_fields=['login_attempts', 'lockout_until'])
            return None # Return None for failed authentication