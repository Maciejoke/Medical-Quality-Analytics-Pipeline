# Medical Quality Analytics Pipeline 🏥📊

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![SQL](https://img.shields.io/badge/SQL-SQLite-orange)
![Data Engineering](https://img.shields.io/badge/Data-Engineering-green)
![Status](https://img.shields.io/badge/Status-Prototype-yellow)

## 📌 O projekcie
**Medical Quality Analytics Pipeline** to zautomatyzowany proces ETL (Extract, Transform, Load) zaprojektowany do monitorowania kluczowych wskaźników jakości (KPI) w placówkach medycznych.

Projekt powstał w celu rozwiązania problemu manualnego raportowania wskaźników takich jak:
* Przedłużone pobyty.

System wspiera procesy decyzyjne i pomaga w utrzymaniu standardów wymaganych do **Akredytacji** oraz raportowania do **NFZ**.

> **Uwaga:** Ze względu na wrażliwy charakter danych medycznych (RODO/GDPR), repozytorium zawiera wyłącznie **wygenerowane dane syntetyczne**, które zachowują strukturę statystyczną oryginału, ale nie zawierają prawdziwych danych osobowych.

## ⚙️ Architektura i Funkcjonalności

Projekt realizuje pełny przepływ danych:

1.  **Data Ingestion:** Pobieranie surowych danych z plików eksportowych (Excel/XLSX).
2.  **Data Sanitization (RODO):** Autorski moduł anonimizacji. Dane osobowe (PESEL) są haszowane algorytmem **SHA-256** z użyciem dynamicznej "soli" przed trafieniem do bazy analitycznej.
3.  **Data Warehousing:** Transformacja danych do postaci relacyjnej (3NF) w bazie **SQLite**.
    * Struktura: `Patients`, `Hospitalizations`, `Doctors`, `Wards`.
    * Wykorzystanie **Widoków SQL (Views)** do agregacji logiki biznesowej.
4.  **Analytics Logic:** Wyznaczanie norm pobytu na podstawie **90. percentyla** dla poszczególnych kodów ICD-10 (eliminacja wpływu wartości skrajnych).
5.  **Visualization:** Automatyczne generowanie dashboardów w `Matplotlib` i `Seaborn`.

## 🛠️ Technologie

* **Język:** Python 3.x
* **Baza danych:** SQLite3 (z wykorzystaniem `sql_schema` i indeksowania)
* **Biblioteki:**
    * `Pandas` & `NumPy` - manipulacja danymi i obliczenia wektorowe.
    * `Hashlib` - kryptografia i bezpieczeństwo danych.
    * `Seaborn` & `Matplotlib` - warstwa wizualizacyjna.

## 🚀 Jak uruchomić?

1.  **Sklonuj repozytorium:**
    ```bash
    git clone [https://github.com/TwojNick/medical-quality-pipeline.git](https://github.com/TwojNick/medical-quality-pipeline.git)
    cd medical-quality-pipeline
    ```

2.  **Zainstaluj wymagane biblioteki:**
    ```bash
    pip install pandas matplotlib seaborn openpyxl
    ```

3.  **Uruchom proces ETL:**
    Upewnij się, że plik `Dane testowe.xlsx` znajduje się w katalogu głównym.
    ```bash
    python main.py
    ```

4.  **Wynik:**
    * Skrypt utworzy bazę danych `szpital.db`.
    * Zostaną wygenerowane wykresy analityczne w nowym oknie.
    * Logi z importu pojawią się w konsoli.

## 📊 Przykładowe wizualizacje
![Wykres1](https://github.com/Maciejoke/Medical-Quality-Analytics-Pipeline/blob/078cdf02752bb28ee7448e908d670a56d00b5fab/Wizualizacje%20Testowe.png)

---
*Autor: Maciej Urban*
