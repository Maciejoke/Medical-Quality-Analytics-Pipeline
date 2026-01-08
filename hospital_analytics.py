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

# --- TWORZENIE STRUKTURY BAZY DANYCH (wykorzystałem moją bazę z Final Project HarvardX) ---
conn = sqlite3.connect(DB_FILE)
sql_schema = """
DROP TABLE IF EXISTS "procedures";
DROP TABLE IF EXISTS "hospitalizations";
DROP TABLE IF EXISTS "doctors";
DROP TABLE IF EXISTS "wards";
DROP TABLE IF EXISTS "patients";
DROP VIEW IF EXISTS "rehospitalizations";
DROP VIEW IF EXISTS "prolonged_stays";

-- Represent patients
CREATE TABLE "patients" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "first_name" TEXT,
    "last_name" TEXT,
    "pesel" TEXT NOT NULL UNIQUE,
    "birth_date" DATE NOT NULL,
    "sex" TEXT NOT NULL
);

-- Represent hospitalizations
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

-- Represent doctors
CREATE TABLE "doctors"(
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "first_name" TEXT NOT NULL,
    "last_name" TEXT NOT NULL,
    "ward_id" INTEGER,
    FOREIGN KEY("ward_id") REFERENCES "wards"("id")
);

-- Represent procedures
CREATE TABLE "procedures"(
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "hospitalization_id" INTEGER,
    "icd9" TEXT NOT NULL,
    "date" DATE NOT NULL,
    FOREIGN KEY("hospitalization_id") REFERENCES "hospitalizations"("id")
);

-- Represents wards
CREATE TABLE "wards"(
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL
);

-- Create indexes to speed common searches
CREATE INDEX "readmissions" ON "hospitalizations"("patient_id","admission_date","discharge_date");
CREATE INDEX "search_icd9" ON "procedures"("icd9");
CREATE INDEX "hosp_ward" ON "hospitalizations"("ward_id");

-- Create view rehospitaliztions
CREATE VIEW "rehospitalizations" AS
SELECT p.pesel,
p.first_name,
p.last_name,
h1.admission_date AS "prev_admission",
h1.discharge_date AS "prev_discharge",
w1.name AS "prev_ward",
h1.icd10 AS "prev_icd10",
h2.admission_date AS "readmission_date",
h2.discharge_date AS "read_discharge_date",
w2.name AS "readmission_ward",
h2.icd10 AS "readmission_icd10",
(JULIANDAY(h1.admission_date) - JULIANDAY(p.birth_date)) / 365.25 AS "age",
JULIANDAY(h2.admission_date) - JULIANDAY(h1.discharge_date) AS "days_between"
FROM hospitalizations h1
JOIN hospitalizations h2 ON h1.patient_id = h2.patient_id
AND h2.admission_date > h1.discharge_date
AND h1.id < h2.id
JOIN patients p ON p.id = h1.patient_id
LEFT JOIN wards w1 ON w1.id = h1.ward_id
LEFT JOIN wards w2 ON w2.id = h2.ward_id
WHERE h1.discharge_date IS NOT NULL;

-- CREATE VIEW prolonged_stays
CREATE VIEW "prolonged_stays" AS
SELECT p.pesel,
p.first_name,
p.last_name,
h.icd10,
h.admission_date,
h.discharge_date,
w.name AS ward_name,
JULIANDAY(h.discharge_date) - JULIANDAY(h.admission_date) AS days_of_stay
FROM hospitalizations h
JOIN patients p ON p.id = h.patient_id
LEFT JOIN wards w ON w.id = h.ward_id
WHERE h.discharge_date IS NOT NULL; """

try:
    conn.executescript(sql_schema)
    print("Struktura bazy danych została pomyślnie utworzona!")
except Exception as e:
    print(f"Błąd podczas tworzenia bazy: {e}")
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
    salt = "TestowyTajnyKlucz2025"
    pesel_str = str(pesel).replace('.0', '').strip()
    return hashlib.sha256((pesel_str + salt).encode()).hexdigest()[:16]

def get_sex_from_pesel(pesel):
    try:
        p = str(pesel).replace('.0', '').strip()
        if len(p) == 11 and p.isdigit():
            return 'K' if int(p[9]) % 2 == 0 else 'M'
    except: pass
    return 'N/D'

# --- IMPORT DANYCH ---
try:
    df = pd.read_excel(Dane testowe.xlsx)
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
    print(f"BŁĄD: {e}")

# --- ANALIZA I WYKRESY ---
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

statystyki = df.groupby('icd10')['LOS'].quantile(0.90).reset_index()
statystyki.rename(columns={'LOS': 'Norma_Dni'}, inplace=True)
df = pd.merge(df, statystyki, on='icd10', how='left')

df_przedluzone = df[df['LOS'] > df['Norma_Dni']].copy()

if df_przedluzone.empty:
    print("Brak danych.")
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


    fig, axes = plt.subplots(3, 1, figsize=(14, 22), layout='constrained')
    sns.set_style("whitegrid")

    # Wykres 1
    sns.barplot(ax=axes[0], x='Liczba', y='icd10', data=agg, color='#3498db')
    axes[0].set_title('1. SKALA PROBLEMU: Ilu pacjentów przekroczyło normę?', fontsize=16, fontweight='bold', loc='left')
    axes[0].set_xlabel('Liczba pacjentów', fontsize=12)
    axes[0].bar_label(axes[0].containers[0], padding=3, fmt='%d', fontsize=12, fontweight='bold')

    # Wykres 2
    df_czas = agg.melt(id_vars='icd10', value_vars=['Czas_Norma', 'Czas_przedłużony'],
                        var_name='Typ_Czasu', value_name='Dni')
    df_czas['Typ_Czasu'] = df_czas['Typ_Czasu'].replace({'Czas_Norma': 'Norma', 'Czas_przedłużony': 'przedłużony'})

    sns.barplot(ax=axes[1], x='Dni', y='icd10', hue='Typ_Czasu', data=df_czas,
                palette={'Norma': '#2ecc71', 'przedłużony': '#e74c3c'})

    axes[1].set_title('2. ANALIZA CZASU: Norma (Zielony) vs przedłużone (Czerwony)', fontsize=16, fontweight='bold', loc='left')
    axes[1].set_xlabel('Liczba dni', fontsize=12)
    axes[1].legend(loc='lower right')
    for container in axes[1].containers:
        axes[1].bar_label(container, fmt='%.1f dni', padding=3, fontsize=10)

    # Wykres 3
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

    axes[2].set_title('3. DEMOGRAFIA: Średnia wieku + Odchylenie Standardowe (czarne linie)', fontsize=16, fontweight='bold', loc='left')
    axes[2].set_xlabel('Wiek pacjenta (lata)', fontsize=12)

    for i, row in agg.iterrows():
        label = f"{row['Wiek_Srednia']:.0f} lat\n(±{row['Wiek_SD']:.0f})"
        axes[2].text(row['Wiek_Srednia'] + row['Wiek_SD'] + 1, i, label,
                     va='center', fontsize=10, fontweight='bold', color='#4a235a')

    plt.show()
