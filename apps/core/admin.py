from django.contrib import admin
from django.http import HttpResponse


class NoAuthAdminSite(admin.AdminSite):
    """Admin site without authentication for debugging Lambda issues."""
    
    def has_permission(self, request):
        """Allow access to admin without authentication (DEBUG ONLY)."""
        return True
    
    def login(self, request, extra_context=None):
        """Skip login and go directly to admin."""
        from django.shortcuts import redirect
        return redirect('/admin/')

# Create debug admin site
debug_admin_site = NoAuthAdminSite(name='debug_admin')