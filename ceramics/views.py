import calendar
import logging
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.text import slugify
from django.views import View
from django.views.decorators.http import require_http_methods
from django.contrib.auth.mixins import LoginRequiredMixin

from wagtail.models import Page

from .ai_service import analyze_ceramic_image
from .forms import CollectionForm, PieceForm, PieceUpdateForm, ProfileForm
from .models import CollectionIndexPage, CollectionPage, PiecePage, PieceUpdateImage, UserProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_or_create_index():
    """Return the singleton CollectionIndexPage, creating it if absent."""
    index = CollectionIndexPage.objects.live().first()
    if not index:
        root = Page.objects.filter(depth=1).first()
        index = CollectionIndexPage(
            title="Ceramics Portfolio",
            slug="ceramics-portfolio",
            live=True,
        )
        root.add_child(instance=index)
    return index


def _unique_slug(parent, title):
    base = slugify(title) or "page"
    slug = base
    n = 1
    while parent.get_children().filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


# ---------------------------------------------------------------------------
# Profile helpers
# ---------------------------------------------------------------------------


def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@login_required
def dashboard(request):
    index = _get_or_create_index()
    collections = CollectionPage.objects.child_of(index).live().filter(owner=request.user)
    return render(request, "ceramics/dashboard.html", {"collections": collections})


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


class CollectionCreateView(LoginRequiredMixin, View):
    template_name = "ceramics/collection_form.html"

    def get(self, request):
        return render(request, self.template_name, {
            "form": CollectionForm(),
            "action": "New Collection",
        })

    def post(self, request):
        form = CollectionForm(request.POST)
        if form.is_valid():
            index = _get_or_create_index()
            collection = CollectionPage(
                title=form.cleaned_data["name"],
                description=form.cleaned_data.get("description", ""),
                slug=_unique_slug(index, form.cleaned_data["name"]),
                live=True,
                owner=request.user,
            )
            index.add_child(instance=collection)
            messages.success(request, f'Collection "{collection.title}" created!')
            return redirect(collection.get_absolute_url())
        return render(request, self.template_name, {"form": form, "action": "New Collection"})


class CollectionDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        collection = get_object_or_404(CollectionPage, pk=pk, owner=request.user, live=True)
        return render(request, "ceramics/collection_detail.html", {"object": collection})


class CollectionUpdateView(LoginRequiredMixin, View):
    template_name = "ceramics/collection_form.html"

    def _get(self, request, pk):
        return get_object_or_404(CollectionPage, pk=pk, owner=request.user)

    def get(self, request, pk):
        collection = self._get(request, pk)
        form = CollectionForm(initial={
            "name": collection.title,
            "description": collection.description,
        })
        return render(request, self.template_name, {
            "form": form,
            "action": "Edit Collection",
            "object": collection,
        })

    def post(self, request, pk):
        collection = self._get(request, pk)
        form = CollectionForm(request.POST)
        if form.is_valid():
            collection.title = form.cleaned_data["name"]
            collection.description = form.cleaned_data.get("description", "")
            collection.save()
            messages.success(request, "Collection updated.")
            return redirect(collection.get_absolute_url())
        return render(request, self.template_name, {
            "form": form,
            "action": "Edit Collection",
            "object": collection,
        })


class CollectionDeleteView(LoginRequiredMixin, View):
    template_name = "ceramics/confirm_delete.html"

    def _get(self, request, pk):
        return get_object_or_404(CollectionPage, pk=pk, owner=request.user)

    def get(self, request, pk):
        return render(request, self.template_name, {"object": self._get(request, pk)})

    def post(self, request, pk):
        self._get(request, pk).delete()
        messages.success(request, "Collection deleted.")
        return redirect(reverse_lazy("dashboard"))


# ---------------------------------------------------------------------------
# Pieces
# ---------------------------------------------------------------------------


class PieceCreateView(LoginRequiredMixin, View):
    template_name = "ceramics/piece_form.html"

    def _get_collection(self, request, collection_pk):
        return get_object_or_404(CollectionPage, pk=collection_pk, owner=request.user)

    def get(self, request, collection_pk):
        collection = self._get_collection(request, collection_pk)
        return render(request, self.template_name, {
            "form": PieceForm(),
            "collection": collection,
            "action": "New Piece",
        })

    def post(self, request, collection_pk):
        collection = self._get_collection(request, collection_pk)
        form = PieceForm(request.POST)
        if form.is_valid():
            piece = PiecePage(
                title=form.cleaned_data["title"],
                date=form.cleaned_data["date"],
                slug=_unique_slug(collection, form.cleaned_data["title"]),
                live=True,
                owner=request.user,
            )
            collection.add_child(instance=piece)
            messages.success(request, f'"{piece.title}" added to your collection!')
            return redirect(piece.get_absolute_url())
        return render(request, self.template_name, {
            "form": form,
            "collection": collection,
            "action": "New Piece",
        })


class PieceDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        piece = get_object_or_404(PiecePage, pk=pk, owner=request.user, live=True)
        return render(request, "ceramics/piece_detail.html", {"object": piece})


class PieceUpdateView(LoginRequiredMixin, View):
    template_name = "ceramics/piece_form.html"

    def _get(self, request, pk):
        return get_object_or_404(PiecePage, pk=pk, owner=request.user)

    def get(self, request, pk):
        piece = self._get(request, pk)
        return render(request, self.template_name, {
            "form": PieceForm(initial={"title": piece.title, "date": piece.date}),
            "collection": piece.collection,
            "action": "Edit Piece",
        })

    def post(self, request, pk):
        piece = self._get(request, pk)
        form = PieceForm(request.POST)
        if form.is_valid():
            piece.title = form.cleaned_data["title"]
            piece.date = form.cleaned_data["date"]
            piece.save()
            messages.success(request, "Piece updated.")
            return redirect(piece.get_absolute_url())
        return render(request, self.template_name, {
            "form": form,
            "collection": piece.collection,
            "action": "Edit Piece",
        })


class PieceDeleteView(LoginRequiredMixin, View):
    template_name = "ceramics/confirm_delete.html"

    def _get(self, request, pk):
        return get_object_or_404(PiecePage, pk=pk, owner=request.user)

    def get(self, request, pk):
        return render(request, self.template_name, {"object": self._get(request, pk)})

    def post(self, request, pk):
        piece = self._get(request, pk)
        collection_url = piece.collection.get_absolute_url()
        piece.delete()
        messages.success(request, "Piece deleted.")
        return redirect(collection_url)


# ---------------------------------------------------------------------------
# Photo uploads
# ---------------------------------------------------------------------------


class PieceUpdateCreateView(LoginRequiredMixin, View):
    template_name = "ceramics/piece_update_form.html"

    def _get_piece(self, request, piece_pk):
        return get_object_or_404(PiecePage, pk=piece_pk, owner=request.user)

    def get(self, request, piece_pk):
        piece = self._get_piece(request, piece_pk)
        return render(request, self.template_name, {"form": PieceUpdateForm(), "piece": piece})

    def post(self, request, piece_pk):
        piece = self._get_piece(request, piece_pk)
        images = request.FILES.getlist("images")
        form = PieceUpdateForm(request.POST)
        if not images:
            form.add_error(None, "Please select at least one photo.")
            return render(request, self.template_name, {"form": form, "piece": piece})
        if form.is_valid():
            update = form.save(commit=False)
            update.page = piece
            update.save()
            for i, img in enumerate(images):
                PieceUpdateImage.objects.create(update=update, image=img, sort_order=i)
            count = len(images)
            messages.success(
                request,
                f'{count} photo{"s" if count > 1 else ""} added at the '
                f"{update.get_stage_display()} stage. Add another or view the piece below.",
            )
            return redirect(reverse("piece-upload", kwargs={"piece_pk": piece.pk}))
        return render(request, self.template_name, {"form": form, "piece": piece})


# ---------------------------------------------------------------------------
# AI analysis endpoint
# ---------------------------------------------------------------------------


@login_required
@require_http_methods(["POST"])
def analyze_image_view(request):
    if "image" not in request.FILES:
        return JsonResponse({"error": "No image file provided."}, status=400)

    image_file = request.FILES["image"]
    piece_title = request.POST.get("title", "ceramic piece").strip() or "ceramic piece"
    media_type = image_file.content_type or "image/jpeg"

    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if media_type not in allowed_types:
        return JsonResponse({"error": f"Unsupported image type: {media_type}"}, status=400)

    result = analyze_ceramic_image(image_file.read(), piece_title, media_type)
    return JsonResponse(result)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@login_required
def profile_view(request):
    profile = _get_or_create_profile(request.user)
    index = _get_or_create_index()
    total_collections = CollectionPage.objects.child_of(index).live().filter(owner=request.user).count()
    total_pieces = PiecePage.objects.filter(owner=request.user, live=True).count()
    return render(request, "ceramics/profile.html", {
        "profile": profile,
        "total_collections": total_collections,
        "total_pieces": total_pieces,
    })


@login_required
def profile_edit_view(request):
    profile = _get_or_create_profile(request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "ceramics/profile_edit.html", {"form": form, "profile": profile})


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


@login_required
def timeline_view(request, year=None, month=None):
    today = date.today()
    year  = int(year)  if year  else today.year
    month = int(month) if month else today.month

    try:
        current_month_start = date(year, month, 1)
    except ValueError:
        return redirect("timeline")

    prev_year,  prev_month  = (year - 1, 12) if month == 1  else (year, month - 1)
    next_year,  next_month  = (year + 1,  1) if month == 12 else (year, month + 1)

    pieces_this_month = PiecePage.objects.filter(
        owner=request.user,
        live=True,
        date__year=year,
        date__month=month,
    )

    pieces_by_day = {}
    for piece in pieces_this_month:
        day = piece.date.day
        pieces_by_day.setdefault(day, []).append(piece)

    weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
    grid = [
        [
            {
                "day": d or None,
                "pieces": pieces_by_day.get(d, []) if d else [],
                "is_today": bool(d and d == today.day and year == today.year and month == today.month),
            }
            for d in week
        ]
        for week in weeks
    ]

    return render(request, "ceramics/timeline.html", {
        "grid": grid,
        "year": year,
        "month": month,
        "month_name": current_month_start.strftime("%B %Y"),
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "today": today,
    })
