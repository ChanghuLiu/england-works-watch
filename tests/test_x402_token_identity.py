from england_works_watch.x402_gate import eip712_token_identity


def test_base_mainnet_usdc_uses_onchain_eip712_name(monkeypatch):
    monkeypatch.delenv("EWW_X402_TOKEN_NAME", raising=False)
    monkeypatch.delenv("EWW_X402_TOKEN_VERSION", raising=False)
    assert eip712_token_identity("eip155:8453") == ("USD Coin", "2")


def test_base_sepolia_usdc_keeps_test_token_name(monkeypatch):
    monkeypatch.delenv("EWW_X402_TOKEN_NAME", raising=False)
    monkeypatch.delenv("EWW_X402_TOKEN_VERSION", raising=False)
    assert eip712_token_identity("eip155:84532") == ("USDC", "2")


def test_explicit_token_domain_override(monkeypatch):
    monkeypatch.setenv("EWW_X402_TOKEN_NAME", "Custom Coin")
    monkeypatch.setenv("EWW_X402_TOKEN_VERSION", "7")
    assert eip712_token_identity("eip155:999") == ("Custom Coin", "7")
