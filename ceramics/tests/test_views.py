"""
View integration tests
======================
These tests send real HTTP requests through Django's test client and verify
the response status, redirect target, and resulting database state.

Each test class inherits from ``BaseCeramicsTestCase``, which creates:
  - ``self.user``        — the logged-in owner
  - ``self.other_user``  — a second user who owns nothing
  - ``self.index``       — the singleton CollectionIndexPage
  - ``self.collection``  — a CollectionPage owned by self.user
  - ``self.piece``       — a PiecePage owned by self.user

The client is logged in as ``self.user`` before every test.
"""

import datetime
import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from wagtail.models import Page

from ceramics.models import (
    CollectionIndexPage,
    CollectionPage,
    PiecePage,
    PieceUpdate,
    PieceUpdateImage,
    UserProfile,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_image_file(name="photo.jpg"):
    from PIL import Image as PilImage
    from django.core.files.uploadedfile import SimpleUploadedFile
    buf = io.BytesIO()
    PilImage.new("RGB", (10, 10), color=(180, 90, 40)).save(buf, "JPEG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/jpeg")


# ---------------------------------------------------------------------------
# Base test case — shared page-tree setup
# ---------------------------------------------------------------------------

class BaseCeramicsTestCase(TestCase):
    def setUp(self):
        self.user       = User.objects.create_user("potter",  password="clay")
        self.other_user = User.objects.create_user("potter2", password="clay")
        self.client.login(username="potter", password="clay")

        root = Page.objects.filter(depth=1).first()
        self.index = CollectionIndexPage(
            title="Portfolio", slug="portfolio", live=True
        )
        root.add_child(instance=self.index)

        self.collection = CollectionPage(
            title="Spring Mugs", slug="spring-mugs",
            description="My spring mugs", live=True, owner=self.user,
        )
        self.index.add_child(instance=self.collection)

        self.piece = PiecePage(
            title="Fancy Mug", slug="fancy-mug",
            date=datetime.date(2026, 4, 5), live=True, owner=self.user,
        )
        self.collection.add_child(instance=self.piece)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardViewTest(BaseCeramicsTestCase):

    def test_requires_login(self):
        """Unauthenticated requests are redirected to the login page."""
        self.client.logout()
        r = self.client.get(reverse("dashboard"))
        self.assertRedirects(r, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_shows_only_users_own_collections(self):
        """Collections owned by another user are not shown."""
        other_collection = CollectionPage(
            title="Other Mugs", slug="other-mugs", live=True, owner=self.other_user,
        )
        self.index.add_child(instance=other_collection)

        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 200)
        collections = list(r.context["collections"])
        self.assertIn(self.collection, collections)
        self.assertNotIn(other_collection, collections)

    def test_auto_creates_index_page(self):
        """If no CollectionIndexPage exists, the dashboard creates one."""
        CollectionIndexPage.objects.all().delete()
        self.assertEqual(CollectionIndexPage.objects.count(), 0)
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(CollectionIndexPage.objects.count(), 1)


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

class CollectionCreateViewTest(BaseCeramicsTestCase):

    def test_get_returns_200(self):
        r = self.client.get(reverse("collection-create"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("form", r.context)

    def test_post_creates_collection_page(self):
        r = self.client.post(reverse("collection-create"), {
            "name": "Autumn Bowls",
            "description": "My autumn bowls",
        })
        self.assertTrue(CollectionPage.objects.filter(title="Autumn Bowls").exists())
        new = CollectionPage.objects.get(title="Autumn Bowls")
        self.assertRedirects(r, new.get_absolute_url())

    def test_new_collection_is_owned_by_current_user(self):
        self.client.post(reverse("collection-create"), {"name": "New Set", "description": ""})
        col = CollectionPage.objects.get(title="New Set")
        self.assertEqual(col.owner, self.user)

    def test_post_with_missing_name_rerenders_form(self):
        r = self.client.post(reverse("collection-create"), {"name": "", "description": ""})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(CollectionPage.objects.filter(title="").exists())


class CollectionDetailViewTest(BaseCeramicsTestCase):

    def test_returns_200_for_owner(self):
        r = self.client.get(reverse("collection-detail", kwargs={"pk": self.collection.pk}))
        self.assertEqual(r.status_code, 200)

    def test_returns_404_for_other_user(self):
        """Another user's collection must not be accessible."""
        other = CollectionPage(
            title="Secret Mugs", slug="secret-mugs", live=True, owner=self.other_user,
        )
        self.index.add_child(instance=other)
        r = self.client.get(reverse("collection-detail", kwargs={"pk": other.pk}))
        self.assertEqual(r.status_code, 404)


class CollectionUpdateViewTest(BaseCeramicsTestCase):

    def test_post_updates_title_and_description(self):
        self.client.post(
            reverse("collection-update", kwargs={"pk": self.collection.pk}),
            {"name": "Winter Mugs", "description": "Cold weather mugs"},
        )
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.title, "Winter Mugs")
        self.assertEqual(self.collection.description, "Cold weather mugs")

    def test_get_prefills_form_with_current_values(self):
        r = self.client.get(reverse("collection-update", kwargs={"pk": self.collection.pk}))
        self.assertEqual(r.context["form"].initial["name"], "Spring Mugs")


class CollectionDeleteViewTest(BaseCeramicsTestCase):

    def test_post_deletes_collection(self):
        pk = self.collection.pk
        self.client.post(reverse("collection-delete", kwargs={"pk": pk}))
        self.assertFalse(CollectionPage.objects.filter(pk=pk).exists())

    def test_post_redirects_to_dashboard(self):
        r = self.client.post(reverse("collection-delete", kwargs={"pk": self.collection.pk}))
        self.assertRedirects(r, reverse("dashboard"))


# ---------------------------------------------------------------------------
# Pieces
# ---------------------------------------------------------------------------

class PieceCreateViewTest(BaseCeramicsTestCase):

    def test_post_creates_piece_with_date(self):
        self.client.post(
            reverse("piece-create", kwargs={"collection_pk": self.collection.pk}),
            {"title": "Small Bowl", "date": "2026-03-15"},
        )
        self.assertTrue(PiecePage.objects.filter(title="Small Bowl").exists())
        piece = PiecePage.objects.get(title="Small Bowl")
        self.assertEqual(piece.date, datetime.date(2026, 3, 15))

    def test_new_piece_is_child_of_correct_collection(self):
        self.client.post(
            reverse("piece-create", kwargs={"collection_pk": self.collection.pk}),
            {"title": "Tall Vase", "date": "2026-04-01"},
        )
        piece = PiecePage.objects.get(title="Tall Vase")
        self.assertEqual(piece.get_parent().specific, self.collection)

    def test_new_piece_owned_by_current_user(self):
        self.client.post(
            reverse("piece-create", kwargs={"collection_pk": self.collection.pk}),
            {"title": "Teapot", "date": "2026-04-01"},
        )
        piece = PiecePage.objects.get(title="Teapot")
        self.assertEqual(piece.owner, self.user)

    def test_post_with_missing_title_rerenders_form(self):
        r = self.client.post(
            reverse("piece-create", kwargs={"collection_pk": self.collection.pk}),
            {"title": "", "date": "2026-04-01"},
        )
        self.assertEqual(r.status_code, 200)


class PieceDetailViewTest(BaseCeramicsTestCase):

    def test_returns_200_for_owner(self):
        r = self.client.get(reverse("piece-detail", kwargs={"pk": self.piece.pk}))
        self.assertEqual(r.status_code, 200)

    def test_returns_404_for_other_users_piece(self):
        other_collection = CollectionPage(
            title="Other", slug="other", live=True, owner=self.other_user,
        )
        self.index.add_child(instance=other_collection)
        other_piece = PiecePage(
            title="Secret Piece", slug="secret-piece",
            date=datetime.date(2026, 4, 1), live=True, owner=self.other_user,
        )
        other_collection.add_child(instance=other_piece)

        r = self.client.get(reverse("piece-detail", kwargs={"pk": other_piece.pk}))
        self.assertEqual(r.status_code, 404)


class PieceEditViewTest(BaseCeramicsTestCase):

    def test_post_updates_title_and_date(self):
        self.client.post(
            reverse("piece-update", kwargs={"pk": self.piece.pk}),
            {"title": "Renamed Mug", "date": "2026-05-10"},
        )
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.title, "Renamed Mug")
        self.assertEqual(self.piece.date, datetime.date(2026, 5, 10))

    def test_get_prefills_form_with_current_date(self):
        r = self.client.get(reverse("piece-update", kwargs={"pk": self.piece.pk}))
        self.assertEqual(r.context["form"].initial["date"], datetime.date(2026, 4, 5))


class PieceDeleteViewTest(BaseCeramicsTestCase):

    def test_post_deletes_piece(self):
        pk = self.piece.pk
        self.client.post(reverse("piece-delete", kwargs={"pk": pk}))
        self.assertFalse(PiecePage.objects.filter(pk=pk).exists())

    def test_post_redirects_to_collection(self):
        r = self.client.post(reverse("piece-delete", kwargs={"pk": self.piece.pk}))
        self.assertRedirects(r, self.collection.get_absolute_url())


# ---------------------------------------------------------------------------
# Photo uploads
# ---------------------------------------------------------------------------

class PieceUploadViewTest(BaseCeramicsTestCase):

    def setUp(self):
        super().setUp()
        self.media_dir = tempfile.mkdtemp()
        self.upload_url = reverse("piece-upload", kwargs={"piece_pk": self.piece.pk})

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.media_dir, ignore_errors=True)

    def test_get_returns_200(self):
        r = self.client.get(self.upload_url)
        self.assertEqual(r.status_code, 200)

    def test_post_with_no_images_shows_error(self):
        r = self.client.post(self.upload_url, {"stage": "greenware", "description": ""})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PieceUpdate.objects.count(), 0)

    def test_post_creates_piece_update(self):
        with override_settings(MEDIA_ROOT=self.media_dir):
            self.client.post(self.upload_url, {
                "images": [_make_image_file()],
                "stage": "greenware",
                "description": "Fresh off the wheel.",
                "glaze_notes": "",
            })
        self.assertEqual(PieceUpdate.objects.filter(page=self.piece).count(), 1)

    def test_post_creates_one_image_per_file(self):
        with override_settings(MEDIA_ROOT=self.media_dir):
            self.client.post(self.upload_url, {
                "images": [_make_image_file("a.jpg"), _make_image_file("b.jpg")],
                "stage": "bisque",
                "description": "",
                "glaze_notes": "",
            })
        update = PieceUpdate.objects.get(page=self.piece)
        self.assertEqual(update.images.count(), 2)

    def test_images_saved_in_sort_order(self):
        """First file in the list gets sort_order=0, second gets sort_order=1."""
        with override_settings(MEDIA_ROOT=self.media_dir):
            self.client.post(self.upload_url, {
                "images": [_make_image_file("first.jpg"), _make_image_file("second.jpg")],
                "stage": "greenware",
                "description": "",
                "glaze_notes": "",
            })
        update = PieceUpdate.objects.get(page=self.piece)
        orders = list(update.images.values_list("sort_order", flat=True))
        self.assertEqual(orders, [0, 1])

    def test_post_redirects_back_to_upload_form_not_piece_detail(self):
        """After a successful upload the user lands on the upload form again
        (the 'Add another' flow), NOT on the piece detail page."""
        with override_settings(MEDIA_ROOT=self.media_dir):
            r = self.client.post(self.upload_url, {
                "images": [_make_image_file()],
                "stage": "greenware",
                "description": "",
                "glaze_notes": "",
            })
        self.assertRedirects(r, self.upload_url)

    def test_second_upload_creates_second_update(self):
        """Uploading twice produces two separate PieceUpdate records."""
        with override_settings(MEDIA_ROOT=self.media_dir):
            for stage in ("greenware", "bisque"):
                self.client.post(self.upload_url, {
                    "images": [_make_image_file()],
                    "stage": stage,
                    "description": "",
                    "glaze_notes": "",
                })
        self.assertEqual(PieceUpdate.objects.filter(page=self.piece).count(), 2)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class ProfileViewTest(BaseCeramicsTestCase):

    def test_returns_200(self):
        r = self.client.get(reverse("profile"))
        self.assertEqual(r.status_code, 200)

    def test_auto_creates_profile_if_missing(self):
        """Visiting the profile page creates a UserProfile for new users."""
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())
        self.client.get(reverse("profile"))
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())

    def test_context_contains_collection_and_piece_counts(self):
        UserProfile.objects.create(user=self.user)
        r = self.client.get(reverse("profile"))
        self.assertEqual(r.context["total_collections"], 1)
        self.assertEqual(r.context["total_pieces"], 1)

    def test_requires_login(self):
        self.client.logout()
        r = self.client.get(reverse("profile"))
        self.assertEqual(r.status_code, 302)


class ProfileEditViewTest(BaseCeramicsTestCase):

    def test_post_updates_bio(self):
        UserProfile.objects.create(user=self.user)
        self.client.post(reverse("profile-edit"), {"bio": "I love mugs."})
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.bio, "I love mugs.")

    def test_post_redirects_to_profile(self):
        UserProfile.objects.create(user=self.user)
        r = self.client.post(reverse("profile-edit"), {"bio": "Potter since 2020."})
        self.assertRedirects(r, reverse("profile"))


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

class TimelineViewTest(BaseCeramicsTestCase):

    def test_returns_200_for_current_month(self):
        r = self.client.get(reverse("timeline"))
        self.assertEqual(r.status_code, 200)

    def test_returns_200_for_explicit_month(self):
        r = self.client.get(reverse("timeline-month", kwargs={"year": 2026, "month": 4}))
        self.assertEqual(r.status_code, 200)

    def test_piece_appears_in_correct_day_cell(self):
        """self.piece has date=2026-04-05; it must appear in the day-5 cell."""
        r = self.client.get(reverse("timeline-month", kwargs={"year": 2026, "month": 4}))
        grid = r.context["grid"]
        day5_cell = next(
            cell for week in grid for cell in week if cell["day"] == 5
        )
        self.assertIn(self.piece, day5_cell["pieces"])

    def test_piece_not_shown_in_wrong_month(self):
        """A piece dated April must not appear in a March calendar."""
        r = self.client.get(reverse("timeline-month", kwargs={"year": 2026, "month": 3}))
        grid = r.context["grid"]
        all_pieces = [p for week in grid for cell in week for p in cell["pieces"]]
        self.assertNotIn(self.piece, all_pieces)

    def test_other_users_pieces_not_shown(self):
        """Pieces owned by another user must not appear in the calendar."""
        other_col = CollectionPage(
            title="Other", slug="other-col", live=True, owner=self.other_user,
        )
        self.index.add_child(instance=other_col)
        other_piece = PiecePage(
            title="Other Mug", slug="other-mug",
            date=datetime.date(2026, 4, 5), live=True, owner=self.other_user,
        )
        other_col.add_child(instance=other_piece)

        r = self.client.get(reverse("timeline-month", kwargs={"year": 2026, "month": 4}))
        grid = r.context["grid"]
        all_pieces = [p for week in grid for cell in week for p in cell["pieces"]]
        self.assertNotIn(other_piece, all_pieces)

    def test_today_cell_is_marked(self):
        """The cell matching today's date must have is_today=True."""
        import datetime as dt
        today = dt.date.today()
        r = self.client.get(
            reverse("timeline-month", kwargs={"year": today.year, "month": today.month})
        )
        grid = r.context["grid"]
        today_cells = [
            cell for week in grid for cell in week if cell.get("is_today")
        ]
        self.assertEqual(len(today_cells), 1)
        self.assertEqual(today_cells[0]["day"], today.day)

    def test_invalid_month_redirects(self):
        r = self.client.get(reverse("timeline-month", kwargs={"year": 2026, "month": 13}))
        self.assertRedirects(r, reverse("timeline"))

    def test_prev_and_next_month_context(self):
        r = self.client.get(reverse("timeline-month", kwargs={"year": 2026, "month": 4}))
        self.assertEqual(r.context["prev_month"], 3)
        self.assertEqual(r.context["next_month"], 5)

    def test_prev_month_wraps_to_december(self):
        r = self.client.get(reverse("timeline-month", kwargs={"year": 2026, "month": 1}))
        self.assertEqual(r.context["prev_month"], 12)
        self.assertEqual(r.context["prev_year"],  2025)

    def test_next_month_wraps_to_january(self):
        r = self.client.get(reverse("timeline-month", kwargs={"year": 2026, "month": 12}))
        self.assertEqual(r.context["next_month"], 1)
        self.assertEqual(r.context["next_year"],  2027)
