"""
Model unit tests
================
These tests exercise model properties and business logic directly, without
going through the HTTP layer.  They answer the question:
"Given some database state, do the model methods return the right values?"

Page tree setup
---------------
Wagtail stores pages in a treebeard MP_Node tree.  You MUST use
``parent.add_child(instance=child)`` — never ``child.save()`` alone —
to register the page in the tree correctly.  Wagtail's own migrations
create a root Page at depth=1 which is available in every TestCase.
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
# Shared helpers
# ---------------------------------------------------------------------------

def _build_tree(user):
    """Return (index, collection, piece) rooted under the Wagtail root page."""
    root = Page.objects.filter(depth=1).first()

    index = CollectionIndexPage(title="Portfolio", slug="portfolio", live=True)
    root.add_child(instance=index)

    collection = CollectionPage(
        title="Spring Mugs",
        slug="spring-mugs",
        description="My spring collection",
        live=True,
        owner=user,
    )
    index.add_child(instance=collection)

    piece = PiecePage(
        title="Fancy Mug",
        slug="fancy-mug",
        date=datetime.date(2026, 4, 5),
        live=True,
        owner=user,
    )
    collection.add_child(instance=piece)

    return index, collection, piece


def _make_image_file(name="photo.jpg"):
    """Return a minimal valid JPEG as a SimpleUploadedFile."""
    from PIL import Image as PilImage
    from django.core.files.uploadedfile import SimpleUploadedFile

    buf = io.BytesIO()
    PilImage.new("RGB", (10, 10), color=(200, 100, 50)).save(buf, "JPEG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/jpeg")


# ---------------------------------------------------------------------------
# CollectionPage
# ---------------------------------------------------------------------------

class CollectionPageModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("potter", password="clay")
        self.index, self.collection, self.piece = _build_tree(self.user)

    def test_name_property_returns_title(self):
        """CollectionPage.name is a shim so templates can use .name."""
        self.assertEqual(self.collection.name, self.collection.title)

    def test_pieces_returns_live_child_pages(self):
        """CollectionPage.pieces returns the live PiecePages under it."""
        qs = self.collection.pieces
        self.assertIn(self.piece, qs)
        self.assertEqual(qs.count(), 1)

    def test_pieces_excludes_draft_pages(self):
        """Draft pieces must not appear in .pieces."""
        draft = PiecePage(
            title="Draft Mug", slug="draft-mug",
            date=datetime.date(2026, 4, 5), live=False,
        )
        self.collection.add_child(instance=draft)
        self.assertEqual(self.collection.pieces.count(), 1)

    def test_get_absolute_url(self):
        expected = reverse("collection-detail", kwargs={"pk": self.collection.pk})
        self.assertEqual(self.collection.get_absolute_url(), expected)


# ---------------------------------------------------------------------------
# PiecePage
# ---------------------------------------------------------------------------

class PiecePageModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("potter", password="clay")
        self.index, self.collection, self.piece = _build_tree(self.user)

    def test_collection_property_returns_parent_collection(self):
        self.assertEqual(self.piece.collection, self.collection)

    def test_latest_update_is_none_with_no_updates(self):
        self.assertIsNone(self.piece.latest_update)

    def test_current_stage_is_none_with_no_updates(self):
        self.assertIsNone(self.piece.current_stage)

    def test_current_stage_display_with_no_updates(self):
        self.assertEqual(self.piece.current_stage_display, "No photos yet")

    def test_cover_image_is_none_with_no_updates(self):
        self.assertIsNone(self.piece.cover_image)

    def test_latest_update_returns_most_recent(self):
        u1 = PieceUpdate(page=self.piece, stage="greenware"); u1.save()
        u2 = PieceUpdate(page=self.piece, stage="bisque");    u2.save()
        self.assertEqual(self.piece.latest_update.stage, "bisque")

    def test_current_stage_reflects_latest_update(self):
        PieceUpdate(page=self.piece, stage="glaze").save()
        self.assertEqual(self.piece.current_stage, "glaze")

    def test_current_stage_display_reflects_latest_update(self):
        PieceUpdate(page=self.piece, stage="bisque").save()
        self.assertEqual(self.piece.current_stage_display, "Bisque Fire")

    def test_get_absolute_url(self):
        expected = reverse("piece-detail", kwargs={"pk": self.piece.pk})
        self.assertEqual(self.piece.get_absolute_url(), expected)

    def test_cover_image_returns_first_image_of_latest_update(self):
        media_dir = tempfile.mkdtemp()
        try:
            with override_settings(MEDIA_ROOT=media_dir):
                update = PieceUpdate(page=self.piece, stage="greenware")
                update.save()
                img = PieceUpdateImage.objects.create(
                    update=update, image=_make_image_file(), sort_order=0
                )
                cover = self.piece.cover_image
                self.assertIsNotNone(cover)
                self.assertEqual(cover.name, img.image.name)
        finally:
            shutil.rmtree(media_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# PieceUpdate
# ---------------------------------------------------------------------------

class PieceUpdateModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("potter", password="clay")
        _, _, self.piece = _build_tree(self.user)

    def test_save_assigns_sort_order_zero_for_first_update(self):
        u = PieceUpdate(page=self.piece, stage="greenware")
        u.save()
        self.assertEqual(u.sort_order, 0)

    def test_save_increments_sort_order(self):
        u1 = PieceUpdate(page=self.piece, stage="greenware"); u1.save()
        u2 = PieceUpdate(page=self.piece, stage="bisque");    u2.save()
        self.assertEqual(u1.sort_order, 0)
        self.assertEqual(u2.sort_order, 1)

    def test_save_mirrors_description_to_piece(self):
        u = PieceUpdate(page=self.piece, stage="greenware", description="A lovely mug.")
        u.save()
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.description, "A lovely mug.")

    def test_save_does_not_clear_description_when_empty(self):
        """An update with no description should not wipe the piece's description."""
        self.piece.description = "Existing description."
        self.piece.save()
        PieceUpdate(page=self.piece, stage="bisque", description="").save()
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.description, "Existing description.")

    def test_str(self):
        u = PieceUpdate(page=self.piece, stage="bisque")
        u.save()
        self.assertIn("Fancy Mug", str(u))
        self.assertIn("Bisque Fire", str(u))


# ---------------------------------------------------------------------------
# PieceUpdateImage
# ---------------------------------------------------------------------------

class PieceUpdateImageModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("potter", password="clay")
        _, _, piece = _build_tree(self.user)
        self.update = PieceUpdate(page=piece, stage="greenware")
        self.update.save()

    def test_ordering_by_sort_order(self):
        media_dir = tempfile.mkdtemp()
        try:
            with override_settings(MEDIA_ROOT=media_dir):
                i2 = PieceUpdateImage.objects.create(
                    update=self.update, image=_make_image_file("b.jpg"), sort_order=2
                )
                i0 = PieceUpdateImage.objects.create(
                    update=self.update, image=_make_image_file("a.jpg"), sort_order=0
                )
                first = self.update.images.first()
                self.assertEqual(first.pk, i0.pk)
        finally:
            shutil.rmtree(media_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# UserProfile
# ---------------------------------------------------------------------------

class UserProfileModelTest(TestCase):
    def test_str(self):
        user = User.objects.create_user("potter", password="clay")
        profile = UserProfile.objects.create(user=user)
        self.assertEqual(str(profile), "Profile(potter)")

    def test_bio_is_blank_by_default(self):
        user = User.objects.create_user("potter2", password="clay")
        profile = UserProfile.objects.create(user=user)
        self.assertEqual(profile.bio, "")

    def test_avatar_is_blank_by_default(self):
        user = User.objects.create_user("potter3", password="clay")
        profile = UserProfile.objects.create(user=user)
        self.assertFalse(bool(profile.avatar))
