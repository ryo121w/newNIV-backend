from django.contrib.auth.models import AbstractUser
from django.db import models


class ExtendedUser(AbstractUser):
    is_host_approved = models.BooleanField(default=False)
    isSuperUser = models.BooleanField(default=False)
