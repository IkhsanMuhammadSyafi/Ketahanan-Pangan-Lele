import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client, Client
from io import BytesIO

# === Setup Supabase Client ===
SB_URL = st.secrets["supabase"]["url"]
SB_KEY = st.secrets["supabase"]["key"]
supabase: Client = create_client(SB_URL, SB_KEY)

# === Helper: Hitung minggu ke-berapa dalam bulan ===
def week_of_month(dt: date) -> int:
    first_day = dt.replace(day=1)
    dom = dt.day
    adjusted = dom + first_day.weekday()
    return int((adjusted - 1) // 7 + 1)

ID_BULAN = {
    1:"Januari",2:"Februari",3:"Maret",4:"April",5:"Mei",6:"Juni",
    7:"Juli",8:"Agustus",9:"September",10:"Oktober",11:"November",12:"Desember"
}

def build_periode(dt: date, kategori: str) -> str:
    if kategori == "Harian":
        return dt.strftime("%Y-%m-%d")
    elif kategori == "Mingguan":
        return f"{ID_BULAN[dt.month]} {dt.year} - Minggu {week_of_month(dt)}"
    elif kategori == "Bulanan":
        return f"{ID_BULAN[dt.month]} {dt.year}"
    elif kategori == "Tahunan":
        return f"{dt.year}"
    return ""

# === CRUD Functions ===
def insert_transaksi(tgl: date, kategori: str, jenis: str, keterangan: str, jumlah: float):
    periode = build_periode(tgl, kategori)
    data = {
        "tgl": str(tgl),
        "periode": periode,
        "kategori": kategori,
        "jenis": jenis,
        "keterangan": keterangan,
        "jumlah": jumlah
    }
    supabase.table("transaksi").insert(data).execute()

def fetch_transaksi(kat_filter="Semua", cari_text=""):
    q = supabase.table("transaksi").select("*")
    if kat_filter != "Semua":
        q = q.eq("kategori", kat_filter)
    if cari_text.strip():
        like = f"%{cari_text.strip()}%"
        q = q.or_(f"periode.ilike.{like},jenis.ilike.{like},keterangan.ilike.{like}")
    res = q.order("id", desc=True).execute()
    rows = res.data or []
    return pd.DataFrame(rows)

def update_transaksi(id_: int, tgl: date, kategori: str, jenis: str, keterangan: str, jumlah: float):
    periode = build_periode(tgl, kategori)
    supabase.table("transaksi").update({
        "tgl": str(tgl),
        "periode": periode,
        "kategori": kategori,
        "jenis": jenis,
        "keterangan": keterangan,
        "jumlah": jumlah
    }).eq("id", id_).execute()

def delete_transaksi(id_: int):
    supabase.table("transaksi").delete().eq("id", id_).execute()

# === Streamlit App ===
st.title("📊 Sistem Keuangan Ketahanan Pangan Lele Desa Protomulyo")

menu = st.sidebar.radio("Menu", ["Tambah Data", "Lihat Data", "Export Excel"])

if menu == "Tambah Data":
    st.header("➕ Tambah Data Transaksi")
    with st.form("form_transaksi"):
        tgl = st.date_input("Tanggal", value=date.today())
        kategori = st.selectbox("Kategori", ["Harian","Mingguan","Bulanan","Tahunan"])
        jenis = st.radio("Jenis", ["Pemasukan","Pengeluaran"])
        keterangan = st.text_input("Keterangan - Pemasukan/Pengeluaran", placeholder="Misal: Lele terjual ... kg")
        jumlah = st.number_input("Jumlah", min_value=0.0, step=1000.0)
        submit = st.form_submit_button("Simpan")

        if submit:
            insert_transaksi(tgl, kategori, jenis, keterangan, jumlah)
            st.success("✅ Data berhasil disimpan!")

elif menu == "Lihat Data":
    st.header("📑 Data Transaksi")
    kat_filter = st.selectbox("Filter Kategori", ["Semua","Harian","Mingguan","Bulanan","Tahunan"])
    cari_text = st.text_input("Cari keterangan / periode")

    df = fetch_transaksi(kat_filter, cari_text)

    if not df.empty:
        st.dataframe(df)

        # Pilih baris untuk update / delete
        selected = st.selectbox("Pilih ID untuk edit/hapus", df["id"].tolist())
        if selected:
            row = df[df["id"]==selected].iloc[0]

            st.subheader("✏️ Edit / Hapus")
            new_tgl = st.date_input("Tanggal", value=pd.to_datetime(row["tgl"]).date())
            new_kategori = st.selectbox("Kategori", ["Harian","Mingguan","Bulanan","Tahunan"], index=["Harian","Mingguan","Bulanan","Tahunan"].index(row["kategori"]))
            new_jenis = st.radio("Jenis", ["Pemasukan","Pengeluaran"], index=0 if row["jenis"]=="Pemasukan" else 1)
            new_jumlah = st.number_input("Jumlah", min_value=0.0, step=1000.0, value=float(row["jumlah"]))
            new_keterangan = st.text_input("Keterangan", value=row["keterangan"] or "")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Simpan Perubahan"):
                    update_transaksi(int(selected), new_tgl, new_kategori, new_jenis, new_keterangan, new_jumlah)
                    st.success("✅ Data berhasil diupdate!")
                    st.rerun()
            with col2:
                if st.button("🗑️ Hapus"):
                    delete_transaksi(int(selected))
                    st.warning("⚠️ Data dihapus.")
                    st.rerun()
    else:
        st.info("Belum ada data.")

elif menu == "Export Excel":
    st.header("📤 Export Data ke Excel")
    df = fetch_transaksi()
    if not df.empty:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Transaksi")
            # Rekap per kategori
            df.groupby("kategori")["jumlah"].sum().to_excel(writer, sheet_name="Rekap_Kategori")
            # Rekap per jenis
            df.groupby("jenis")["jumlah"].sum().to_excel(writer, sheet_name="Rekap_Jenis")
        buffer.seek(0)
        st.download_button(
            "💾 Download Excel",
            data=buffer,
            file_name="rekap_keuangan_lele.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Belum ada data untuk diexport.")
