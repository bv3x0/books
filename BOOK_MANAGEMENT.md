# Book Management Guide

This guide explains how to safely delete or rename books in the system.

## System Architecture

The system maintains data in multiple interconnected locations:

```
notes/book-name.md           ← Markdown summary
index/book-name.json         ← Structured data (claims, concepts, entities)
index/vectors.db             ← Embeddings for semantic search
index/_concepts.json         ← Concept registry (tracks which books use which concepts)
```

## Deleting a Book

**⚠️ WARNING:** Manually deleting files leaves orphaned data in the vector database and concept registry.

### Safe Method: Use the deletion script

```bash
# Preview what would be deleted
python3 app/cli/delete_book.py "book name" --dry-run

# Actually delete
python3 app/cli/delete_book.py "book name"
```

**What it does:**
1. ✅ Deletes `notes/book-name.md`
2. ✅ Deletes `index/book-name.json`
3. ✅ Removes all claims from vector database
4. ✅ Removes book references from concept registry

### Manual Deletion (NOT RECOMMENDED)

If you must delete manually:

```bash
# Delete files
rm "notes/book-name.md"
rm "index/book-name.json"

# Then reconcile vector database and concept registry
python3 scripts/reconcile_vectors.py --apply-all
```

## Renaming a Book

**⚠️ WARNING:** Simply renaming the markdown file creates a mismatch with the JSON index.

### Safe Method: Use the rename script

```bash
# Preview changes
python3 app/cli/rename_book.py "old name" "new name" --dry-run

# Actually rename
python3 app/cli/rename_book.py "old name" "new name"
```

**What it does:**
1. ✅ Renames `notes/old-name.md` → `notes/new-name.md`
2. ✅ Updates book title in JSON index
3. ✅ Renames `index/old-name.json` → `index/new-name.json`
4. ✅ Updates all claims in vector database
5. ✅ Updates all concept references

### Manual Renaming (NOT RECOMMENDED)

If you must rename manually, you'll need to:

1. Rename the markdown file
2. Rename the JSON index file
3. Update the `book.title` field inside the JSON
4. Run: `python3 scripts/reconcile_vectors.py --apply-all`

## Troubleshooting

### "Book has orphaned data after deletion"

If you deleted files manually without using the script:

```bash
# Repair vector/database drift from current notes/index state
python3 scripts/reconcile_vectors.py --apply-all
```

### "Renamed book appears twice in searches"

The old name still exists in the vector database:

```bash
# Use the deletion script on the old name
python3 app/cli/delete_book.py "old name"
```

## Best Practices

1. **Always use the provided scripts** for deletion and renaming
2. **Run dry-run first** to preview changes
3. **Keep backups** before bulk operations:
   ```bash
   cp -r notes/ backups/notes-$(date +%Y%m%d)/
   cp -r index/ backups/index-$(date +%Y%m%d)/
   ```
4. **Test semantic search** after major changes to verify data integrity

## Quick Reference

| Operation | Command | Safe? |
|-----------|---------|-------|
| Delete book | `python3 app/cli/delete_book.py "name"` | ✅ |
| Rename book | `python3 app/cli/rename_book.py "old" "new"` | ✅ |
| Manual file deletion | `rm notes/name.md` | ❌ Leaves orphans |
| Manual file rename | `mv notes/old.md notes/new.md` | ❌ Creates mismatch |
