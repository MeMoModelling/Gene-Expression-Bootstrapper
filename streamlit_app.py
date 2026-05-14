import streamlit as st
import pandas as pd
import os
import sys
import traceback
import tempfile
import io
import contextlib
import zipfile

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# ==========================================
# CUSTOM EXCEPTIONS
# ==========================================
class FileInputError(Exception): pass
class DataValidationError(Exception): pass
class EmptyOutputError(Exception): pass

_ALL = (FileInputError, DataValidationError, EmptyOutputError, MemoryError, OSError)

# ==========================================
# HELPERS
# ==========================================
def record_error(e):
    st.session_state["error"] = {
        "message": str(e),
        "traceback": traceback.format_exc(),
    }

def clear_error():
    st.session_state.pop("error", None)

def display_error():
    err = st.session_state.get("error")
    if not err: return
    st.error(f"**Error:** {err['message']}")
    with st.expander("Full traceback"):
        st.code(err["traceback"], language="python")

def validate_ext(f, exts, label):
    if f is None: return
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in exts:
        raise FileInputError(f"'{f.name}' — expected {', '.join(exts)}, got '{ext}'.")

def validate_not_empty(df, label):
    if df.empty:
        raise DataValidationError(f"'{label}' contains no data rows.")

def write_b(name, data, d):
    path = os.path.join(d, name)
    with open(path, "wb") as f: f.write(data)
    return path

def write_up(f, d):
    path = os.path.join(d, f.name)
    with open(path, "wb") as fout: fout.write(f.getbuffer())
    return path

def schema_expander(title, columns, notes=""):
    with st.expander(f"ℹ️ **Expected format: {title}**"):
        rows = [{"Column": f"`{c['name']}`", "Type": c["type"],
                 "Required": "Yes" if c["required"] else "Optional",
                 "Description": c["description"]} for c in columns]
        st.table(pd.DataFrame(rows))
        if notes: st.caption(notes)

# ==========================================
# APP CONFIG
# ==========================================
st.set_page_config(page_title="Gene Expression Bootstrapping", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 16px !important;
}
.main .block-container {
    padding: 2.5rem 3.5rem 4rem 3.5rem !important;
    max-width: 1080px !important;
}
h1 {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 2.2rem !important;
    font-weight: 700 !important;
    letter-spacing: -1px !important;
    border: none !important;
    margin-bottom: 0.2rem !important;
}
h2, h3 {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: -0.5px !important;
}
.stButton > button[kind="primary"] {
    background: #006d5b !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 4px !important;
    padding: 0.6rem 1.8rem !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    font-family: 'DM Sans', sans-serif !important;
}
.stButton > button[kind="primary"]:hover { background: #005548 !important; }
.stButton > button:not([kind="primary"]) {
    border-radius: 4px !important;
    font-size: 14px !important;
    font-family: 'DM Sans', sans-serif !important;
}
.stDownloadButton > button {
    border-radius: 4px !important;
    font-size: 14px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
}
[data-testid="stFileUploader"] {
    border-radius: 6px !important;
    padding: 0.4rem !important;
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {
    font-family: 'DM Sans', sans-serif !important;
    border-radius: 4px !important;
}
[data-testid="stExpander"] {
    border-radius: 6px !important;
}
[data-testid="stAlert"] {
    border-radius: 6px !important;
    font-family: 'DM Sans', sans-serif !important;
}
code, pre {
    font-family: 'DM Mono', monospace !important;
    font-size: 13px !important;
    border-radius: 6px !important;
}
hr { margin: 1.5rem 0 !important; }
.stSpinner > div { border-top-color: #006d5b !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# SESSION STATE
# ==========================================
for k, v in [("result_zip", None), ("log_lines", [])]:
    if k not in st.session_state:
        st.session_state[k] = v

# ==========================================
# MAIN
# ==========================================
st.title("Gene Expression Bootstrapping")
st.markdown(
    "Imputes expression values for unmapped and unknown genes using bootstrapping. "
    "Output files serve as the geneExpr folder input for FEA."
)

st.markdown("---")

# ── Inputs ──
st.markdown("### Upload input files")

col1, col2 = st.columns(2)

with col1:
    schema_expander("Prefixed Models (.xlsx)", [
        {"name": "Reactions sheet", "type": "sheet", "required": True,
         "description": "Must contain 'system' and 'genes' columns. Output of Step 5 (Community Assembly) of the pipeline — the species-prefixed model files, not combined_graph.xlsx."},
    ], notes="One file per species in the same order as your mapping files. e.g. LC_model.xlsx, LLm1_model.xlsx")
    model_files = st.file_uploader(
        "model",
        accept_multiple_files=True,
        key="model_upload",
        label_visibility="collapsed"
    )

with col2:
    schema_expander("Identifier Mappings (.xlsx)", [
        {"name": "Model sheet", "type": "sheet", "required": True,
         "description": "Must contain 'model_tag', 'gene_id', and 'has_mapping' columns. Output of Step 3 (Gene to Genome Annotation) of the pipeline."},
    ], notes="One file per species in the same order as the model files. e.g. LC_mapping.xlsx, LLm1_mapping.xlsx")
    mapping_files = st.file_uploader(
        "mapping",
        accept_multiple_files=True,
        key="mapping_upload",
        label_visibility="collapsed"
    )

schema_expander("Gene Expression CSV (combined_geneExpr.csv)", [
    {"name": "index (first col)", "type": "string", "required": True,
     "description": "Gene IDs matching those in the identifier mapping files (e.g. 'gene-QMZ85_RS00005')."},
    {"name": "sample columns",    "type": "float",  "required": True,
     "description": "One column per sample (e.g. 'mLC-1', 'mLC-2'). Values are normalised expression counts."},
], notes="Combined across all species and all samples. Row index is gene ID.")
gene_expr_file = st.file_uploader(
    "geneexpr",
    key="geneexpr_upload",
    label_visibility="collapsed"
)

st.markdown("---")

# ── Settings ──
st.markdown("### Settings")
batch_count = st.number_input(
    "Number of bootstrap batches",
    min_value=1,
    max_value=10000,
    value=1000,
    step=100,
    help="Number of bootstrap iterations. Each produces one output CSV file. Default is 1000."
)

st.markdown("---")

# ── Run ──
if st.button("▶ Run Bootstrapping", type="primary"):
    if not model_files or not mapping_files or not gene_expr_file:
        st.warning("Please upload all required files.")
    elif len(model_files) != len(mapping_files):
        st.error("Number of model files must match number of mapping files.")
    else:
        clear_error()
        st.session_state["result_zip"] = None
        st.session_state["log_lines"] = []
        try:
            try:
                from utils.bootstrap_genes import bootstrap_genes
            except ImportError as e:
                raise RuntimeError(
                    f"Could not import bootstrap_genes: {e}. "
                    f"Ensure utils/bootstrap_genes.py is present."
                )

            # Validate file extensions
            for f in model_files:
                validate_ext(f, [".xlsx"], "Prefixed Models")
            for f in mapping_files:
                validate_ext(f, [".xlsx"], "Identifier Mappings")
            validate_ext(gene_expr_file, [".csv"], "Gene Expression CSV")

            # Validate gene expression CSV
            try:
                gene_expr_df = pd.read_csv(gene_expr_file, index_col=0)
            except Exception as e:
                raise FileInputError(f"Could not read '{gene_expr_file.name}': {e}") from e
            validate_not_empty(gene_expr_df, gene_expr_file.name)

            # Derive species prefixes from model filenames
            species_prefixes = [os.path.splitext(f.name)[0].split("_")[0] for f in model_files]

            log_lines = []

            with st.spinner(f"Bootstrapping {batch_count} batches — this may take several minutes…"), \
                 tempfile.TemporaryDirectory() as tmp:

                # Write all files to temp
                m_paths  = [write_b(f.name, f.getbuffer(), tmp) for f in model_files]
                mp_paths = [write_b(f.name, f.getbuffer(), tmp) for f in mapping_files]
                ge_path  = write_b(gene_expr_file.name, gene_expr_file.getbuffer(), tmp)
                out_dir  = os.path.join(tmp, "geneExpr_output")
                os.makedirs(out_dir)

                # Run bootstrapping
                cap = io.StringIO()
                with contextlib.redirect_stdout(cap):
                    bootstrap_genes(
                        model_pre_filenames=m_paths,
                        mapping_filenames=mp_paths,
                        species_prefixes=species_prefixes,
                        combined_geneExpr_filename=ge_path,
                        geneExpr_folder=out_dir,
                        batch_count=int(batch_count),
                    )
                log_lines = cap.getvalue().splitlines()

                # Validate output
                output_files = sorted([
                    f for f in os.listdir(out_dir) if f.startswith("geneExpr_") and f.endswith(".csv")
                ])
                if not output_files:
                    raise EmptyOutputError("Bootstrapping completed but no output files were generated.")

                # Build ZIP in memory before tmpdir closes
                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for fname in output_files:
                        zf.write(os.path.join(out_dir, fname), arcname=fname)
                zip_bytes = zip_buf.getvalue()

            st.session_state["result_zip"] = zip_bytes
            st.session_state["log_lines"] = log_lines

        except _ALL as e:
            record_error(e)
        except Exception as e:
            record_error(e)

# ── Results ──
if st.session_state["result_zip"]:
    st.success(f"✅ Bootstrapping complete. {batch_count} output files generated.")

    st.download_button(
        label=f"⬇️ Download all files (geneExpr_bootstrapped.zip)",
        data=st.session_state["result_zip"],
        file_name="geneExpr_bootstrapped.zip",
        mime="application/zip",
        key="dl_zip"
    )

    if st.session_state["log_lines"]:
        with st.expander("View processing log"):
            st.text("\n".join(st.session_state["log_lines"]))

display_error()
