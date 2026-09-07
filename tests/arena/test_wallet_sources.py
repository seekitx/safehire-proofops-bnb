from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from eth_abi.abi import encode
from eth_utils.crypto import keccak

from proofops.arena.models import utcnow
from proofops.arena.wallet_sources import ASSETS, observe_wallet, price_from_round, wallet_summary
from proofops.decision.paid import BscReader


@pytest.mark.parametrize('values', [
    (1, 0, 990, 990, 1), (1, -1, 990, 990, 1), (1, 100000000, 1001, 1001, 1),
    (1, 100000000, 800, 800, 1), (2, 100000000, 990, 990, 1),
])
def test_bad_price_is_unknown_not_one_dollar(values):
    with pytest.raises(ValueError):
        price_from_round(values, 1000, 120)


def test_price_and_summary_do_not_claim_entire_wallet_or_profit():
    assert price_from_round((1, 99800000, 990, 990, 1), 1000, 120) == Decimal('0.998')
    rows = [{'symbol': 'BNB', 'balance_raw': '1', 'reference_value_usd': '5'},
            {'symbol': 'USDT', 'balance_raw': '10', 'reference_value_usd': None},
            {'symbol': 'USDC', 'balance_raw': None, 'reference_value_usd': None}]
    summary = wallet_summary(rows)
    assert summary['priced_subset_value_usd'] == '5'
    assert summary['unvalued_or_unread_assets'] == ['USDT', 'USDC']
    assert not summary['full_portfolio_complete']
    assert not summary['watchlist_valuation_complete']
    assert summary['realized_profit_usd'] is None
    assert rows[1]['share_of_priced_subset_pct'] is None


class WalletReader(BscReader):
    reorg = False
    bad_price = False

    async def rpc(self, method, params):
        if method == 'eth_chainId':
            return '0x38'
        if method == 'eth_blockNumber':
            return hex(1012)
        if method == 'eth_getBlockByNumber':
            return {'number': hex(1000), 'hash': '0x' + 'a' * 64,
                    'timestamp': hex(int(utcnow().timestamp()))}
        assert params[-1] == {'blockHash': '0x' + 'a' * 64, 'requireCanonical': True}
        if method == 'eth_getBalance':
            return hex(10**18)
        assert method == 'eth_call'
        selector = params[0]['data'][2:10]
        if selector == keccak(text='decimals()')[:4].hex():
            is_feed = params[0]['to'] in {v[1] for v in ASSETS.values()}
            return '0x' + encode(['uint8'], [8 if is_feed else 18]).hex()
        if selector == keccak(text='balanceOf(address)')[:4].hex():
            return '0x' + encode(['uint256'], [0]).hex()
        assert selector == keccak(text='latestRoundData()')[:4].hex()
        now = int(utcnow().timestamp()) - (2000 if self.bad_price else 10)
        return '0x' + encode(['uint80', 'int256', 'uint256', 'uint256', 'uint80'],
                              [1, 100000000, now, now, 1]).hex()

    async def canonical_block_hash(self, block_number):
        return '0x' + ('b' if self.reorg else 'a') * 64


def test_live_reader_contract_preserves_exact_balances_and_rejects_reorg():
    reader = WalletReader()
    result = asyncio.run(observe_wallet('0x' + '1' * 40, reader=reader))
    assert result['assets'][0]['balance_raw'] == str(10**18)
    assert result['summary']['priced_subset_value_usd'] == '1'
    assert not result['settlement_authorized']
    reader.reorg = True
    with pytest.raises(ValueError, match='reorganized'):
        asyncio.run(observe_wallet('0x' + '1' * 40, reader=reader))


def test_stale_prices_keep_readable_balances_without_fake_values():
    reader = WalletReader()
    reader.bad_price = True
    result = asyncio.run(observe_wallet('0x' + '1' * 40, reader=reader))
    assert result['assets'][0]['balance_raw'] == str(10**18)
    assert result['assets'][0]['reference_value_usd'] is None
    assert result['summary']['unvalued_or_unread_assets'] == ['BNB']
