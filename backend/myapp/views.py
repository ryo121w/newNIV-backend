import json
import os
import uuid
import openpyxl
import boto3
import tempfile
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

import io
from io import BytesIO
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
import cloudinary
import cloudinary.uploader
import cloudinary.api
from scipy import ndimage
from sklearn.decomposition import PCA
import prince
from scipy.integrate import simps
from scipy.signal import savgol_filter


# Cloudinary設定
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

# AWS S3設定
s3_client = boto3.client('s3',
                         aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                         aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))
bucket_name = settings.AWS_STORAGE_BUCKET_NAME

# バケット内のフォルダを指定して取得することができる


def list_files(s3_client, bucket, prefix):
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    if 'Contents' in response:
        return [content['Key'] for content in response['Contents']]
    return []

# バケット内の特定のフォルダ内にあるデータを消去する


def delete_files_in_folder(s3_client, bucket, folder):
    """Delete all files in a specific S3 folder."""
    files = list_files(s3_client, bucket, folder)
    for file_key in files:
        s3_client.delete_object(Bucket=bucket, Key=file_key)


# ファイルアップロード関数
@csrf_exempt
def upload_file(request):
    if request.method == 'POST':
        try:
            print("Access Key:", os.environ.get('AWS_ACCESS_KEY_ID'))
            print("Secret Key:", os.environ.get('AWS_SECRET_ACCESS_KEY'))

            data = json.loads(request.body.decode('utf-8'))

            file_name = f"{uuid.uuid4()}.xlsx"

            workbook = openpyxl.Workbook()
            sheet = workbook.active
            for index, row in enumerate(data):
                for key, value in row.items():
                    if index == 0:
                        header_col = sheet.cell(
                            row=1, column=list(row.keys()).index(key) + 1)
                        header_col.value = key

                    cell = sheet.cell(
                        row=index + 2, column=list(row.keys()).index(key) + 1)
                    cell.value = value

            with open(file_name, 'wb') as f:
                workbook.save(f)

            s3_path = f"uploads/excel/{file_name}"

            s3_client = boto3.client('s3', aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                                     aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))

            existing_files = list_files(
                s3_client, settings.AWS_STORAGE_BUCKET_NAME, 'uploads/excel/')
            for file_key in existing_files:
                s3_client.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file_key)

            s3_client.upload_file(
                file_name, settings.AWS_STORAGE_BUCKET_NAME, s3_path)

            os.remove(file_name)

            file_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{s3_path}"

            return JsonResponse({'message': 'Data processed and saved to S3 successfully!', 'file_url': file_url})
        except json.JSONDecodeError:
            return JsonResponse({'message': 'Failed to decode JSON data.'}, status=400)

    return JsonResponse({'message': 'Only POST requests are allowed.'})

# NIRスペクトル関数


def generate_spectrum_graph(request):
    # Cloudinaryの設定
    cloudinary.config(
        cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key=os.environ.get('CLOUDINARY_API_KEY'),
        api_secret=os.environ.get('CLOUDINARY_API_SECRET')
    )

    s3_client = boto3.client('s3', aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                             aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    # S3内の'uploads/excel/'ディレクトリから最新のファイルを取得
    # (list_files関数の定義がないため、この部分を具体的には確認できません。)
    files = list_files(s3_client, bucket_name, 'uploads/excel/')
    if not files:
        return HttpResponse('No files found in S3 bucket.')

    latest_uploaded_file = sorted(files)[-1]

    # S3からExcelファイルをダウンロード
    obj = s3_client.get_object(Bucket=bucket_name, Key=latest_uploaded_file)
    df = pd.read_excel(BytesIO(obj['Body'].read()))
    df = df[(df['波長'] >= 6000) & (df['波長'] <= 8000)]

    # グラフ生成
    plt.figure(figsize=(10, 6))
    plt.xlim(6000, 8000)

    # 6000-8000の範囲での最大値を検知し、y軸の上限を設定
    max_y_val_within_range = df[df.columns[1:]].max().max()
    plt.ylim(0, max_y_val_within_range + 0.1)

    concentrations = None
    concentrations_columns = concentrations if concentrations else list(
        df.columns[1:])
    colors = plt.cm.rainbow(np.linspace(0, 0.5, len(concentrations_columns)))

    for col_name, color in zip(concentrations_columns, colors):
        if col_name in df.columns:
            plt.plot(df['波長'], df[col_name], label=col_name, color=color)

    plt.title('NIR Spectrum')
    plt.xlabel('Wavelength (cm-1)')
    plt.ylabel('Absorbance')
    plt.legend()

    # グラフをバイナリのIOストリームとして保存
    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)
    plt.close()

    # Cloudinaryに保存されている古いイメージを削除
    folder_name = 'spectrums'
    stored_images = cloudinary.api.resources(
        type='upload', prefix=folder_name, max_results=500)
    for image in stored_images['resources']:
        cloudinary.uploader.destroy(image['public_id'])

    # 新しいイメージをCloudinaryのフォルダにアップロード
    upload_response = cloudinary.uploader.upload(
        img_data,
        folder=folder_name,
        use_filename=True,
        unique_filename=False
    )
    graph_url = upload_response['url']

    return HttpResponse(graph_url)

# モル吸光係数
# モル濃度の情報を取得


def get_molarities_from_excel(file_path):
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        s3_client = boto3.client('s3', aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                                 aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    s3_client.download_file(bucket_name, file_path, temp_file.name)
    df = pd.read_excel(temp_file.name)
    molarities = df.columns[1:].tolist()
    return molarities

# ファイルからモル濃度の情報を取得


def get_files_from_s3(request):
    s3_client = boto3.client('s3')
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    files = list_files(s3_client, bucket_name, 'uploads/excel/')

    if not files:
        return JsonResponse({'error': 'No files found in S3 bucket.'}, status=404)

    # エクセルファイルから濃度情報を取得 (ここでは最初のファイルを仮で利用)
    file_path = files[0]
    molarities = get_molarities_from_excel(file_path)
    return JsonResponse({'files': files, 'molarities': molarities})

# エクセルファイルダウンロード


def download_excel(request):
    s3_client = boto3.client('s3',
                             aws_access_key_id=os.environ.get(
                                 'AWS_ACCESS_KEY_ID'),
                             aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))

    # S3内の'uploads/excel/'ディレクトリから最新のファイルを取得（あなたのコードを前提としています）
    bucket_name = 'newniv-bucket'
    files = list_files(s3_client, bucket_name, 'processed_data')

    if not files:
        return HttpResponse('No files found in S3 bucket.')

    try:
        # 最新のファイルのキー
        latest_file_key = files[0]

        # メモリ上のバイナリストリームとしてファイルを取得
        file_stream = s3_client.get_object(
            Bucket=bucket_name, Key=latest_file_key)['Body']

        # クライアントに送信するためのレスポンスを作成
        response = HttpResponse(file_stream.read(),
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        # 最新のファイル名をそのまま使用
        response[
            'Content-Disposition'] = f'attachment; filename="{latest_file_key.split("/")[-1]}"'

        return response

    except Exception as e:
        print(e)
        return HttpResponse("An error occurred while downloading the file.")

# AWSのファイルをリストで取得


def list_files(s3_client, bucket_name, prefix):
    # バケットから特定のプレフィックスを持つオブジェクトのリストを取得
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    return [content['Key'] for content in response.get('Contents', [])]

# モル吸光係数


class ConcentrationGraphView(APIView):
    parser_classes = (MultiPartParser,)

    def post(self, request):
        print(f"Debug: Received POST data: {request.data}")
        concentrations = request.data.getlist('concentrations[]', [])
        print(f"Debug: Received concentrations: {concentrations}")

        # S3 configuration
        s3_client = boto3.client('s3', aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                                 aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))
        bucket_name = os.environ.get('AWS_STORAGE_BUCKET_NAME')

        # S3内の'uploads/excel/'ディレクトリから最新のファイルを取得
        files = list_files(s3_client, bucket_name, 'uploads/excel/')
        if not files:
            return HttpResponse('No files found in S3 bucket.')

        latest_file_key = files[-1]
        local_path = "/tmp/latest_file.xlsx"
        s3_client.download_file(bucket_name, latest_file_key, local_path)

        df = pd.read_excel(local_path)
        columns = df.columns.drop('波長')
        print(f"Debug: Excel columns: {columns.tolist()}")

        if len(columns) != len(concentrations):
            error_message = f'Mismatch between number of data columns ({len(columns)}) and provided concentrations ({len(concentrations)}). Columns: {columns.tolist()}, Concentrations: {concentrations}'
            return Response({'error': error_message}, status=status.HTTP_400_BAD_REQUEST)

        plt.figure(figsize=(10, 6))
        plt.xlim(8000, 6000)

        max_val = 0  # Initialize max_val to be updated for each processed column

        colors = cm.rainbow(np.linspace(0, 0.5, len(columns)))

        for i, (column, color) in enumerate(zip(columns, colors)):
            # Process/normalize the column data here
            norm_column = df[column] / float(concentrations[i])

            # Update max_val if new max found
            current_max = norm_column[(df['波長'] >= 6000) & (
                df['波長'] <= 8000)].max()
            max_val = max(max_val, current_max)

            plt.plot(df['波長'], norm_column,
                     label=f'{column} - {concentrations[i]}M', color=color)

        plt.ylim(0, max_val + 0.01)  # Set y limit based on max_val

        plt.title('NIR Spectrum of LiCl with Concentrations')
        plt.xlabel('Wavelength (cm-1)')
        plt.ylabel('Absorbance')
        plt.legend()

        graph_filename = 'concentration_nir_spectrum.png'
        graph_dir = 'static'
        graph_filepath = os.path.join(graph_dir, graph_filename)

        if not os.path.exists(graph_dir):
            os.makedirs(graph_dir)

        plt.savefig(graph_filepath)
        plt.close()

        # Delete previous data in the processed_data folder
        delete_files_in_folder(s3_client, bucket_name, 'processed_data/')

        # Processed Excel data to a new S3 folder
        processed_excel_path = os.path.join(graph_dir, 'processed_data.xlsx')
        df.to_excel(processed_excel_path, index=False)
        s3_upload_path = f'processed_data/processed_data.xlsx'
        s3_client.upload_file(processed_excel_path,
                              bucket_name, s3_upload_path)

        # Cloudinaryの設定
        cloudinary.config(
            cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
            api_key=os.environ.get('CLOUDINARY_API_KEY'),
            api_secret=os.environ.get('CLOUDINARY_API_SECRET')
        )

        # Cloudinaryに保存されている古いイメージを削除
        folder_name = 'concentration'
        stored_images = cloudinary.api.resources(
            type='upload', prefix=f"{folder_name}/", max_results=500)
        for image in stored_images['resources']:
            cloudinary.uploader.destroy(image['public_id'])

        # グラフをCloudinaryのフォルダにアップロード
        upload_response = cloudinary.uploader.upload(
            graph_filepath, folder=folder_name, use_filename=True, unique_filename=False)
        cloudinary_url = upload_response['url']

        response_data = {'graph_url': cloudinary_url}
        return JsonResponse(response_data)


# 二次微分
class SecondDerivativeGraphView(APIView):

    def post(self, request):
        s3_client = boto3.client('s3')
        bucket_name = 'newniv-bucket'

        files = list_files(s3_client, bucket_name, 'processed_data/')
        if not files:
            return HttpResponse('No files found in S3 bucket.')

        latest_file_key = files[-1]
        local_path = "/tmp/latest_file.xlsx"
        s3_client.download_file(bucket_name, latest_file_key, local_path)

        df = pd.read_excel(local_path)
        columns = df.columns.drop('波長')

        # Create a copy of the dataframe to store the second derivative data
        derivative_df = df.copy()

        plt.figure(figsize=(10, 6))
        plt.xlim(8000, 6000)

        # Initialize variables to find max and min values dynamically
        max_val, min_val = None, None

        colors = plt.cm.rainbow(np.linspace(0, 1, len(columns)))

        for col, c in zip(columns, colors):
            if col.startswith('Molar_Absorptivity_'):
                continue

            smoothed_data = ndimage.gaussian_filter1d(df[col], sigma=10)
            y = ndimage.gaussian_filter1d(smoothed_data, sigma=10, order=2)
            derivative_df[col] = y

            # Dynamically find max and min values in the specified range
            current_max = y[(df['波長'] >= 6000) & (df['波長'] <= 8000)].max()
            current_min = y[(df['波長'] >= 6000) & (df['波長'] <= 8000)].min()

            # Update max and min values if new extremes found
            max_val = current_max if max_val is None else max(
                max_val, current_max)
            min_val = current_min if min_val is None else min(
                min_val, current_min)

            plt.plot(df['波長'], y, label=col, color=c)

        # Set y limit based on dynamically found max and min values
        plt.ylim(min_val, max_val)

        plt.title('Second Derivative of NIR Spectrum')
        plt.xlabel('Wavelength (cm-1)')
        plt.ylabel('Second Derivative of Absorbance')
        plt.legend(loc='upper right')

        graph_filename = 'second_derivative_nir_spectrum.png'
        graph_dir = 'static'
        graph_filepath = os.path.join(graph_dir, graph_filename)

        if not os.path.exists(graph_dir):
            os.makedirs(graph_dir)

        plt.savefig(graph_filepath)
        plt.close()

        # Save the second derivative data to S3
        processed_excel_path = os.path.join(
            graph_dir, 'second_derivative_data.xlsx')
        derivative_df.to_excel(processed_excel_path, index=False)
        s3_upload_path = f'second_derivative/second_derivative_data.xlsx'
        s3_client.upload_file(processed_excel_path,
                              bucket_name, s3_upload_path)

        # Cloudinaryの設定
        cloudinary.config(
            cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
            api_key=os.environ.get('CLOUDINARY_API_KEY'),
            api_secret=os.environ.get('CLOUDINARY_API_SECRET')
        )

        # Cloudinaryに保存されている古いイメージを削除
        folder_name = 'SecondDerivative'
        stored_images = cloudinary.api.resources(
            type='upload', prefix=f"{folder_name}/", max_results=500)
        for image in stored_images['resources']:
            cloudinary.uploader.destroy(image['public_id'])

        # グラフをCloudinaryのフォルダにアップロード
        upload_response = cloudinary.uploader.upload(
            graph_filepath, folder=folder_name, use_filename=True, unique_filename=False)
        cloudinary_url = upload_response['url']

        response_data = {'graph_url': cloudinary_url}
        return JsonResponse(response_data)
# 二次微分のエクセルデータダウンロード


def second_derivative_download(request):
    s3_client = boto3.client('s3',
                             aws_access_key_id=os.environ.get(
                                 'AWS_ACCESS_KEY_ID'),
                             aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))

    # S3内の'second_derivative/'ディレクトリから最新のファイルを取得
    bucket_name = 'newniv-bucket'
    prefix = 'second_derivative/'
    files = list_files(s3_client, bucket_name, prefix)

    if not files:
        return HttpResponse('No files found in S3 bucket under the specified prefix.')

    try:
        # 最新のファイルのキー
        latest_file_key = files[-1]  # 最新のファイルを取得するために[-1]を使用

        # メモリ上のバイナリストリームとしてファイルを取得
        file_stream = s3_client.get_object(
            Bucket=bucket_name, Key=latest_file_key)['Body']

        # クライアントに送信するためのレスポンスを作成
        response = HttpResponse(file_stream.read(),
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        # 最新のファイル名をそのまま使用
        response[
            'Content-Disposition'] = f'attachment; filename="{latest_file_key.split("/")[-1]}"'

        return response

    except Exception as e:
        print(e)
        return HttpResponse("An error occurred while downloading the file.")

# 三次微分


class ThirdDerivativeGraphView(APIView):

    def post(self, request):
        s3_client = boto3.client('s3')
        bucket_name = 'newniv-bucket'

        files = list_files(s3_client, bucket_name, 'processed_data/')
        if not files:
            return HttpResponse('No files found in S3 bucket.')

        latest_file_key = files[-1]
        local_path = "/tmp/latest_file.xlsx"
        s3_client.download_file(bucket_name, latest_file_key, local_path)

        df = pd.read_excel(local_path)
        columns = df.columns.drop('波長')

        # Create a copy of the dataframe to store the third derivative data
        derivative_df = df.copy()

        plt.figure(figsize=(10, 6))
        plt.xlim(8000, 6000)

        # Initialize variables to find max and min values dynamically
        max_val, min_val = None, None

        colors = plt.cm.rainbow(np.linspace(0, 1, len(columns)))

        for col, c in zip(columns, colors):
            if col.startswith('Molar_Absorptivity_'):
                continue

            smoothed_data = ndimage.gaussian_filter1d(df[col], sigma=10)
            y = ndimage.gaussian_filter1d(smoothed_data, sigma=10, order=3)
            derivative_df[col] = y

            # Dynamically find max and min values in the specified range
            current_max = y[(df['波長'] >= 6000) & (df['波長'] <= 8000)].max()
            current_min = y[(df['波長'] >= 6000) & (df['波長'] <= 8000)].min()

            # Update max and min values if new extremes found
            max_val = current_max if max_val is None else max(
                max_val, current_max)
            min_val = current_min if min_val is None else min(
                min_val, current_min)

            plt.plot(df['波長'], y, label=col, color=c)

        # Set y limit based on dynamically found max and min values
        plt.ylim(min_val, max_val)

        plt.title('Third Derivative of NIR Spectrum')
        plt.xlabel('Wavelength (cm-1)')
        plt.ylabel('Third Derivative of Absorbance')
        plt.legend(loc='upper right')

        graph_filename = 'third_derivative_nir_spectrum.png'
        graph_dir = 'static'
        graph_filepath = os.path.join(graph_dir, graph_filename)

        if not os.path.exists(graph_dir):
            os.makedirs(graph_dir)

        plt.savefig(graph_filepath)
        plt.close()

        # Save the third derivative data to S3
        processed_excel_path = os.path.join(
            graph_dir, 'third_derivative_data.xlsx')
        derivative_df.to_excel(processed_excel_path, index=False)
        s3_upload_path = f'third_derivative/third_derivative_data.xlsx'
        s3_client.upload_file(processed_excel_path,
                              bucket_name, s3_upload_path)

        # Cloudinaryの設定
        cloudinary.config(
            cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
            api_key=os.environ.get('CLOUDINARY_API_KEY'),
            api_secret=os.environ.get('CLOUDINARY_API_SECRET')
        )

        # Cloudinaryに保存されている古いイメージを削除
        folder_name = 'ThirdDerivative'
        stored_images = cloudinary.api.resources(
            type='upload', prefix=f"{folder_name}/", max_results=500)
        for image in stored_images['resources']:
            cloudinary.uploader.destroy(image['public_id'])

        # グラフをCloudinaryのフォルダにアップロード
        upload_response = cloudinary.uploader.upload(
            graph_filepath, folder=folder_name, use_filename=True, unique_filename=False)
        cloudinary_url = upload_response['url']

        response_data = {'graph_url': cloudinary_url}
        return JsonResponse(response_data)
# 三次微分のエクセルデータダウンロード


def third_derivative_download(request):
    s3_client = boto3.client('s3',
                             aws_access_key_id=os.environ.get(
                                 'AWS_ACCESS_KEY_ID'),
                             aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))

    # S3内の'second_derivative/'ディレクトリから最新のファイルを取得
    bucket_name = 'newniv-bucket'
    prefix = 'third_derivative/'
    files = list_files(s3_client, bucket_name, prefix)

    if not files:
        return HttpResponse('No files found in S3 bucket under the specified prefix.')

    try:
        # 最新のファイルのキー
        latest_file_key = files[-1]  # 最新のファイルを取得するために[-1]を使用

        # メモリ上のバイナリストリームとしてファイルを取得
        file_stream = s3_client.get_object(
            Bucket=bucket_name, Key=latest_file_key)['Body']

        # クライアントに送信するためのレスポンスを作成
        response = HttpResponse(file_stream.read(),
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        # 最新のファイル名をそのまま使用
        response[
            'Content-Disposition'] = f'attachment; filename="{latest_file_key.split("/")[-1]}"'

        return response

    except Exception as e:
        print(e)
        return HttpResponse("An error occurred while downloading the file.")

# 四次微分


class FourthDerivativeGraphView(APIView):

    def post(self, request):
        s3_client = boto3.client('s3')
        bucket_name = 'newniv-bucket'

        files = list_files(s3_client, bucket_name, 'processed_data/')
        if not files:
            return HttpResponse('No files found in S3 bucket.')

        latest_file_key = files[-1]
        local_path = "/tmp/latest_file.xlsx"
        s3_client.download_file(bucket_name, latest_file_key, local_path)

        df = pd.read_excel(local_path)
        columns = df.columns.drop('波長')

        # Create a copy of the dataframe to store the fourth derivative data
        derivative_df = df.copy()

        plt.figure(figsize=(10, 6))
        plt.xlim(8000, 6000)

        # Initialize variables to find max and min values dynamically
        max_val, min_val = None, None

        colors = plt.cm.rainbow(np.linspace(0, 1, len(columns)))

        for col, c in zip(columns, colors):
            if col.startswith('Molar_Absorptivity_'):
                continue

            smoothed_data = ndimage.gaussian_filter1d(df[col], sigma=10)
            y = ndimage.gaussian_filter1d(smoothed_data, sigma=10, order=4)
            derivative_df[col] = y

            # Dynamically find max and min values in the specified range
            current_max = y[(df['波長'] >= 6000) & (df['波長'] <= 8000)].max()
            current_min = y[(df['波長'] >= 6000) & (df['波長'] <= 8000)].min()

            # Update max and min values if new extremes found
            max_val = current_max if max_val is None else max(
                max_val, current_max)
            min_val = current_min if min_val is None else min(
                min_val, current_min)

            plt.plot(df['波長'], y, label=col, color=c)

        # Set y limit based on dynamically found max and min values
        plt.ylim(min_val, max_val)

        plt.title('Fourth Derivative of NIR Spectrum')
        plt.xlabel('Wavelength (cm-1)')
        plt.ylabel('Fourth Derivative of Absorbance')
        plt.legend(loc='upper right')

        graph_filename = 'fourth_derivative_nir_spectrum.png'
        graph_dir = 'static'
        graph_filepath = os.path.join(graph_dir, graph_filename)

        if not os.path.exists(graph_dir):
            os.makedirs(graph_dir)

        plt.savefig(graph_filepath)
        plt.close()

        # Save the fourth derivative data to S3
        processed_excel_path = os.path.join(
            graph_dir, 'fourth_derivative_data.xlsx')
        derivative_df.to_excel(processed_excel_path, index=False)
        s3_upload_path = f'fourth_derivative/fourth_derivative_data.xlsx'
        s3_client.upload_file(processed_excel_path,
                              bucket_name, s3_upload_path)

        # Cloudinary configuration
        cloudinary.config(
            cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
            api_key=os.environ.get('CLOUDINARY_API_KEY'),
            api_secret=os.environ.get('CLOUDINARY_API_SECRET')
        )

        # Delete old images stored in Cloudinary
        folder_name = 'FourthDerivative'
        stored_images = cloudinary.api.resources(
            type='upload', prefix=f"{folder_name}/", max_results=500)
        for image in stored_images['resources']:
            cloudinary.uploader.destroy(image['public_id'])

        # Upload the graph to Cloudinary folder
        upload_response = cloudinary.uploader.upload(
            graph_filepath, folder=folder_name, use_filename=True, unique_filename=False)
        cloudinary_url = upload_response['url']

        response_data = {'graph_url': cloudinary_url}
        return JsonResponse(response_data)
# 四次微分のエクセルデータダウンロード


def fourth_derivative_download(request):
    s3_client = boto3.client('s3',
                             aws_access_key_id=os.environ.get(
                                 'AWS_ACCESS_KEY_ID'),
                             aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))

    # S3内の'second_derivative/'ディレクトリから最新のファイルを取得
    bucket_name = 'newniv-bucket'
    prefix = 'fourth_derivative/'
    files = list_files(s3_client, bucket_name, prefix)

    if not files:
        return HttpResponse('No files found in S3 bucket under the specified prefix.')

    try:
        # 最新のファイルのキー
        latest_file_key = files[-1]  # 最新のファイルを取得するために[-1]を使用

        # メモリ上のバイナリストリームとしてファイルを取得
        file_stream = s3_client.get_object(
            Bucket=bucket_name, Key=latest_file_key)['Body']

        # クライアントに送信するためのレスポンスを作成
        response = HttpResponse(file_stream.read(),
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        # 最新のファイル名をそのまま使用
        response[
            'Content-Disposition'] = f'attachment; filename="{latest_file_key.split("/")[-1]}"'

        return response

    except Exception as e:
        print(e)
        return HttpResponse("An error occurred while downloading the file.")

# 差スペクトル


class DifferenceGraphView(APIView):
    parser_classes = [MultiPartParser]

    s3 = boto3.client('s3')
    BUCKET_NAME = 'newniv-bucket'

    def list_files_in_s3(self, s3_client, bucket_name, prefix):
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        if 'Contents' not in response:
            return []
        files = [item['Key'] for item in response['Contents']]
        return files

    def fetch_latest_data_from_s3(self):
        s3_client = boto3.client('s3')
        bucket_name = 'newniv-bucket'

        files = self.list_files_in_s3(
            s3_client, bucket_name, 'processed_data/')
        if not files:
            raise Exception('No files found in S3 bucket.')

        latest_file_key = files[-1]
        local_path = "/tmp/latest_file.xlsx"
        s3_client.download_file(bucket_name, latest_file_key, local_path)

        df = pd.read_excel(local_path)
        if 'Unnamed: 0' in df.columns:
            df = df.drop(columns='Unnamed: 0')

        return df

    def post(self, request, *args, **kwargs):
        df = self.fetch_latest_data_from_s3()
        if df is None:
            return Response({"error": "Could not fetch the latest data from S3"}, status=status.HTTP_400_BAD_REQUEST)

        zero_m_data = df.get('0M')
        if zero_m_data is None:
            return Response({"error": "0M column not found in the data"}, status=status.HTTP_400_BAD_REQUEST)

        columns = [col for col in df.columns if col not in [
            '0M', '波長'] and not col.startswith('Molar_Absorptivity_')]

        for column in columns:
            df[column] -= zero_m_data
            baseline = np.polyfit(df['波長'], df[column], 3)
            baseline = np.polyval(baseline, df['波長'])
            df[column] -= baseline

        df = df.drop(columns='0M')

        plt.figure(figsize=(10, 6))
        plt.xlim(8000, 6000)

        # Initialize variables to find max and min values dynamically
        max_val, min_val = None, None

        colors = cm.rainbow(np.linspace(0, 0.5, len(columns)))
        for column, color in zip(columns, colors):
            # Dynamically find max and min values in the specified range
            current_max = df[column][(df['波長'] >= 6000)
                                     & (df['波長'] <= 8000)].max()
            current_min = df[column][(df['波長'] >= 6000)
                                     & (df['波長'] <= 8000)].min()

            # Update max and min values if new extremes found
            max_val = current_max if max_val is None else max(
                max_val, current_max)
            min_val = current_min if min_val is None else min(
                min_val, current_min)

            plt.plot(df['波長'], df[column], label=column, color=color)

        # Set y limit based on dynamically found max and min values
        plt.ylim(min_val, max_val)

        plt.title('Difference Spectrum with Baseline Correction')
        plt.xlabel('Wavelength (cm-1)')
        plt.ylabel('Difference Intensity')
        plt.legend()

        image_path = "/tmp/difference_graph_corrected.png"
        plt.savefig(image_path)
        plt.close()
        cloudinary_upload = cloudinary.uploader.upload(
            image_path, folder="Difference", public_id="difference_graph_corrected")

        # 不要な最初の行 (行A) を削除
        df = df.iloc[1:].reset_index(drop=True)

        difference_data_path = "/tmp/difference_data.xlsx"
        df.to_excel(difference_data_path, index=False)  # 無条件で最初の行を削除
        self.s3.upload_file(difference_data_path,
                            self.BUCKET_NAME, 'difference/difference_data.xlsx')

        image_url = cloudinary_upload['secure_url']
        return JsonResponse({"graph_url": image_url})
# 差スペクトルのデータをダウンロード


def difference_download(request):
    s3_client = boto3.client('s3',
                             aws_access_key_id=os.environ.get(
                                 'AWS_ACCESS_KEY_ID'),
                             aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))

    # S3内の'second_derivative/'ディレクトリから最新のファイルを取得
    bucket_name = 'newniv-bucket'
    prefix = 'difference/'
    files = list_files(s3_client, bucket_name, prefix)

    if not files:
        return HttpResponse('No files found in S3 bucket under the specified prefix.')

    try:
        # 最新のファイルのキー
        latest_file_key = files[-1]  # 最新のファイルを取得するために[-1]を使用

        # メモリ上のバイナリストリームとしてファイルを取得
        file_stream = s3_client.get_object(
            Bucket=bucket_name, Key=latest_file_key)['Body']

        # クライアントに送信するためのレスポンスを作成
        response = HttpResponse(file_stream.read(),
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        # 最新のファイル名をそのまま使用
        response[
            'Content-Disposition'] = f'attachment; filename="{latest_file_key.split("/")[-1]}"'

        return response

    except Exception as e:
        print(e)
        return HttpResponse("An error occurred while downloading the file.")

# PCA実行


class PrincipalComponentAnalysisView(APIView):

    def post(self, request):
        s3_client = boto3.client('s3')
        bucket_name = 'newniv-bucket'

        files = list_files(s3_client, bucket_name, 'processed_data/')
        if not files:
            return Response({'error': 'No files found in S3 bucket.'}, status=404)

        latest_file_key = files[-1]
        local_path = "/tmp/latest_file.xlsx"
        s3_client.download_file(bucket_name, latest_file_key, local_path)

        df = pd.read_excel(local_path)

        # '波長'の列を除外
        pca_data = df.drop(columns=['波長'])

        # PCAのコンポーネント数を動的に設定
        n_components = min(pca_data.shape[0], pca_data.shape[1])
        pca = PCA(n_components=n_components)
        pca_result = pca.fit_transform(pca_data)

        plt.figure(figsize=(10, 6))
        plt.plot(range(1, n_components+1),
                 pca.explained_variance_ratio_.cumsum(), marker='o', linestyle='--')
        plt.title('Explained Variance by Components')
        plt.xlabel('Number of Components')
        plt.ylabel('Cumulative Explained Variance')
        plt.savefig("/tmp/pca_scree_plot.png")

        # Save the PCA result data to S3
        pca_result_df = pd.DataFrame(data=pca_result, columns=[
                                     f'PC{i}' for i in range(1, n_components+1)])
        pca_result_df.to_excel("/tmp/pca_result.xlsx", index=False)
        s3_client.upload_file("/tmp/pca_result.xlsx",
                              bucket_name, "principal_analysis/pca_result.xlsx")

        # Configure Cloudinary
        cloudinary.config(
            cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
            api_key=os.environ.get('CLOUDINARY_API_KEY'),
            api_secret=os.environ.get('CLOUDINARY_API_SECRET')
        )

        # Upload image to Cloudinary
        upload_response = cloudinary.uploader.upload(
            "/tmp/pca_scree_plot.png",
            folder="principal_analysis",
            use_filename=True,
            unique_filename=False
        )

        return Response({"graph_url": upload_response['url']}, status=200)


# MCA実行


class MCAnalysis(APIView):
    def post(self, request):
        # S3からのデータ取得コード
        s3_client = boto3.client('s3')
        bucket_name = 'newniv-bucket'

        files = list_files(s3_client, bucket_name, 'processed_data/')
        if not files:
            return Response({'error': 'No files found in S3 bucket.'}, status=404)

        latest_file_key = files[-1]
        local_path = "/tmp/latest_file.xlsx"
        s3_client.download_file(bucket_name, latest_file_key, local_path)

        df = pd.read_excel(local_path)

        # MCAの実行
        n_components = min(df.shape) - 1  # use min(rows, columns) - 1 for MCA
        mca = prince.MCA(n_components=n_components)
        mca_result = mca.fit(df)

        # S3への処理後のデータアップロード
        mca_result_df = pd.DataFrame(
            data=mca_result.row_coordinates(df),
            columns=[f'MC{i}' for i in range(1, n_components+1)]
        )
        mca_result_df.to_excel("/tmp/mca_result.xlsx", index=False)
        s3_client.upload_file(
            "/tmp/mca_result.xlsx", bucket_name, "Multiple_correspondence_analysis/mca_result.xlsx")

        # Scree plot (explained variance by component)
        ax = mca.plot_row_coordinates(
            df, figsize=(10, 6), show_row_points=True, show_row_labels=False, show_column_points=True, show_column_labels=True)
        ax.get_figure().savefig("/tmp/mca_scree_plot.png")

        # Cloudinaryへの処理後のイメージアップロード
        cloudinary.config(
            cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
            api_key=os.environ.get('CLOUDINARY_API_KEY'),
            api_secret=os.environ.get('CLOUDINARY_API_SECRET')
        )

        upload_response = cloudinary.uploader.upload(
            "/tmp/mca_scree_plot.png",
            folder="Multiple_correspondence_analysis",
            use_filename=True,
            unique_filename=False
        )

        # 最後にフロントにurlを返す
        return Response({"graph_url": upload_response['url']}, status=200)


# FUVのエクセルファイルアップロード


@csrf_exempt
def FUVUpload_file(request):
    if request.method == 'POST':
        try:
            print("Access Key:", os.environ.get('AWS_ACCESS_KEY_ID'))
            print("Secret Key:", os.environ.get('AWS_SECRET_ACCESS_KEY'))

            data = json.loads(request.body.decode('utf-8'))

            file_name = f"{uuid.uuid4()}.xlsx"

            workbook = openpyxl.Workbook()
            sheet = workbook.active
            for index, row in enumerate(data):
                for key, value in row.items():
                    if index == 0:
                        header_col = sheet.cell(
                            row=1, column=list(row.keys()).index(key) + 1)
                        header_col.value = key

                    cell = sheet.cell(
                        row=index + 2, column=list(row.keys()).index(key) + 1)
                    cell.value = value

            with open(file_name, 'wb') as f:
                workbook.save(f)

            s3_path = f"fuv/upload/{file_name}"

            s3_client = boto3.client('s3', aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                                     aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))

            existing_files = list_files(
                s3_client, settings.AWS_STORAGE_BUCKET_NAME, 'fuv/upload/')
            for file_key in existing_files:
                s3_client.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file_key)

            s3_client.upload_file(
                file_name, settings.AWS_STORAGE_BUCKET_NAME, s3_path)

            os.remove(file_name)

            file_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{s3_path}"

            return JsonResponse({'message': 'Data processed and saved to S3 successfully!', 'file_url': file_url})
        except json.JSONDecodeError:
            return JsonResponse({'message': 'Failed to decode JSON data.'}, status=400)

    return JsonResponse({'message': 'Only POST requests are allowed.'})


@csrf_exempt
def smooth_data(data, window_length=5, polyorder=2):
    """
    Smooth the data using Savitzky-Golay filter.

    Parameters:
    - data: The data to be smoothed
    - window_length: The length of the filter window (must be an odd integer)
    - polyorder: The order of the polynomial used to fit the samples

    Returns:
    - smoothed_data: The smoothed data
    """
    return savgol_filter(data, window_length, polyorder)


@csrf_exempt
def kk_transform(absorption, wavelength, n_inf, incident_angle, np_value):
    """
    Perform the KK transformation.

    Parameters:
    - absorption: The absorption spectrum
    - wavelength: The wavelength values corresponding to the absorption spectrum
    - n_inf: Refractive index at infinite wavelength (or the refractive index of the sample)
    - incident_angle: Incident angle in degrees

    Returns:
    - phase: The phase spectrum obtained from the KK transformation
    """

    # Compute k (absorption coefficient) from absorption
    k = absorption / (4 * np.pi * wavelength)

    # Conversion of the wavelength from nm to cm
    wavenumber = 1e7 / wavelength

    # Convert incident_angle from degrees to radians
    theta = np.radians(incident_angle)

    # (5)式に基づいて位相スペクトルを計算します
    integral_phi = np.array([
        simps((np.log(np.sqrt(np.maximum(absorption, 1e-10))) /
              np.maximum(wavenumber[i] - wavenumber, 1e-10)), wavenumber)
        for i in range(len(wavenumber))
    ])
    inside_sqrt = np_value * np_value * \
        np.sin(theta)**2 - np.maximum(n_inf**2, 1e-10)
    phi = 2 * np.arctan(
        np.sqrt(np.maximum(inside_sqrt, 0)) /
        np.maximum(np_value * np_value * np.cos(theta), 1e-10)
    ) + (2 * wavenumber / np.pi) * integral_phi

    # Safe computation for r
    numerator = np.sqrt(np.maximum(absorption, 1e-10))
    denominator = np.maximum(1 + np.exp(1j * phi), 1e-10)
    r = numerator / denominator

    # (8) and (9)式に基づいて屈折率の実部nと虚部κを計算します
    inside_sqrt_2 = np.sin(theta)**2 + np.maximum(1 - r, 1e-10) / \
        np.maximum(1 + r, 1e-10)**2 * np.cos(theta)**2
    sqrt_value = np.sqrt(np.maximum(inside_sqrt_2, 0))
    n = np_value * np.real(sqrt_value)
    kappa = -np_value * np.imag(sqrt_value)

    # (10)式に基づいて吸収係数を計算します
    alpha = (4 * np.pi * kappa) / wavelength

    return phi, r, n, kappa, alpha


@csrf_exempt
def kk_transformed_spectrum(request):
    # S3クライアントの初期化
    s3_client = boto3.client('s3', aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                             aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    # 最新のファイルをS3バケットから取得
    files = list_files(s3_client, bucket_name, 'fuv/upload')
    if not files:
        return HttpResponse('No files found in S3 bucket.')

    latest_uploaded_file = sorted(files)[-1]

    # Excelファイルをデータフレームとして読み込む
    obj = s3_client.get_object(Bucket=bucket_name, Key=latest_uploaded_file)
    df = pd.read_excel(BytesIO(obj['Body'].read()))

    wavelength = df["波長"].values
    data = json.loads(request.body.decode("utf-8"))

    # Reactからのデータを抽出
    n_inf = float(data['n_inf'])
    incident_angle = float(data['incident_angle'])
    np_value = float(data['np'])

    concentration_columns = [col for col in df.columns if col.endswith("M")]
    for conc in concentration_columns:
        absorbance = df[conc].values
        smoothed_absorbance = smooth_data(absorbance)  # Apply smoothing

        phi, _, _, _, _ = kk_transform(
            smoothed_absorbance, wavelength, n_inf, incident_angle, np_value)

        if len(phi) != len(df):
            return HttpResponse('Length mismatch between phase data and DataFrame.')

        df[f"{conc}_phase"] = phi

    # 変換されたデータをS3に保存
    excel_io = io.BytesIO()
    df.to_excel(excel_io, index=False)
    excel_io.seek(0)
    s3_client.upload_fileobj(excel_io, bucket_name,
                             'fuv/kk/kk_transformed.xlsx')

    return HttpResponse('KK transformed data uploaded to S3 successfully.')
