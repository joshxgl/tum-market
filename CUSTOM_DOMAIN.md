# Custom Domain Setup Guide

## Prerequisites

- A registered domain (e.g., from GoDaddy, Namecheap, Google Domains, etc.)
- Admin access to your domain's DNS settings
- Your GitHub Pages site already deployed (https://joshxgl.github.io/tum-market/)

---

## Option 1: Using GitHub's Nameservers (Recommended)

### Step 1: Configure GitHub Pages Settings

1. Go to your GitHub repository: https://github.com/joshxgl/tum-market
2. Click **Settings** → **Pages** (left sidebar)
3. Under "Custom domain", enter your domain (e.g., `tum-market.com` or `marketplace.tum-market.com`)
4. Click **Save**
5. GitHub will automatically create a **CNAME** file in your repository
6. **Check "Enforce HTTPS"** for secure browsing

### Step 2: Update DNS Records

This depends on your domain registrar. Contact their support or follow their documentation:

**For most registrars (GoDaddy, Namecheap, Google Domains):**

Update your DNS settings to point your domain to GitHub Pages:

```
CNAME record:
  Name/Host: @ (or leave blank)
  Value: joshxgl.github.io
  TTL: 3600 (or auto)
```

**Example for www subdomain:**
```
CNAME record:
  Name/Host: www
  Value: joshxgl.github.io
  TTL: 3600
```

### Step 3: Verify DNS Setup

1. Open terminal/command prompt
2. Run: `nslookup tum-market.com`
3. You should see it pointing to `joshxgl.github.io`

### Step 4: Wait for DNS Propagation

- DNS changes can take **15 minutes to 48 hours** to fully propagate
- Once done, your site will be accessible at your custom domain
- GitHub automatically manages SSL/HTTPS certificates

---

## Option 2: Using GitHub's IP Addresses (A Records)

If CNAME doesn't work, use GitHub's IP addresses:

### Step 1: Get GitHub's IP Addresses

Add four A records pointing to GitHub's servers:

```
A Records:
  185.199.108.153
  185.199.109.153
  185.199.110.153
  185.199.111.153
```

### Step 2: Update DNS

In your domain registrar's DNS settings:

```
A record 1: 185.199.108.153
A record 2: 185.199.109.153
A record 3: 185.199.110.153
A record 4: 185.199.111.153
```

### Step 3: Add CNAME for WWW (Optional)

To support `www` prefix:

```
CNAME record:
  Name/Host: www
  Value: joshxgl.github.io
```

---

## Option 3: Subdomain Only

If you want your site at `marketplace.tum-market.com`:

### Step 1: Add Subdomain CNAME

```
CNAME record:
  Name/Host: marketplace
  Value: joshxgl.github.io
```

### Step 2: GitHub Pages Custom Domain

1. Go to Settings → Pages
2. Enter: `marketplace.tum-market.com`
3. Click Save

---

## Testing Your Custom Domain

After DNS propagates, verify:

1. **Test 1:** Visit `https://your-domain.com` in your browser
2. **Test 2:** Check HTTPS works (padlock icon in browser)
3. **Test 3:** Verify the page loads your marketplace
4. **Test 4:** Test in dev tools (F12) → check Console for any errors

---

## Domain Registrars & DNS Setup

### GoDaddy
1. Login to GoDaddy
2. Go to **My Products** → Select your domain
3. Click **Manage** → **DNS**
4. Update or add CNAME/A records as shown above

### Namecheap
1. Login to Namecheap
2. Go to **Domain List**
3. Click **Manage** next to your domain
4. Go to **Advanced DNS**
5. Add/edit CNAME or A records

### Google Domains
1. Login to Google Domains
2. Select your domain
3. Click **DNS** (left sidebar)
4. Under "Custom Records", add CNAME or A records

### Hover, Name.com, etc.
1. Login to your registrar
2. Find **DNS** or **Domain Management**
3. Add CNAME or A records as shown above

---

## Troubleshooting

### Domain not resolving?
- Wait 24-48 hours for DNS to propagate
- Use `nslookup` or `dig` to check DNS records
- Clear your browser cache (Ctrl+Shift+Delete)

### HTTPS not working?
- Wait 24 hours after DNS setup
- GitHub automatically provisions SSL certificates
- Ensure "Enforce HTTPS" is checked in GitHub Pages settings

### Site shows GitHub 404?
- Verify CNAME file exists in your repository
- Check custom domain is set in GitHub Pages settings
- Ensure your `docs/` folder is being used as the source

### Mixed content warning?
- Ensure HTTPS is enforced in GitHub Pages settings
- Update any hardcoded `http://` URLs to `https://` or protocol-relative (`//`)

---

## CNAME File

GitHub auto-generates a CNAME file. You'll see it in your repository at `.github/CNAME`. 

Example content:
```
tum-market.com
```

Don't manually edit this unless you know what you're doing. GitHub manages it automatically.

---

## SSL/TLS Certificate

GitHub Pages provides **free SSL/TLS certificates** via Let's Encrypt. Your domain will have:

- ✅ Automatic certificate provisioning
- ✅ HTTPS by default
- ✅ Auto-renewal
- ✅ No additional cost

Just enable "Enforce HTTPS" in GitHub Pages settings.

---

## Next Steps After Domain Setup

1. **Update Links:**
   - Update `README.md` to reference new domain
   - Share new URL with your team

2. **Email Configuration (Optional):**
   - If you want custom email (e.g., support@tum-market.com), configure MX records via your registrar
   - Services like Gmail, Proton Mail, Zoho support custom domains

3. **Analytics (Optional):**
   - Add Google Analytics by updating your HTML with tracking code
   - Monitor traffic to your custom domain

4. **SSL Monitoring:**
   - Your certificate auto-renews; no action needed
   - Certificate status visible in GitHub Pages settings

---

## Cost

- **GitHub Pages:** FREE
- **Custom Domain:** ~$10-15/year (depending on registrar)
- **SSL/TLS:** FREE (via GitHub + Let's Encrypt)

Total: Just the domain registration cost!

---

## Support

If DNS setup fails:

1. Double-check your DNS records match exactly
2. Wait 24-48 hours for propagation
3. Contact your domain registrar's support
4. GitHub Help: https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site
