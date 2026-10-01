from django.urls import path

from .views import OverviewView


urlpatterns = [path("statistics/overview", OverviewView.as_view())]
