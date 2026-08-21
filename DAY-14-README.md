# Day 14: OAuth2 — "Sign in with Google"

Adds Google OAuth2 login alongside the existing username/password login from
Day 10. Nothing about the old flow changes — this is additive.

## What was added

| File | Change |
|---|---|
| `oauth.py` | **New.** Builds the Google auth URL, exchanges the code for a token, fetches the user's Google profile, and finds/creates the local user row. |
| `database.py` | `users` table gains `email`, `oauth_provider`, `oauth_id`, `avatar_url` columns. `password_hash` is now nullable (OAuth users have no password). Existing databases are migrated automatically on next boot — no manual steps. |
| `chatbot.py` | Login screen shows a **"Sign in with Google"** button when OAuth is configured. Handles the `?code=&state=` redirect Google sends back. |

## How the flow works

1. User clicks **Sign in with Google** → sent to Google's consent screen.
2. Google redirects back to the app with `?code=...&state=...`.
3. `oauth.exchange_code_for_token()` swaps the code for an access token.
4. `oauth.fetch_google_userinfo()` gets `{sub, email, name, picture}`.
5. `oauth.login_or_create_oauth_user()` looks up a user by
   `(provider, oauth_id)`. First time in, it creates a new row (username
   derived from their name/email, no password set). Every time after, it's
   the same account.
6. A normal session token is issued via `auth.create_session()` — from here
   on an OAuth login and a password login are indistinguishable to the rest
   of the app.

## Setup

1. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials),
   create an **OAuth 2.0 Client ID** (type: Web application).
2. Add your app's URL as an **Authorized redirect URI** (e.g.
   `https://your-app.streamlit.app/`).
3. Add to `.env` (local) or Streamlit **Secrets** (deployed):

```
GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxxxx
GOOGLE_REDIRECT_URI=https://your-app.streamlit.app/
```

No new pip packages are needed — `oauth.py` only uses `requests`, which is
already in `requirements.txt`.

## Known limitations (honest list)

- Redirect URI must match Google's console entry **exactly** (trailing
  slash included), or Google will reject the callback.
- Streamlit reruns the whole script on every interaction, so the OAuth
  `state` value is stored in `st.session_state` — it resets if the user
  opens the login link in a fresh tab/session before finishing it once.
- This adds Google only. Adding another provider (GitHub, Microsoft) means
  duplicating the three functions in `oauth.py` with that provider's
  endpoints — the DB schema already supports it via `oauth_provider`.
- No refresh-token handling — that's fine here since we only use the
  Google login to establish identity once, not to keep calling Google's API
  on the user's behalf.
