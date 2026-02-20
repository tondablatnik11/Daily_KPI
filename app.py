import streamlit as st
import pandas as pd
from fpdf import FPDF
import datetime

st.set_page_config(page_title="Denní KPI Skladu", layout="wide")

# Funkce pro bezpečný export do PDF
def odstran_diakritiku(text):
    nahrad = {'á':'a', 'č':'c', 'ď':'d', 'é':'e', 'ě':'e', 'í':'i', 'ň':'n', 'ó':'o', 'ř':'r', 'š':'s', 'ť':'t', 'ú':'u', 'ů':'u', 'ý':'y', 'ž':'z', 
              'Á':'A', 'Č':'C', 'Ď':'D', 'É':'E', 'Ě':'E', 'Í':'I', 'Ň':'N', 'Ó':'O', 'Ř':'R', 'Š':'S', 'Ť':'T', 'Ú':'U', 'Ů':'U', 'Ý':'Y', 'Ž':'Z'}
    for k, v in nahrad.items():
        text = text.replace(k, v)
    return text

def create_pdf_report(date_str, inbound_qty, pick_qty, pick_orders, pack_orders, pack_packages, pack_pieces, carrier_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    pdf.cell(200, 10, txt=odstran_diakritiku(f"Denni KPI Report Skladu - {date_str}"), ln=True, align='C')
    pdf.ln(10)
    
    # Inbound a Pick
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=odstran_diakritiku("Prijem a Vychystavani:"), ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.cell(200, 10, txt=odstran_diakritiku(f"- INBOUND: {int(inbound_qty):,} ks"), ln=True)
    pdf.cell(200, 10, txt=odstran_diakritiku(f"- PICK (Kusy): {int(pick_qty):,} ks"), ln=True)
    pdf.cell(200, 10, txt=odstran_diakritiku(f"- PICK (Zakazky): {int(pick_orders)} zakazek"), ln=True)
    pdf.ln(5)
    
    # Pack
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=odstran_diakritiku("Baleni a Expedice:"), ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.cell(200, 10, txt=odstran_diakritiku(f"- Zabaleno zakazek: {int(pack_orders)}"), ln=True)
    pdf.cell(200, 10, txt=odstran_diakritiku(f"- Zabaleno baliku (HU): {int(pack_packages)}"), ln=True)
    pdf.cell(200, 10, txt=odstran_diakritiku(f"- Zabaleno kusu: {int(pack_pieces):,} ks"), ln=True)
    pdf.ln(5)
    
    # Dopravci
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=odstran_diakritiku("Zabaleno podle dopravcu (Status 50/60):"), ln=True)
    pdf.set_font("Arial", '', 12)
    for index, row in carrier_data.iterrows():
         pdf.cell(200, 10, txt=odstran_diakritiku(f"- {row['Forwarding agent name']}: {row['Počet zakázek']} zakazek"), ln=True)
         
    pdf.ln(15)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, txt=odstran_diakritiku(f"Vygenerovano systemem: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"), ln=True)
    
    return bytes(pdf.output(dest='S').encode('latin-1'))

st.title("Skladové KPI: Inbound, Pick & Pack 📊")

col1, col2, col3, col4 = st.columns(4)
file_inbound = col1.file_uploader("1. INBOUND (.xlsx)", type=['xlsx', 'csv'])
file_pick = col2.file_uploader("2. PICK (.xlsx)", type=['xlsx', 'csv'])
file_pack = col3.file_uploader("3. PACK v2 (.xlsx)", type=['xlsx', 'csv'])
file_ship = col4.file_uploader("4. SHIPPING (.xlsx)", type=['xlsx', 'csv'])

if file_inbound and file_pick and file_pack and file_ship:
    with st.spinner("Zpracovávám data..."):
        try:
            # Načtení dat (podpora pro CSV i XLSX exporty)
            df_inbound = pd.read_csv(file_inbound) if file_inbound.name.endswith('.csv') else pd.read_excel(file_inbound)
            df_pick = pd.read_csv(file_pick) if file_pick.name.endswith('.csv') else pd.read_excel(file_pick)
            df_pack = pd.read_csv(file_pack) if file_pack.name.endswith('.csv') else pd.read_excel(file_pack)
            df_ship = pd.read_csv(file_ship) if file_ship.name.endswith('.csv') else pd.read_excel(file_ship)

            # --- VÝPOČTY INBOUND ---
            inbound_qty = df_inbound['Source actual qty.'].sum() if 'Source actual qty.' in df_inbound.columns else 0

            # --- VÝPOČTY PICK ---
            pick_qty = df_pick['Source actual qty.'].sum() if 'Source actual qty.' in df_pick.columns else 0
            pick_orders = df_pick['Delivery'].nunique() if 'Delivery' in df_pick.columns else 0

            # --- VÝPOČTY DOPRAVCI (SHIPPING) ---
            # Filtrujeme pouze zabalené (Status 50 a 60)
            df_packed_ship = df_ship[df_ship['Status'].isin([50, 60])].copy()
            carrier_stats = df_packed_ship.groupby('Forwarding agent name').size().reset_index(name='Počet zakázek')
            carrier_stats = carrier_stats.sort_values(by='Počet zakázek', ascending=False)

            # --- VÝPOČTY PACK ---
            pack_packages = df_pack['Handling Unit'].nunique() if 'Handling Unit' in df_pack.columns else 0
            pack_orders = df_pack['Generated delivery'].nunique() if 'Generated delivery' in df_pack.columns else 0
            
            # Zjištění kusů pro balení (Spárování Pick a Pack přes číslo zakázky)
            if 'Delivery' in df_pick.columns and 'Generated delivery' in df_pack.columns:
                # Kolik kusů má každá zakázka podle pickingu
                kusu_na_zakazku = df_pick.groupby('Delivery')['Source actual qty.'].sum().reset_index()
                kusu_na_zakazku.rename(columns={'Delivery': 'Generated delivery'}, inplace=True)
                
                # Unikátní zakázky v Packu a připojení kusů z Picku
                unikatni_pack_zakazky = df_pack[['Generated delivery', 'Created By']].drop_duplicates(subset=['Generated delivery'])
                pack_s_kusy = pd.merge(unikatni_pack_zakazky, kusu_na_zakazku, on='Generated delivery', how='left')
                pack_pieces = pack_s_kusy['Source actual qty.'].sum()
            else:
                pack_pieces = 0

            # --- DASHBOARD UI ---
            tab1, tab2, tab3, tab4 = st.tabs(["📋 Shrnutí & Export", "🛒 Pick Výkonnost", "📦 Pack Výkonnost", "🚚 Dopravci (Shipping)"])
            
            with tab1:
                st.header("Denní Souhrn")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Přijato (ks)", f"{int(inbound_qty):,}")
                m2.metric("Vychystáno (ks)", f"{int(pick_qty):,}")
                m3.metric("Zabaleno Balíků (HU)", f"{int(pack_packages):,}")
                m4.metric("Zabaleno Zakázek", f"{int(pack_orders):,}")
                
                st.markdown("---")
                pdf_bytes = create_pdf_report(
                    datetime.date.today().strftime("%d.%m.%Y"), 
                    inbound_qty, pick_qty, pick_orders, pack_orders, pack_packages, pack_pieces, carrier_stats
                )
                
                st.download_button(
                    label="📄 Stáhnout KPI Report jako PDF",
                    data=pdf_bytes,
                    file_name=f"KPI_Report_{datetime.date.today().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf"
                )

            with tab2:
                st.header("Výkonnost Pickerů")
                # Groupování podle Usera pro Pick
                if 'User' in df_pick.columns:
                    pick_kpi = df_pick.groupby('User').agg(
                        Vypickováno_TO=('Transfer Order Number', 'nunique'),
                        Zakázek=('Delivery', 'nunique'),
                        Pozic=('Transfer Order Number', 'count'), # Počet řádků
                        Kusů=('Source actual qty.', 'sum')
                    ).reset_index()
                    
                    pick_kpi = pick_kpi.sort_values(by='Kusů', ascending=False)
                    st.dataframe(pick_kpi, use_container_width=True, hide_index=True)

            with tab3:
                st.header("Výkonnost Baličů")
                if 'Created By' in df_pack.columns:
                    # 1. Počet zabalených balíků (HU) na baliče
                    baliky_na_balice = df_pack.groupby('Created By')['Handling Unit'].nunique().reset_index(name='Balíků (HU)')
                    
                    # 2. Počet zakázek a kusů na baliče (z dříve vytvořeného pack_s_kusy)
                    zakazky_na_balice = pack_s_kusy.groupby('Created By').agg(
                        Zakázek=('Generated delivery', 'nunique'),
                        Kusů=('Source actual qty.', 'sum')
                    ).reset_index()

                    # Spojení statistik baliče do jedné tabulky
                    pack_kpi = pd.merge(baliky_na_balice, zakazky_na_balice, on='Created By', how='outer').fillna(0)
                    pack_kpi = pack_kpi.sort_values(by='Zakázek', ascending=False)
                    
                    # Formátování na celá čísla
                    pack_kpi['Kusů'] = pack_kpi['Kusů'].astype(int)
                    
                    st.dataframe(pack_kpi, use_container_width=True, hide_index=True)

            with tab4:
                st.header("Zabalené zakázky podle dopravců")
                st.write("*(Kalkulováno ze souboru Shipping, kde je Status 50 nebo 60)*")
                st.dataframe(carrier_stats, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"Došlo k chybě při zpracování souborů. Detail chyby: {e}")
