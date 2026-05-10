# Vantage Release Announcement Template

Use this template for GitHub releases, community posts, or changelog summaries.

## Title

Vantage `<version>`: `<short release theme>`

## Summary

Vantage is a local-first AI command center for operators running private models across local and remote machines. This release focuses on `<main capability>`.

## Highlights

- `<highlight 1>`
- `<highlight 2>`
- `<highlight 3>`

## Upgrade Notes

- Back up SQLite before upgrading production deployments.
- Run migrations through the production backend entrypoint or Alembic.
- Review `.env.production.example` for new required variables.

## Verification

```powershell
python -m pytest tests -q
cd frontend
npm run test -- --run
npm run build
```

## Links

- README: `./README.md`
- Operator Guide: `./OPERATOR_GUIDE.md`
- Release Packaging: `./RELEASE.md`
- Security: `./SECURITY.md`
