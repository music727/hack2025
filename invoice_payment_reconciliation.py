import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
import io
import difflib

st.set_page_config(page_title="D365 Finance - Invoice/Payment Reconciliation", layout="wide")




import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
import io
import difflib

st.set_page_config(page_title="D365 Finance - Invoice/Payment Reconciliation", layout="wide")

st.markdown(
    "<h1 style='color:#2564cf; font-size:2.5rem; font-weight:700;'>Dynamics 365 Finance: Invoice & Payment Reconciliation</h1>",
    unsafe_allow_html=True
)

# Session state for tab navigation
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = 0

tabs = ["Step 1: Data Load", "Step 2: Mapping", "Step 3: Preview", "Step 4: Results"]
tab_objs = st.tabs(tabs)

# Step 1: Data Load
with tab_objs[0]:
    st.header("Step 1: Upload Your Data")
    st.write("Upload your payment data (from D365 or your system) and the vendor invoice statement to match.")
    st.markdown('<span style="color:green;font-weight:bold;">Payment Data (CSV)</span>', unsafe_allow_html=True)
    payment_file = st.file_uploader("Upload Payment CSV", type=["csv"], key="pay")
    st.markdown('<span style="color:green;font-weight:bold;">Statement from Vendor (CSV)</span>', unsafe_allow_html=True)
    invoice_file = st.file_uploader("Upload Statement from Vendor (CSV)", type=["csv"], key="inv")
    if payment_file:
        st.success("Payment file uploaded.")
    if invoice_file:
        st.success("Statement from Vendor uploaded.")
    # Next button removed as requested

# Step 2: Mapping
with tab_objs[1]:
    if not ("pay" in st.session_state and "inv" in st.session_state):
        st.info("Please upload both files in Step 1.")
    elif not (payment_file and invoice_file):
        st.info("Please upload both files in Step 1.")
    else:
        # --- Data Cleaning Step ---
        def clean_df(df):
            df.columns = [str(col).strip().lower() for col in df.columns]
            def clean_val(x):
                if pd.isnull(x):
                    return x
                s = str(x).strip()
                if s.isdigit():
                    s = s.lstrip('0') or '0'
                return s
            df = df.applymap(clean_val)
            df = df.dropna(axis=1, how='all')
            df = df.dropna(axis=0, how='all')
            return df
        invoice_file.seek(0)
        raw_invoice = invoice_file.read().decode(errors='ignore')
        cleaned_lines = []
        for line in raw_invoice.splitlines():
            parts = [p.lstrip(' 0').rstrip() for p in line.split(',')]
            cleaned_lines.append(','.join(parts))
        cleaned_invoice_str = '\n'.join(cleaned_lines)
        import io as _io
        invoice_file_obj = _io.StringIO(cleaned_invoice_str)
        delimiter = st.selectbox("Select CSV delimiter for invoice file", [',', ';', '|', '\t'], index=0, help="If your file doesn't load correctly, try a different delimiter.")
        try:
            invoice_file_obj.seek(0)
            invoices = pd.read_csv(invoice_file_obj, dtype=str, delimiter=delimiter).fillna("")
            invoices = clean_df(invoices)
            if invoices.empty or len(invoices.columns) == 0:
                st.error("The uploaded invoice file is empty or has no columns. Please upload a valid CSV with headers and data.")
                st.stop()
        except Exception as e:
            st.error(f"Could not read the uploaded invoice file: {e}")
            st.stop()
        try:
            payment_file.seek(0)
            payments = pd.read_csv(payment_file, dtype=str).fillna("")
            payments = clean_df(payments)
            if payments.empty or len(payments.columns) == 0:
                st.error("The uploaded payment file is empty or has no columns. Please upload a valid CSV with headers and data.")
                st.stop()
        except Exception as e:
            st.error(f"Could not read the uploaded payment file: {e}")
            st.stop()
        st.header("Step 2: Map Columns (Auto-Suggested, Editable)")
        st.write("Below are the standard fields used for reconciliation. Review the suggested mappings and adjust as needed. At minimum, map the invoice number field for both files.")
        standard_fields = ["invoice number", "order id", "vendor", "amount", "currency", "date", "balance"]
        # Smarter auto-suggestion logic
        def suggest_mapping(columns, standard_fields):
            mapping = {}
            synonyms = {
                "invoice number": ["invoice number", "inv number", "inv no", "number", "invnum", "invoice"],
                "order id": ["order id", "purchase order", "purchase order id", "po number", "po", "order", "comments"],
                "vendor": ["vendor", "vendor account", "account", "vendor id", "supplier", "supplier name"],
                "amount": ["amount", "invoice amount", "payment amount", "amt", "total", "paid amount"],
                "currency": ["currency", "currency code", "curr", "curr code"],
                "date": ["date", "invoice date", "payment date", "trans date"],
                "balance": ["balance", "remaining", "outstanding", "open amount"]
            }
            for field in standard_fields:
                if field == "invoice number":
                    # Only match 'Invoice' (not Invoice Account), then 'Document Number', never Invoice Account
                    invoice_exact = [c for c in columns if c.strip().lower() == "invoice"]
                    if invoice_exact:
                        mapping[field] = invoice_exact[0]
                        continue
                    doc_number = [c for c in columns if c.strip().lower() == "document number"]
                    if doc_number:
                        mapping[field] = doc_number[0]
                        continue
                    # fallback: any column with 'invoice' in name but not 'account'
                    invoice_like = [c for c in columns if "invoice" in c.lower() and "account" not in c.lower()]
                    if invoice_like:
                        mapping[field] = invoice_like[0]
                        continue
                    mapping[field] = "(none)"
                    continue
                candidates = [c for c in columns if any(s in c.lower() for s in synonyms.get(field, []))]
                # Special logic for order id in comments
                if field == "order id" and not candidates:
                    candidates = [c for c in columns if "comment" in c.lower()]
                if candidates:
                    mapping[field] = candidates[0]
                else:
                    # fallback to fuzzy match
                    matches = difflib.get_close_matches(field.replace(' ',''), [c.replace(' ','').lower() for c in columns], n=1, cutoff=0.7)
                    if matches:
                        for c in columns:
                            if c.replace(' ','').lower() == matches[0]:
                                mapping[field] = c
                                break
                    else:
                        mapping[field] = "(none)"
            return mapping
        invoice_suggested = suggest_mapping(list(invoices.columns), standard_fields)
        payment_suggested = suggest_mapping(list(payments.columns), standard_fields)
        invoice_col_map = {}
        payment_col_map = {}
        mapping_rows = []


        field_help = {
            "invoice number": "Unique identifier for each invoice. Required for matching.",
            "order id": "Order reference, e.g. purchase order number.",
            "vendor": "Supplier or vendor name.",
            "amount": "Invoice/payment amount.",
            "currency": "Currency code (e.g., USD, EUR).",
            "date": "Invoice or payment date.",
            "balance": "Remaining balance, if tracked."
        }
        st.markdown("<div style='background:#222;padding:0.5em 1em;border-radius:8px;font-weight:bold;margin-bottom:0.5em;'>Map each standard field to the appropriate column in your files. <span style='color:#d13438;'>*</span> Required fields.</div>", unsafe_allow_html=True)
        # Show file names only once at the top of the mapping columns
        mapping_cols = st.columns([2, 4, 4])
        with mapping_cols[0]:
            st.markdown("<span style='font-weight:bold;'>&nbsp;</span>", unsafe_allow_html=True)
        with mapping_cols[1]:
            st.markdown(f"<span style='color:#2564cf;font-size:0.95em;font-weight:bold;'>Statement from Vendor: {invoice_file.name if invoice_file else ''}</span>", unsafe_allow_html=True)
        with mapping_cols[2]:
            st.markdown(f"<span style='color:#43a047;font-size:0.95em;font-weight:bold;'>Payment Data: {payment_file.name if payment_file else ''}</span>", unsafe_allow_html=True)

        for i, field in enumerate(standard_fields):
            with st.container():
                row_cols = st.columns([2, 4, 4])
                with row_cols[0]:
                    st.markdown(f"<span style='font-weight:bold;'>{field.title()}</span>" + (" <span style='color:#d13438;'>*</span>" if field == "invoice number" else ""), unsafe_allow_html=True)
                    if field in field_help:
                        st.caption(field_help[field])
                with row_cols[1]:
                    inv_options = ["(none)"] + list(invoices.columns)
                    invoice_col = st.selectbox(
                        " ",
                        options=inv_options,
                        index=inv_options.index(invoice_suggested[field]) if invoice_suggested[field] in inv_options else 0,
                        key=f"inv_{field}_{i}"
                    )
                with row_cols[2]:
                    pay_options = ["(none)"] + list(payments.columns)
                    payment_col = st.selectbox(
                        "  ",
                        options=pay_options,
                        index=pay_options.index(payment_suggested[field]) if payment_suggested[field] in pay_options else 0,
                        key=f"pay_{field}_{i}"
                    )
                invoice_col_map[field] = invoice_col
                payment_col_map[field] = payment_col
                mapping_rows.append({"Standard Field": field, "Invoice Column": invoice_col, "Payment Column": payment_col})
                st.markdown("<hr style='margin:0.5em 0;'>", unsafe_allow_html=True)
        # Next button removed as requested

# Step 3: Preview
with tab_objs[2]:
    if not ("pay" in st.session_state and "inv" in st.session_state):
        st.info("Please complete Steps 1 and 2.")
    elif not (payment_file and invoice_file):
        st.info("Please complete Steps 1 and 2.")
    else:
        # Use the same cleaned data and mappings from Step 2
        mapped_invoice_cols = list(dict.fromkeys([row["Invoice Column"] for row in mapping_rows if row["Invoice Column"] != "(none)"]))
        mapped_payment_cols = list(dict.fromkeys([row["Payment Column"] for row in mapping_rows if row["Payment Column"] != "(none)"]))
        st.header("Step 3: Preview Cleaned & Mapped Data")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(":blue[Invoice Data Preview]")
            if mapped_invoice_cols:
                st.dataframe(invoices[mapped_invoice_cols].head(10), use_container_width=True)
        with col2:
            st.subheader(":green[Payment Data Preview]")
            if mapped_payment_cols:
                st.dataframe(payments[mapped_payment_cols].head(10), use_container_width=True)
        # Next button removed as requested

# Step 4: Results
with tab_objs[3]:
    # Only show results, not other steps
    if not ("pay" in st.session_state and "inv" in st.session_state):
        st.info("Please complete all previous steps.")
    elif not (payment_file and invoice_file):
        st.info("Please complete all previous steps.")
    else:
        # Use the same cleaned data and mappings from Step 2
        inv_num_col = invoice_col_map["invoice number"]
        pay_num_col = payment_col_map["invoice number"]
        inv_amt_col = invoice_col_map["amount"]
        pay_amt_col = payment_col_map["amount"]
        inv_bal_col = invoice_col_map["balance"] if "balance" in invoice_col_map else None
        pay_bal_col = payment_col_map["balance"] if "balance" in payment_col_map else None
        pay_lookup = {str(row[pay_num_col]).strip(): row for _, row in payments.iterrows() if pay_num_col != "(none)"}
        results = []
        for _, inv_row in invoices.iterrows():
            inv_num = str(inv_row[inv_num_col]).strip() if inv_num_col != "(none)" else ""
            pay_row = pay_lookup.get(inv_num, None)
            invoice_amt = None
            try:
                if inv_amt_col != "(none)" and inv_row[inv_amt_col] not in [None, ""]:
                    invoice_amt = float(str(inv_row[inv_amt_col]).replace(',', ''))
            except Exception:
                invoice_amt = None
            payment_amt = None
            if pay_row is not None and pay_amt_col != "(none)" and pay_row[pay_amt_col] not in [None, ""]:
                try:
                    payment_amt = float(str(pay_row[pay_amt_col]).replace(',', ''))
                except Exception:
                    payment_amt = None
            paid_amt = None
            if inv_bal_col and inv_bal_col != "(none)" and inv_row[inv_bal_col] not in [None, ""] and invoice_amt is not None:
                try:
                    paid_amt = invoice_amt - float(str(inv_row[inv_bal_col]).replace(',', ''))
                except Exception:
                    paid_amt = None
            if pay_row is None:
                status = "No Match"
                status_color = "red"
                details = "No payment found for this invoice."
            elif invoice_amt is not None and payment_amt is not None:
                if abs(invoice_amt - payment_amt) < 0.01:
                    status = "Exact Match"
                    status_color = "green"
                    details = "Invoice and payment amounts match."
                elif paid_amt is not None and abs(paid_amt - payment_amt) < 0.01:
                    status = "Partial Payment"
                    status_color = "orange"
                    details = f"Invoice partially paid. Paid: {paid_amt}, Outstanding: {inv_row[inv_bal_col]}"
                else:
                    status = "Amount Mismatch"
                    status_color = "orange"
                    details = f"Invoice and payment amounts differ. Invoice: {invoice_amt}, Payment: {payment_amt}"
            else:
                status = "Data Issue"
                status_color = "orange"
                details = "Could not determine payment or invoice amount."
            invoice_details = {f"Invoice: {col}": inv_row[col] for col in invoices.columns}
            payment_details = {f"Payment: {col}": pay_row[col] if pay_row is not None else "" for col in payments.columns}
            result = {
                "Invoice Number": inv_num,
                "Invoice Amount": inv_row[inv_amt_col] if inv_amt_col != "(none)" else "",
                "Payment Amount": pay_row[pay_amt_col] if pay_row is not None and pay_amt_col != "(none)" else "",
                "Status": status,
                "Status Color": status_color,
                "Details": details,
                "Invoice Details": invoice_details,
                "Payment Details": payment_details
            }
            results.append(result)
        results_df = pd.DataFrame(results)
        if results_df.empty:
            st.info("No results to display. Please check your mappings and data.")
        else:
            # Add summary statistics at the top
            n_total = len(results_df)
            n_exact = (results_df["Status"] == "Exact Match").sum()
            n_partial = (results_df["Status"] == "Partial Payment").sum()
            n_mismatch = (results_df["Status"] == "Amount Mismatch").sum()
            n_no_match = (results_df["Status"] == "No Match").sum()
            n_data_issue = (results_df["Status"] == "Data Issue").sum()
            st.markdown(f"""
                <div style='display:flex;gap:2em;margin-bottom:1em;'>
                    <div style='color:green;font-weight:bold;'>Exact Match: {n_exact}</div>
                    <div style='color:orange;font-weight:bold;'>Partial/Amount Mismatch: {n_partial + n_mismatch}</div>
                    <div style='color:red;font-weight:bold;'>No Match/Data Issue: {n_no_match + n_data_issue}</div>
                    <div style='font-weight:bold;'>Total: {n_total}</div>
                </div>
            """, unsafe_allow_html=True)

            # Download summary results CSV
            summary_csv_df = results_df[["Invoice Number", "Invoice Amount", "Payment Amount", "Status", "Details"]].copy()
            st.download_button(
                "Download Results as CSV",
                summary_csv_df.to_csv(index=False).encode('utf-8'),
                "reconciliation_results.csv",
                "text/csv",
                key="download_results_tab4"
            )
            # Download detailed results CSV (includes all columns)
            st.download_button(
                "Download Detailed Results as CSV",
                results_df.to_csv(index=False).encode('utf-8'),
                "reconciliation_detailed_results.csv",
                "text/csv",
                key="download_detailed_results_tab4"
            )
            # Filter selector
            filter_options = ["All", "Exact Match", "Partial Payment", "Amount Mismatch", "No Match", "Data Issue"]
            filter_map = {
                "All": None,
                "Exact Match": "Exact Match",
                "Partial Payment": "Partial Payment",
                "Amount Mismatch": "Amount Mismatch",
                "No Match": "No Match",
                "Data Issue": "Data Issue"
            }
            selected_filter = st.selectbox("Show results for:", filter_options, key="results_filter")
            if filter_map[selected_filter]:
                filtered_df = results_df[results_df["Status"] == filter_map[selected_filter]]
            else:
                filtered_df = results_df

            # Show colored status column
            color_map = {'green': '#4CAF50', 'orange': '#FFA500', 'red': '#F44336'}
            styled_df = filtered_df[["Invoice Number", "Invoice Amount", "Payment Amount", "Status", "Details", "Status Color"]].copy()
            styled_df["Status"] = styled_df.apply(lambda row: f'<span style="background-color:{color_map.get(row["Status Color"],"#ccc")};color:white;padding:2px 8px;border-radius:4px;">{row["Status"]}</span>', axis=1)
            st.write(styled_df.to_html(escape=False, index=False, columns=["Invoice Number", "Invoice Amount", "Payment Amount", "Status", "Details"]), unsafe_allow_html=True)

            # --- Detailed Results Section ---
            st.markdown("<br><h4>Detailed Results</h4>", unsafe_allow_html=True)
            import streamlit.components.v1 as components
            import json
            from collections import OrderedDict

            # Show/Hide All toggle
            if 'expand_all' not in st.session_state:
                st.session_state['expand_all'] = False
            def toggle_expand():
                st.session_state['expand_all'] = not st.session_state['expand_all']
            expand_label = "Expand All" if not st.session_state['expand_all'] else "Collapse All"
            st.button(expand_label, on_click=toggle_expand, key="expand_all_btn")

            # Helper to pretty print details as table, hiding empty fields
            def pretty_details(details_dict, highlight_keys=None):
                if not isinstance(details_dict, dict):
                    try:
                        details_dict = json.loads(details_dict)
                    except Exception:
                        return "<i>Invalid details</i>"
                rows = []
                for k, v in details_dict.items():
                    if v is None or v == "" or v == "nan":
                        continue
                    key_disp = f"<b>{k}</b>" if highlight_keys and k in highlight_keys else k
                    val_disp = f"<span style='color:#fff;font-weight:bold'>{v}</span>" if highlight_keys and k in highlight_keys else v
                    rows.append(f"<tr><td style='padding:2px 8px;'><b>{key_disp}</b></td><td style='padding:2px 8px;'>{val_disp}</td></tr>")
                if not rows:
                    return "<i>No details</i>"
                return f"<table style='width:100%;font-size:0.95em;'>{''.join(rows)}</table>"

            # Only expand the first card by default, or all if expand_all is set
            for idx, row in filtered_df.iterrows():
                expanded = st.session_state['expand_all'] or idx == 0
                with st.expander(f"Invoice {row['Invoice Number']} - {row['Status']}", expanded=expanded):
                    st.markdown(f"""
                        <div style='max-width:700px;margin-bottom:0.5em;position:relative;background:#23272e;border-radius:8px;padding:1em 1.5em 1em 1em;border:1px solid #222;'>
                            <div style='display:flex;justify-content:space-between;align-items:center;'>
                                <div><b style='font-size:1.1em;color:#fff;'>Invoice Number:</b> <span style='font-size:1.1em;color:#fff;'>{row['Invoice Number']}</span></div>
                                <div style='position:sticky;top:0;right:0;z-index:2;font-weight:bold;color:white;padding:2px 12px;border-radius:4px;background:{color_map.get(row['Status Color'],'#ccc')}'>{row['Status']}</div>
                            </div>
                            <div style='margin-top:0.5em;'><b>Invoice Amount:</b> <span style='color:#fff;'>{row['Invoice Amount']}</span> &nbsp; | &nbsp; <b>Payment Amount:</b> <span style='color:#fff;'>{row['Payment Amount']}</span></div>
                            <div style='margin-top:0.5em;'><b>Details:</b> <span style='color:#fff;'>{row['Details']}</span></div>
                            <div style='margin-top:0.5em;display:flex;gap:2em;'>
                                <div style='flex:1;'>
                                    <b style='color:#2564cf;'>Invoice Details</b>
                                    {pretty_details(row['Invoice Details'], highlight_keys=[inv_num_col, inv_amt_col])}
                                </div>
                                <div style='flex:1;'>
                                    <b style='color:#2564cf;'>Payment Details</b>
                                    {pretty_details(row['Payment Details'], highlight_keys=[pay_num_col, pay_amt_col])}
                                </div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
    try:
        invoice_file_obj.seek(0)
        invoices = pd.read_csv(invoice_file_obj, dtype=str, delimiter=delimiter).fillna("")
        invoices = clean_df(invoices)
        if invoices.empty or len(invoices.columns) == 0:
            st.error("The uploaded invoice file is empty or has no columns. Please upload a valid CSV with headers and data.")
            st.stop()
    except Exception as e:
        st.error(f"Could not read the uploaded invoice file: {e}")
        st.stop()
    try:
        payment_file.seek(0)
        payments = pd.read_csv(payment_file, dtype=str).fillna("")
        payments = clean_df(payments)
        if payments.empty or len(payments.columns) == 0:
            st.error("The uploaded payment file is empty or has no columns. Please upload a valid CSV with headers and data.")
            st.stop()
    except Exception as e:
        st.error(f"Could not read the uploaded payment file: {e}")
        st.stop()


    # Removed Step 2 header and mapping instructions from Results tab

    def suggest_mapping(columns, standard_fields):
        mapping = {}
        for field in standard_fields:
            matches = difflib.get_close_matches(field.replace(' ',''), [c.replace(' ','').lower() for c in columns], n=1, cutoff=0.7)
            if matches:
                for c in columns:
                    if c.replace(' ','').lower() == matches[0]:
                        mapping[field] = c
                        break
            else:
                mapping[field] = "(none)"
        return mapping

    invoice_suggested = suggest_mapping(list(invoices.columns), standard_fields)
    payment_suggested = suggest_mapping(list(payments.columns), standard_fields)

    invoice_col_map = {}
    payment_col_map = {}
    mapping_rows = []
    st.markdown("<style>th,td {padding: 0.2em 0.5em !important;}</style>", unsafe_allow_html=True)
    for field in standard_fields:
        cols = st.columns([2, 3, 3])
        with cols[0]:
            st.markdown(f"**{field.title()}**")
        with cols[1]:
            inv_options = ["(none)"] + list(invoices.columns)
            invoice_col = st.selectbox(
                " ",
                options=inv_options,
                index=inv_options.index(invoice_suggested[field]) if invoice_suggested[field] in inv_options else 0,
                key=f"inv_{field}"
            )
        with cols[2]:
            pay_options = ["(none)"] + list(payments.columns)
            payment_col = st.selectbox(
                "  ",
                options=pay_options,
                index=pay_options.index(payment_suggested[field]) if payment_suggested[field] in pay_options else 0,
                key=f"pay_{field}"
            )
        invoice_col_map[field] = invoice_col
        payment_col_map[field] = payment_col
        mapping_rows.append({"Standard Field": field, "Invoice Column": invoice_col, "Payment Column": payment_col})

    # Show preview of mapped/cleaned data
    # Removed Step 3 header and preview from Results tab


    # Only require invoice number mapping to proceed
    if invoice_col_map["invoice number"] == "(none)" or payment_col_map["invoice number"] == "(none)":
        st.warning("At minimum, map the 'invoice number' field for both files to proceed with reconciliation.")
        st.stop()

    # --- Modern Results Section ---
    inv_num_col = invoice_col_map["invoice number"]
    pay_num_col = payment_col_map["invoice number"]
    inv_amt_col = invoice_col_map["amount"]
    pay_amt_col = payment_col_map["amount"]
    inv_bal_col = invoice_col_map["balance"] if "balance" in invoice_col_map else None
    pay_bal_col = payment_col_map["balance"] if "balance" in payment_col_map else None

    # Build lookup for payments by invoice number
    pay_lookup = {str(row[pay_num_col]).strip(): row for _, row in payments.iterrows() if pay_num_col != "(none)"}

    results = []
    for _, inv_row in invoices.iterrows():
        inv_num = str(inv_row[inv_num_col]).strip() if inv_num_col != "(none)" else ""
        pay_row = pay_lookup.get(inv_num, None)
        invoice_amt = float(str(inv_row[inv_amt_col]).replace(',', '')) if inv_amt_col != "(none)" and inv_row[inv_amt_col] not in [None, ""] else None
        payment_amt = None
        if pay_row is not None and pay_amt_col != "(none)" and pay_row[pay_amt_col] not in [None, ""]:
            try:
                payment_amt = float(str(pay_row[pay_amt_col]).replace(',', ''))
            except Exception:
                payment_amt = None
        # Calculate paid amount if balance is present
        paid_amt = None
        if inv_bal_col and inv_bal_col != "(none)" and inv_row[inv_bal_col] not in [None, ""] and invoice_amt is not None:
            try:
                paid_amt = invoice_amt - float(str(inv_row[inv_bal_col]).replace(',', ''))
            except Exception:
                paid_amt = None
        # Status and details logic
        if pay_row is None:
            status = "🟥 No Match"
            details = "No payment found for this invoice."
        elif invoice_amt is not None and payment_amt is not None:
            if abs(invoice_amt - payment_amt) < 0.01:
                status = "✅ Exact Match"
                details = "Invoice and payment amounts match."
            elif paid_amt is not None and abs(paid_amt - payment_amt) < 0.01:
                status = "🟡 Partial Payment"
                details = f"Invoice partially paid. Paid: {paid_amt}, Outstanding: {inv_row[inv_bal_col]}"
            else:
                status = "🟠 Amount Mismatch"
                details = f"Invoice and payment amounts differ. Invoice: {invoice_amt}, Payment: {payment_amt}"
        else:
            status = "🟠 Data Issue"
            details = "Could not determine payment or invoice amount."
        # Collect both sides for expansion
        invoice_details = {f"Invoice: {col}": inv_row[col] for col in invoices.columns}
        payment_details = {f"Payment: {col}": pay_row[col] if pay_row is not None else "" for col in payments.columns}
        result = {
            "Invoice Number": inv_num,
            "Invoice Amount": inv_row[inv_amt_col] if inv_amt_col != "(none)" else "",
            "Payment Amount": pay_row[pay_amt_col] if pay_row is not None and pay_amt_col != "(none)" else "",
            "Status": status,
            "Details": details,
            "Invoice Details": invoice_details,
            "Payment Details": payment_details
        }
        results.append(result)

    results_df = pd.DataFrame(results)

    # Removed Step 4 header from Results tab
    if results_df.empty:
        st.info("No results to display. Please check your mappings and data.")
    else:
        # Show summary table
        st.dataframe(results_df[["Invoice Number", "Invoice Amount", "Payment Amount", "Status", "Details"]], use_container_width=True)
        # Expandable details for each row
        st.markdown("#### Expand to see full details for each match")
        for idx, row in results_df.iterrows():
            with st.expander(f"Invoice {row['Invoice Number']} - {row['Status']}"):
                st.write("**Invoice Details:**")
                st.json(row["Invoice Details"])
                st.write("**Payment Details:**")
                st.json(row["Payment Details"])
        st.download_button(
            "Download Results as CSV",
            results_df.to_csv(index=False).encode('utf-8'),
            "reconciliation_results.csv",
            "text/csv",
            key="download_results_tab3"
        )



    # Prepare for fuzzy matching
    invoices['__row_id'] = invoices.index
    payments['__row_id'] = payments.index

    matches = []
    used_payment_indices = set()


    # Add unmatched payments
    unmatched_payments = set(payments.index) - used_payment_indices
    for j in unmatched_payments:
        pay_row = payments.loc[j]
        matches.append({
            **{f"inv_{col}": "" for col in invoices.columns if col != '__row_id'},
            **{f"pay_{col}": pay_row[col] for col in payments.columns if col != '__row_id'},
            "MatchScore": 0,
            "Status": "🟨 Payment Only"
        })

    result_df = pd.DataFrame(matches)

    # Try to find amount columns for comparison
    amount_invoice_col = next((col for col in result_df.columns if col.lower().startswith('inv_amount')), None)
    amount_payment_col = next((col for col in result_df.columns if col.lower().startswith('pay_amount')), None)

    def highlight_diff(row):
        color = ''
        if row['Status'] == '🟥 No Match':
            color = 'background-color: #e6f0fa'
        elif row['Status'] == '🟨 Payment Only':
            color = 'background-color: #fff2cc'
        elif row['Status'] == '✅ Fuzzy Match':
            color = 'background-color: #fde9d9'
        return [color]*len(row)

    # Summary metrics
    n_total = len(result_df)
    n_exact = (result_df["Status"] == "✅ Exact Match").sum()
    n_fuzzy = (result_df["Status"] == "✅ Fuzzy Match").sum()
    n_no_match = (result_df["Status"] == "🟥 No Match").sum()
    n_pay_only = (result_df["Status"] == "🟨 Payment Only").sum()


