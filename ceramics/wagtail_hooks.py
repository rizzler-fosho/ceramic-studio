"""
Wagtail sidebar integration.

Adds a "My Collections" link to the Wagtail admin left-hand nav
so editors can jump to the ceramics portfolio without leaving the CMS.
"""

from django.urls import reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem


@hooks.register("register_admin_menu_item")
def register_ceramics_menu_item():
    return MenuItem(
        label="My Collections",
        url=reverse("dashboard"),
        icon_name="folder-open-inverse",
        order=200,
    )
