"""Loopback-only static wallet UI. No server-side RPC, signing or transfer endpoint."""
import argparse
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from scripts.operational_read_only import read_private, ReadOnlyError
from scripts.private_wallet_chain_monitor import _private_config, WalletSourceError

TOKEN = '0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf'
ADDRESS = re.compile(r'0x[0-9a-fA-F]{40}')

class PortalError(ValueError):
    pass

def require(ok):
    if not ok:
        raise PortalError('PORTAL_CONFIGURATION_REJECTED')

def load_config(watch_path, policy_path=None):
    try:
        watch = _private_config(read_private(watch_path))
        result = {'accounts': sorted(set(w[1] for w in watch)), 'policy': None}
        if policy_path is None:
            return result
        p = read_private(policy_path)
        allowed = {'mode', 'chain_id', 'from_label', 'destination', 'asset', 'max_amount',
                   'max_execution_fee_wei', 'destination_confirmed_in_coinbase', 'confirmed_at', 'expires_at'}
        require(set(p) == allowed and p['mode'] == 'USER_CONFIRMED_WALLET_TRANSFER')
        require(type(p['chain_id']) is int and p['chain_id'] in (1, 8453))
        matches = [w for w in watch if w[0] == p['chain_id'] and w[2] == p['from_label']]
        require(len(matches) == 1)
        chain, sender, _, tokens = matches[0]
        require(p['asset'] in ('ETH', 'cbBTC'))
        require(p['asset'] != 'cbBTC' or TOKEN in tokens)
        to = p['destination']
        require(isinstance(to, str) and ADDRESS.fullmatch(to))
        to = to.lower()
        require(to not in (sender, TOKEN, '0x' + '0' * 40))
        require(p['destination_confirmed_in_coinbase'] is True)
        now = datetime.now(timezone.utc)
        confirmed = datetime.fromisoformat(p['confirmed_at'].replace('Z', '+00:00'))
        expires = datetime.fromisoformat(p['expires_at'].replace('Z', '+00:00'))
        require(confirmed.tzinfo is not None and expires.tzinfo is not None)
        require(now - timedelta(hours=24) <= confirmed <= now)
        require(now < expires <= confirmed + timedelta(hours=24))
        amount = p['max_amount']; precision = 8 if p['asset'] == 'cbBTC' else 18
        require(isinstance(amount, str) and len(amount) <= 80 and
                re.fullmatch(r'(0|[1-9][0-9]*)(\.[0-9]{1,' + str(precision) + r'})?', amount))
        require(0 < Decimal(amount) * 10 ** precision < 2 ** 256)
        fee = p['max_execution_fee_wei']
        require(isinstance(fee, str) and re.fullmatch(r'[1-9][0-9]{0,29}', fee))
        result['policy'] = {'chainId': chain, 'from': sender, 'to': to, 'asset': p['asset'],
                            'maxAmount': amount, 'maxExecutionFeeWei': fee,
                            'expiresAt': int(expires.timestamp() * 1000)}
        return result
    except (ReadOnlyError, WalletSourceError, ValueError, TypeError, KeyError, AttributeError):
        raise PortalError('PORTAL_CONFIGURATION_REJECTED') from None

def make_handler(config, asset_root):
    assets = {'/': ('index.html', 'text/html; charset=utf-8'),
              '/app.js': ('dist/app.js', 'text/javascript; charset=utf-8')}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body=b'', content_type='text/plain; charset=utf-8'):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Cross-Origin-Opener-Policy', 'same-origin-allow-popups')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' https://rpc.wallet.coinbase.com https://keys.coinbase.com; frame-src https://keys.coinbase.com; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def do_GET(self):
            origin = f'http://127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != origin.removeprefix('http://'):
                return self.reply(403)
            supplied = self.headers.get('Origin')
            if supplied is not None and supplied != origin:
                return self.reply(403)
            if self.path == '/session':
                if supplied != origin and self.headers.get('Sec-Fetch-Site') != 'same-origin':
                    return self.reply(403)
                return self.reply(200, json.dumps(config).encode(), 'application/json')
            if self.path == '/favicon.ico':
                return self.reply(204)
            if self.path not in assets:
                return self.reply(404)
            name, mime = assets[self.path]
            try:
                body = (Path(asset_root) / name).read_bytes()
                if len(body) > 8 * 1024 * 1024:
                    return self.reply(503)
            except OSError:
                return self.reply(503)
            self.reply(200, body, mime)

        def do_HEAD(self):
            self.do_GET()

        def do_POST(self):
            self.reply(405)

    return Handler

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watchlist', type=Path, required=True)
    parser.add_argument('--transfer-policy', type=Path)
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    try:
        config = load_config(args.watchlist, args.transfer_policy)
        root = Path(__file__).resolve().parents[1] / 'wallet-portal'
        require((root / 'dist/app.js').is_file())
        server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(config, root))
    except (PortalError, OSError):
        parser.exit(2, 'Portal unavailable: check private configuration, build and port.\n')
    print(f'Wallet portal: http://127.0.0.1:{server.server_port} (stop: Ctrl+C)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
