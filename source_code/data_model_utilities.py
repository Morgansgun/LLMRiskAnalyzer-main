import csv

def convert_csv_to_json(csv_file_path):
    fmea_data = {
        "table": {
            "header": [],
            "rows": []
        }
    }

    with open(csv_file_path, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        headers = next(reader)  
        fmea_data["table"]["header"] = headers

        for row in reader:
            details_list = [[{"content": "", "reason": "", "comment": ""}] for _ in range(14)]  # Additional empty entries

          
            fmea_data["table"]["rows"].append({
                "data": row,  
                "details": details_list
            })


    return fmea_data


def convert_json_to_csv_text(json_data):
    # Extract headers and rows from JSON data
    header = json_data['table']['header']
    rows = json_data['table']['rows']
    text_header = ""+str(header)
    rows= [row['data'] for row in rows]
    text_rows = "\n".join([str(row) for row in rows])
    text = text_header + "\n"+ text_rows
    return text



def add_new_row_to_fmea_data(fmea_data, row_id=""):
    
    fmea_data["table"]["rows"].append({
        "data": [row_id, '', '', '', '', '', '', '', '', '','', '', '', ''],  # Add row ID if not included in CSV
        "details": [[{"content": "", "reason": "", "comment": ""}]for _ in range(14)]
    })
    return fmea_data




if __name__ == "__main__":
    pass

