# Changelog

All notable changes to Vault will be documented here.
Versions follow [Semantic Versioning](https://semver.org): `MAJOR.MINOR.PATCH`

- **MAJOR** — breaking changes (e.g. DB schema requires migration)
- **MINOR** — new features, backwards compatible
- **PATCH** — bug fixes, visual tweaks

---

## [Unreleased]

---

## [v1.1.0] — 2026-04-10
### Added
- PDF417 barcode format support (selectable per card at creation time)
- Barcode format stored in database (`barcode_fmt` column, auto-migrated)
- Barcode aspect ratio matches real-world gift card reference (1.744:1)

### Changed
- Barcodes now fill the full scan panel width for easier scanning
- Scan panel side padding reduced to maximise barcode display area

---

## [v1.0.0] — 2026-04-08
### Added
- Initial release
- Gift card wallet with store templates and live card designer
- Code 128 barcodes rendered client-side
- Transaction history with inline editing and balance tracking
- 3 built-in starter templates (Aurora, Prism, Obsidian)
- 9 card pattern overlays
- Docker image published to Docker Hub (`dockersette/vault`)
- Fresh installs start with zero cards
