# app_streamlit.py
# WebApp Keuangan Ketahanan Pangan Lele - Desa Protomulyo
# Framework: Streamlit

import sqlite3
from datetime import date, datetime
from io import BytesIO

import pandas as pd
import streamlit as st

DB_NAME = "keuangan_lele.db"  # gunakan DB yang sama agar kompatibel dengan versi desktop

# --------------------- Util & DB ---------------------

def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS transaksi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                periode TEXT NOT NULL,
                kategori TEXT NOT NULL CHECK(kategori IN ('Harian','Mingguan','Bulanan','Tahunan')),
                jenis TEXT NOT NULL CHECK(jenis IN ('Pemasukan','Pengeluaran')),
                keterangan TEXT,
                jumlah REAL NOT NULL,
                created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime'))
            )
            """
        )
        conn.commit()


def rupiah(x: float) -> str:
    try:
        return f"Rp {x:,.0f}".replace(",", ".")
    except Exception:
        return str(x)


def week_of_month(dt: date) -> int:
    # Minggu dalam bulan dengan anchor Senin (sesuai weekday Python: Mon=0)
    first_day = dt.replace(day=1)
    dom = dt.day
    adjusted = dom + first_day.weekday()
    return int((adjusted - 1) // 7 + 1)


def build_periode(dt: date, kategori: str) -> str:
    if kategori == "Harian":
        return dt.strftime("%Y-%m-%d")
    elif kategori == "Mingguan":
        minggu_ke = week_of_month(dt)
        return f"{dt.strftime('%B %Y')} - Minggu {minggu_ke}"
    elif kategori == "Bulanan":
        return dt.strftime("%B %Y")
    elif kategori == "Tahunan":
        return dt.strftime("%Y")
    return ""


# --------------------- App UI ---------------------

st.set_page_config(
    page_title="Keuangan Lele Protomulyo",
    page_icon="🐟",
    layout="wide",
)

st.title("🐟 Keuangan Ketahanan Pangan Lele — Desa Protomulyo")
init_db()
conn = get_conn()

with st.sidebar:
    st.header("Input / Edit Transaksi")
    mode = st.radio("Mode", ["Tambah", "Edit/Hapus"], horizontal=True)

    # Kategori + tanggal
    kategori = st.selectbox("Kategori", ["Harian", "Mingguan", "Bulanan", "Tahunan"], index=0)
    tgl = st.date_input("Tanggal", value=date.today())

    # jenis, keterangan, jumlah
    jenis = st.selectbox("Jenis", ["Pemasukan", "Pengeluaran"])
    keterangan = st.text_input("Keterangan", placeholder="contoh: jual lele / beli pakan")
    jumlah = st.number_input("Jumlah (Rp)", min_value=0.0, step=1000.0, format="%f")

    periode = build_periode(tgl, kategori)
    st.caption(f"Periode otomatis: **{periode}**")

    if mode == "Tambah":
        if st.button("Simpan Transaksi", use_container_width=True):
            if not jumlah or jumlah <= 0:
                st.error("Jumlah harus lebih dari 0")
            elif not jenis:
                st.error("Pilih jenis transaksi")
            else:
                with conn:
                    conn.execute(
                        "INSERT INTO transaksi (periode, kategori, jenis, keterangan, jumlah) VALUES (?,?,?,?,?)",
                        (periode, kategori, jenis, keterangan, float(jumlah)),
                    )
                st.success("Data tersimpan")
                st.rerun()

    else:  # Edit/Hapus
        df_all = pd.read_sql_query(
            "SELECT id, periode, kategori, jenis, keterangan, jumlah, created_at FROM transaksi ORDER BY id DESC",
            conn,
        )
        pick_id = st.selectbox(
            "Pilih ID transaksi untuk diedit/dihapus",
            options=df_all["id"].tolist() if not df_all.empty else [],
        )
        if pick_id:
            row = df_all[df_all["id"] == pick_id].iloc[0]
            # Prefill
            kategori_e = st.selectbox("Kategori (edit)", ["Harian", "Mingguan", "Bulanan", "Tahunan"],
                                      index=["Harian","Mingguan","Bulanan","Tahunan"].index(row["kategori"]))
            # Tanggal untuk rekalkulasi periode (gunakan hari ini jika tak bisa parse)
            tgl_e = st.date_input("Tanggal (edit)", value=date.today(), key="tgl_edit")
            jenis_e = st.selectbox("Jenis (edit)", ["Pemasukan", "Pengeluaran"],
                                   index=["Pemasukan","Pengeluaran"].index(row["jenis"]))
            ket_e = st.text_input("Keterangan (edit)", value=row["keterangan"] or "")
            jml_e = st.number_input("Jumlah (edit)", min_value=0.0, step=1000.0, value=float(row["jumlah"]), format="%f")

            periode_e = build_periode(tgl_e, kategori_e)
            st.caption(f"Periode otomatis (edit): **{periode_e}**")

            cols = st.columns(2)
            with cols[0]:
                if st.button("Simpan Perubahan", use_container_width=True):
                    with conn:
                        conn.execute(
                            "UPDATE transaksi SET periode=?, kategori=?, jenis=?, keterangan=?, jumlah=? WHERE id=?",
                            (periode_e, kategori_e, jenis_e, ket_e, float(jml_e), int(pick_id)),
                        )
                    st.success("Data diperbarui")
                    st.rerun()
            with cols[1]:
                if st.button("Hapus Data", use_container_width=True):
                    with conn:
                        conn.execute("DELETE FROM transaksi WHERE id=?", (int(pick_id),))
                    st.warning("Data dihapus")
                    st.rerun()

st.markdown("---")

# --------------------- Data & Filter ---------------------
st.subheader("📋 Data Transaksi")
colf = st.columns([1,1,2,1])
with colf[0]:
    filter_kat = st.selectbox("Filter Kategori", ["Semua", "Harian", "Mingguan", "Bulanan", "Tahunan"], index=0)
with colf[1]:
    cari = st.text_input("Cari (periode/jenis/keterangan)")
with colf[2]:
    pass
with colf[3]:
    refresh = st.button("Refresh Data")

q = "SELECT id, periode, kategori, jenis, keterangan, jumlah, created_at FROM transaksi"
params = []
filters = []
if filter_kat != "Semua":
    filters.append("kategori = ?")
    params.append(filter_kat)
if cari.strip():
    like = f"%{cari.strip()}%"
    filters.append("(periode LIKE ? OR jenis LIKE ? OR keterangan LIKE ?)")
    params.extend([like, like, like])
if filters:
    q += " WHERE " + " AND ".join(filters)
q += " ORDER BY id DESC"

df = pd.read_sql_query(q, conn, params=params)

if df.empty:
    st.info("Belum ada data.")
else:
    df_show = df.copy()
    df_show["jumlah_rp"] = df_show["jumlah"].apply(rupiah)
    st.dataframe(
        df_show[["id", "periode", "kategori", "jenis", "keterangan", "jumlah_rp", "created_at"]],
        use_container_width=True,
        hide_index=True,
    )

# --------------------- Rekap ---------------------
st.subheader("📈 Rekap Otomatis")
if df.empty:
    st.caption("—")
else:
    # Rekap per kategori x jenis
    pivot = df.groupby(["kategori", "jenis"]).agg(total=("jumlah", "sum")).reset_index()
    # Buat tabel saldo per kategori
    tbl = pivot.pivot(index="kategori", columns="jenis", values="total").fillna(0)
    tbl["Saldo"] = tbl.get("Pemasukan", 0) - tbl.get("Pengeluaran", 0)
    tbl = tbl.reset_index()

    # Tampilkan
    tbl_show = tbl.copy()
    for col in [c for c in tbl_show.columns if c != "kategori"]:
        tbl_show[col] = tbl_show[col].apply(rupiah)
    st.table(tbl_show)

    # Rekap rinci per periode mingguan/bulanan/tahunan untuk laporan
    rekap_mingguan = df[df["kategori"] == "Mingguan"].groupby(["periode", "jenis"]).sum(numeric_only=True).reset_index()
    rekap_bulanan = df[df["kategori"] == "Bulanan"].groupby(["periode", "jenis"]).sum(numeric_only=True).reset_index()
    rekap_tahunan = df[df["kategori"] == "Tahunan"].groupby(["periode", "jenis"]).sum(numeric_only=True).reset_index()

# --------------------- Export Excel ---------------------
st.subheader("📦 Export ke Excel")
if df.empty:
    st.caption("Tidak ada data untuk diexport.")
else:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Transaksi")
        # Rekap ringkas per kategori
        pvt = df.pivot_table(index=["kategori", "jenis"], values="jumlah", aggfunc="sum").reset_index()
        pvt.to_excel(writer, index=False, sheet_name="Rekap_Kategori")
        # Rekap Mingguan/Bulanan/Tahunan
        rekap_mingguan.to_excel(writer, index=False, sheet_name="Rekap_Mingguan")
        rekap_bulanan.to_excel(writer, index=False, sheet_name="Rekap_Bulanan")
        rekap_tahunan.to_excel(writer, index=False, sheet_name="Rekap_Tahunan")
    buffer.seek(0)
    today = date.today().strftime("%Y-%m-%d")
    st.download_button(
        label="Download Excel Laporan",
        data=buffer,
        file_name=f"laporan_keuangan_lele_{today}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.markdown(":grey[© Desa Protomulyo — Aplikasi Keuangan Lele]")
