-- schema v2: 合同工程名录（工程名称精确匹配）

CREATE TABLE IF NOT EXISTS project_contracts (
    project_name TEXT NOT NULL PRIMARY KEY,
    manager TEXT,
    handler TEXT,
    source_file TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_project_contracts_manager ON project_contracts(manager);
CREATE INDEX IF NOT EXISTS idx_project_contracts_handler ON project_contracts(handler);

INSERT OR IGNORE INTO schema_version (version) VALUES (2);
