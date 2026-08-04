from django.urls import path

from . import views

app_name = "stars"

urlpatterns = [
    path("", views.kid_list, name="kid_list"),
    path("kid/<int:kid_id>/", views.kid_detail, name="kid_detail"),
    path("kid/<int:kid_id>/add/", views.add_stars, name="add_stars"),
    path("kid/<int:kid_id>/quick/<int:action_id>/", views.quick_action, name="quick_action"),
    path("kid/<int:kid_id>/delete/<int:txn_id>/", views.delete_transaction, name="delete_transaction"),
]
