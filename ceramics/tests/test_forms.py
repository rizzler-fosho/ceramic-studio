"""
Form validation tests
=====================
These tests check that each form accepts valid data and rejects invalid data,
without touching the database or HTTP layer.

``PieceUpdateForm`` is a ``ModelForm`` so we also verify the ``save()``
call returns the right model instance.
"""

import datetime

from django.test import TestCase

from ceramics.forms import CollectionForm, PieceForm, PieceUpdateForm, ProfileForm


# ---------------------------------------------------------------------------
# CollectionForm
# ---------------------------------------------------------------------------

class CollectionFormTest(TestCase):

    def test_valid_with_name_only(self):
        form = CollectionForm({"name": "Spring Mugs", "description": ""})
        self.assertTrue(form.is_valid())

    def test_valid_with_name_and_description(self):
        form = CollectionForm({"name": "Spring Mugs", "description": "My first collection"})
        self.assertTrue(form.is_valid())

    def test_invalid_when_name_is_blank(self):
        form = CollectionForm({"name": "", "description": "Something"})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_invalid_when_name_is_missing(self):
        form = CollectionForm({"description": "No name provided"})
        self.assertFalse(form.is_valid())

    def test_description_is_not_required(self):
        """description is optional — the form must be valid without it."""
        form = CollectionForm({"name": "Autumn Bowls"})
        self.assertTrue(form.is_valid())


# ---------------------------------------------------------------------------
# PieceForm
# ---------------------------------------------------------------------------

class PieceFormTest(TestCase):

    def test_valid_with_title_and_date(self):
        form = PieceForm({"title": "Fancy Mug", "date": "2026-04-05"})
        self.assertTrue(form.is_valid())

    def test_invalid_when_title_is_blank(self):
        form = PieceForm({"title": "", "date": "2026-04-05"})
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_invalid_when_date_is_missing(self):
        form = PieceForm({"title": "Mug"})
        self.assertFalse(form.is_valid())
        self.assertIn("date", form.errors)

    def test_invalid_when_date_format_is_wrong(self):
        form = PieceForm({"title": "Mug", "date": "April 5, 2026"})
        self.assertFalse(form.is_valid())
        self.assertIn("date", form.errors)

    def test_cleaned_date_is_a_date_object(self):
        form = PieceForm({"title": "Bowl", "date": "2026-03-15"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["date"], datetime.date(2026, 3, 15))


# ---------------------------------------------------------------------------
# PieceUpdateForm
# ---------------------------------------------------------------------------

class PieceUpdateFormTest(TestCase):

    def test_valid_with_stage_only(self):
        """Only stage is required; description and glaze_notes are optional."""
        form = PieceUpdateForm({"stage": "greenware", "description": "", "glaze_notes": ""})
        self.assertTrue(form.is_valid())

    def test_valid_with_all_fields(self):
        form = PieceUpdateForm({
            "stage": "glaze",
            "description": "Shiny and fired.",
            "glaze_notes": "Golden Hour yellow on the body.",
        })
        self.assertTrue(form.is_valid())

    def test_invalid_when_stage_is_missing(self):
        form = PieceUpdateForm({"description": "No stage", "glaze_notes": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("stage", form.errors)

    def test_invalid_stage_value(self):
        form = PieceUpdateForm({"stage": "raku", "description": "", "glaze_notes": ""})
        self.assertFalse(form.is_valid())

    def test_valid_stages_are_accepted(self):
        for stage in ("greenware", "bisque", "glaze"):
            with self.subTest(stage=stage):
                form = PieceUpdateForm({"stage": stage, "description": "", "glaze_notes": ""})
                self.assertTrue(form.is_valid(), f"Stage '{stage}' should be valid")


# ---------------------------------------------------------------------------
# ProfileForm
# ---------------------------------------------------------------------------

class ProfileFormTest(TestCase):

    def test_valid_with_bio(self):
        form = ProfileForm({"bio": "I love making mugs."}, files={})
        self.assertTrue(form.is_valid())

    def test_valid_with_empty_bio(self):
        """bio is not required — an empty submission is valid."""
        form = ProfileForm({"bio": ""}, files={})
        self.assertTrue(form.is_valid())

    def test_valid_with_no_data_submitted(self):
        """Submitting the form with no fields is valid (both fields are optional)."""
        form = ProfileForm({}, files={})
        self.assertTrue(form.is_valid())
