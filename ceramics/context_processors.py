from .models import Kiln


def kilns(request):
    """Inject all kilns into every template context."""
    return {"kilns": Kiln.objects.all()}
