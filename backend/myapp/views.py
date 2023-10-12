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
import io
from io import BytesIO
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
import cloudinary
import cloudinary.uploader
import cloudinary.api

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
    plt.ylim(0, 1.6)

    concentrations = None
    concentrations_columns = concentrations if concentrations else list(
        df.columns[1:])
    colors = cm.rainbow(np.linspace(0, 0.5, len(concentrations_columns)))

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


def list_files(s3_client, bucket_name, prefix):
    # バケットから特定のプレフィックスを持つオブジェクトのリストを取得
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    return [content['Key'] for content in response.get('Contents', [])]


class ConcentrationGraphView(APIView):
    parser_classes = (MultiPartParser,)

    def post(self, request):
        print(f"Debug: Received POST data: {request.data}")
        concentrations = request.data.getlist('concentrations[]', [])
        print(f"Debug: Received concentrations: {concentrations}")

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
        plt.ylim(0, 0.03)

        colors = cm.rainbow(np.linspace(0, 0.5, len(columns)))

        for i, (column, color) in enumerate(zip(columns, colors)):
            df[column] = df[column] / float(concentrations[i])
            plt.plot(df['波長'], df[column],
                     label=f'{column} - {concentrations[i]}M', color=color)

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
