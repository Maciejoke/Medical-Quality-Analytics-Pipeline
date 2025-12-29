# Medical Quality Analytics Pipeline

## O projekcie
Prototypowy system analityczny stworzony w celu monitorowania jakości i efektywności leczenia w podmiotach leczniczych. Projekt łączy inżynierię danych (ETL) z analizą statystyczną w celu optymalizacji czasu hospitalizacji.

## Kluczowe Funkcjonalności
Bezpieczeństwo (RODO): Autorski moduł anonimizacji danych wrażliwych z wykorzystaniem skrótów SHA-256 i "soli".
Architektura SQL: Relacyjna baza danych (SQLite) z widokami monitorującymi rehospitalizacje i przedłużone pobyty.
Analiza Statystyczna: Wyznaczanie norm pobytu na podstawie 90. kwantyla dla poszczególnych kodów ICD-10.
Wizualizacja: Automatyczne generowanie raportów dotyczących skali problemu, odchyleń od normy i demografii grup ryzyka.

## Technologie
Język: Python
Biblioteki: Pandas, Matplotlib, Seaborn, SQLite3, Hashlib

## Jak uruchomić?
1. Sklonuj repozytorium razem z plikiem "Dane testowe.xlxs".
2. Uruchom skrypt.

## DANE DO PROJEKTU ZOSTAŁY WYGENEROWANE
