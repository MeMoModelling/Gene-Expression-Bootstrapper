import os
import pandas as pd
import re
import sys

def write_to_excel(output_filename, dfs_towrite, index = False, col_width=22):
    with pd.ExcelWriter(output_filename) as writer:
        for name, df in dfs_towrite.items():
            df.to_excel(writer, sheet_name = name, index = index)
            num_col = len(df.columns) if index else len(df.columns)-1
            writer.sheets[name].set_column(0, num_col, col_width)
    print("Write to", output_filename)

def read_model_excel(model_excel_filename, sheet_name):
    if not os.path.isfile(model_excel_filename):
        raise FileNotFoundError(f"Missing model excel file, expected at {model_excel_filename}")
    if sheet_name not in pd.ExcelFile(model_excel_filename).sheet_names:
        raise ValueError(f"{sheet_name} are expected to be in the parsed model excel file - {model_excel_filename}")
    sheet_df = pd.read_excel(model_excel_filename, sheet_name=sheet_name)
    sheet_df = sheet_df.fillna("")
    return sheet_df

def read_mapping(mapping_filename):
    if not os.path.isfile(mapping_filename):
        raise FileNotFoundError(f"Missing mapping file, expected at {mapping_filename}")

    mapping_df = pd.read_excel(mapping_filename)
    mapping_df = mapping_df[mapping_df["has_mapping"] == True]

    mapping_dict = dict(zip(mapping_df["model_tag"], mapping_df["gene_id"]))
    return mapping_dict