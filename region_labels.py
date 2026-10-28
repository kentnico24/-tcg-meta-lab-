"""Country helpers: player-declared location, not tournament venue."""
import re

UNKNOWN_CODES = {'XX', 'ZZ', 'UN', 'UK'}  # UK is not ISO alpha-2 (use GB).


def normalize_country(value):
    """Return an uppercase ISO-like code or '' if unreported/invalid."""
    if not isinstance(value, str):
        return ''
    code = value.strip().upper()
    return code if re.fullmatch(r'[A-Z]{2}', code) and code not in UNKNOWN_CODES else ''


def country_group(value):
    code = normalize_country(value)
    if code == 'JP':
        return '国内'
    if code:
        return '海外'
    return '不明'


def eligible_player(country_a, country_b, side, selection):
    """Membership is per-player perspective, never inferred from event names."""
    a = normalize_country(country_a)
    b = normalize_country(country_b)
    player = a if side == 'a' else b
    if selection == 'すべて':
        return True
    if selection == '国内':
        return player == 'JP'
    if selection == '海外':
        return bool(player) and player != 'JP'
    if selection == '国内同士':
        return a == 'JP' and b == 'JP'
    if selection == '国不明':
        return not player
    raise ValueError('Unexpected region selection: ' + str(selection))
