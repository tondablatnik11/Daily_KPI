import streamlit as st
import pandas as pd
from fpdf import FPDF
from io import BytesIO
import datetime

st.set_page_config(page_title="Denní KPI Skladu", layout="wide")

# Funkce pro odstranění diakritiky pro bezpečný export do základního PDF
def odstran_diakritiku(text):
    nahrad = {'á':'a', 'č':'c', 'ď':'d', 'é':'e', 'ě':'e', 'í':'i', 'ň':'n', 'ó':'o', 'ř':'r', 'š':'s', 'ť':'t', 'ú':'u', 'ů':'u', 'ý':'y', 'ž':'z', 
              'Á':'A', 'Č':'C', 'Ď':'D', 'É':'E', 'Ě':'E', 'Í':'I', 'Ň':'N', 'Ó':'O', 'Ř':'R', 'Š':'S', 'Ť':'T', 'Ú':'U', 'Ů':'U', 'Ý':'Y', 'Ž':'Z'}
    for k, v in nahrad.items():
        text = text.replace(k, v)
    return text

def create_pdf_report(date_str, inbound_qty, pick_qty, pack_cartons, pack_pallets, lanes_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    # Hlavička
    pdf.cell(200, 10, txt=odstran_diakritiku(f"Denni KPI Report Skladu - {date_str}"), ln=True, align='C')
    pdf.ln(10)
    
    # Celková čísla
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=odstran_diakritiku("Celkove objemy (Kusy):"), ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.cell(200, 10, txt=odstran_diakritiku(f"- INBOUND (Prijem): {int(inbound_qty):,} ks"), ln=True)
    pdf.cell(200, 10, txt=odstran_diakritiku(f"- PICK (Vychystano): {int(pick_qty):,} ks"), ln=True)
    pdf.ln(5)
    
    # Balení
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=odstran_diakritiku("Baleni a Expedice:"), ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.cell(200, 10, txt=odstran_diakritiku(f"- Zabaleno do kartonu: {pack_cartons} zakazek"), ln=True)
    pdf.cell(200, 10, txt=odstran_diakritiku(f"- Zabaleno na palety: {pack_pallets} zakazek"), ln=True)
    pdf.ln(5)
    
    # Dopravci (Lanes)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=odstran_diakritiku("Rozdeleni podle dopravcu (Lanes):"), ln=True)
    pdf.set_font("Arial", '', 12)
    for lane, count in lanes_data.items():
         pdf.cell(200, 10, txt=odstran_diakritiku(f"- {lane}: {count} manipulaci/palet"), ln=True)
         
    pdf.ln(15)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, txt=odstran_diakritiku(f"Vygenerovano systemem: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"), ln=True)
    
    # Export do stringu (bytes) pro Streamlit
    return bytes(pdf.output(dest='S').encode('latin-1'))

st.title("Skladové KPI: Inbound, Pick & Pack 📊")
st.markdown("Nahrajte denní exporty ze SAPu a získejte okamžitý přehled o výkonu skladu. **Množství je počítáno ze sloupce `Source actual qty.`**")

col1, col2, col3, col4 = st.columns(4)
file_inbound = col1.file_uploader("1. INBOUND (.xlsx)", type=['xlsx'])
file_pick = col2.file_uploader("2. PICK (.xlsx)", type=['xlsx'])
file_pack = col3.file_uploader("3. PACK v2 (.xlsx)", type=['xlsx'])
file_pack_end = col4.file_uploader("4. PACK END (.xlsx)", type=['xlsx'])

if file_inbound and file_pick and file_pack and file_pack_end:
    with st.spinner("Zpracovávám data..."):
        try:
            # Načtení dat
            df_inbound = pd.read_excel(file_inbound)
            df_pick = pd.read_excel(file_pick)
            df_pack = pd.read_excel(file_pack)
            df_pack_end = pd.read_excel(file_pack_end)
            
            # --- ZÁKLADNÍ VÝPOČTY ---
            # 1. INBOUND
            inbound_qty = df_inbound['Source actual qty.'].sum() if 'Source actual qty.' in df_inbound.columns else 0
            
            # 2. PICK
            pick_qty = df_pick['Source actual qty.'].sum() if 'Source actual qty.' in df_pick.columns else 0
            
            # 3. PACK (Zakázky a Kartony vs Palety)
            # Určení palet (Carton-16, 17, 18)
            palety_list = ['CARTON-16', 'CARTON-17', 'CARTON-18']
            df_pack['Typ Balení'] = df_pack['Packaging materials'].apply(
                lambda x: 'Paleta' if str(x).strip().upper() in palety_list else 'Karton'
            )
            
            # Unikátní zakázky podle typu
            pack_stats = df_pack.drop_duplicates(subset=['Generated delivery']).groupby('Typ Balení').size()
            pack_cartons = pack_stats.get('Karton', 0)
            pack_pallets = pack_stats.get('Paleta', 0)
            
            # 4. PACK END (Dopravci / Lanes)
            # LANE01, LANE02 atd. jsou v Dest.Storage Bin
            if 'Dest.Storage Bin' in df_pack_end.columns:
                lane_stats = df_pack_end['Dest.Storage Bin'].value_counts().to_dict()
            else:
                lane_stats = {}

            # --- VIZUALIZACE (DASHBOARD) ---
            tab1, tab2, tab3, tab4 = st.tabs(["📋 Shrnutí & Export", "📥 Inbound Detail", "🛒 Pick Detail", "📦 Pack & Expedice"])
            
            with tab1:
                st.header("Denní Souhrn")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Přijato kusů (Inbound)", f"{int(inbound_qty):,}")
                m2.metric("Vychystáno kusů (Pick)", f"{int(pick_qty):,}")
                m3.metric("Zabaleno Kartonů (zakázek)", pack_cartons)
                m4.metric("Zabaleno Palet (zakázek)", pack_pallets)
                
                st.subheader("Expedice podle dopravců (Lanes)")
                lane_df = pd.DataFrame(list(lane_stats.items()), columns=['Linka (Dopravce)', 'Počet manipulací/uzavření'])
                st.dataframe(lane_df, hide_index=True)
                
                # PDF EXPORT Tlačítko
                st.markdown("---")
                pdf_bytes = create_pdf_report(
                    datetime.date.today().strftime("%d.%m.%Y"), 
                    inbound_qty, pick_qty, pack_cartons, pack_pallets, lane_stats
                )
                
                st.download_button(
                    label="📄 Stáhnout Report jako PDF (Pro E-mail)",
                    data=pdf_bytes,
                    file_name=f"KPI_Report_{datetime.date.today().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf"
                )

            with tab2:
                st.header("Inbound Detail")
                if 'User' in df_inbound.columns and 'Source actual qty.' in df_inbound.columns:
                    st.subheader("Top 10 Příjemců")
                    top_inbound = df_inbound.groupby('User')['Source actual qty.'].sum().sort_values(ascending=False).head(10)
                    st.bar_chart(top_inbound)

            with tab3:
                st.header("Pick Detail")
                if 'User' in df_pick.columns and 'Source actual qty.' in df_pick.columns:
                    st.subheader("Top 10 Pickerů (Kusy)")
                    top_pickers = df_pick.groupby('User')['Source actual qty.'].sum().sort_values(ascending=False).head(10)
                    st.bar_chart(top_pickers)

            with tab4:
                st.header("Balení a Expedice")
                st.write("**Rozdělení typu balení (Karton vs. Paleta)**")
                st.bar_chart(pack_stats)
                
                st.write("**Výkon baličů (Top 10 podle počtu zakázek)**")
                if 'Created By' in df_pack.columns:
                    top_packers = df_pack.drop_duplicates(subset=['Generated delivery'])['Created By'].value_counts().head(10)
                    st.bar_chart(top_packers)

        except Exception as e:
            st.error(f"Došlo k chybě při zpracování souborů. Zkontrolujte, že vkládáte správné formáty SAP. Detail chyby: {e}")
