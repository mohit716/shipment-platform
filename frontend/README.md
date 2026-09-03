# FleetLine dashboard

React + TypeScript + Vite. Talks to the FastAPI backend over HTTP; it does not
embed business rules.

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite proxy forwards `/shipments`, `/auth` and
the other API paths to http://127.0.0.1:8000, so the API must be running.

Sign in with the seeded demo account:

- customer: `ada@example.com` / `correct-horse`
- staff: `depot@fleetline.example` / `correct-horse`
