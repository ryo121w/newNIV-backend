import json
import os
import uuid
import openpyxl
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse


@csrf_exempt
def upload_file(request):
    if request.method == 'POST':
        # Ensure the directory exists
        if not os.path.exists('uploaded_files'):
            os.makedirs('uploaded_files')
        try:
            # request.bodyからJSONデータを読み取ります
            data = json.loads(request.body.decode('utf-8'))

            # 保存するファイル名を決定します
            # 元のファイル名を取得できるようにフロントエンドを調整するとよいですが、
            # ここではデモのため一意の名前を生成します
            file_name = f"{uuid.uuid4()}.xlsx"
            save_path = os.path.join('uploaded_files', file_name)

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
