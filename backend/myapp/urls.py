"""
URL configuration for myapp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from . import views
from .views import ConcentrationGraphView, SecondDerivativeGraphView, ThirdDerivativeGraphView, FourthDerivativeGraphView, DifferenceGraphView, PrincipalComponentAnalysisView


urlpatterns = [
    path("admin/", admin.site.urls),
    # Upload Excel File
    path('api/upload_excel/', views.upload_file, name='upload_file'),

    # NIRGraph
    path('api/latest_graph/', views.generate_spectrum_graph, name='latest-graph'),

    # Get Files From S3
    path('api/get_files_from_s3/', views.get_files_from_s3,
         name='get_files_from_s3'),

    # Concentration Graph
    path('api/concentration_graph/', ConcentrationGraphView.as_view(),
         name='concentration_graph'),

    # Download Excel(Concentration)
    path('api/download_excel/', views.download_excel, name='download_excel'),


    # SecondDerivative
    path('api/second_derivative_graph/', SecondDerivativeGraphView.as_view(),
         name='second_derivative_graph'),

    # Download Excel(SecondDerivative)
    path('api/second_derivative_download/', views.second_derivative_download,
         name='second_derivative_download'),


    # ThirdDerivative
    path('api/third_derivative_graph/', ThirdDerivativeGraphView.as_view(),
         name='third_derivative_graph'),

    # Download Excel(ThirdDerivative)
    path('api/third_derivative_download/', views.third_derivative_download,
         name='third_derivative_download'),



    # FourthDerivative
    path('api/fourth_derivative_graph/', FourthDerivativeGraphView.as_view(),
         name='fourth_derivative_graph'),

    # Download Excel(ThirdDerivative)
    path('api/fourth_derivative_download/', views.fourth_derivative_download,
         name='fourth_derivative_download'),

    # Difference
    path('api/difference_graph/', DifferenceGraphView.as_view(),
         name='difference_graph'),


    path('api/difference_download/', views.difference_download,
         name='difference_download'),



    path('api/pca_analysis/', PrincipalComponentAnalysisView.as_view(),
         name='pca_analysis'),
]
