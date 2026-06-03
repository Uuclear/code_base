-- ReportDesk SQLite schema (v1)
-- report_no is globally unique (normalized uppercase)

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL PRIMARY KEY
);

INSERT OR IGNORE INTO schema_version (version) VALUES (1);

CREATE TABLE IF NOT EXISTS reports (
    report_no TEXT NOT NULL PRIMARY KEY,
    source_channel TEXT,
    decode_method TEXT,
    scrape_status TEXT DEFAULT 'ok',
    order_no TEXT,
    testing_report_id TEXT,
    testing_order_id INTEGER,
    anti_fake_code TEXT,
    institute_r_id_raw TEXT,
    project_name TEXT,
    project_address TEXT,
    project_part TEXT,
    section_folder TEXT,
    project_section_extra TEXT,
    project_serial_no TEXT,
    unit_name TEXT,
    unit_code TEXT,
    institute_name TEXT,
    institute_address TEXT,
    institute_phone TEXT,
    institute_postcode TEXT,
    construction_unit TEXT,
    witness_unit TEXT,
    sampler TEXT,
    witness TEXT,
    contract_no TEXT,
    total_fee REAL,
    consign_date TEXT,
    report_date TEXT,
    testing_date TEXT,
    sampling_date TEXT,
    order_time TEXT,
    report_status TEXT,
    consign_type TEXT,
    testing_type_code TEXT,
    testing_type_name TEXT,
    change_status TEXT,
    testing_result TEXT,
    conclusion_summary TEXT,
    scrape_json TEXT,
    scraped_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    organize_project_dir TEXT,
    organize_section_dir TEXT
);

CREATE TABLE IF NOT EXISTS report_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_no TEXT NOT NULL REFERENCES reports(report_no) ON DELETE CASCADE,
    file_index INTEGER NOT NULL,
    original_path TEXT NOT NULL,
    stored_path TEXT,
    original_filename TEXT,
    file_hash TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (report_no, file_index)
);

CREATE TABLE IF NOT EXISTS report_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_no TEXT NOT NULL REFERENCES reports(report_no) ON DELETE CASCADE,
    seq INTEGER NOT NULL DEFAULT 0,
    sample_no TEXT,
    sample_name TEXT,
    specification TEXT,
    grade TEXT,
    project_part TEXT,
    exam_result TEXT,
    testing_date TEXT,
    manufacturer TEXT,
    delegate_quantity TEXT,
    molding_date TEXT,
    age_time TEXT,
    extra_json TEXT
);

CREATE TABLE IF NOT EXISTS report_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_no TEXT NOT NULL REFERENCES reports(report_no) ON DELETE CASCADE,
    task_id INTEGER,
    sample_id INTEGER,
    task_name TEXT,
    sample_no TEXT,
    sample_name TEXT,
    task_status_name TEXT,
    dept_name TEXT,
    editor TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS report_audit_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_no TEXT NOT NULL REFERENCES reports(report_no) ON DELETE CASCADE,
    audit_user_name TEXT,
    audit_result TEXT,
    create_time TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS integrated_list_row (
    report_no TEXT NOT NULL PRIMARY KEY REFERENCES reports(report_no) ON DELETE CASCADE,
    testing_order_id INTEGER,
    testing_order_no TEXT,
    testing_order_contract_no TEXT,
    testing_order_unit_name TEXT,
    testing_order_unit_code TEXT,
    project_name TEXT,
    testing_institute_name TEXT,
    testing_type_code TEXT,
    testing_order_type_desp TEXT,
    testing_order_status_code TEXT,
    testing_order_time TEXT,
    sampling_date TEXT,
    total_fee REAL,
    sample_count INTEGER,
    report_count INTEGER,
    change_status TEXT
);

CREATE TABLE IF NOT EXISTS batch_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    total_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    output_root TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS batch_job_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES batch_jobs(id) ON DELETE CASCADE,
    image_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    report_no TEXT,
    error_message TEXT,
    file_index INTEGER,
    stored_path TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT NOT NULL PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_report_files_report_no ON report_files(report_no);
CREATE INDEX IF NOT EXISTS idx_reports_project_name ON reports(project_name);
CREATE INDEX IF NOT EXISTS idx_reports_unit_name ON reports(unit_name);
CREATE INDEX IF NOT EXISTS idx_batch_job_items_job ON batch_job_items(job_id);
