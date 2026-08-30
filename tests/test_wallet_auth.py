from __future__ import annotations

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct

from proofops.execution.store import SQLiteStore
from proofops.services.wallet_auth import WalletAuthService


def test_wallet_challenge_is_signed_once_and_session_persists(tmp_path) -> None:
    account = Account.create()
    store = SQLiteStore(tmp_path / "wallet.db")
    auth = WalletAuthService(store)
    challenge = auth.challenge(account.address)
    signature = Account.sign_message(
        encode_defunct(text=challenge["message"]), account.key
    ).signature.hex()

    session = auth.verify(
        owner=account.address,
        message=challenge["message"],
        signature=signature,
    )

    assert session["owner"] == account.address.lower()
    assert auth.require_session(session["session_token"]) == account.address.lower()
    assert (
        WalletAuthService(SQLiteStore(tmp_path / "wallet.db")).require_session(
            session["session_token"], owner=account.address
        )
        == account.address.lower()
    )
    with pytest.raises(ValueError, match="already been used"):
        auth.verify(
            owner=account.address,
            message=challenge["message"],
            signature=signature,
        )


def test_wallet_signature_must_match_requested_owner(tmp_path) -> None:
    owner = Account.create()
    attacker = Account.create()
    auth = WalletAuthService(SQLiteStore(tmp_path / "wallet.db"))
    challenge = auth.challenge(owner.address)
    signature = Account.sign_message(
        encode_defunct(text=challenge["message"]), attacker.key
    ).signature.hex()

    with pytest.raises(ValueError, match="does not match owner"):
        auth.verify(
            owner=owner.address,
            message=challenge["message"],
            signature=signature,
        )
