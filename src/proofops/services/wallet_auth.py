from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from eth_account import Account
from eth_account.messages import encode_defunct

from proofops.execution.store import SQLiteStore

ADDRESS_PATTERN = re.compile(r"0x[a-fA-F0-9]{40}")


class WalletAuthService:
    def __init__(
        self,
        store: SQLiteStore,
        *,
        challenge_minutes: int = 10,
        session_minutes: int = 60,
    ) -> None:
        self._store = store
        self._challenge_minutes = challenge_minutes
        self._session_minutes = session_minutes

    @staticmethod
    def normalize_address(owner: str) -> str:
        if not ADDRESS_PATTERN.fullmatch(owner):
            raise ValueError("owner must be a 20-byte EVM address")
        return owner.lower()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def challenge(self, owner: str) -> dict[str, str]:
        normalized = self.normalize_address(owner)
        expires_at = datetime.now(UTC) + timedelta(minutes=self._challenge_minutes)
        nonce = secrets.token_urlsafe(24)
        message = (
            "SafeHire wallet sign-in\n"
            f"Owner: {normalized}\n"
            f"Nonce: {nonce}\n"
            f"Expires: {expires_at.isoformat()}\n"
            "Purpose: create and control scoped agent permissions.\n"
            "This signature does not authorize a blockchain transaction."
        )
        self._store.save_wallet_challenge(owner=normalized, message=message, expires_at=expires_at)
        return {"owner": normalized, "message": message, "expires_at": expires_at.isoformat()}

    def verify(self, *, owner: str, message: str, signature: str) -> dict[str, str]:
        normalized = self.normalize_address(owner)
        expected_message, expires_at, used = self._store.get_wallet_challenge(normalized)
        if used:
            raise ValueError("wallet challenge has already been used")
        if datetime.now(UTC) >= expires_at:
            raise ValueError("wallet challenge has expired")
        if not secrets.compare_digest(message, expected_message):
            raise ValueError("wallet challenge message does not match")
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
        if recovered.lower() != normalized:
            raise ValueError("wallet signature does not match owner")
        self._store.consume_wallet_challenge(normalized)
        token = secrets.token_urlsafe(32)
        session_expires = datetime.now(UTC) + timedelta(minutes=self._session_minutes)
        self._store.save_wallet_session(
            token_hash=self._token_hash(token),
            owner=normalized,
            expires_at=session_expires,
        )
        return {
            "owner": normalized,
            "session_token": token,
            "expires_at": session_expires.isoformat(),
        }

    def require_session(self, token: str, *, owner: str | None = None) -> str:
        if not token:
            raise ValueError("wallet session token is required")
        session_owner, expires_at = self._store.get_wallet_session(self._token_hash(token))
        if datetime.now(UTC) >= expires_at:
            raise ValueError("wallet session has expired")
        if owner and session_owner != self.normalize_address(owner):
            raise ValueError("wallet session does not control this owner")
        return session_owner
