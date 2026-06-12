# Realty Project — Deployment guide

Quick-reference deployment guide for the Community edition.
Full step-by-step with screenshots: https://docs.bsdinsight.com/vi/realtypro/project/

---

## 1. Architecture

```
Internet
  └── your-domain.com  (DNS provider)
        └── Cloudflare Tunnel  OR  Nginx + Let's Encrypt
              └── Docker network → odoo:8069
                    ├── realtypro-odoo       (Odoo 19)
                    ├── realtypro-db         (PostgreSQL 16)
                    └── realtypro-cloudflared (tunnel, optional)
```

Single-stack pattern, no host ports exposed by default. Public access
through your choice of reverse proxy.

---

## 2. First-time deploy (laptop or VPS)

### 2.1 Pre-flight

```bash
docker --version          # >= 24
docker compose version    # >= v2.20
```

### 2.2 Clone

```bash
git clone https://github.com/bsdinsight/realtypro.git
cd realtypro
```

### 2.3 Configure environment

```bash
cp .env.example .env
nano .env
```

Required:
- `POSTGRES_PASSWORD` — strong random string. **MUST be set BEFORE the
  first `docker compose up -d db`** (Postgres only applies the password
  during data-dir initialization; changing it later requires
  `ALTER USER` inside psql).
- `TUNNEL_TOKEN` — leave empty for now (fill in §4 if using
  Cloudflare Tunnel).

### 2.4 Laptop dev override (optional)

For local development with port exposure + hot-reload:

```bash
cp compose.override.yml.example compose.override.yml
```

The override is gitignored so it never reaches the VPS.

### 2.5 Boot Postgres first

```bash
docker compose up -d db
docker compose logs -f db   # Ctrl-C once "database system is ready"
```

### 2.6 Boot Odoo

```bash
docker compose up -d odoo
docker compose logs -f odoo   # Ctrl-C once "HTTP service running"
```

### 2.7 Create DB and install modules

```bash
# Create empty DB
docker compose exec -T db createdb -U odoo dev

# Install base + Realty Project modules
docker compose exec odoo odoo -d dev \
  -i base,re_loan,rp_estimate,rp_contract,rp_progress,rp_contractor,rp_loan_bridge \
  --stop-after-init --no-http

docker compose restart odoo
```

### 2.8 First login

Laptop: http://localhost:8169/odoo
VPS: through your reverse proxy (see §4)

Login: `admin` / `admin`

> 🔒 **Change the admin password immediately** at Settings → Users →
> Admin → Change Password. The default is unacceptable for any
> internet-exposed instance.

---

## 3. Restore from backup (migration dev → prod)

On source machine:

```bash
./backup.sh
ls -lh backups/
```

Copy to destination:

```bash
scp -r backups/realtypro-2026-06-12_*/ user@destination:/path/restore/
```

On destination (with the stack running):

```bash
cd /path/to/realtypro

# Drop existing dev DB (if any)
docker compose exec -T db psql -U odoo -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='dev';"
docker compose exec -T db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS dev;"
docker compose exec -T db createdb -U odoo dev

# Restore dump
gunzip -c restore/dev.dump.gz | \
  docker compose exec -T db pg_restore -U odoo --no-owner -d dev

# Restore filestore
mkdir -p data/filestore
tar -xzf restore/filestore.tar.gz -C data/filestore/

# Fix permissions (filestore extracted by root → Odoo uid 101 needs ownership)
docker compose exec --user root odoo chown -R odoo:odoo /var/lib/odoo

# Update web.base.url for the new hostname
docker compose exec -T db psql -U odoo -d dev -c "
  UPDATE ir_config_parameter SET value = 'https://your-domain.com'
    WHERE key = 'web.base.url';
  UPDATE ir_config_parameter SET value = 'False'
    WHERE key = 'web.base.url.freeze';
"

# Clear asset cache
docker compose exec -T db psql -U odoo -d dev -c \
  "DELETE FROM ir_attachment WHERE name LIKE '%web.assets%';"

docker compose restart odoo
```

---

## 4. Expose to internet

### Option A: Cloudflare Tunnel (recommended — no open ports)

1. Cloudflare Zero Trust → Networks → **Tunnels** → Create tunnel →
   Connector: **Docker** → copy the `eyJ...` token.

2. Paste the token (only the token value) into `.env`:

```bash
nano .env
# TUNNEL_TOKEN=eyJ...
```

3. In Cloudflare **Public Hostname** tab:
   - Subdomain: `realtypro`
   - Domain: `your-domain.com`
   - Path: **leave empty**
   - Service: `HTTP` → `odoo:8069`

4. Start cloudflared:

```bash
docker compose --profile tunnel up -d cloudflared
docker compose logs -f cloudflared
# Look for "Connection registered" (4 connections)
```

> ⚠️ Don't use `docker run` for cloudflared — it lands on the default
> bridge network and can't resolve `odoo:8069`. Always use `docker
> compose --profile tunnel up -d cloudflared`.

### Option B: Nginx + Let's Encrypt

```bash
sudo apt install nginx certbot python3-certbot-nginx

# Customize the template (server_name, paths)
sudo cp nginx/sites-available/realtypro.conf.example \
        /etc/nginx/sites-available/realtypro.conf
sudo nano /etc/nginx/sites-available/realtypro.conf

sudo ln -s /etc/nginx/sites-available/realtypro.conf \
           /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Get SSL
sudo certbot --nginx -d realtypro.your-domain.com
```

The nginx upstream `odoo` expects port 8169 by default (matching the
laptop dev port in `compose.override.yml`). For a VPS install, either
expose `8169:8069` on the odoo service or change the upstream to
match a different host port.

---

## 5. Routine operations

### Deploy new code

```bash
cd /path/to/realtypro
git pull
docker compose exec odoo odoo -d dev -u <module> --stop-after-init --no-http
docker compose restart odoo
```

For JS/SCSS changes, also clear the asset cache:

```bash
docker compose exec -T db psql -U odoo -d dev -c \
  "DELETE FROM ir_attachment WHERE name LIKE '%web.assets%';"
```

### Daily backup

```bash
./backup.sh /path/to/backup-storage
```

Cron entry (server-local backup):

```cron
30 2 * * * root cd /path/to/realtypro && ./backup.sh /path/to/backup-storage >> /var/log/realtypro-backup.log 2>&1
```

> 🔒 **Production**: ship `/path/to/backup-storage/` off the host
> (S3, B2, rsync to another machine) on a separate cron. Local backups
> won't survive disk failure or ransomware.

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `lookup odoo on 8.8.8.8:53: no such host` | cloudflared on default bridge | `docker compose --profile tunnel up -d cloudflared`, NOT `docker run` |
| 500 PermissionError `/var/lib/odoo/sessions` | Filestore extracted as root after restore | `docker compose exec --user root odoo chown -R odoo:odoo /var/lib/odoo` |
| Login redirects to old hostname | `web.base.url` frozen from restored backup | Re-run the `UPDATE ir_config_parameter` step in §3 |
| Postgres password change ignored | Postgres only applies it during data-dir init | Set in `.env` BEFORE first `up -d db`, or `ALTER USER` inside psql |
| Browser loads stale JS after code update | Asset bundle cache in DB | `DELETE FROM ir_attachment WHERE name LIKE '%web.assets%';` + Cmd+Shift+R |

---

## 7. Security checklist

- [ ] `POSTGRES_PASSWORD` changed from default
- [ ] Odoo admin user password changed from `admin`
- [ ] `admin_passwd` in `odoo.conf` changed from `admin`
- [ ] Daily `backup.sh` cron set + **shipped off-host**
- [ ] Firewall: only outbound HTTPS if using Cloudflare Tunnel; 80/443
      if using nginx
- [ ] `.env` and `compose.override.yml` are in `.gitignore`
- [ ] 2FA on Cloudflare account (if using Tunnel)
- [ ] SSH key + password auth disabled on the VPS
- [ ] Uptime monitor (UptimeRobot, healthchecks.io, etc.)

---

## 8. Upgrade to Enterprise

Realty Project Enterprise adds:
- Bryntum Gantt (full VN localization, Critical Path, Resource Leveling)
- Unlimited projects / contracts / structures
- Multi-company
- Premium support

License: OPL-1. Contact: https://bsdinsight.com/contact

After being granted access to the private repo:

```bash
cd /path/to/parent
git clone https://github.com/bsdinsight/realtypro-enterprise.git
```

Update `docker-compose.yml` to mount the enterprise addons:

```yaml
services:
  odoo:
    volumes:
      - ./addons:/mnt/community-addons
      - /path/to/realtypro-enterprise/addons:/mnt/enterprise-addons
```

Update `odoo.conf` `addons_path` to include the enterprise paths.
Restart + upgrade modules.
