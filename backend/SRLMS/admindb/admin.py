from django.contrib import admin
from .models import *
# Register your models here.
apps = [Location, Marker]
admin.site.register(apps)