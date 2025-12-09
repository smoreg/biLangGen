"""Global word dictionary database.

Stores words and translations across all projects.
Allows manual curation (marking words as skip, editing translations).
"""

import sqlite3
from pathlib import Path
from typing import Optional


class WordDictionary:
    """Global dictionary for rare words across all projects.

    SQLite-based with skip flags for cognates, proper nouns, etc.
    """

    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "general.db"
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                lang TEXT NOT NULL,
                lemma TEXT,
                zipf REAL,
                translation TEXT,
                translation_lang TEXT,
                skip INTEGER DEFAULT 0,
                skip_reason TEXT,
                source_project TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(word, lang, translation_lang)
            );

            CREATE INDEX IF NOT EXISTS idx_words_word ON words(word);
            CREATE INDEX IF NOT EXISTS idx_words_lang ON words(lang);
            CREATE INDEX IF NOT EXISTS idx_words_skip ON words(skip);
            CREATE INDEX IF NOT EXISTS idx_words_lang_pair ON words(lang, translation_lang);

            -- Skip reasons:
            -- 'cognate' - sounds similar in both languages
            -- 'proper_noun' - name/place (transliterated, not translated)
            -- 'common' - too common word (zipf > threshold)
            -- 'manual' - manually marked by user
        """)
        self.conn.commit()

    def add_word(
        self,
        word: str,
        lang: str,
        translation: str = None,
        translation_lang: str = None,
        lemma: str = None,
        zipf: float = None,
        source_project: str = None,
        skip: bool = False,
        skip_reason: str = None,
    ) -> int:
        """Add or update word in dictionary. Returns word ID."""
        cursor = self.conn.execute(
            """
            INSERT INTO words (word, lang, lemma, zipf, translation, translation_lang,
                              skip, skip_reason, source_project)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(word, lang, translation_lang) DO UPDATE SET
                lemma = COALESCE(excluded.lemma, lemma),
                zipf = COALESCE(excluded.zipf, zipf),
                translation = COALESCE(excluded.translation, translation),
                skip = CASE WHEN excluded.skip = 1 THEN 1 ELSE skip END,
                skip_reason = COALESCE(excluded.skip_reason, skip_reason),
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            (word.lower(), lang, lemma, zipf, translation, translation_lang,
             1 if skip else 0, skip_reason, source_project)
        )
        row = cursor.fetchone()
        self.conn.commit()
        return row[0] if row else None

    def get_word(self, word: str, lang: str, translation_lang: str = None) -> Optional[dict]:
        """Get word from dictionary."""
        if translation_lang:
            cursor = self.conn.execute(
                "SELECT * FROM words WHERE word = ? AND lang = ? AND translation_lang = ?",
                (word.lower(), lang, translation_lang)
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM words WHERE word = ? AND lang = ?",
                (word.lower(), lang)
            )
        row = cursor.fetchone()
        return dict(row) if row else None

    def is_skip(self, word: str, lang: str, translation_lang: str = None) -> bool:
        """Check if word should be skipped."""
        entry = self.get_word(word, lang, translation_lang)
        return entry is not None and entry.get('skip') == 1

    def mark_skip(self, word: str, lang: str, reason: str, translation_lang: str = None):
        """Mark word to skip (cognate, proper noun, etc)."""
        # First ensure word exists
        existing = self.get_word(word, lang, translation_lang)
        if existing:
            if translation_lang:
                self.conn.execute(
                    """UPDATE words SET skip = 1, skip_reason = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE word = ? AND lang = ? AND translation_lang = ?""",
                    (reason, word.lower(), lang, translation_lang)
                )
            else:
                self.conn.execute(
                    """UPDATE words SET skip = 1, skip_reason = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE word = ? AND lang = ?""",
                    (reason, word.lower(), lang)
                )
        else:
            # Add new word with skip flag
            self.add_word(word, lang, translation_lang=translation_lang, skip=True, skip_reason=reason)
        self.conn.commit()

    def mark_unskip(self, word: str, lang: str, translation_lang: str = None):
        """Unmark word from skip."""
        if translation_lang:
            self.conn.execute(
                """UPDATE words SET skip = 0, skip_reason = NULL, updated_at = CURRENT_TIMESTAMP
                   WHERE word = ? AND lang = ? AND translation_lang = ?""",
                (word.lower(), lang, translation_lang)
            )
        else:
            self.conn.execute(
                """UPDATE words SET skip = 0, skip_reason = NULL, updated_at = CURRENT_TIMESTAMP
                   WHERE word = ? AND lang = ?""",
                (word.lower(), lang)
            )
        self.conn.commit()

    def update_translation(self, word: str, lang: str, translation: str, translation_lang: str):
        """Update word translation."""
        self.conn.execute(
            """UPDATE words SET translation = ?, updated_at = CURRENT_TIMESTAMP
               WHERE word = ? AND lang = ? AND translation_lang = ?""",
            (translation, word.lower(), lang, translation_lang)
        )
        self.conn.commit()

    def get_skip_words(self, lang: str, translation_lang: str = None) -> set[str]:
        """Get set of words to skip for given language pair."""
        if translation_lang:
            cursor = self.conn.execute(
                "SELECT word FROM words WHERE lang = ? AND translation_lang = ? AND skip = 1",
                (lang, translation_lang)
            )
        else:
            cursor = self.conn.execute(
                "SELECT word FROM words WHERE lang = ? AND skip = 1",
                (lang,)
            )
        return {row[0] for row in cursor.fetchall()}

    def get_translations(self, lang: str, translation_lang: str) -> dict[str, str]:
        """Get all translations for language pair as dict."""
        cursor = self.conn.execute(
            "SELECT word, translation FROM words WHERE lang = ? AND translation_lang = ? AND translation IS NOT NULL",
            (lang, translation_lang)
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def import_from_project(self, project_name: str, project_db_path: Path) -> int:
        """Import rare words from project database."""
        proj_conn = sqlite3.connect(str(project_db_path))
        proj_conn.row_factory = sqlite3.Row

        # Get project metadata
        meta = proj_conn.execute("SELECT key, value FROM meta").fetchall()
        meta_dict = {row['key']: row['value'] for row in meta}
        target_lang = meta_dict.get('target_lang', 'es')
        source_lang = meta_dict.get('source_lang', 'ru')

        # Import words
        words = proj_conn.execute(
            "SELECT word, zipf, translation FROM rare_words WHERE translation IS NOT NULL"
        ).fetchall()

        imported = 0
        for row in words:
            word, zipf, translation = row
            self.add_word(
                word=word,
                lang=target_lang,
                translation=translation,
                translation_lang=source_lang,
                zipf=zipf,
                source_project=project_name,
            )
            imported += 1

        proj_conn.close()
        return imported

    def import_from_all_projects(self, projects_dir: Path) -> dict[str, int]:
        """Import from all projects in directory."""
        results = {}
        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            db_path = project_dir / "project.db"
            if not db_path.exists():
                continue
            try:
                count = self.import_from_project(project_dir.name, db_path)
                results[project_dir.name] = count
            except Exception as e:
                results[project_dir.name] = f"error: {e}"
        return results

    def stats(self) -> dict:
        """Get dictionary statistics."""
        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN skip = 1 THEN 1 ELSE 0 END) as skipped,
                SUM(CASE WHEN translation IS NOT NULL THEN 1 ELSE 0 END) as translated,
                COUNT(DISTINCT lang) as languages,
                COUNT(DISTINCT source_project) as projects
            FROM words
        """)
        row = cursor.fetchone()

        # Skip reasons breakdown
        reasons = self.conn.execute("""
            SELECT skip_reason, COUNT(*) as count
            FROM words WHERE skip = 1 AND skip_reason IS NOT NULL
            GROUP BY skip_reason
        """).fetchall()

        # Language pairs
        pairs = self.conn.execute("""
            SELECT lang || '->' || translation_lang as pair, COUNT(*) as count
            FROM words
            WHERE translation_lang IS NOT NULL
            GROUP BY lang, translation_lang
        """).fetchall()

        return {
            "total_words": row['total'] or 0,
            "skipped": row['skipped'] or 0,
            "translated": row['translated'] or 0,
            "languages": row['languages'] or 0,
            "projects": row['projects'] or 0,
            "skip_reasons": {r['skip_reason']: r['count'] for r in reasons},
            "language_pairs": {r['pair']: r['count'] for r in pairs},
        }

    def search(self, query: str, lang: str = None, translation_lang: str = None,
               limit: int = 50, offset: int = 0) -> list[dict]:
        """Search words by prefix with pagination."""
        conditions = ["word LIKE ?"]
        params = [f"{query.lower()}%"]

        if lang:
            conditions.append("lang = ?")
            params.append(lang)
        if translation_lang:
            conditions.append("translation_lang = ?")
            params.append(translation_lang)

        where = " AND ".join(conditions)
        params.extend([limit, offset])

        cursor = self.conn.execute(
            f"SELECT * FROM words WHERE {where} ORDER BY word LIMIT ? OFFSET ?",
            params
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_words(self, lang: str = None, translation_lang: str = None,
                   skip_only: bool = False, limit: int = 100, offset: int = 0) -> list[dict]:
        """List words with pagination and filters."""
        conditions = []
        params = []

        if lang:
            conditions.append("lang = ?")
            params.append(lang)
        if translation_lang:
            conditions.append("translation_lang = ?")
            params.append(translation_lang)
        if skip_only:
            conditions.append("skip = 1")

        where = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        cursor = self.conn.execute(
            f"SELECT * FROM words WHERE {where} ORDER BY word LIMIT ? OFFSET ?",
            params
        )
        return [dict(row) for row in cursor.fetchall()]

    def count(self, lang: str = None, translation_lang: str = None, skip_only: bool = False) -> int:
        """Count words with filters."""
        conditions = []
        params = []

        if lang:
            conditions.append("lang = ?")
            params.append(lang)
        if translation_lang:
            conditions.append("translation_lang = ?")
            params.append(translation_lang)
        if skip_only:
            conditions.append("skip = 1")

        where = " AND ".join(conditions) if conditions else "1=1"

        cursor = self.conn.execute(f"SELECT COUNT(*) FROM words WHERE {where}", params)
        return cursor.fetchone()[0]

    def close(self):
        """Close database connection."""
        self.conn.close()


# Singleton instance
_dictionary: Optional[WordDictionary] = None


def get_dictionary(db_path: Path = None) -> WordDictionary:
    """Get global dictionary instance."""
    global _dictionary
    if _dictionary is None:
        _dictionary = WordDictionary(db_path)
    return _dictionary
