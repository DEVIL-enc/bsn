# Backend API Reference

This document provides complete technical specifications for all REST and Server-Sent Events (SSE) endpoints provided by `server.mjs`.

---

## Base URL
```
http://localhost:3000
```

---

## 1. System Health Check

Returns the operational status of the server.

- **Endpoint**: `/api/health`
- **Method**: `GET`
- **Access**: Public
- **Response Type**: `application/json`

### Success Response (`200 OK`)
```json
{
  "status": "ok",
  "uptime": 42.15,
  "timestamp": "2026-10-16T14:15:00.000Z"
}
```

---

## 2. Real-Time Library Fetch Stream (SSE)

Initiates an asynchronous scan of the user's PlayStation Network digital catalog, streaming real-time status and progress updates over Server-Sent Events.

- **Endpoint**: `/api/fetch-stream`
- **Method**: `GET`
- **Query Parameters**:
  - `npsso` *(required, string)*: 64-character Sony NPSSO authentication token.
- **Headers**:
  - `Accept`: `text/event-stream`
- **Rate Limit**: Maximum 5 requests per 60-second window per client IP.

### Stream Event Types

#### `event: status`
Sent periodically as each fetch step is executed.
```
event: status
data: {"message": "Validating NPSSO token...", "timestamp": 1729088100}
```

#### `event: progress`
Sent to update the client progress bar and ETA.
```
event: progress
data: {"percent": 45, "eta": "fetching page 2 of 4..."}
```

#### `event: done`
Sent when the entire catalog has been fetched and saved to disk.
```
event: done
data: {
  "success": true,
  "count": 128,
  "user": {
    "onlineId": "SUPPOSED-GIANT83",
    "avatarUrl": "https://...",
    "isPlus": true,
    "tier": "DELUXE"
  }
}
```

#### `event: error`
Sent when an authentication failure, network error, or invalid token occurs.
```
event: error
data: {"error": "Invalid NPSSO token. Please verify ca.account.sony.com/api/v1/ssocookie"}
```

---

## 3. Cached Library Retrieval

Retrieves the currently saved library dataset from `psn-game-library.json` without re-querying Sony services.

- **Endpoint**: `/api/library`
- **Method**: `GET`
- **Response Type**: `application/json`

### Success Response (`200 OK`)
```json
{
  "fetchedAt": "2026-10-16T14:15:00.000Z",
  "account": {
    "onlineId": "SUPPOSED-GIANT83",
    "avatarUrl": "https://image.api.playstation.com/...",
    "isPlus": true,
    "plusTier": "DELUXE"
  },
  "counts": {
    "total": 128,
    "ps4Owned": 102,
    "ps5Owned": 26,
    "ps4Plus": 76,
    "ps5Plus": 64
  },
  "games": [
    {
      "titleId": "CUSA05932_00",
      "name": "A KING'S TALE: FINAL FANTASY XV",
      "platform": "PS4",
      "isPsPlus": false,
      "imageUrl": "https://image.api.playstation.com/...",
      "playtime": "<1h",
      "playCount": 2,
      "lastPlayed": "2024-02-10T11:20:00Z"
    }
  ]
}
```

### Error Response (`404 Not Found`)
```json
{
  "error": "No cached library found on disk. Run fetch first."
}
```

---

## 4. CSV Library Export

Downloads the full categorized game library as a standard comma-separated values (CSV) file.

- **Endpoint**: `/api/download/csv`
- **Method**: `GET`
- **Response Type**: `text/csv; charset=utf-8`
- **Content-Disposition**: `attachment; filename="psn-game-library.csv"`

### Sample Output
```csv
Title,Platform,License,Title ID,Entitlement ID,Playtime,Play Count,Last Played,Cover URL
"A KING'S TALE: FINAL FANTASY XV","PS4","OWNED","CUSA05932_00","UP0082-CUSA05932_00-AKINGSTALEFFXV00","<1h","2","2024-02-10","https://image.api.playstation.com/..."
```

---

## 5. Text Summary Export

Downloads a clean plaintext list grouped by platform and sorted alphabetically.

- **Endpoint**: `/api/download/txt`
- **Method**: `GET`
- **Response Type**: `text/plain; charset=utf-8`
- **Content-Disposition**: `attachment; filename="psn-game-list.txt"`
