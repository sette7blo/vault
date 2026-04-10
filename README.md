# Vault — Self-Hosted Gift Card Wallet

A privacy-first gift card wallet you run yourself. Store card numbers, PINs, balances, and transaction history with real scannable barcodes (Code 128 & PDF417). Fully customisable card templates with a live design builder. Runs entirely in Docker on a single port.

---

## Features

- Scannable barcodes — Code 128 and PDF417 supported
- Custom card templates with gradient, pattern, and font options
- Transaction history with inline editing
- Cards grouped by store with combined balance
- No account, no cloud, no tracking — your data stays on your server

---

## Quick Start

No build required — pull straight from Docker Hub.

**1. Create a `docker-compose.yml`:**

```yaml
services:
  vault:
    image: dockersette/vault:latest
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
    environment:
      - DB_PATH=/data/vault.db
    restart: unless-stopped
```

**2. Start it:**

```bash
docker compose up -d
```

**3. Open it:**

```
http://YOUR_SERVER_IP:8080
```

Data is stored in `./data/vault.db` and persists across restarts and updates.

---

## Updating

```bash
docker compose pull && docker compose up -d
```

---

## Port

Default is **8080**. Change the left side of the ports mapping to use a different host port:

```yaml
ports:
  - "9000:8080"   # serve on port 9000 instead
```

---

## Security

Vault has no authentication. It is designed for **personal / home server use only**, behind a firewall or VPN. Do not expose port 8080 to the public internet without adding an auth layer (e.g. HTTP Basic Auth via an nginx reverse proxy).

---

## License

MIT
