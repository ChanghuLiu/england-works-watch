"""Exercise both purchase and recovery handlers' email rejection predicates."""
import ast
from pathlib import Path


def test_purchase_and_recovery_email_guards_reject_missing_email_parts():
    source = ast.parse(Path('src/england_works_watch/server.py').read_text())
    guards = [node.test for node in ast.walk(source) if isinstance(node, ast.If)
              and 'contact_email.count' in ast.unparse(node.test)]
    assert len(guards) == 2
    for guard in guards:
        code = compile(ast.Expression(guard), '<email rejection guard>', 'eval')
        for email in ('', '@example.test', 'buyer@', 'buyer', 'a@@example.test', 'a b@example.test'):
            assert eval(code, {'contact_email': email, 'checkout_id': '1' * 32}) is True
        assert eval(code, {'contact_email': 'buyer@example.test', 'checkout_id': '1' * 32}) is False
