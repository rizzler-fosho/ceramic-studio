from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls

urlpatterns = [
    # Root → redirect to ceramics dashboard
    path("", RedirectView.as_view(url="/my-collections/", permanent=False)),

    # Django auth (login / logout)
    path("accounts/", include("django.contrib.auth.urls")),

    # Our ceramics app
    path("my-collections/", include("ceramics.urls")),

    # Django & Wagtail admin
    path("django-admin/", admin.site.urls),
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("pages/", include(wagtail_urls)),
]

# Serve local media in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=getattr(settings, "MEDIA_ROOT", ""))
