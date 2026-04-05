import datetime

from django import forms

from .models import PieceUpdate, UserProfile

_FIELD_CLASS = (
    "w-full rounded-lg border border-stone-300 px-4 py-2 "
    "focus:outline-none focus:ring-2 focus:ring-amber-500"
)


class CollectionForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            "class": _FIELD_CLASS,
            "placeholder": "e.g. Spring Mugs 2024",
        }),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": _FIELD_CLASS,
            "rows": 3,
            "placeholder": "A brief description of this collection (optional)",
        }),
    )


class PieceForm(forms.Form):
    title = forms.CharField(
        max_length=200,
        label="Name",
        widget=forms.TextInput(attrs={
            "class": _FIELD_CLASS,
            "placeholder": "e.g. Fancy Mug",
        }),
    )
    date = forms.DateField(
        label="Start Date",
        initial=datetime.date.today,
        widget=forms.DateInput(attrs={
            "class": _FIELD_CLASS,
            "type": "date",
        }),
    )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["avatar", "bio"]
        widgets = {
            "avatar": forms.ClearableFileInput(attrs={
                "class": "hidden",
                "id": "id_avatar",
                "accept": "image/*",
            }),
            "bio": forms.Textarea(attrs={
                "class": _FIELD_CLASS,
                "rows": 4,
                "placeholder": "Tell us about your ceramic journey…",
            }),
        }
        labels = {"bio": "Bio"}


class PieceUpdateForm(forms.ModelForm):
    class Meta:
        model = PieceUpdate
        fields = ["stage", "description", "glaze_notes"]
        widgets = {
            "stage": forms.Select(attrs={
                "class": _FIELD_CLASS,
                "id": "id_stage",
            }),
            "description": forms.Textarea(attrs={
                "class": _FIELD_CLASS,
                "rows": 4,
                "id": "id_description",
                "placeholder": "AI will describe your piece here after you upload a photo…",
            }),
            "glaze_notes": forms.Textarea(attrs={
                "class": _FIELD_CLASS,
                "rows": 2,
                "id": "id_glaze_notes",
                "placeholder": "e.g. Golden Hour yellow on the body, Carmel and White Gloss on the lid",
            }),
        }
        labels = {"glaze_notes": "Glaze Names (AI — edit before saving)"}
        help_texts = {
            "stage": "AI will guess this from your first photo — you can correct it.",
            "description": "AI-generated. Feel free to personalise it.",
            "glaze_notes": "Only shown for Final Glaze Fire stage.",
        }
