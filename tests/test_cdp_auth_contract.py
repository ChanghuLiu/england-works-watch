from __future__ import annotations
import base64
import importlib
import subprocess
import sys

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from england_works_watch.cdp_facilitator import create_facilitator_config


@pytest.mark.parametrize('kind', ['ec', 'ed25519'])
def test_facilitator_jwt_matches_sdk_contract(monkeypatch, kind):
    if kind == 'ec':
        key = ec.generate_private_key(ec.SECP256R1())
        secret = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()).decode().replace('\n', '\\n')
        algorithm = 'ES256'
    else:
        key = ed25519.Ed25519PrivateKey.generate()
        secret = base64.b64encode(key.private_bytes_raw() + key.public_key().public_bytes_raw()).decode()
        algorithm = 'EdDSA'
    monkeypatch.setenv('CDP_API_KEY_ID', 'owned-fixture-key')
    monkeypatch.setenv('CDP_API_KEY_SECRET', secret)
    config = create_facilitator_config()
    sdk = importlib.import_module('cdp.x402').create_facilitator_config()
    ours, theirs = config['create_headers'](), sdk['create_headers']()
    assert config['url'] == sdk['url']
    assert ours['list'] == theirs['list']
    previous = config['create_headers']()
    for operation, method in [('verify', 'POST'), ('settle', 'POST'), ('supported', 'GET')]:
        def decode(h):
            return jwt.decode(h['Authorization'].split(' ', 1)[1], key.public_key(), algorithms=[algorithm], issuer='cdp')
        a, b = decode(ours[operation]), decode(theirs[operation])
        for name in ('sub', 'iss', 'aud', 'uris'):
            assert a[name] == b[name]
        assert a['uris'] == [f'{method} api.cdp.coinbase.com/platform/v2/x402/{operation}']
        assert a['exp'] - a['nbf'] == b['exp'] - b['nbf'] == 120
        assert ours[operation]['Content-Type'] == theirs[operation]['Content-Type']
        assert ours[operation]['Correlation-Context'] == theirs[operation]['Correlation-Context']
        header = jwt.get_unverified_header(ours[operation]['Authorization'].split(' ', 1)[1])
        other = jwt.get_unverified_header(previous[operation]['Authorization'].split(' ', 1)[1])
        assert header['alg'] == algorithm
        assert header['kid'] == 'owned-fixture-key'
        assert header['nonce'] != other['nonce']


def test_invalid_key_fails_closed_without_echo(monkeypatch):
    monkeypatch.setenv('CDP_API_KEY_ID', 'owned-fixture-key')
    monkeypatch.setenv('CDP_API_KEY_SECRET', 'do-not-echo-this-fixture')
    with pytest.raises(RuntimeError, match='Invalid CDP API signing key') as err:
        create_facilitator_config()
    assert 'do-not-echo' not in str(err.value)


def test_auth_does_not_import_wallet_sdk():
    result = subprocess.run([sys.executable, '-c', "import sys; import england_works_watch.cdp_facilitator; assert not any(n == 'cdp' or n.startswith('cdp.') for n in sys.modules)"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
