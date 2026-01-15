#!/usr/bin/env python3
"""One-time script to get Spotify refresh token via OAuth."""

import os
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import httpx

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:8888/callback"
SCOPES = "user-follow-read"


class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/callback":
            query = parse_qs(parsed.query)
            code = query.get("code", [None])[0]

            if code:
                response = httpx.post(
                    "https://accounts.spotify.com/api/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": REDIRECT_URI,
                    },
                    auth=(CLIENT_ID, CLIENT_SECRET),
                )
                response.raise_for_status()
                tokens = response.json()

                print("\n" + "=" * 50)
                print("REFRESH TOKEN (add to GitHub secrets):")
                print(tokens["refresh_token"])
                print("=" * 50 + "\n")

                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Success! Check terminal for refresh token.</h1>")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"No code received")


def main() -> None:
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables")
        return

    auth_url = (
        f"https://accounts.spotify.com/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={SCOPES}"
    )

    print("Opening browser for Spotify authorization...")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 8888), OAuthHandler)
    print("Waiting for callback on http://localhost:8888/callback ...")
    server.handle_request()


if __name__ == "__main__":
    main()
