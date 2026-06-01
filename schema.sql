CREATE TABLE IF NOT EXISTS hcl_documente (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id   TEXT UNIQUE,
    an            INTEGER,
    numar_hcl     TEXT,
    data_adoptare TEXT,
    titlu         TEXT,
    obiect        TEXT,
    text_complet  TEXT,
    url_original  TEXT
);

CREATE TABLE IF NOT EXISTS topicuri (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nume     TEXT UNIQUE,
    aliasuri TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS hcl_fts USING fts5(
    titlu, text_complet,
    content='hcl_documente', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS hcl_ai AFTER INSERT ON hcl_documente BEGIN
    INSERT INTO hcl_fts(rowid, titlu, text_complet)
    VALUES (new.id, new.titlu, new.text_complet);
END;
CREATE TRIGGER IF NOT EXISTS hcl_ad AFTER DELETE ON hcl_documente BEGIN
    INSERT INTO hcl_fts(hcl_fts, rowid, titlu, text_complet)
    VALUES ('delete', old.id, old.titlu, old.text_complet);
END;
CREATE TRIGGER IF NOT EXISTS hcl_au AFTER UPDATE ON hcl_documente BEGIN
    INSERT INTO hcl_fts(hcl_fts, rowid, titlu, text_complet)
    VALUES ('delete', old.id, old.titlu, old.text_complet);
    INSERT INTO hcl_fts(rowid, titlu, text_complet)
    VALUES (new.id, new.titlu, new.text_complet);
END;
