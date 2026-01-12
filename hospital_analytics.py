import os
import sqlite3
import pandas as pd
import hashlib
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from datetime import datetime, timedelta

# --- KONFIGURACJA ŚCIEŻEK ---
NAZWA_PLIKU = 'Dane testowe.xlsx'
DB_FILE = 'szpital.db'

# --- TWORZENIE STRUKTURY BAZY DANYCH ---
conn = sqlite3.connect(DB_FILE)
sql_schema = """
DROP TABLE IF EXISTS "procedures";
DROP TABLE IF EXISTS "hospitalizations";
DROP TABLE IF EXISTS "doctors";
DROP TABLE IF EXISTS "wards";
DROP TABLE IF EXISTS "patients";
DROP VIEW IF EXISTS "rehospitalizations";
DROP VIEW IF EXISTS "prolonged_stays";

CREATE TABLE "patients" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "first_name" TEXT,
    "last_name" TEXT,
    "pesel" TEXT NOT NULL UNIQUE,
    "birth_date" DATE NOT NULL,
    "sex" TEXT NOT NULL
);

CREATE TABLE "hospitalizations"(
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "patient_id" INTEGER,
    "admission_date" DATE NOT NULL,
    "discharge_date" DATE,
    "mode_discharge" TEXT,
    "mode_admission" TEXT,
    "icd10" TEXT NOT NULL,
    "ward_id" INTEGER,
    "doctor_id" INTEGER,
    FOREIGN KEY("doctor_id") REFERENCES "doctors"("id"),
    FOREIGN KEY("patient_id") REFERENCES "patients"("id"),
    FOREIGN KEY("ward_id") REFERENCES "wards"("id")
);

CREATE TABLE "doctors"(
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "first_name" TEXT NOT NULL,
    "last_name" TEXT NOT NULL,
    "ward_id" INTEGER,
    FOREIGN KEY("ward_id") REFERENCES "wards"("id")
);

CREATE TABLE "procedures"(
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "hospitalization_id" INTEGER,
    "icd9" TEXT NOT NULL,
    "date" DATE NOT NULL,
    FOREIGN KEY("hospitalization_id") REFERENCES "hospitalizations"("id")
);

CREATE TABLE "wards"(
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL
);

CREATE INDEX "readmissions" ON "hospitalizations"("patient_id","admission_date","discharge_date");
CREATE INDEX "search_icd9" ON "procedures"("icd9");
CREATE INDEX "hosp_ward" ON "hospitalizations"("ward_id");

CREATE VIEW "rehospitalizations" AS
SELECT p.pesel, p.first_name, p.last_name,
h1.admission_date AS "prev_admission", h1.discharge_date AS "prev_discharge",
w1.name AS "prev_ward", h1.icd10 AS "prev_icd10",
h2.admission_date AS "readmission_date", h2.discharge_date AS "read_discharge_date",
w2.name AS "readmission_ward", h2.icd10 AS "readmission_icd10",
(JULIANDAY(h1.admission_date) - JULIANDAY(p.birth_date)) / 365.25 AS "age",
JULIANDAY(h2.admission_date) - JULIANDAY(h1.discharge_date) AS "days_between"
FROM hospitalizations h1
JOIN hospitalizations h2 ON h1.patient_id = h2.patient_id
AND h2.admission_date > h1.discharge_date AND h1.id < h2.id
JOIN patients p ON p.id = h1.patient_id
LEFT JOIN wards w1 ON w1.id = h1.ward_id
LEFT JOIN wards w2 ON w2.id = h2.ward_id
WHERE h1.discharge_date IS NOT NULL;

CREATE VIEW "prolonged_stays" AS
SELECT p.pesel, p.first_name, p.last_name,
h.icd10, h.admission_date, h.discharge_date,
w.name AS ward_name,
JULIANDAY(h.discharge_date) - JULIANDAY(h.admission_date) AS days_of_stay
FROM hospitalizations h
JOIN patients p ON p.id = h.patient_id
LEFT JOIN wards w ON w.id = h.ward_id
WHERE h.discharge_date IS NOT NULL;
"""

try:
    conn.executescript(sql_schema)
    print("Struktura bazy danych została utworzona.")
except Exception as e:
    print(f"Błąd bazy: {e}")
finally:
    conn.close()

# --- CZYSZCZENIE I POMOCNICZE FUNKCJE ---
conn = sqlite3.connect(DB_FILE)
conn.executescript("DELETE FROM hospitalizations; DELETE FROM patients; DELETE FROM doctors; DELETE FROM wards;")
conn.commit()
conn.close()

def get_birth_date_from_pesel(pesel):
    try:
        p = str(pesel).replace('.0', '').strip()
        if len(p) != 11 or not p.isdigit(): return '1900-01-01'
        rok = int(p[0:2]); miesiac = int(p[2:4]); dzien = int(p[4:6])
        if 81 <= miesiac <= 92: rok += 1800; miesiac -= 80
        elif 1 <= miesiac <= 12: rok += 1900
        elif 21 <= miesiac <= 32: rok += 2000; miesiac -= 20
        elif 41 <= miesiac <= 52: rok += 2100; miesiac -= 40
        elif 61 <= miesiac <= 72: rok += 2200; miesiac -= 60
        return f"{rok}-{miesiac:02d}-{dzien:02d}"
    except: return '1900-01-01'

def anonymize_pesel(pesel):
    if pd.isna(pesel): return None
    salt = "Klucz2025"
    pesel_str = str(pesel).replace('.0', '').strip()
    return hashlib.sha256((pesel_str + salt).encode()).hexdigest()[:16]

def get_sex_from_pesel(pesel):
    try:
        p = str(pesel).replace('.0', '').strip()
        if len(p) == 11 and p.isdigit(): return 'K' if int(p[9]) % 2 == 0 else 'M'
    except: pass
    return 'N/D'

# --- IMPORT DANYCH ---
try:
    df = pd.read_excel(NAZWA_PLIKU)
    col_pesel = [c for c in df.columns if 'PESEL' in str(c).upper()][0]

    df['real_birth_date'] = df[col_pesel].apply(get_birth_date_from_pesel)
    df['sex'] = df[col_pesel].apply(get_sex_from_pesel)
    df['anon_id'] = df[col_pesel].apply(anonymize_pesel)
    df['admission_date'] = pd.to_datetime(df['Data przyjęcia'], dayfirst=True, errors='coerce')
    df['discharge_date'] = pd.to_datetime(df['Data wypisania'], dayfirst=True, errors='coerce')

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    df_safe = df.drop(columns=[c for c in ['Imiona', 'Nazwisko', 'PESEL', 'Lp.'] if c in df.columns])

    count = 0
    for index, row in df_safe.iterrows():
        if pd.isna(row['anon_id']): continue
        ward_name = str(row['Oddział']).strip()
        cursor.execute("INSERT OR IGNORE INTO wards (name) VALUES (?)", (ward_name,))
        ward_id = cursor.execute("SELECT id FROM wards WHERE name = ?", (ward_name,)).fetchone()[0]

        res_pat = cursor.execute("SELECT id FROM patients WHERE pesel = ?", (row['anon_id'],)).fetchone()
        if res_pat: patient_id = res_pat[0]
        else:
            cursor.execute("INSERT INTO patients (first_name, last_name, pesel, birth_date, sex) VALUES (?, ?, ?, ?, ?)",
                           ('Anonim', 'Pacjent', row['anon_id'], row['real_birth_date'], row['sex']))
            patient_id = cursor.lastrowid

        adm = row['admission_date'].strftime('%Y-%m-%d') if not pd.isna(row['admission_date']) else None
        dis = row['discharge_date'].strftime('%Y-%m-%d') if not pd.isna(row['discharge_date']) else None

        cursor.execute("""
            INSERT INTO hospitalizations (patient_id, admission_date, discharge_date, mode_discharge, mode_admission, icd10, ward_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (patient_id, adm, dis, str(row['Tryb wypisu']), str(row['Tryb przyjęcia']), str(row['Rozpoznanie zasadnicze']), ward_id))
        count += 1
    conn.commit()
    print(f"Zaimportowano {count} rekordów.")
    conn.close()
except Exception as e:
    print(f"BŁĄD IMPORTU: {e}")

# --- ANALIZA PRZEDŁUŻONYCH POBYTÓW ---
conn = sqlite3.connect(DB_FILE)
query = """
SELECT
    h.icd10,
    h.admission_date,
    h.discharge_date,
    p.birth_date
FROM hospitalizations h
JOIN patients p ON h.patient_id = p.id
WHERE h.discharge_date IS NOT NULL
"""
df = pd.read_sql(query, conn)
conn.close()

df['admission_date'] = pd.to_datetime(df['admission_date'])
df['discharge_date'] = pd.to_datetime(df['discharge_date'])
df['birth_date'] = pd.to_datetime(df['birth_date'], errors='coerce')
df['LOS'] = (df['discharge_date'] - df['admission_date']).dt.days
df['LOS'] = df['LOS'].apply(lambda x: x if x > 0 else 1)
df['Wiek'] = (df['admission_date'] - df['birth_date']).dt.days // 365
df = df[(df['Wiek'] >= 0) & (df['Wiek'] <= 110)]

total_hospital_cases = len(df)

icd_counts_total = df['icd10'].value_counts()

statystyki = df.groupby('icd10')['LOS'].quantile(0.90).reset_index()
statystyki.rename(columns={'LOS': 'Norma_Dni'}, inplace=True)
df = pd.merge(df, statystyki, on='icd10', how='left')

df_przedluzone = df[df['LOS'] > df['Norma_Dni']].copy()

if df_przedluzone.empty:
    print("Brak danych o przedłużonych pobytach.")
else:
    top_10 = df_przedluzone['icd10'].value_counts().nlargest(10).index.tolist()
    df_final = df_przedluzone[df_przedluzone['icd10'].isin(top_10)].copy()

    agg = df_final.groupby('icd10').agg(
        Liczba=('LOS', 'count'),
        Czas_przedłużony=('LOS', 'mean'),
        Czas_Norma=('Norma_Dni', 'mean'),
        Wiek_Srednia=('Wiek', 'mean'),
        Wiek_SD=('Wiek', 'std')
    ).reindex(top_10).reset_index()

    agg['Wiek_SD'] = agg['Wiek_SD'].fillna(0)

    agg['Total_Cases_ICD'] = agg['icd10'].map(icd_counts_total)

    agg['Proc_Ogolu_Szpitala'] = (agg['Liczba'] / total_hospital_cases) * 100

    agg['Proc_Danej_Choroby'] = (agg['Liczba'] / agg['Total_Cases_ICD']) * 100

    fig, axes = plt.subplots(3, 1, figsize=(15, 22), constrained_layout=True)
    sns.set_style("whitegrid")

    fig.suptitle(f'ANALIZA PRZEDŁUŻONYCH POBYTÓW',
                 fontsize=18, fontweight='bold', color='#2c3e50')

    # --- WYKRES 1: SKALA PROBLEMU I PROCENTY ---
    sns.barplot(ax=axes[0], x='Liczba', y='icd10', data=agg, color='#3498db')
    axes[0].set_title('1. SKALA PROBLEMU: Liczba pacjentów przedłużonych', fontsize=14, fontweight='bold', loc='left')
    axes[0].set_xlabel('Liczba pacjentów z przedłużonym pobytem', fontsize=12)

    for container in axes[0].containers:
        labels = []
        for _, row in agg.iterrows():
            label = (f"{int(row['Liczba'])} "
                     f"({row['Proc_Ogolu_Szpitala']:.2f}% * | "
                     f"{row['Proc_Danej_Choroby']:.1f}% **)")
            labels.append(label)
        axes[0].bar_label(container, labels=labels, padding=5, fontsize=10, fontweight='bold', color='#2c3e50')
    tekst_legendy = (
        "LEGENDA:\n"
        "* % ogółu wszystkich hospitalizowanych w oddziale\n"
        "** % hospitalizowanych z tym samym rozpoznaniem"
    )
    axes[0].text(0.98, 0.05, tekst_legendy,
                 transform=axes[0].transAxes,
                 fontsize=11,
                 verticalalignment='bottom',
                 horizontalalignment='right',
                 bbox=dict(boxstyle="round,pad=0.5", facecolor='white', alpha=0.9, edgecolor='gray'))


    # --- WYKRES 2: CZAS ---
    df_czas = agg.melt(id_vars='icd10', value_vars=['Czas_Norma', 'Czas_przedłużony'],
                       var_name='Typ_Czasu', value_name='Dni')
    df_czas['Typ_Czasu'] = df_czas['Typ_Czasu'].replace({'Czas_Norma': 'Norma (90 percentyl)', 'Czas_przedłużony': 'Średni czas faktyczny'})

    sns.barplot(ax=axes[1], x='Dni', y='icd10', hue='Typ_Czasu', data=df_czas,
                palette={'Norma (90 percentyl)': '#2ecc71', 'Średni czas faktyczny': '#e74c3c'})

    axes[1].set_title('2. ANALIZA CZASU: Norma(Zielony) - przedłużone(czerwony)', fontsize=14, fontweight='bold', loc='left')
    axes[1].set_xlabel('Liczba dni', fontsize=12)
    axes[1].legend(loc='lower right', title='Legenda')
    for container in axes[1].containers:
        axes[1].bar_label(container, fmt='%.1f dni', padding=3, fontsize=9)

    sns.barplot(ax=axes[2], x='Wiek_Srednia', y='icd10', data=agg, color='#9b59b6')

    axes[2].errorbar(
        x=agg['Wiek_Srednia'],
        y=range(len(agg)),
        xerr=agg['Wiek_SD'],
        fmt='none',
        c='black',
        capsize=5,
        linewidth=2
    )

    axes[2].set_title('3. DEMOGRAFIA: Średnia wieku + Odchylenie Standardowe )', fontsize=14, fontweight='bold', loc='left')
    axes[2].set_xlabel('Wiek pacjenta (lata)', fontsize=12)
    max_age_val = (agg['Wiek_Srednia'] + agg['Wiek_SD']).max()
    axes[2].set_xlim(0, max_age_val * 1.15)

    for i, row in agg.iterrows():
        label = f"{row['Wiek_Srednia']:.0f} lat (±{row['Wiek_SD']:.0f})"
        axes[2].text(row['Wiek_Srednia'] + row['Wiek_SD'] + 1, i, label,
                     va='center', fontsize=10, fontweight='bold', color='#4a235a')

    plt.show()
def analiza_kpi_cmj_szczegolowa_procent_globalny(db_path):
    # --- KONFIGURACJA ---
    LIMIT_DNI = 14

    print(f"Łączenie z bazą: {db_path}...")
    conn = sqlite3.connect(db_path)

    query_total = "SELECT count(*) FROM hospitalizations WHERE discharge_date IS NOT NULL"
    total_wypisy = pd.read_sql(query_total, conn).iloc[0, 0]

    query_reh = f"""
    SELECT
        readmission_icd10,
        age,
        days_between
    FROM rehospitalizations
    WHERE days_between <= {LIMIT_DNI}
    """
    df = pd.read_sql(query_reh, conn)
    conn.close()

    if df.empty:
        print(f"[INFO] Brak danych dla powrotów < {LIMIT_DNI} dni.")
        return

    liczba_powrotow = len(df)
    procent_globalny = (liczba_powrotow / total_wypisy * 100) if total_wypisy > 0 else 0

    # 3. Agregacja
    stats = df.groupby('readmission_icd10')['age'].agg(['count', 'mean', 'std']).reset_index()
    stats = stats.sort_values(by='count', ascending=False).head(8)
    stats['std'] = stats['std'].fillna(0)

    stats['procent_globalny_icd'] = (stats['count'] / total_wypisy) * 100

    print("\n" + "="*90)
    print(f" RAPORT: WPŁYW DIAGNOZ NA GLOBALNY WSKAŹNIK POWROTÓW (DO {LIMIT_DNI} DNI)")
    print(f" Baza wszystkich wypisów: {total_wypisy}")
    print("="*90)
    print(f"{'KOD ICD-10':<35} | {'ILOŚĆ':<5} | {'% OGÓŁU PACJENTÓW':<18} | {'ŚR. WIEK'}")
    print("-" * 90)

    for _, row in stats.iterrows():
        icd = row['readmission_icd10'][:33]
        count = int(row['count'])
        proc_glob = row['procent_globalny_icd']
        mean_age = row['mean']

        print(f"{icd:<35} | {count:<5} | {proc_glob:.4f}%            | {mean_age:.0f} lat")
    print("-" * 90)

    # --- WIZUALIZACJA ---
    sns.set_style("whitegrid")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 13), constrained_layout=True)

    tytul = (f'ANALIZA POWROTÓW (< {LIMIT_DNI} DNI) WZGLĘDEM OGÓŁU WYPISÓW\n'
             f'Całkowita liczba pacjentów w bazie: {total_wypisy} | Powróciło: {liczba_powrotow} ({procent_globalny:.2f}%)')

    fig.suptitle(tytul, fontsize=16, fontweight='bold', color='#c0392b')

    # WYKRES 1
    sns.barplot(data=stats, x='count', y='readmission_icd10', ax=ax1, palette='Reds_r')
    ax1.set_title(f'Top przyczyny powrotów (Wartości procentowe = % ogółu leczonych)', fontsize=13, fontweight='bold')
    ax1.set_xlabel('Liczba pacjentów')
    ax1.set_ylabel('')

    for container in ax1.containers:
        labels = [f'{width:.0f} ({width/total_wypisy*100:.2f}%)' for width in [bar.get_width() for bar in container]]
        ax1.bar_label(container, labels=labels, padding=3, fontweight='bold')

    # WYKRES 2
    sns.barplot(data=stats, x='mean', y='readmission_icd10', ax=ax2, color='#3498db')
    ax2.errorbar(x=stats['mean'], y=np.arange(len(stats)), xerr=stats['std'],
                 fmt='none', ecolor='black', capsize=5, elinewidth=2)

    ax2.set_title('Profil wiekowy (+/- Odchylenie Standardowe)', fontsize=13, fontweight='bold')
    ax2.set_xlabel('Wiek (lata)')
    ax2.set_ylabel('')

    max_x_val = (stats['mean'] + stats['std']).max()
    ax2.set_xlim(0, max_x_val * 1.25)

    for i, (m, s) in enumerate(zip(stats['mean'], stats['std'])):
        text_pos = m + s + 1.5
        label = f"{m:.0f} lat (±{s:.1f})"
        ax2.text(text_pos, i, label, va='center', fontsize=10, fontweight='bold', color='#2c3e50')

    plt.show()

# Uruchomienie
analiza_kpi_cmj_szczegolowa_procent_globalny(DB_FILE)
