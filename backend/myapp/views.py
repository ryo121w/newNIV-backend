import json
import os
import uuid
import openpyxl
import boto3
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from rest_framework.views import APIView
from io import BytesIO
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np


def list_files(s3_client, bucket, prefix):
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    if 'Contents' in response:
        return [content['Key'] for content in response['Contents']]
    return []


@csrf_exempt
def upload_file(request):

    if request.method == 'POST':
        try:
            print("Access Key:", os.environ.get('AWS_ACCESS_KEY_ID'))
            print("Secret Key:", os.environ.get('AWS_SECRET_ACCESS_KEY'))
            # request.bodyからJSONデータを読み取ります
            data = json.loads(request.body.decode('utf-8'))

            # 保存するファイル名を決定します
            file_name = f"{uuid.uuid4()}.xlsx"

            # JSONデータをエクセルファイルに変換します
            workbook = openpyxl.Workbook()
            sheet = workbook.active
            for index, row in enumerate(data):
                for key, value in row.items():
                    if index == 0:
                        # ヘッダを追加します
                        header_col = sheet.cell(
                            row=1, column=list(row.keys()).index(key) + 1)
                        header_col.value = key

                    cell = sheet.cell(
                        row=index + 2, column=list(row.keys()).index(key) + 1)
                    cell.value = value

            # エクセルファイルを一時的なバイナリストリームとして保存します
            with open(file_name, 'wb') as f:
                workbook.save(f)

            # S3の「フォルダ」にアップロードするためのパスを指定します
            s3_path = f"uploads/excel/{file_name}"

            # S3にアップロードします
            s3_client = boto3.client('s3', aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                                     aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))

            # 既存のファイルをすべて削除します
            existing_files = list_files(
                s3_client, settings.AWS_STORAGE_BUCKET_NAME, 'uploads/excel/')
            for file_key in existing_files:
                s3_client.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file_key)

            s3_client.upload_file(
                file_name, settings.AWS_STORAGE_BUCKET_NAME, s3_path)

            # 一時ファイルを削除します
            os.remove(file_name)

            return JsonResponse({'message': 'Data processed and saved to S3 successfully!'})
        except json.JSONDecodeError:
            return JsonResponse({'message': 'Failed to decode JSON data.'}, status=400)

    return JsonResponse({'message': 'Only POST requests are allowed.'})


def generate_spectrum_graph(request):
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

    # Concentrationsの部分が前のコードから不足していたので、以下の仮のコードを追加します
    # もしrequestからconcentrationsを取得する必要がある場合、適切に修正してください
    concentrations = None  # 仮のコード

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

    # PNGファイルとして保存
    graph_filename = 'nir_spectrum.png'
    graph_dir = 'static/graphs'  # "graphs"サブディレクトリも指定しています
    graph_filepath = os.path.join(graph_dir, graph_filename)

    if not os.path.exists(graph_dir):
        os.makedirs(graph_dir)

    plt.savefig(graph_filepath)
    plt.close()  # リソースの解放

    return HttpResponse(f'/static/{graph_filename}')
