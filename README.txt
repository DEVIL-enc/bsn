PSN GAME FETCHER CLI — WINDOWS

A command-line tool to scan and categorize your PlayStation Network digital library using official OAuth endpoints and GraphQL catalog retrieval.

FEATURES
- Authenticates securely with your NPSSO token.
- Live progress bar tracking library retrieval in real-time.
- Unambiguous classification:
  * Non-PS-Plus Digital Licenses (Owned / Purchased / Free digital games)
  * PS Plus Entitlements (Claimed via PS Plus monthly games or subscription)
- Separated breakdowns for PlayStation 4 and PlayStation 5 games.
- Attaches playtime and play count when available.
- Automatically exports to:
  * psn-game-library.json (Full metadata for developers & backup)
  * psn-game-library.csv (Spreadsheet-ready for Microsoft Excel & Google Sheets)

HOW TO RUN
1. Double-click "run.bat"
   OR in Command Prompt / PowerShell, run:
      npm start
2. When prompted:
      Enter your NPSSO token here:
   Paste your 64-character token and press Enter.

HOW TO GET YOUR NPSSO TOKEN
1. Open your browser and log into https://www.playstation.com
2. Once logged in, open this URL in another tab:
   https://ca.account.sony.com/api/v1/ssocookie
3. Copy the 64-character alphanumeric string inside {"npsso":"<token>"}.
