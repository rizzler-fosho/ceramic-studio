import datetime

from django.conf import settings
from django.db import models
from django.db.models import Max
from django.urls import reverse

from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.models import Orderable, Page


class CollectionIndexPage(Page):
    """Singleton root page — parent of all CollectionPages."""

    subpage_types = ["ceramics.CollectionPage"]
    parent_page_types = ["wagtailcore.Page"]

    class Meta:
        verbose_name = "Collection Index Page"


class CollectionPage(Page):
    """A named group of ceramic pieces belonging to one user."""

    description = models.TextField(blank=True)

    subpage_types = ["ceramics.PiecePage"]
    parent_page_types = ["ceramics.CollectionIndexPage"]

    content_panels = Page.content_panels + [
        FieldPanel("description"),
    ]

    # ── Template-compatibility shims ──────────────────────────────────────────

    @property
    def name(self):
        return self.title

    @property
    def pieces(self):
        return PiecePage.objects.child_of(self).live()

    def get_absolute_url(self):
        return reverse("collection-detail", kwargs={"pk": self.pk})

    class Meta:
        verbose_name = "Collection"


class PieceUpdate(Orderable):
    """A stage update for a piece — may have one or more photos."""

    STAGE_CHOICES = [
        ("greenware", "Greenware"),
        ("bisque", "Bisque Fire"),
        ("glaze", "Final Glaze Fire"),
    ]

    page = ParentalKey(
        "ceramics.PiecePage",
        on_delete=models.CASCADE,
        related_name="updates",
    )
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    ai_stage_guess = models.CharField(
        max_length=20,
        choices=STAGE_CHOICES,
        blank=True,
        help_text="Stage automatically detected by Claude",
    )
    ai_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="AI confidence score 0.0–1.0",
    )
    description = models.TextField(blank=True)
    glaze_notes = models.TextField(
        blank=True,
        help_text="Short glaze name description, e.g. \"Golden Hour yellow on body, Carmel and White Gloss on lid\"",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldPanel("stage"),
        FieldPanel("description"),
        FieldPanel("glaze_notes"),
    ]

    def __str__(self):
        return f"{self.page.title} — {self.get_stage_display()}"

    def save(self, *args, **kwargs):
        if self.sort_order is None:
            max_order = PieceUpdate.objects.filter(page_id=self.page_id).aggregate(
                m=Max("sort_order")
            )["m"]
            self.sort_order = 0 if max_order is None else max_order + 1
        super().save(*args, **kwargs)
        if self.description:
            PiecePage.objects.filter(pk=self.page_id).update(description=self.description)


class PieceUpdateImage(models.Model):
    """One photo within a PieceUpdate (a single stage update can have many photos)."""

    update = models.ForeignKey(
        PieceUpdate,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="ceramics/pieces/")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return f"Image {self.sort_order} for {self.update}"


class PiecePage(Page):
    """A single ceramic piece within a collection."""

    date = models.DateField(default=datetime.date.today, verbose_name="Start date")
    description = models.TextField(blank=True)

    subpage_types = []
    parent_page_types = ["ceramics.CollectionPage"]

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("description"),
        InlinePanel("updates", label="Updates"),
    ]

    # ── Template-compatibility shims ──────────────────────────────────────────

    @property
    def collection(self):
        return self.get_parent().specific

    @property
    def latest_update(self):
        return self.updates.order_by("-uploaded_at").first()

    @property
    def current_stage(self):
        latest = self.latest_update
        return latest.stage if latest else None

    @property
    def current_stage_display(self):
        latest = self.latest_update
        return latest.get_stage_display() if latest else "No photos yet"

    @property
    def cover_image(self):
        latest = self.latest_update
        if not latest:
            return None
        first = latest.images.first()
        return first.image if first else None

    def get_absolute_url(self):
        return reverse("piece-detail", kwargs={"pk": self.pk})

    class Meta:
        verbose_name = "Piece"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ceramics_profile",
    )
    avatar = models.ImageField(upload_to="ceramics/avatars/", blank=True)
    bio = models.TextField(blank=True)

    def __str__(self):
        return f"Profile({self.user.username})"


class Kiln(models.Model):
    """A physical kiln whose status can be pushed via the IoT API."""

    STATUS_CHOICES = [
        ("idle",    "Idle"),
        ("firing",  "Firing"),
        ("cooling", "Cooling"),
        ("done",    "Done"),
    ]

    number    = models.PositiveSmallIntegerField(unique=True)
    name      = models.CharField(max_length=100)
    temp      = models.FloatField(default=0.0, help_text="Current temperature in °F")
    cone_fire = models.CharField(max_length=20, blank=True)
    status    = models.CharField(max_length=20, choices=STATUS_CHOICES, default="idle")
    notes     = models.TextField(blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"Kiln {self.number} — {self.name}"

    @property
    def temp_display(self):
        return f"{self.temp:,.0f}°F"

    @property
    def temp_percent(self):
        """Heat bar 0–100 % scaled to cone 10 max (~2381°F)."""
        return min(100, max(0, round(self.temp / 2381 * 100)))

    @property
    def icon_color(self):
        return {
            "firing":  "text-orange-500",
            "cooling": "text-blue-400",
            "done":    "text-green-500",
            "idle":    "text-stone-400",
        }.get(self.status, "text-stone-400")

    @property
    def badge_class(self):
        return {
            "firing":  "bg-orange-100 text-orange-700",
            "cooling": "bg-blue-100 text-blue-700",
            "done":    "bg-green-100 text-green-700",
            "idle":    "bg-stone-100 text-stone-500",
        }.get(self.status, "bg-stone-100 text-stone-500")

    @property
    def bar_class(self):
        return {
            "firing":  "bg-orange-400",
            "cooling": "bg-blue-300",
            "done":    "bg-green-400",
            "idle":    "bg-stone-300",
        }.get(self.status, "bg-stone-300")

    @property
    def is_firing(self):
        return self.status == "firing"
