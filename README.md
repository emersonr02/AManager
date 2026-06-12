# AManager

A robust, local Manufacturing Execution System (MES) designed specifically for Additive Manufacturing (AM) laboratories and 3D printing farms. 

This tool was developed to replace manual spreadsheets and decentralized tracking, providing a unified dashboard to manage print orders, track machine park status, and log production metrics across different technologies (FDM, SLA, and SLS).

## 🚀 Key Features

* **Order Management (Backlog):** Centralized system to register, track, and update internal production requests.
* **Production Logging:** Intuitive interface to launch production orders, automatically calculating material consumption (including specific formulas for SLS powder refresh rates).
* **Machine Park Control:** Real-time tracking of 3D printers, operational status, and maintenance history.
* **Quality & Downtime Tracking:** Standardized root-cause analysis using Non-Conformity (NC) codes for failed prints.
* **Analytical Export:** One-click CSV generation for Pareto charts, material consumption summaries, and machine load balancing.

## 🏗️ Architecture & Technology

The system is built entirely in **Python** and utilizes a modular, MVC-inspired architecture to separate the graphical interface from business logic and data handling.

* **GUI:** Built with [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) for a modern, dark-mode user experience.
* **Data Persistence:** Local JSON files acting as a lightweight database.
* **Concurrency Control:** Custom file-locking mechanism in the `JSONManager` to ensure data integrity when multiple engineers access the system simultaneously via a shared network drive. No SQL server installation required.

### Directory Structure

```text
MES_i3D_System/
├── main.py                 # Application entry point
├── config/                 # Global settings, paths, and static dictionaries
├── data/                   # Local JSON database files
├── database/               # JSONManager with file-locking concurrency protocol
├── models/                 # Data classes and object structures
├── services/               # Business logic, material calculations, and CSV export
└── gui/                    # Separated CustomTkinter tab interfaces and dialogs
