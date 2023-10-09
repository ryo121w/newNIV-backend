import json
import os
import uuid
import openpyxl
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from rest_framework.views import APIView
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np


@csrf_exempt
def upload_file(request):
    if request.method == 'POST':
        # Ensure the directory exists
        dir_path = 'uploaded_files'
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        else:
            # Remove all files inside the directory
            for file_name in os.listdir(dir_path):
                file_path = os.path.join(dir_path, file_name)
                if os.path.isfile(file_path):
                    os.remove(file_path)

        try:
            # request.bodyからJSONデータを読み取ります
            data = json.loads(request.body.decode('utf-8'))

            # 保存するファイル名を決定します
            # 元のファイル名を取得できるようにフロントエンドを調整するとよいですが、
            # ここではデモのため一意の名前を生成します
            file_name = f"{uuid.uuid4()}.xlsx"
            save_path = os.path.join(dir_path, file_name)

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

            # エクセルファイルを保存します
            workbook.save(save_path)

            return JsonResponse({'message': 'Data processed and saved successfully!'})
        except json.JSONDecodeError:
            return JsonResponse({'message': 'Failed to decode JSON data.'}, status=400)

    return JsonResponse({'message': 'Only POST requests are allowed.'})


def generate_spectrum_graph(request):
    # uploaded_filesディレクトリ内のファイルを取得
    uploaded_file_path = os.path.join(
        'uploaded_files', os.listdir('uploaded_files')[0])

    # Excelファイルを読み込む
    df = pd.read_excel(uploaded_file_path)
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

    # PNGファイルとして保存
    graph_dir_abs = os.path.join(settings.BASE_DIR, graph_dir)
    graph_filepath_abs = os.path.join(settings.BASE_DIR, graph_filepath)

    if not os.path.exists(graph_dir_abs):
        os.makedirs(graph_dir_abs)

    plt.savefig(graph_filepath_abs)
    plt.close()

    # 静的ファイルのURLを正しく構築
    graph_url = reverse('django.views.static.serve',
                        kwargs={'path': graph_filepath})
    return HttpResponse(graph_url)
