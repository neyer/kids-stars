from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "stars"

urlpatterns = [
    path("", views.kid_list, name="kid_list"),
    path("quick/", views.quick_tap, name="quick_tap"),
    path("kid/<int:kid_id>/tap/", views.tap, name="tap"),
    path("kid/<int:kid_id>/", views.kid_detail, name="kid_detail"),
    path("kid/<int:kid_id>/add/", views.add_stars, name="add_stars"),
    path("kid/<int:kid_id>/quick/<int:action_id>/", views.quick_action, name="quick_action"),
    path("kid/<int:kid_id>/delete/<int:txn_id>/", views.delete_transaction, name="delete_transaction"),
    path("login/", auth_views.LoginView.as_view(template_name="stars/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
