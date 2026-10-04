from django.contrib import admin

from .models import ClothRoll, DipRun, Loft, SealLock

admin.site.register(Loft)
admin.site.register(ClothRoll)
admin.site.register(DipRun)
admin.site.register(SealLock)
