from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),

    # Collections
    path("new/", views.CollectionCreateView.as_view(), name="collection-create"),
    path("<int:pk>/", views.CollectionDetailView.as_view(), name="collection-detail"),
    path("<int:pk>/edit/", views.CollectionUpdateView.as_view(), name="collection-update"),
    path("<int:pk>/delete/", views.CollectionDeleteView.as_view(), name="collection-delete"),

    # Pieces
    path("<int:collection_pk>/pieces/new/", views.PieceCreateView.as_view(), name="piece-create"),
    path("pieces/<int:pk>/", views.PieceDetailView.as_view(), name="piece-detail"),
    path("pieces/<int:pk>/edit/", views.PieceUpdateView.as_view(), name="piece-update"),
    path("pieces/<int:pk>/delete/", views.PieceDeleteView.as_view(), name="piece-delete"),

    # Photo uploads
    path("pieces/<int:piece_pk>/upload/", views.PieceUpdateCreateView.as_view(), name="piece-upload"),

    # Profile
    path("profile/",      views.profile_view,      name="profile"),
    path("profile/edit/", views.profile_edit_view, name="profile-edit"),

    # Timeline
    path("timeline/",                          views.timeline_view, name="timeline"),
    path("timeline/<int:year>/<int:month>/",   views.timeline_view, name="timeline-month"),

    # AI analysis endpoint
    path("api/analyze/", views.analyze_image_view, name="analyze-image"),

    # Kiln IoT API
    path("api/kilns/<int:number>/", views.kiln_update_api, name="kiln-update"),
]
