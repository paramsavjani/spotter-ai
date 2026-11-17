from django.urls import path, re_path

from routing import views

urlpatterns = [
    path("api/geocode/", views.geocode),
    path("api/plan/", views.plan_trip),
    re_path(r"^(?!api/).*$", views.frontend),
]
