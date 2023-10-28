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
from django.views.generic import TemplateView
from django.urls import re_path
from .views import ConcentrationGraphView, SecondDerivativeGraphView, ThirdDerivativeGraphView, FourthDerivativeGraphView, DifferenceGraphView, PrincipalComponentAnalysisView, MCAnalysis, SmoothingData


urlpatterns = [
    path("xzoDx2yX/", admin.site.urls),
    # Upload Excel File(NIV)
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

    # Download Excel(Difference)
    path('api/difference_download/', views.difference_download,
         name='difference_download'),


    # PCA
    path('pca/', PrincipalComponentAnalysisView.as_view(),
         name='pca'),

    # MCA
    path('mca/', MCAnalysis.as_view(), name='mca_analysis'),




    # FileUpload(FUV)
    path('api/fuv_upload/', views.FUVUpload_file, name='fuv_upload'),


    path('api/kk_transformed_spectrum/', views.kk_transformed_spectrum,
         name='kk_transformed_spectrum'),

    path('api/nire_upload/', views.FUVNireUpload_file, name='fuv_nire_upload'),
    path('api/kk_download_url', views.kk_download_all, name='download_url'),


    path('api/fuv_second_derivative/',
         views.fuv_second_derivative, name='second_derivative'),

    path('api/fuv_second_derivative_upload/', views.FUVSecondDerivativeUpload,
         name='fuv_second_derivative_upload'),

    path('api/fuv_second_derivative_download/',
         views.fuv_second_derivative_download, name='fuv_second_derivative_download'),


    path('api/find_peak_upload_file/',
         views.find_peak_upload_file, name='upload-file-to-s3'),

    path('api/find_peak/', views.evaluate_peaks_within_range, name='find_peak'),


    path('api/download_peaks_data/', views.download_peaks_data,
         name='download_peaks_data'),

    path('api/upload_file_for_smoothing/',
         views.upload_file_for_smoothing, name='upload_file_for_smoothing'),

    path('api/smoothing_data/', SmoothingData.as_view(), name='smoothing_data'),



    path('api/download_smoothed_data/', views.download_smoothed_data,
         name='download_smoothed_data'),
    path('login/', views.login_view, name='login'),

    path('signup/', views.signup_view, name='signup'),

    path('superuser-login/', views.superuser_login, name='superuser_login'),


    re_path(r'^.*$', TemplateView.as_view(template_name="index.html")),
]
