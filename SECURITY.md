# Security policy

Crema is a self-hosted personal app, but it still handles accounts and private data.

## Reporting a vulnerability

Please report security issues privately rather than in a public issue. If the repository has GitHub private vulnerability reporting enabled, use **Security → Report a vulnerability**. Otherwise contact the maintainer directly through the address on their GitHub profile.

Include a short description, reproduction steps, and the affected version or commit. You should get an acknowledgement within a few days. Please give a reasonable window to fix the issue before disclosing it publicly.

## Supported versions

Only the latest commit on `main` is supported.

## Deployment expectations

Crema is designed to run behind a TLS-terminating reverse proxy. The bundled Gunicorn configuration binds to localhost. Exposing the Flask development server, or the app port directly to the internet, is not supported.

There is no password-reset flow and no email verification. If you open registration to the public internet, enable the owner approval toggle or add rate limiting at the proxy.
