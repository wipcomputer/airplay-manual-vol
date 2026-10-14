"""One-time pairing with a password-protected HomePod.

Does persistent HAP pair-setup (X-Apple-HKP: 3) with the AirPlay password as the
SRP PIN, skipping the /pair-pin-start request that a password-protected HomePod
rejects with 470. Returns the long-term credentials string pyatv uses.

Each failed attempt makes the HomePod lock out pairing for longer, so callers
must not retry in a loop.
"""

from pyatv.auth import hap_tlv8
from pyatv.auth.hap_srp import SRPAuthHandler
from pyatv.support.http import http_connect

HEADERS = {
    "User-Agent": "AirPlay/320.20",
    "Connection": "keep-alive",
    "X-Apple-HKP": 3,
    "Content-Type": "application/octet-stream",
}


class PairingError(Exception):
    pass


async def _post(http, data, step):
    resp = await http.post(
        "/pair-setup", body=hap_tlv8.write_tlv(data), headers=HEADERS, allow_error=True
    )
    tlv = hap_tlv8.read_tlv(resp.body) if isinstance(resp.body, bytes) and resp.body else {}
    if hap_tlv8.TlvValue.Error in tlv:
        backoff = tlv.get(hap_tlv8.TlvValue.BackOff)
        if backoff:
            raise PairingError(f"HomePod is refusing pairing for {int.from_bytes(backoff, 'little')} s after earlier failures")
        if step == "M3":
            raise PairingError("Wrong AirPlay password")
        raise PairingError(f"Pairing failed at {step} (error {tlv[hap_tlv8.TlvValue.Error].hex()})")
    if resp.code == 470:
        raise PairingError("HomePod refused pairing: set Speaker & TV Access to Anyone on the Same Network")
    if resp.code != 200:
        raise PairingError(f"Pairing failed at {step}: HTTP {resp.code} {resp.message}")
    return tlv


async def pair_homepod(host: str, password: str, name: str = "Wall Volume Panel") -> str:
    http = await http_connect(host, 7000)
    try:
        srp = SRPAuthHandler()
        srp.initialize()
        m2 = await _post(http, {hap_tlv8.TlvValue.Method: b"\x00", hap_tlv8.TlvValue.SeqNo: b"\x01"}, "M1")
        srp.step1(password)
        pub, proof = srp.step2(m2[hap_tlv8.TlvValue.PublicKey], m2[hap_tlv8.TlvValue.Salt])
        await _post(http, {hap_tlv8.TlvValue.SeqNo: b"\x03", hap_tlv8.TlvValue.PublicKey: pub,
                           hap_tlv8.TlvValue.Proof: proof}, "M3")
        m6 = await _post(http, {hap_tlv8.TlvValue.SeqNo: b"\x05",
                                hap_tlv8.TlvValue.EncryptedData: srp.step3(name=name)}, "M5")
        return str(srp.step4(m6[hap_tlv8.TlvValue.EncryptedData]))
    finally:
        http.close()
