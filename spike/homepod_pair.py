"""One-time pairing with a password-protected HomePod.

Does persistent HAP pair-setup (X-Apple-HKP: 3) with the AirPlay password as the
SRP PIN. Unlike `atvremote pair`, it skips /pair-pin-start, which a
password-protected HomePod rejects with 470.

Usage: homepod_pair.py HOST PASSWORD [OUT_FILE]
"""

import asyncio
import sys

from pyatv.auth import hap_tlv8
from pyatv.auth.hap_srp import SRPAuthHandler
from pyatv.support.http import http_connect

HEADERS = {
    "User-Agent": "AirPlay/320.20",
    "Connection": "keep-alive",
    "X-Apple-HKP": 3,
    "Content-Type": "application/octet-stream",
}


async def post(http, data, step):
    resp = await http.post(
        "/pair-setup", body=hap_tlv8.write_tlv(data), headers=HEADERS, allow_error=True
    )
    print(f"{step}: HTTP {resp.code} {resp.message}")
    tlv = hap_tlv8.read_tlv(resp.body) if isinstance(resp.body, bytes) and resp.body else {}
    if hap_tlv8.TlvValue.Error in tlv:
        # Repeated failures trigger HomeKit's growing anti-brute-force backoff
        backoff = tlv.get(hap_tlv8.TlvValue.BackOff, b"").hex()
        print(f"{step}: TLV error {tlv[hap_tlv8.TlvValue.Error].hex()} backoff {backoff}")
        sys.exit(1)
    if resp.code != 200:
        sys.exit(1)
    return tlv


async def main(host, password, out_file):
    http = await http_connect(host, 7000)
    srp = SRPAuthHandler()
    srp.initialize()

    m2 = await post(
        http, {hap_tlv8.TlvValue.Method: b"\x00", hap_tlv8.TlvValue.SeqNo: b"\x01"}, "M1->M2"
    )
    srp.step1(password)
    pub, proof = srp.step2(m2[hap_tlv8.TlvValue.PublicKey], m2[hap_tlv8.TlvValue.Salt])
    await post(
        http,
        {
            hap_tlv8.TlvValue.SeqNo: b"\x03",
            hap_tlv8.TlvValue.PublicKey: pub,
            hap_tlv8.TlvValue.Proof: proof,
        },
        "M3->M4",
    )
    m6 = await post(
        http,
        {
            hap_tlv8.TlvValue.SeqNo: b"\x05",
            hap_tlv8.TlvValue.EncryptedData: srp.step3(name="Panel test"),
        },
        "M5->M6",
    )
    creds = srp.step4(m6[hap_tlv8.TlvValue.EncryptedData])
    with open(out_file, "w") as f:
        f.write(str(creds))
    print(f"PAIRED, credentials saved to {out_file}")
    http.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "credentials.txt"))
