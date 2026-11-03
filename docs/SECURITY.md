# Security & Privacy Architecture

This document details the security principles, credential sanitization protocols, HTTP header policies, and rate-limiting safeguards implemented in this project.

---

## 1. Zero-Retention Credential Policy

The application requires an **NPSSO (Sony Single Sign-On Cookie)** to authenticate with Sony's OAuth 2.0 server. The handling of this token follows strict zero-retention principles:

1. **In-Memory Lifetime**: The NPSSO token is received exclusively during the active `/api/fetch-stream` SSE request. It is kept only in local memory during the lifecycle of the exchange and is discarded immediately after exchanging for a short-lived bearer access token.
2. **Zero Storage**: The NPSSO token is **never** written to disk, never logged to terminal stdout, and never sent to any third-party remote server.
3. **Official Endpoints Only**: All authentication requests are made directly to Sony's official OAuth servers (`ca.account.sony.com`).

---

## 2. Hardened HTTP Security Headers

Every HTTP response emitted by `server.mjs` includes defensive security headers configured to prevent clickjacking, MIME-sniffing, and cross-site scripting:

```javascript
res.setHeader("X-Content-Type-Options", "nosniff");
res.setHeader("X-Frame-Options", "DENY");
res.setHeader("X-XSS-Protection", "1; mode=block");
res.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");
res.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()");
res.setHeader(
  "Content-Security-Policy",
  [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https://image.api.playstation.com https://store.playstation.com https://*.playstation.net",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "base-uri 'self'"
  ].join("; ")
);
```

### Protection Details:
- **`Content-Security-Policy`**: Restricts image loading strictly to `self`, `data:` URIs, and official PlayStation domains (`*.api.playstation.com`, `store.playstation.com`, `*.playstation.net`). No arbitrary external domains can execute scripts or fetch network data.
- **`frame-ancestors 'none'` / `X-Frame-Options: DENY`**: Protects the interface against clickjacking attempts by forbidding embedding inside any `<iframe>`.

---

## 3. Rate Limiting Protection

To prevent abuse or automated scraping hammering Sony's endpoints, `server.mjs` enforces an in-memory IP rate limiter:

- **Window Duration**: 60 seconds
- **Max Requests**: 5 fetch operations per IP per window
- **Auto-Cleanup**: Expired IP records are purged automatically every 5 minutes to prevent memory leaks.
- **Exceeded Penalty**: Triggers an HTTP `429 Too Many Requests` response.

---

## 4. Input Sanitization & URL Validation

- **Token Parser**: Cleans input strings, stripping extraneous quotes, whitespace, or raw JSON copied directly from `{"npsso": "..."}`.
- **Client-Side Image Sanitizer**: Prior to inserting URLs into `img.src` attributes, URLs are parsed with the native `URL` constructor to verify valid `https:` protocols, preventing `javascript:` protocol injection.
- **CSV Data Sanitization**: Double-quotes and separator characters are escaped to prevent CSV formula injection.
